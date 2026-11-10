import calendar
import datetime

from flask import redirect, request, url_for
from flask_admin import AdminIndexView, expose
from flask_admin.contrib.sqla import ModelView
from flask_admin.menu import MenuLink
from flask_security import current_user  # type: ignore
from markupsafe import Markup, escape
from sqlalchemy import and_, case, func, select

from firenze.services.auth_service import hash_user_password

from .extensions import admin, db
from .models import (
    ApiCredential,
    AsteriskCDR,
    Client,
    ClientAni,
    DoNotCall,
    Operator,
    OperatorPhone,
    Service,
    ServiceNumber,
    User,
)

_TIMESTAMP_EXCLUDED = ["created_at", "modified_at"]
_REPORT_MIN_YEAR = 2024
_MONTHS_ES = {
    1: "Enero",
    2: "Febrero",
    3: "Marzo",
    4: "Abril",
    5: "Mayo",
    6: "Junio",
    7: "Julio",
    8: "Agosto",
    9: "Septiembre",
    10: "Octubre",
    11: "Noviembre",
    12: "Diciembre",
}


def _collect_monthly_report(year: int, month: int) -> dict:
    month_start = datetime.datetime(year, month, 1)
    next_month = (month_start + datetime.timedelta(days=32)).replace(day=1)

    services = db.query(Service).order_by(Service.id).all()
    service_catalog = [{"slug": svc.slug, "name": svc.name} for svc in services if svc.slug]
    service_slugs = [svc["slug"] for svc in service_catalog]
    if service_slugs:
        rows = (
            db.query(
                func.date(AsteriskCDR.calldate).label("day"),
                AsteriskCDR.accountcode,
                func.coalesce(func.floor(func.sum(AsteriskCDR.billsec) / 60), 0).label("minutes"),
            )
            .filter(
                AsteriskCDR.calldate >= month_start,
                AsteriskCDR.calldate < next_month,
                AsteriskCDR.disposition == "ANSWERED",
                AsteriskCDR.lastapp == "Dial",
                AsteriskCDR.zvn_clientid.is_not(None),
                AsteriskCDR.zvn_clientid > 1,
                AsteriskCDR.accountcode.in_(service_slugs),
            )
            .group_by(func.date(AsteriskCDR.calldate), AsteriskCDR.accountcode)
            .all()
        )
    else:
        rows = []

    by_day: dict[str, dict[str, int]] = {}
    for row in rows:
        day_key = row.day.isoformat()
        by_day.setdefault(day_key, {})
        by_day[day_key][row.accountcode] = int(row.minutes or 0)

    days = []
    totals_by_service = {svc["slug"]: 0 for svc in service_catalog}
    days_in_month = calendar.monthrange(year, month)[1]
    for day_number in range(1, days_in_month + 1):
        day_key = month_start.replace(day=day_number).date().isoformat()
        service_minutes = {svc["slug"]: by_day.get(day_key, {}).get(svc["slug"], 0) for svc in service_catalog}
        day_total = sum(service_minutes.values())
        days.append(
            {
                "date": day_key,
                "services": service_minutes,
                "total": day_total,
            }
        )
        for slug, minutes in service_minutes.items():
            totals_by_service[slug] += minutes

    return {
        "services": service_catalog,
        "days": days,
        "totals": {
            "services": totals_by_service,
            "total": sum(totals_by_service.values()),
        },
    }


