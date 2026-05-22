import asyncio
import calendar
import datetime
import logging

import redis as redis_lib
from markupsafe import Markup, escape
from sqladmin import Admin, BaseView, ModelView, expose
from sqladmin.authentication import login_required
from sqlalchemy import and_, case, func, select
from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette.routing import Route

from firenze.config import settings
from firenze.database import SessionLocal
from firenze.models import (
    ApiCredential,
    AsteriskCDR,
    Client,
    ClientAni,
    DoNotCall,
    Event,
    OnlineCalls,
    Operator,
    OperatorPhone,
    PostCallProcess,
    Service,
    ServiceNumber,
    User,
)
from firenze.redis import get_redis
from firenze.services import auth_service

_log = logging.getLogger("firenze")

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

    db = SessionLocal()
    try:
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
    finally:
        db.close()

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

    db = SessionLocal()
    try:
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
    finally:
        db.close()

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


class ClientAdmin(ModelView, model=Client):
    name = "Cliente"
    name_plural = "Clientes"
    icon = "fa-solid fa-user"
    category = "FonoTarot"
    category_icon = "fa-solid fa-eye"
    details_template = "sqladmin/client_details.html"
    form_excluded_columns = _TIMESTAMP_EXCLUDED
    column_searchable_list = [Client.client_id, Client.email]
    column_sortable_list = [Client.client_id, Client.email, Client.id, Client.credits]
    column_list = [
        Client.full_name,
        Client.email,
        Client.credits,
        Client.service,
        Client.client_id,
        Client.anis,
    ]
    column_labels = {
        Client.full_name: "Nombre",
        Client.email: "Correo Electrónico",
        Client.credits: "Segundos",
        Client.service: "Servicio Asociado",
        Client.client_id: "Identificador del Cliente",
        Client.anis: "Teléfono",
    }
    column_formatters = {
        Client.anis: lambda model, _: (
            [
                Markup(
                    f'<span class="badge bg-blue-lt text-blue">{escape(client_ani.ani)} '
                    f"({escape(client_ani.q_calls)})</span>"
                )
                for client_ani in model.anis
            ]
            if model.anis
            else []
        )
    }

    async def get_object_for_details(self, request: Request) -> Client | None:
        model = await super().get_object_for_details(request)
        if not model:
            return None

        ani_values = [ani.ani for ani in model.anis if ani.ani]
        dnc_ani_set: set[str] = set()
        if ani_values:
            dnc_rows = await self._run_query(select(DoNotCall.ani).where(DoNotCall.ani.in_(ani_values)))
            dnc_ani_set = {str(ani) for ani in dnc_rows if ani}

        cdr_stmt = (
            select(AsteriskCDR)
            .where(AsteriskCDR.zvn_clientid == model.client_id)
            .where(AsteriskCDR.lastapp == "Dial")
            .order_by(AsteriskCDR.calldate.desc())
            .limit(15)
        )
        if model.service and model.service.slug:
            cdr_stmt = cdr_stmt.where(AsteriskCDR.accountcode == model.service.slug)

        model.dnc_ani_set = dnc_ani_set
        model.last_calls = await self._run_query(cdr_stmt)
        return model


class ClientAniAdmin(ModelView, model=ClientAni):
    name = "ANI del Cliente"
    name_plural = "ANIs del Cliente"
    icon = "fa-solid fa-mobile-screen"
    category = "FonoTarot"
    category_icon = "fa-solid fa-eye"
    form_excluded_columns = _TIMESTAMP_EXCLUDED
    column_searchable_list = [ClientAni.ani, ClientAni.client_id]
    column_sortable_list = [ClientAni.client_id, ClientAni.q_calls, ClientAni.last_call]
    column_list = [
        ClientAni.client_id,
        ClientAni.ani,
        ClientAni.q_calls,
        ClientAni.last_call,
    ]
    column_labels = {
        ClientAni.client_id: "Identificador del Cliente",
        ClientAni.ani: "Teléfono",
        ClientAni.q_calls: "Cantidad de Llamadas",
        ClientAni.last_call: "Última Llamada",
    }


class DNCAdmin(ModelView, model=DoNotCall):
    column_list = [DoNotCall.ani, DoNotCall.reason, DoNotCall.created_at]
    column_searchable_list = [DoNotCall.ani]
    form_excluded_columns = _TIMESTAMP_EXCLUDED
    name = "DNC"
    name_plural = "Lista DNC"
    icon = "fa-solid fa-phone-slash"
    category = "Autenticación"
    category_icon = "fa-solid fa-key"
    column_labels = {DoNotCall.created_at: "Fecha Agregada"}
    form_args = {
        "ani": {"description": "Número de teléfono en formato E.164, por ejemplo 56912345678"},
        "reason": {"description": "Razón por la que este número está bloqueado"},
    }


class ServiceAdmin(ModelView, model=Service):
    column_list = [Service.id, Service.name, Service.slug, Service.created_at]
    column_searchable_list = [Service.name, Service.slug]
    form_excluded_columns = _TIMESTAMP_EXCLUDED
    name = "Servicio"
    name_plural = "Servicios"
    icon = "fa-solid fa-blender-phone"
    category = "FonoTarot"
    category_icon = "fa-solid fa-eye"
    form_args = {
        "name": {"description": "Nombre de servicio legible para el usuario, por ejemplo FonoTarot Chile"},
        "slug": {"description": "Identificador único usado en dialplan y API, por ejemplo fonotarot-cl"},
    }