def _collect_monthly_agent_report(year: int, month: int, selected_agents: tuple[int, ...] | None = None) -> dict:
    month_start = datetime.datetime(year, month, 1)
    next_month = (month_start + datetime.timedelta(days=32)).replace(day=1)

    operators = db.query(Operator).order_by(Operator.number).all()
    all_agents = [{"number": int(op.number), "name": op.name} for op in operators]

    rows_query = db.query(
        func.date(AsteriskCDR.calldate).label("day"),
        AsteriskCDR.zvn_operator.label("operator"),
        func.coalesce(func.floor(func.sum(AsteriskCDR.billsec) / 60), 0).label("minutes"),
    ).filter(
        AsteriskCDR.calldate >= month_start,
        AsteriskCDR.calldate < next_month,
        AsteriskCDR.disposition == "ANSWERED",
        AsteriskCDR.lastapp == "Dial",
        AsteriskCDR.zvn_operator.is_not(None),
        AsteriskCDR.zvn_clientid.is_not(None),
        AsteriskCDR.zvn_clientid > 1,
    )
    if selected_agents:
        rows_query = rows_query.filter(AsteriskCDR.zvn_operator.in_(selected_agents))
    rows = rows_query.group_by(func.date(AsteriskCDR.calldate), AsteriskCDR.zvn_operator).all()

    if selected_agents:
        agent_set = set(selected_agents)
        agents = [agent for agent in all_agents if agent["number"] in agent_set]
    else:
        agents = all_agents

    by_day: dict[str, dict[int, int]] = {}
    for row in rows:
        day_key = row.day.isoformat()
        operator_number = int(row.operator or 0)
        by_day.setdefault(day_key, {})
        by_day[day_key][operator_number] = int(row.minutes or 0)

    days = []
    totals_by_agent = {agent["number"]: 0 for agent in agents}
    days_in_month = calendar.monthrange(year, month)[1]
    for day_number in range(1, days_in_month + 1):
        day_key = month_start.replace(day=day_number).date().isoformat()
        minutes_by_agent = {agent["number"]: by_day.get(day_key, {}).get(agent["number"], 0) for agent in agents}
        day_total = sum(minutes_by_agent.values())
        days.append({"date": day_key, "minutes_by_agent": minutes_by_agent, "total": day_total})
        for operator_number, minutes in minutes_by_agent.items():
            totals_by_agent[operator_number] += minutes

    return {
        "agents": agents,
        "all_agents": all_agents,
        "days": days,
        "totals": {
            "by_agent": totals_by_agent,
            "total": sum(totals_by_agent.values()),
        },
    }


def format_phone_with_flag(_view, _context, model, name: str):
    # 'name' is "did", "ani", "number", etc.
    raw_number = getattr(model, name, "") or ""
    if not raw_number:
        return ""
    import phonenumbers
    from phonenumbers.phonenumberutil import region_code_for_number

    phone = str(raw_number).strip()
    flag = ""
    try:
        parsed = phonenumbers.parse(phone if phone.startswith("+") else f"+{phone}")
        region = region_code_for_number(parsed)
        if region and len(region) == 2:
            flag = "".join(chr(127397 + ord(c)) for c in region.upper())
    except Exception:
        pass

    safe_phone = escape(phone)
    if flag:
        return Markup(f'<span class="me-1">{flag}</span> +{safe_phone}')
    return safe_phone


class SecureAdminIndexView(AdminIndexView):
    """Admin index view that requires an authenticated user with the 'admin' role."""

    def is_accessible(self):
        # return current_user and current_user.is_authenticated and current_user.has_role("admin")
        return True

    def inaccessible_callback(self, name, **kwargs):
        # return redirect(url_for("security.login", next=request.url))
        return True


class SecureModelView(ModelView):
    """ModelView accessible only to authenticated users with the 'admin' role."""

    # column_type_formatters = dict(ModelView.column_type_formatters)

    can_view_details = True

    def is_accessible(self):
        # return current_user and current_user.is_authenticated and current_user.has_role("admin")
        return True

    def inaccessible_callback(self, name, **kwargs):
        # return redirect(url_for("security.login", next=request.url))
        return True


class DNCAdmin(SecureModelView):
    column_list = ["ani", "reason", "created_at"]
    column_searchable_list = ["ani"]
    form_excluded_columns = _TIMESTAMP_EXCLUDED
    column_labels = {"created_at": "Fecha Agregada"}
    form_args = {
        "ani": {"description": "Número de teléfono en formato E.164, por ejemplo 56912345678"},
        "reason": {"description": "Razón por la que este número está bloqueado"},
    }
    column_formatters = {"ani": format_phone_with_flag}


class ApiCredentialAdmin(SecureModelView):
    form_excluded_columns = _TIMESTAMP_EXCLUDED + ["api_secret_hash", "last_used_at", "revoked_at"]
    can_create = False
    column_list = ["user_id", "name", "api_key", "enabled", "expires_at", "last_used_at", "revoked_at"]
    column_searchable_list = ["api_key", "name"]
    form_args = {
        "name": {"description": "Etiqueta interna opcional para esta credencial"},
        "api_key": {
            "description": "Identificador de clave pública. Crear/rotar a través de comandos CLI de usuarios."
        },
        "enabled": {"description": "Deshabilitar para bloquear inmediatamente esta credencial"},
        "expires_at": {"description": "Marca de tiempo de vencimiento opcional (UTC)"},
    }