class ServiceNumberAdmin(ModelView, model=ServiceNumber):
    column_list = [
        ServiceNumber.did,
        ServiceNumber.active,
        ServiceNumber.asterisk_context,
        ServiceNumber.service,
    ]
    column_searchable_list = [ServiceNumber.did, ServiceNumber.asterisk_context]
    form_excluded_columns = _TIMESTAMP_EXCLUDED
    name = "DID"
    name_plural = "DIDs del Servicio"
    icon = "fa-solid fa-mobile-retro"
    category = "FonoTarot"
    category_icon = "fa-solid fa-eye"
    form_args = {
        "did": {"description": "Número DID completo en formato E.164, por ejemplo 56229402147"},
        "active": {"description": "Desmarcar para dejar de enrutar llamadas a este DID"},
        "asterisk_context": {
            "description": "Contexto de dialplan de Asterisk al que enrutar este DID, por ejemplo prepago-fonotarot-cl"
        },
    }


class OperatorAdmin(ModelView, model=Operator):
    column_list = [
        Operator.number,
        Operator.name,
        Operator.option,
        Operator.loggedin,
        Operator.available,
        Operator.lastcall,
    ]
    column_searchable_list = [Operator.name]
    column_sortable_list = [Operator.number, Operator.lastcall, Operator.loggedin]
    form_excluded_columns = _TIMESTAMP_EXCLUDED + [
        "loggedin",
        "available",
        "lastcall",
    ]
    name = "Operador"
    name_plural = "Operadores"
    icon = "fa-solid fa-headphones"
    category = "FonoTarot"
    category_icon = "fa-solid fa-eye"
    form_args = {
        "number": {"description": "Número interno de extensión SIP, por ejemplo 1001"},
        "name": {"description": "Nombre de visualización del operador, usado en audio IVR y registros"},
        "description": {"description": "Notas internas sobre este operador (opcional)"},
        "option": {"description": "Código de 1-2 dígitos que el llamador presiona para seleccionar este operador, por ejemplo 01"},
        "enable_valkey": {"description": "Usar Redis/Valkey para estado de disponibilidad en tiempo real (recomendado)"},
    }


class OperatorPhoneAdmin(ModelView, model=OperatorPhone):
    column_list = [
        OperatorPhone.number,
        OperatorPhone.trunk,
        OperatorPhone.enabled,
        OperatorPhone.contact,
        OperatorPhone.operator,
    ]
    column_searchable_list = [OperatorPhone.number]
    form_excluded_columns = _TIMESTAMP_EXCLUDED
    name = "Teléfono del Operador"
    name_plural = "Teléfonos de Operadores"
    icon = "fa-solid fa-phone"
    category = "FonoTarot"
    category_icon = "fa-solid fa-eye"
    form_args = {
        "number": {"description": "Número de teléfono a marcar, por ejemplo 56912345678"},
        "enabled": {"description": "Desmarcar para deshabilitar temporalmente este número de teléfono"},
        "contact": {"description": "Marcar como número de contacto principal para este operador"},
        "pin": {"description": "PIN de 4 dígitos utilizado para el inicio de sesión del operador desde teléfono (opcional)"},
        "trunk": {
            "description": (
                "Troncal SIP saliente a utilizar para este número, por ejemplo claro1, didww-mia-out. "
                "Dejar en blanco para usar el troncal predeterminado"
            )
        },
    }


class OnlineCallsAdmin(ModelView, model=OnlineCalls):
    column_list = [
        OnlineCalls.service,
        OnlineCalls.ani,
        OnlineCalls.did,
        OnlineCalls.operator,
        OnlineCalls.client_id,
        OnlineCalls.created_at,
    ]
    column_searchable_list = [OnlineCalls.ani, OnlineCalls.service]
    column_sortable_list = [OnlineCalls.created_at, OnlineCalls.service]
    can_create = False
    can_edit = False
    can_delete = True
    name = "Llamada En Línea"
    name_plural = "Llamadas En Línea"
    icon = "fa-solid fa-signal"
    category = "Informes"
    category_icon = "fa-solid fa-chart-simple"


class AsteriskCDRAdmin(ModelView, model=AsteriskCDR):
    column_list = [
        AsteriskCDR.calldate,
        AsteriskCDR.src,
        AsteriskCDR.dst,
        AsteriskCDR.billsec,
        AsteriskCDR.disposition,
        AsteriskCDR.accountcode,
        AsteriskCDR.zvn_clientid,
        AsteriskCDR.zvn_client_ani,
        AsteriskCDR.zvn_operator,
    ]
    column_searchable_list = [
        AsteriskCDR.src,
        AsteriskCDR.dst,
        AsteriskCDR.zvn_clientid,
        AsteriskCDR.zvn_client_ani,
        AsteriskCDR.zvn_operator,
    ]
    column_sortable_list = [
        AsteriskCDR.calldate,
        AsteriskCDR.accountcode,
        AsteriskCDR.zvn_clientid,
        AsteriskCDR.zvn_client_ani,
        AsteriskCDR.zvn_operator,
    ]
    column_default_sort = (AsteriskCDR.calldate, True)
    can_create = False
    can_edit = False
    can_delete = False
    name = "CDR"
    name_plural = "CDRs"
    icon = "fa-solid fa-music"
    category = "Informes"
    category_icon = "fa-solid fa-chart-simple"


class PostCallProcessAdmin(ModelView, model=PostCallProcess):
    column_list = [
        PostCallProcess.service,
        PostCallProcess.process_name,
        PostCallProcess.client_id,
        PostCallProcess.processed,
        PostCallProcess.created_at,
    ]
    column_searchable_list = [PostCallProcess.service, PostCallProcess.process_name]
    column_sortable_list = [PostCallProcess.created_at, PostCallProcess.processed]
    can_create = False
    can_edit = False
    can_delete = False
    name = "Proceso Post-Llamada"
    name_plural = "Procesos Post-Llamada"