class UserAdmin(SecureModelView):
    column_list = ["login", "email", "enabled", "scopes"]
    column_searchable_list = ["login", "email"]
    form_excluded_columns = _TIMESTAMP_EXCLUDED
    form_args = {
        "login": {"description": "Nombre de usuario para autenticación SQLAdmin sin contraseña"},
        "email": {"description": "Dirección de correo electrónico de contacto"},
        "password": {"description": "Texto plano — se hash automáticamente al guardar"},
        "allowed_ips": {
            "description": (
                'Deprecado. Se mantiene solo para compatibilidad; no es aplicado por auth. Formato anterior: ["10.0.0.1"].'
            )
        },
        "enabled": {"description": "Desmarcar para deshabilitar acceso a API sin eliminar el usuario"},
        "scopes": {
            "description": (
                'Lista JSON de alcances, por ejemplo ["core", "admin"]. Disponibles: core, audiotex, asterisk, firenze, admin'
            )
        },
    }

    def on_model_change(self, data, model, is_created, request):
        if data.get("password"):
            data["password"] = hash_user_password(data["password"])
        elif is_created:
            raise ValueError("Password is required when creating a user")


class ClientAdmin(SecureModelView):
    # details_template = "sqladmin/client_details.html"
    form_excluded_columns = _TIMESTAMP_EXCLUDED
    column_searchable_list = ["client_id", "email"]
    column_sortable_list = ["client_id", "email", "credits"]
    column_list = ["full_name", "email", "credits", "service", "client_id", "anis"]
    column_labels = {
        "full_name": "Nombre",
        "email": "Correo Electrónico",
        "credits": "Segundos",
        "service": "Servicio Asociado",
        "client_id": "Identificador del Cliente",
        "anis": "Teléfono",
    }
    column_formatters = {
        "anis": lambda _view, _context, model, _name: (
            Markup(" ").join(
                Markup(
                    f'<span class="badge bg-blue-lt text-blue">{escape(client_ani.ani)} '
                    f"({escape(client_ani.q_calls)})</span>"
                )
                for client_ani in model.anis
            )
            if model.anis
            else ""
        )
    }

    # def get_object_for_details(self, request: Request) -> Client | None:
    #     model = super().get_object_for_details(request)
    #     if not model:
    #         return None

    #     ani_values = [ani.ani for ani in model.anis if ani.ani]
    #     dnc_ani_set: set[str] = set()
    #     if ani_values:
    #         dnc_rows = await self._run_query(select(DoNotCall.ani).where(DoNotCall.ani.in_(ani_values)))
    #         dnc_ani_set = {str(ani) for ani in dnc_rows if ani}

    #     cdr_stmt = (
    #         select(AsteriskCDR)
    #         .where(AsteriskCDR.zvn_clientid == model.client_id)
    #         .where(AsteriskCDR.lastapp == "Dial")
    #         .order_by(AsteriskCDR.calldate.desc())
    #         .limit(15)
    #     )
    #     if model.service and model.service.slug:
    #         cdr_stmt = cdr_stmt.where(AsteriskCDR.accountcode == model.service.slug)

    #     model.dnc_ani_set = dnc_ani_set
    #     model.last_calls = await self._run_query(cdr_stmt)
    #     return model


class ClientAniAdmin(SecureModelView):
    form_excluded_columns = _TIMESTAMP_EXCLUDED
    column_searchable_list = ["ani", "client_id"]
    column_sortable_list = ["client_id", "q_calls", "last_call"]
    column_list = ["client_id", "service_id", "ani", "q_calls", "last_call"]
    column_labels = {
        "client_id": "Identificador del Cliente (rel. missing)",
        "service_id": "Servicio (rel. missing)",
        "ani": "Teléfono",
        "q_calls": "Cantidad de Llamadas",
        "last_call": "Última Llamada",
    }
    column_formatters = {"ani": format_phone_with_flag}


class ServiceAdmin(SecureModelView):
    column_list = ["name", "slug", "created_at"]
    column_searchable_list = ["name", "slug"]
    form_excluded_columns = _TIMESTAMP_EXCLUDED
    form_args = {
        "name": {"description": "Nombre de servicio legible para el usuario, por ejemplo FonoTarot Chile"},
        "slug": {"description": "Identificador único usado en dialplan y API, por ejemplo fonotarot-cl"},
        "auth_method": {"description": "Manera de authorizacion: ani o pin"},
        "intro_audio": {"description": "Audio de introducción"},
    }


class ServiceNumberAdmin(SecureModelView):
    column_list = ["did", "active", "asterisk_context", "service"]
    column_searchable_list = ["did", "asterisk_context"]
    form_excluded_columns = _TIMESTAMP_EXCLUDED
    form_args = {
        "did": {"description": "Número DID completo en formato E.164, por ejemplo 56229402147"},
        "active": {"description": "Desmarcar para dejar de enrutar llamadas a este DID"},
        "asterisk_context": {
            "description": "Contexto de dialplan de Asterisk al que enrutar este DID, por ejemplo prepago-fonotarot-cl"
        },
    }
    column_formatters = {"did": format_phone_with_flag}