class UserAdmin(ModelView, model=User):
    column_list = [User.id, User.login, User.email, User.enabled, User.scopes]
    column_searchable_list = [User.login, User.email]
    form_excluded_columns = _TIMESTAMP_EXCLUDED
    name = "Usuario de API"
    name_plural = "Usuarios de API"
    icon = "fa-solid fa-user-gear"
    category = "Autenticación"
    category_icon = "fa-solid fa-key"
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

    async def on_model_change(self, data, model, is_created, request):
        if data.get("password"):
            data["password"] = auth_service.hash_user_password(data["password"])
        elif is_created:
            raise ValueError("Password is required when creating a user")


class ApiCredentialAdmin(ModelView, model=ApiCredential):
    name = "Credencial de API"
    name_plural = "Credenciales de API"
    icon = "fa-solid fa-key"
    category = "Autenticación"
    category_icon = "fa-solid fa-key"
    form_excluded_columns = _TIMESTAMP_EXCLUDED + [
        "api_secret_hash",
        "last_used_at",
        "revoked_at",
    ]
    can_create = False
    column_list = [
        ApiCredential.id,
        ApiCredential.user_id,
        ApiCredential.name,
        ApiCredential.api_key,
        ApiCredential.enabled,
        ApiCredential.expires_at,
        ApiCredential.last_used_at,
        ApiCredential.revoked_at,
    ]
    column_searchable_list = [ApiCredential.api_key, ApiCredential.name]
    form_args = {
        "name": {"description": "Etiqueta interna opcional para esta credencial"},
        "api_key": {"description": "Identificador de clave pública. Crear/rotar a través de comandos CLI de usuarios."},
        "enabled": {"description": "Deshabilitar para bloquear inmediatamente esta credencial"},
        "expires_at": {"description": "Marca de tiempo de vencimiento opcional (UTC)"},
    }


class EventAdmin(ModelView, model=Event):
    column_list = [Event.name, Event.verb, Event.ip, Event.url, Event.created_at]
    column_searchable_list = [Event.name, Event.url, Event.ip]
    column_sortable_list = [Event.created_at, Event.name]
    can_create = False
    can_edit = False
    can_delete = False
    name = "Evento"
    name_plural = "Eventos"


class AdminIndex(BaseView):
    name = "Panel de Control"
    icon = "fa fa-gauge"

    @expose("/index", methods=["GET"])
    async def admin(self, request):
        return RedirectResponse(url="/admin")

class APIDocs(BaseView):
    name = "API Docs"
    icon = "fa fa-dna"

    @expose("/api-docs", methods=["GET"])
    async def apidocs(self, request):
        return RedirectResponse(url="/api-docs")


class MonthlyReportIndex(BaseView):
    name = "Informe Mensual"
    icon = "fa fa-calendar-days"
    category = "Informes"
    category_icon = "fa-solid fa-chart-simple"

    @expose("/monthly-report", methods=["GET"], identity="monthly-report")
    @login_required
    async def index(self, request):
        today = datetime.date.today()
        try:
            year = int(request.query_params.get("year", today.year))
            month = int(request.query_params.get("month", today.month))
        except TypeError, ValueError:
            year, month = today.year, today.month

        month = max(1, min(12, month))
        year = max(_REPORT_MIN_YEAR, min(today.year + 1, year))

        report = None
        error = None
        try:
            report = await asyncio.to_thread(_collect_monthly_report, year, month)
        except Exception as exc:  # noqa: BLE001
            _log.exception("monthly_report failed")
            error = str(exc)

        return await self.templates.TemplateResponse(
            request,
            "monthly_report.html",
            context={
                "title": "Informe Mensual",
                "year": year,
                "month": month,
                "months_es": _MONTHS_ES,
                "min_year": _REPORT_MIN_YEAR,
                "today": today,
                "data": report,
                "error": error,
            },
        )


class MonthlyAgentReportIndex(BaseView):
    name = "Informe de Agentes"
    icon = "fa fa-users"
    category = "Informes"
    category_icon = "fa-solid fa-chart-simple"

    @expose("/monthly-agent-report", methods=["GET"], identity="monthly-agent-report")
    @login_required
    async def index(self, request):
        today = datetime.date.today()
        year = today.year
        month = today.month

        selected_raw = request.query_params.getlist("agents")
        selected_agents = tuple(int(v) for v in selected_raw if v.isdigit())
        selected_agents = selected_agents or None

        report = None
        error = None
        try:
            report = await asyncio.to_thread(_collect_monthly_agent_report, year, month, selected_agents)
        except Exception as exc:  # noqa: BLE001
            _log.exception("monthly_agent_report failed")
            error = str(exc)

        return await self.templates.TemplateResponse(
            request,
            "monthly_agent_report.html",
            context={
                "title": "Reporte Agentes",
                "year": year,
                "month": month,
                "months_es": _MONTHS_ES,
                "min_year": _REPORT_MIN_YEAR,
                "today": today,
                "data": report,
                "error": error,
                "selected_agents": set(selected_agents) if selected_agents else set(),
            },
        )


class FirenzeAdmin(Admin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.admin.router.routes.extend(
            [
                Route(
                    "/login/passwordless-request",
                    endpoint=self.passwordless_request,
                    methods=["POST"],
                    name="passwordless-request",
                ),
                Route(
                    "/login/passwordless-verify",
                    endpoint=self.passwordless_verify,
                    methods=["POST"],
                    name="passwordless-verify",
                ),
            ]
        )

    async def passwordless_request(self, request: Request):
        if not settings.AUTH_PASSWORDLESS_ENABLED:
            return RedirectResponse(
                request.url_for("admin:login").include_query_params(
                    step="code",
                    error="El inicio de sesión sin contraseña está deshabilitado.",
                ),
                status_code=302,
            )

        form = await request.form()
        identifier = (form.get("username") or "").strip()
        if not identifier:
            return RedirectResponse(
                request.url_for("admin:login").include_query_params(
                    error="Por favor, ingresa tu correo primero.",
                ),
                status_code=302,
            )

        db = SessionLocal()
        try:
            user = auth_service.find_user_for_passwordless_identifier(db, identifier)
            if user and user.enabled and user.email:
                request_ip = request.client.host if request.client else ""
                user_agent = request.headers.get("user-agent", "")
                if auth_service.can_issue_passwordless_code(db, user, request_ip):
                    code = auth_service.create_passwordless_code(db, user, request_ip, user_agent)
                    auth_service.send_passwordless_code_email(user.email, code)
        finally:
            db.close()

        return RedirectResponse(
            request.url_for("admin:login").include_query_params(
                step="code",
                identifier=identifier,
                message="Si la cuenta existe, se ha enviado un código de inicio de sesión.",
            ),
            status_code=302,
        )

    async def passwordless_verify(self, request: Request):
        if not settings.AUTH_PASSWORDLESS_ENABLED:
            return RedirectResponse(
                request.url_for("admin:login").include_query_params(
                    step="code",
                    error="El inicio de sesión sin contraseña está deshabilitado.",
                ),
                status_code=302,
            )

        form = await request.form()
        identifier = (form.get("identifier") or "").strip()
        code = (form.get("code") or "").strip()
        if not identifier:
            return RedirectResponse(
                request.url_for("admin:login").include_query_params(
                    error="Por favor, ingresa tu correo primero.",
                ),
                status_code=302,
            )
        if not code:
            return RedirectResponse(
                request.url_for("admin:login").include_query_params(
                    step="code",
                    identifier=identifier,
                    error="Por favor, ingresa el código de inicio de sesión.",
                ),
                status_code=302,
            )

        db = SessionLocal()
        try:
            user = auth_service.verify_passwordless_code(db, identifier, code)
            if not user or not auth_service.has_required_scopes(user, ["admin"]):
                return RedirectResponse(
                    request.url_for("admin:login").include_query_params(
                        step="code",
                        identifier=identifier,
                        error="Código inválido o expirado.",
                    ),
                    status_code=302,
                )
            request.session.update({"admin_user_id": user.id})
        finally:
            db.close()

        return RedirectResponse(request.url_for("admin:index"), status_code=302)

    @login_required
    async def index(self, request):
        top_ani_raw = request.query_params.get("top_ani", "10")
        try:
            requested_top_ani = int(top_ani_raw)
        except TypeError, ValueError:
            requested_top_ani = 10
        top_ani_limit = requested_top_ani if requested_top_ani in {5, 10, 15} else 10
        operator_period = request.query_params.get("operator_period", "current_month")
        if operator_period not in {"current_month", "last_month", "last_3_months"}:
            operator_period = "current_month"
        data = await asyncio.to_thread(self._collect_data, top_ani_limit, operator_period)
        return await self.templates.TemplateResponse(
            request,
            "system_status.html",
            context={
                "title": "Estado del Sistema",
                "subtitle": "Salud de Redis / Valkey, informes CDR, estado del operador y llamadas activas",
                **data,
            },
        )

    @staticmethod
    def _collect_data(top_ani_limit: int = 10, operator_period: str = "current_month") -> dict:
        now = datetime.datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow_start = today_start + datetime.timedelta(days=1)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        next_month = (month_start + datetime.timedelta(days=32)).replace(day=1)
        last_month_start = (month_start - datetime.timedelta(days=1)).replace(day=1)
        last_3_months_start = month_start
        for _ in range(2):
            last_3_months_start = (last_3_months_start - datetime.timedelta(days=1)).replace(day=1)

        operator_period_meta = {
            "current_month": {
                "label": "Mes Actual",
                "start": month_start,
                "end": next_month,
            },
            "last_month": {
                "label": "Mes Pasado",
                "start": last_month_start,
                "end": month_start,
            },
            "last_3_months": {
                "label": "Últimos 3 Meses",
                "start": last_3_months_start,
                "end": next_month,
            },
        }
        selected_operator_period = operator_period if operator_period in operator_period_meta else "current_month"
        operator_period_start = operator_period_meta[selected_operator_period]["start"]
        operator_period_end = operator_period_meta[selected_operator_period]["end"]

        redis_conn = get_redis()
        redis_online = redis_conn is not None
        redis_info: dict = {}
        redis_operators: dict[int, dict] = {}
        redis_calls: list[dict] = []

        if redis_conn:
            try:
                redis_info = redis_conn.info()
            except redis_lib.RedisError:
                pass

            try:
                for key in redis_conn.scan_iter("firenze:operator:*", count=100):
                    try:
                        number = int(key.split(":")[-1])
                        raw = redis_conn.hgetall(key)
                        if raw:
                            redis_operators[number] = {
                                "loggedin": bool(int(raw.get("loggedin", 0))),
                                "available": bool(int(raw.get("available", 0))),
                                "lastcall": int(raw.get("lastcall", 0) or 0),
                                "ttl": redis_conn.ttl(key),
                            }
                    except ValueError, redis_lib.RedisError:
                        continue
            except redis_lib.RedisError as exc:
                _log.warning("No se pudo escanear las claves del operador: %s", exc)

            try:
                for key in redis_conn.scan_iter("firenze:call:*", count=100):
                    try:
                        # key format: firenze:call:{service}:{ani}
                        parts = key.split(":", 3)
                        if len(parts) < 4:
                            continue
                        service, ani = parts[2], parts[3]
                        raw = redis_conn.hgetall(key)
                        if raw:
                            redis_calls.append(
                                {
                                    "service": service,
                                    "ani": ani,
                                    "did": raw.get("did", ""),
                                    "operator": int(raw.get("operator", 0) or 0),
                                    "client_id": int(raw.get("client_id", 0) or 0),
                                    "created_at": int(raw.get("created_at", 0) or 0),
                                    "ttl": redis_conn.ttl(key),
                                }
                            )
                    except ValueError, redis_lib.RedisError:
                        continue
            except redis_lib.RedisError as exc:
                _log.warning("No se pudo escanear las claves de llamadas: %s", exc)

        # DB queries
        db = SessionLocal()
        try:
            services = db.query(Service).order_by(Service.id).all()
            operators = db.query(Operator).order_by(Operator.number).all()
            online_calls = db.query(OnlineCalls).order_by(OnlineCalls.created_at.desc()).all()
            cdr_today = (
                db.query(
                    func.count(AsteriskCDR.cdrid).label("total_calls"),
                    func.sum(case((AsteriskCDR.disposition == "ANSWERED", 1), else_=0)).label("answered_calls"),
                    func.sum(case((AsteriskCDR.disposition != "ANSWERED", 1), else_=0)).label("failed_calls"),
                    func.coalesce(
                        func.floor(
                            func.sum(case((AsteriskCDR.disposition == "ANSWERED", AsteriskCDR.billsec), else_=0)) / 60
                        ),
                        0,
                    ).label("answered_minutes"),
                    func.coalesce(
                        func.avg(case((AsteriskCDR.disposition == "ANSWERED", AsteriskCDR.billsec), else_=None)),
                        0,
                    ).label("avg_billsec"),
                )
                .filter(AsteriskCDR.calldate >= today_start, AsteriskCDR.calldate < tomorrow_start, AsteriskCDR.lastapp == "Dial")
                .one()
            )
            cdr_client_activity = (
                db.query(
                    AsteriskCDR.zvn_clientid.label("client_id"),
                    func.max(AsteriskCDR.calldate).label("last_call"),
                    func.count(AsteriskCDR.cdrid).label("calls"),
                )
                .filter(
                    AsteriskCDR.zvn_clientid.is_not(None),
                    AsteriskCDR.zvn_clientid > 1,
                    AsteriskCDR.lastapp == "Dial",
                )
                .group_by(AsteriskCDR.zvn_clientid)
                .subquery()
            )
            ani_usage = (
                db.query(
                    func.count(cdr_client_activity.c.client_id).label("total_anis"),
                    func.coalesce(func.sum(cdr_client_activity.c.calls), 0).label("total_calls"),
                    func.coalesce(func.avg(cdr_client_activity.c.calls), 0).label("avg_calls"),
                    func.sum(case((cdr_client_activity.c.last_call.is_not(None), 1), else_=0)).label("with_last_call"),
                    func.sum(case((cdr_client_activity.c.last_call.is_(None), 1), else_=0)).label("no_last_call"),
                    func.sum(case((cdr_client_activity.c.last_call >= today_start, 1), else_=0)).label("active_24h"),
                    func.sum(
                        case(
                            (cdr_client_activity.c.last_call >= now - datetime.timedelta(days=7), 1),
                            else_=0,
                        )
                    ).label("active_7d"),
                    func.sum(
                        case(
                            (cdr_client_activity.c.last_call >= now - datetime.timedelta(days=15), 1),
                            else_=0,
                        )
                    ).label("active_15d"),
                    func.sum(
                        case(
                            (
                                and_(
                                    cdr_client_activity.c.last_call < now - datetime.timedelta(days=30),
                                    cdr_client_activity.c.last_call >= now - datetime.timedelta(days=60),
                                ),
                                1,
                            ),
                            else_=0,
                        )
                    ).label("stale_30d"),
                    func.sum(
                        case(
                            (cdr_client_activity.c.last_call < now - datetime.timedelta(days=60), 1),
                            else_=0,
                        )
                    ).label("stale_60d"),
                    func.max(cdr_client_activity.c.last_call).label("latest_last_call"),
                )
                .select_from(cdr_client_activity)
                .one()
            )
            cdr_top_client_rows = (
                db.query(
                    AsteriskCDR.zvn_clientid.label("client_id"),
                    func.count(AsteriskCDR.cdrid).label("calls"),
                    func.max(AsteriskCDR.calldate).label("last_call"),
                )
                .filter(
                    AsteriskCDR.calldate >= now - datetime.timedelta(days=7),
                    AsteriskCDR.calldate < tomorrow_start,
                    AsteriskCDR.disposition == "ANSWERED",
                    AsteriskCDR.lastapp == "Dial",
                    AsteriskCDR.zvn_clientid.is_not(None),
                    AsteriskCDR.zvn_clientid > 1,
                )
                .group_by(AsteriskCDR.zvn_clientid)
                .order_by(func.count(AsteriskCDR.cdrid).desc(), func.max(AsteriskCDR.calldate).desc())
                .limit(top_ani_limit)
                .all()
            )
            top_client_ids = [int(row.client_id) for row in cdr_top_client_rows]
            if top_client_ids:
                client_ani_rows = (
                    db.query(
                        ClientAni.client_id,
                        func.min(ClientAni.ani).label("ani"),
                    )
                    .filter(ClientAni.client_id.in_(top_client_ids))
                    .group_by(ClientAni.client_id)
                    .all()
                )
            else:
                client_ani_rows = []
            cdr_month_answered = (
                db.query(
                    func.count(AsteriskCDR.cdrid).label("answered_calls"),
                    func.coalesce(func.floor(func.sum(AsteriskCDR.billsec) / 60), 0).label("answered_minutes"),
                )
                .filter(
                    AsteriskCDR.calldate >= month_start,
                    AsteriskCDR.calldate < next_month,
                    AsteriskCDR.disposition == "ANSWERED",
                    AsteriskCDR.lastapp == "Dial",
                    AsteriskCDR.zvn_clientid.is_not(None),
                    AsteriskCDR.zvn_clientid > 1,
                )
                .one()
            )
            service_catalog = [{"slug": svc.slug, "name": svc.name} for svc in services if svc.slug]
            service_slugs = [svc["slug"] for svc in service_catalog]
            if service_slugs:
                carrier_rows = (
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
                carrier_rows = []
            cdr_operator_rows = (
                db.query(
                    AsteriskCDR.zvn_operator,
                    func.count(AsteriskCDR.cdrid).label("calls"),
                    func.coalesce(func.floor(func.sum(AsteriskCDR.billsec) / 60), 0).label("minutes"),
                )
                .filter(
                    AsteriskCDR.calldate >= operator_period_start,
                    AsteriskCDR.calldate < operator_period_end,
                    AsteriskCDR.disposition == "ANSWERED",
                    AsteriskCDR.lastapp == "Dial",
                    AsteriskCDR.zvn_operator.is_not(None),
                    AsteriskCDR.zvn_clientid.is_not(None),
                    AsteriskCDR.zvn_clientid > 1,
                )
                .group_by(AsteriskCDR.zvn_operator)
                .order_by(AsteriskCDR.zvn_operator.asc())
                .all()
            )
            cdr_operator_activity_rows = (
                db.query(
                    AsteriskCDR.zvn_operator,
                    func.count(AsteriskCDR.cdrid).label("calls"),
                )
                .filter(
                    AsteriskCDR.calldate >= now - datetime.timedelta(days=15),
                    AsteriskCDR.calldate < tomorrow_start,
                    AsteriskCDR.disposition == "ANSWERED",
                    AsteriskCDR.lastapp == "Dial",
                    AsteriskCDR.zvn_operator.is_not(None),
                    AsteriskCDR.zvn_clientid.is_not(None),
                    AsteriskCDR.zvn_clientid > 1,
                )
                .group_by(AsteriskCDR.zvn_operator)
                .order_by(func.count(AsteriskCDR.cdrid).desc())
                .limit(5)
                .all()
            )
            disposition_rows = (
                db.query(
                    AsteriskCDR.disposition,
                    func.count(AsteriskCDR.cdrid).label("count"),
                )
                .filter(
                    AsteriskCDR.calldate >= month_start,
                    AsteriskCDR.calldate < next_month,
                    AsteriskCDR.lastapp == "Dial",
                )
                .group_by(AsteriskCDR.disposition)
                .order_by(func.count(AsteriskCDR.cdrid).desc())
                .all()
            )
            recent_cdr_rows = db.query(AsteriskCDR).order_by(AsteriskCDR.calldate.desc()).limit(40).all()
        finally:
            db.close()

        def _format_time_ago(dt: datetime.datetime | None) -> str:
            if dt is None:
                return "—"
            delta_seconds = max(int((now - dt).total_seconds()), 0)
            if delta_seconds < 60:
                return "just now"
            if delta_seconds < 3600:
                minutes = delta_seconds // 60
                return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
            if delta_seconds < 86400:
                hours = delta_seconds // 3600
                return f"{hours} hour{'s' if hours != 1 else ''} ago"
            days = delta_seconds // 86400
            return f"{days} day{'s' if days != 1 else ''} ago"

        # Enrich operator list with Redis state
        enriched_operators = []
        for op in operators:
            rs = redis_operators.get(op.number)
            if op.enable_valkey and rs is not None:
                synced = rs["loggedin"] == op.loggedin and rs["available"] == op.available
            else:
                synced = None
            enriched_operators.append(
                {
                    "number": op.number,
                    "name": op.name,
                    "option": op.option,
                    "enable_valkey": op.enable_valkey,
                    "db_loggedin": op.loggedin,
                    "db_available": op.available,
                    "db_lastcall": op.lastcall,
                    "lastcall_ago": _format_time_ago(op.lastcall),
                    "redis_state": rs,
                    "synced": synced,
                }
            )
        # UI order: available first, then in-call, then offline.
        enriched_operators.sort(
            key=lambda op: (
                0
                if op["db_loggedin"] and op["db_available"]
                else 1
                if op["db_loggedin"]
                else 2,
                str(op["name"]).lower(),
                int(op["number"]),
            )
        )

        def _format_elapsed_call_duration(created_at: datetime.datetime | None) -> str:
            if created_at is None:
                return "—"
            elapsed_seconds = max(int((now - created_at).total_seconds()), 0)
            hours, remainder = divmod(elapsed_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{hours:02}:{minutes:02}:{seconds:02}"

        # Enrich call list — cross-reference DB vs Redis
        redis_call_keys = {(c["service"], c["ani"]) for c in redis_calls}
        db_call_keys = {(c.service, c.ani) for c in online_calls}

        enriched_calls = []
        for call in online_calls:
            enriched_calls.append(
                {
                    "source": ("db+redis" if (call.service, call.ani) in redis_call_keys else "db_only"),
                    "service": call.service,
                    "ani": call.ani,
                    "did": call.did,
                    "operator": call.operator,
                    "client_id": call.client_id,
                    "created_at": call.created_at,
                    "call_duration": _format_elapsed_call_duration(call.created_at),
                }
            )
        for rc in redis_calls:
            if (rc["service"], rc["ani"]) not in db_call_keys:
                ts = rc.get("created_at")
                created_at = datetime.datetime.fromtimestamp(ts) if ts else None
                enriched_calls.append(
                    {
                        "source": "redis_only",
                        "service": rc["service"],
                        "ani": rc["ani"],
                        "did": rc["did"],
                        "operator": rc["operator"],
                        "client_id": rc["client_id"],
                        "created_at": created_at,
                        "call_duration": _format_elapsed_call_duration(created_at),
                    }
                )

        enriched_calls.sort(
            key=lambda call: (call["created_at"] or datetime.datetime.min),
            reverse=True,
        )

        operator_summary = {
            "total": len(enriched_operators),
            "logged_in": sum(1 for op in enriched_operators if op["db_loggedin"]),
            "available": sum(1 for op in enriched_operators if op["db_available"]),
            "valkey_enabled": sum(1 for op in enriched_operators if op["enable_valkey"]),
            "synced": sum(1 for op in enriched_operators if op["synced"] is True),
            "drift": sum(1 for op in enriched_operators if op["synced"] is False),
        }

        service_counts: dict[str, int] = {}
        for call in enriched_calls:
            service_counts[call["service"]] = service_counts.get(call["service"], 0) + 1
        total_active_calls = len(enriched_calls)
        active_call_services = [
            {
                "service": service,
                "count": count,
                "share": (round((count / total_active_calls) * 100, 1) if total_active_calls else 0.0),
            }
            for service, count in sorted(service_counts.items(), key=lambda item: item[1], reverse=True)
        ]

        carrier_by_day: dict[str, dict[str, int]] = {}
        for row in carrier_rows:
            day_key = row.day.isoformat()
            carrier_by_day.setdefault(day_key, {})
            carrier_by_day[day_key][row.accountcode] = int(row.minutes or 0)

        carrier_days = []
        carrier_totals_by_slug = {svc["slug"]: 0 for svc in service_catalog}
        days_in_month = calendar.monthrange(month_start.year, month_start.month)[1]
        for day_number in range(1, days_in_month + 1):
            day_key = month_start.replace(day=day_number).date().isoformat()
            day_data = {svc["slug"]: carrier_by_day.get(day_key, {}).get(svc["slug"], 0) for svc in service_catalog}
            day_total = sum(day_data.values())
            carrier_days.append(
                {
                    "day": day_key,
                    "services": day_data,
                    "total": day_total,
                }
            )
            for slug, minutes in day_data.items():
                carrier_totals_by_slug[slug] += minutes

        carrier_breakdown = []
        total_carrier_minutes = sum(carrier_totals_by_slug.values())
        for svc in service_catalog:
            minutes = carrier_totals_by_slug[svc["slug"]]
            share = round((minutes / total_carrier_minutes) * 100, 1) if total_carrier_minutes else 0.0
            carrier_breakdown.append({"key": svc["slug"], "label": svc["name"], "minutes": minutes, "share": share})
        carrier_breakdown.sort(key=lambda row: row["minutes"], reverse=True)

        service_color_map = {
            "fonotarot-cl": "var(--tblr-purple)",
            "alotarot": "var(--tblr-blue)",
            "fonotarot-latam": "var(--tblr-green)",
            "admin-stuff": "var(--tblr-yellow)",
        }
        chart_services = carrier_breakdown[:3]
        carrier_chart = {
            "labels": [row["day"] for row in carrier_days],
            "series": [
                {
                    "key": service["key"],
                    "name": service["label"],
                    "data": [int(day["services"].get(service["key"], 0)) for day in carrier_days],
                }
                for service in chart_services
            ],
            "colors": [service_color_map.get(service["key"], "var(--tblr-primary)") for service in chart_services],
        }
        carrier_totals = {"total": total_carrier_minutes}

        operator_name_by_number = {op.number: op.name for op in operators}
        operator_name_by_id = {op.id: op.name for op in operators}
        cdr_operator_totals = []
        for row in cdr_operator_rows:
            operator_ref = int(row.zvn_operator)
            cdr_operator_totals.append(
                {
                    "operator": operator_ref,
                    "name": operator_name_by_number.get(operator_ref)
                    or operator_name_by_id.get(operator_ref)
                    or f"Operador {operator_ref}",
                    "calls": int(row.calls or 0),
                    "minutes": int(row.minutes or 0),
                }
            )
        operator_max_minutes = max((row["minutes"] for row in cdr_operator_totals), default=1)
        operator_max_calls = max((row["calls"] for row in cdr_operator_totals), default=1)
        operator_total_minutes = sum(row["minutes"] for row in cdr_operator_totals)
        operator_total_calls = sum(row["calls"] for row in cdr_operator_totals)
        top_operator_calls_total = sum(int(row.calls or 0) for row in cdr_operator_activity_rows)
        operator_activity_colors = ["bg-purple", "bg-blue", "bg-green", "bg-yellow", "bg-red"]
        operator_activity_top5 = []
        for idx, row in enumerate(cdr_operator_activity_rows):
            operator_ref = int(row.zvn_operator)
            calls = int(row.calls or 0)
            operator_activity_top5.append(
                {
                    "operator": operator_ref,
                    "name": operator_name_by_number.get(operator_ref)
                    or operator_name_by_id.get(operator_ref)
                    or f"Operador {operator_ref}",
                    "calls": calls,
                    "share": round((calls * 100 / top_operator_calls_total), 1) if top_operator_calls_total else 0.0,
                    "color_class": operator_activity_colors[idx % len(operator_activity_colors)],
                }
            )

        disposition_total = sum(int(row.count or 0) for row in disposition_rows)
        cdr_dispositions = [
            {
                "name": row.disposition or "UNKNOWN",
                "count": int(row.count or 0),
                "share": (round((int(row.count or 0) / disposition_total) * 100, 1) if disposition_total else 0.0),
            }
            for row in disposition_rows
        ]
        client_ani_map = {int(row.client_id): (row.ani or "—") for row in client_ani_rows}
        top_ani_calls = max((int(row.calls or 0) for row in cdr_top_client_rows), default=1)
        ani_top_callers = [
            {
                "ani": client_ani_map.get(int(row.client_id), "—"),
                "client_id": int(row.client_id or 0),
                "q_calls": int(row.calls or 0),
                "share": round((int(row.calls or 0) / top_ani_calls) * 100, 1) if top_ani_calls else 0.0,
                "last_call": row.last_call,
            }
            for row in cdr_top_client_rows
        ]
        latest_last_call = ani_usage.latest_last_call
        latest_last_call_hours = (
            round((now - latest_last_call).total_seconds() / 3600, 1) if latest_last_call else None
        )

        recent_cdr = [
            {
                "calldate": row.calldate,
                "src": row.src,
                "dst": row.dst,
                "operator": row.zvn_operator,
                "disposition": row.disposition,
                "billsec": row.billsec,
                "client_id": row.zvn_clientid,
            }
            for row in recent_cdr_rows
        ]

        return {
            "redis_online": redis_online,
            "redis_info": redis_info,
            "operators": enriched_operators,
            "operator_summary": operator_summary,
            "operator_activity_top5": operator_activity_top5,
            "active_calls": enriched_calls,
            "active_call_services": active_call_services,
            "redis_operators_count": len(redis_operators),
            "redis_calls_count": len(redis_calls),
            "ani_reports": {
                "total_anis": int(ani_usage.total_anis or 0),
                "total_calls": int(ani_usage.total_calls or 0),
                "avg_calls": float(ani_usage.avg_calls or 0),
                "with_last_call": int(ani_usage.with_last_call or 0),
                "no_last_call": int(ani_usage.no_last_call or 0),
                "active_24h": int(ani_usage.active_24h or 0),
                "active_7d": int(ani_usage.active_7d or 0),
                "active_15d": int(ani_usage.active_15d or 0),
                "stale_30d": int(ani_usage.stale_30d or 0),
                "stale_60d": int(ani_usage.stale_60d or 0),
                "latest_last_call": latest_last_call,
                "latest_last_call_hours": latest_last_call_hours,
                "top_limit": top_ani_limit,
                "top_options": [5, 10, 15],
                "top_callers": ani_top_callers,
            },
            "cdr_reports": {
                "month_label": month_start.strftime("%Y-%m"),
                "today": {
                    "total_calls": int(cdr_today.total_calls or 0),
                    "answered_calls": int(cdr_today.answered_calls or 0),
                    "failed_calls": int(cdr_today.failed_calls or 0),
                    "answered_minutes": int(cdr_today.answered_minutes or 0),
                    "avg_billsec": float(cdr_today.avg_billsec or 0),
                },
                "month": {
                    "answered_calls": int(cdr_month_answered.answered_calls or 0),
                    "answered_minutes": int(cdr_month_answered.answered_minutes or 0),
                },
                "carrier_days": carrier_days,
                "carrier_totals": carrier_totals,
                "carrier_breakdown": carrier_breakdown,
                "carrier_chart": carrier_chart,
                "dispositions": cdr_dispositions,
                "operator_totals": cdr_operator_totals,
                "operator_max_minutes": operator_max_minutes,
                "operator_max_calls": operator_max_calls,
                "operator_total_minutes": operator_total_minutes,
                "operator_total_calls": operator_total_calls,
                "operator_period": selected_operator_period,
                "operator_period_label": str(operator_period_meta[selected_operator_period]["label"]),
                "operator_period_options": [
                    {"value": "current_month", "label": "Mes Actual"},
                    {"value": "last_month", "label": "Mes Pasado"},
                    {"value": "last_3_months", "label": "Últimos 3 Meses"},
                ],
                "recent_cdr": recent_cdr,
            },
        }


def register_admin(admin):
    admin.add_view(AdminIndex)
    admin.add_view(UserAdmin)
    admin.add_view(ApiCredentialAdmin)
    admin.add_view(DNCAdmin)
    admin.add_view(ClientAdmin)
    admin.add_view(ClientAniAdmin)
    admin.add_view(ServiceAdmin)
    admin.add_view(ServiceNumberAdmin)
    admin.add_view(OperatorAdmin)
    admin.add_view(OperatorPhoneAdmin)
    admin.add_view(AsteriskCDRAdmin)
    admin.add_view(MonthlyReportIndex)
    admin.add_view(MonthlyAgentReportIndex)
    admin.add_view(OnlineCallsAdmin)
    admin.add_view(APIDocs)
    # admin.add_view(PostCallProcessAdmin)
    # admin.add_view(EventAdmin)