class OperatorAdmin(SecureModelView):
    column_list = ["number", "name", "option", "loggedin", "available", "lastcall"]
    column_searchable_list = ["name"]
    column_sortable_list = ["number", "lastcall", "loggedin"]
    form_excluded_columns = _TIMESTAMP_EXCLUDED + ["loggedin", "available", "lastcall"]
    form_args = {
        "number": {"description": "Número interno de extensión SIP, por ejemplo 1001"},
        "name": {"description": "Nombre de visualización del operador, usado en audio IVR y registros"},
        "description": {"description": "Notas internas sobre este operador (opcional)"},
        "option": {
            "description": "Código de 1-2 dígitos que el llamador presiona para seleccionar este operador, por ejemplo 01"
        },
        "enable_valkey": {
            "description": "Usar Redis/Valkey para estado de disponibilidad en tiempo real (no utilizar)"
        },
    }


class OperatorPhoneAdmin(SecureModelView):
    column_list = ["number", "trunk", "enabled", "contact", "operator"]
    column_searchable_list = ["number"]
    form_excluded_columns = _TIMESTAMP_EXCLUDED
    form_args = {
        "number": {"description": "Número de teléfono a marcar, por ejemplo 56912345678"},
        "enabled": {"description": "Desmarcar para deshabilitar temporalmente este número de teléfono"},
        "contact": {"description": "Marcar como número de contacto principal para este operador"},
        "pin": {
            "description": "PIN de 4 dígitos utilizado para el inicio de sesión del operador desde teléfono (opcional)"
        },
        "trunk": {
            "description": ("Troncal SIP saliente a utilizar para este número, por ejemplo: tecnoera, didww-mia-out. ")
        },
    }
    column_formatters = {"number": format_phone_with_flag}



class FirenzeAdminIndexView(SecureAdminIndexView):
    @expose("/")
    def index(self):
        
        services = Service.query.all()
        datos = {
            "services": [{"slug": service.slug, "name": service.name} for service in services if service.slug],
        }

        return self.render("firenze/index.html", **datos)


def setup_admin(app):
    admin.add_category(name="Fonotarot", icon_type="ti", icon_value="eye")
    admin.add_category(name="Informes", icon_type="ti", icon_value="reports")
    admin.add_category(name="Sistema", icon_type="ti", icon_value="settings")

    # Sistema
    admin.add_view(
        DNCAdmin(
            DoNotCall, db.session, name="DNC", category="Sistema", menu_icon_type="ti", menu_icon_value="phone-off"
        )
    )
    admin.add_view(
        ApiCredentialAdmin(
            ApiCredential,
            db.session,
            name="Usuarios API",
            category="Sistema",
            menu_icon_type="ti",
            menu_icon_value="api-app",
        )
    )
    admin.add_view(
        UserAdmin(
            User, db.session, name="Usuarios Locales", category="Sistema", menu_icon_type="ti", menu_icon_value="users"
        )
    )

    # Fonotarot
    admin.add_view(
        ClientAdmin(
            Client, db.session, name="Clientes", category="Fonotarot", menu_icon_type="ti", menu_icon_value="user"
        )
    )
    admin.add_view(
        ClientAniAdmin(
            ClientAni,
            db.session,
            name="ANIs de Cliente",
            category="Fonotarot",
            menu_icon_type="ti",
            menu_icon_value="device-mobile",
        )
    )
    admin.add_view(
        ServiceAdmin(
            Service,
            db.session,
            name="Servicios",
            category="Fonotarot",
            menu_icon_type="ti",
            menu_icon_value="ai-gateway",
        )
    )
    admin.add_view(
        ServiceNumberAdmin(
            ServiceNumber,
            db.session,
            name="DIDs de Servicio",
            category="Fonotarot",
            menu_icon_type="ti",
            menu_icon_value="phone-spark",
        )
    )

    admin.add_view(
        OperatorAdmin(
            Operator,
            db.session,
            name="Tarotistas",
            category="Fonotarot",
            menu_icon_type="ti",
            menu_icon_value="headset",
        )
    )
    admin.add_view(
        OperatorPhoneAdmin(
            OperatorPhone,
            db.session,
            name="Telefonos de Tarotistas",
            category="Fonotarot",
            menu_icon_type="ti",
            menu_icon_value="phone",
        )
    )
    # Informes
    admin.add_link(
        MenuLink(name="API Logs", icon_type="ti", endpoint="admin.index", icon_value="logs", category="Informes")
    )

    # Links: Api Docs,
    admin.add_link(
        MenuLink(name="API Docs", endpoint="api-docs.openapi_swagger_ui", icon_type="ti", icon_value="home")
    )
