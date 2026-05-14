import asyncio
import datetime
import logging

import bcrypt
import redis as redis_lib
from sqladmin import BaseView, ModelView, expose, Admin
from sqladmin.authentication import login_required
from starlette.requests import Request
from starlette.responses import RedirectResponse

from firenze.database import SessionLocal
from firenze.models import (
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

_log = logging.getLogger("firenze")

_TIMESTAMP_EXCLUDED = ["created_at", "modified_at"]


class ClientAdmin(ModelView, model=Client):
    name = "Client"
    name_plural = "Clients"
    form_excluded_columns = _TIMESTAMP_EXCLUDED
    column_searchable_list = [Client.client_id, Client.phone_number, Client.email]
    column_list = [
        Client.full_name,
        Client.email,
        Client.phone_number,
        Client.credits,
        Client.service,
        Client.client_id,
    ]
    column_labels = {
        Client.full_name: "Nombre",
        Client.email: "Correo",
        Client.phone_number: "Teléfono Principal",
        Client.credits: "Segundos",
        Client.service: "Servicio Asociado",
        Client.client_id: "Client ID",
    }


class ClientAniAdmin(ModelView, model=ClientAni):
    name = "Client ANI"
    name_plural = "Client ANIs"
    form_excluded_columns = _TIMESTAMP_EXCLUDED
    column_searchable_list = [ClientAni.ani, ClientAni.client]
    column_list = [ClientAni.client_id, ClientAni.ani]


class DNCAdmin(ModelView, model=DoNotCall):
    column_list = [DoNotCall.ani, DoNotCall.reason, DoNotCall.created_at]
    column_searchable_list = [DoNotCall.ani]
    form_excluded_columns = _TIMESTAMP_EXCLUDED
    name = "DNC"
    name_plural = "DNC List"
    column_labels = {DoNotCall.created_at: "Date Added"}
    form_args = {
        "ani": {"description": "Phone number in E.164 format, e.g. 56912345678"},
        "reason": {"description": "Why this number is blocked"},
    }


class ServiceAdmin(ModelView, model=Service):
    column_list = [Service.id, Service.name, Service.slug, Service.created_at]
    column_searchable_list = [Service.name, Service.slug]
    form_excluded_columns = _TIMESTAMP_EXCLUDED
    name = "Service"
    name_plural = "Services"
    form_args = {
        "name": {"description": "Human-readable service name, e.g. FonoTarot Chile"},
        "slug": {
            "description": "Unique identifier used in dialplan and API, e.g. fonotarot-cl"
        },
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
    name_plural = "Service DIDs"
    form_args = {
        "did": {"description": "Full E.164 DID number, e.g. 56229402147"},
        "active": {"description": "Uncheck to stop routing calls to this DID"},
        "asterisk_context": {
            "description": "Asterisk dialplan context to route this DID to, e.g. prepago-fonotarot-cl"
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
    name = "Operator"
    name_plural = "Operators"
    form_args = {
        "number": {"description": "Internal SIP extension number, e.g. 1001"},
        "name": {"description": "Operator display name, used in IVR audio and logs"},
        "description": {"description": "Internal notes about this operator (optional)"},
        "option": {
            "description": "1-2 digit code the caller presses to select this operator, e.g. 01"
        },
        "enable_valkey": {
            "description": "Use Redis/Valkey for real-time availability state (recommended)"
        },
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
    name = "Operator Phone"
    name_plural = "Operator Phones"
    form_args = {
        "number": {"description": "Phone number to dial, e.g. 56912345678"},
        "enabled": {"description": "Uncheck to temporarily disable this phone number"},
        "contact": {
            "description": "Mark as the primary contact number for this operator"
        },
        "pin": {
            "description": "4-digit PIN used for operator login from phone (optional)"
        },
        "trunk": {
            "description": "Outbound SIP trunk to use for this number, e.g. claro1, didww-mia-out. Leave blank to use the default trunk"
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
    name = "Online Call"
    name_plural = "Online Calls"


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
    name = "Post-Call Process"
    name_plural = "Post-Call Processes"


class UserAdmin(ModelView, model=User):
    column_list = [User.id, User.login, User.email, User.enabled, User.scopes]
    column_searchable_list = [User.login, User.email]
    form_excluded_columns = _TIMESTAMP_EXCLUDED
    name = "API User"
    name_plural = "API Users"
    form_args = {
        "login": {"description": "Username for API authentication"},
        "email": {"description": "Contact email address"},
        "password": {
            "description": "Plain text — will be hashed automatically on save"
        },
        "allowed_ips": {
            "description": 'JSON list of allowed IPs, e.g. ["10.0.0.1"]. Leave empty to allow all'
        },
        "enabled": {
            "description": "Uncheck to disable API access without deleting the user"
        },
        "scopes": {
            "description": 'JSON list of scopes, e.g. ["core", "admin"]. Available: core, audiotex, asterisk, firenze, admin'
        },
    }

    async def on_model_change(self, data, model, is_created, request):
        if data.get("password"):
            data["password"] = bcrypt.hashpw(
                data["password"].encode("utf-8")[:72], bcrypt.gensalt()
            ).decode("utf-8")
        elif is_created:
            raise ValueError("Password is required when creating a user")


class EventAdmin(ModelView, model=Event):
    column_list = [Event.name, Event.verb, Event.ip, Event.url, Event.created_at]
    column_searchable_list = [Event.name, Event.url, Event.ip]
    column_sortable_list = [Event.created_at, Event.name]
    can_create = False
    can_edit = False
    can_delete = False
    name = "Event"
    name_plural = "Events"

class AdminIndex(BaseView):
    name = "Dashboard"
    icon = "fa fa-gauge"

    @expose("/index", methods=["GET"])
    async def admin(self, request):
        return RedirectResponse(url="/admin")

class FirenzeAdmin(Admin):
    @login_required
    async def index(self, request):
        data = await asyncio.to_thread(self._collect_data)
        return await self.templates.TemplateResponse(
            request,
            "system_status.html",
            context={
                "title": "System Status",
                "subtitle": "Redis / Valkey health, operator state, and active calls",
                **data,
            },
        )

    @staticmethod
    def _collect_data() -> dict:
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
                _log.warning("Could not scan operator keys: %s", exc)

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
                _log.warning("Could not scan call keys: %s", exc)

        # DB queries
        db = SessionLocal()
        try:
            operators = db.query(Operator).order_by(Operator.number).all()
            online_calls = (
                db.query(OnlineCalls).order_by(OnlineCalls.created_at.desc()).all()
            )
        finally:
            db.close()

        # Enrich operator list with Redis state
        enriched_operators = []
        for op in operators:
            rs = redis_operators.get(op.number)
            if op.enable_valkey and rs is not None:
                synced = (
                    rs["loggedin"] == op.loggedin and rs["available"] == op.available
                )
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
                    "redis_state": rs,
                    "synced": synced,
                }
            )

        # Enrich call list — cross-reference DB vs Redis
        redis_call_keys = {(c["service"], c["ani"]) for c in redis_calls}
        db_call_keys = {(c.service, c.ani) for c in online_calls}

        enriched_calls = []
        for call in online_calls:
            enriched_calls.append(
                {
                    "source": (
                        "db+redis"
                        if (call.service, call.ani) in redis_call_keys
                        else "db_only"
                    ),
                    "service": call.service,
                    "ani": call.ani,
                    "did": call.did,
                    "operator": call.operator,
                    "client_id": call.client_id,
                    "created_at": call.created_at,
                }
            )
        for rc in redis_calls:
            if (rc["service"], rc["ani"]) not in db_call_keys:
                ts = rc.get("created_at")
                enriched_calls.append(
                    {
                        "source": "redis_only",
                        "service": rc["service"],
                        "ani": rc["ani"],
                        "did": rc["did"],
                        "operator": rc["operator"],
                        "client_id": rc["client_id"],
                        "created_at": (
                            datetime.datetime.fromtimestamp(ts) if ts else None
                        ),
                    }
                )

        return {
            "redis_online": redis_online,
            "redis_info": redis_info,
            "operators": enriched_operators,
            "active_calls": enriched_calls,
            "redis_operators_count": len(redis_operators),
            "redis_calls_count": len(redis_calls),
        }




def register_admin(admin):
    admin.add_view(AdminIndex)
    admin.add_view(UserAdmin)
    admin.add_view(DNCAdmin)
    admin.add_view(ClientAdmin)
    admin.add_view(ClientAniAdmin)
    admin.add_view(ServiceAdmin)
    admin.add_view(ServiceNumberAdmin)
    admin.add_view(OperatorAdmin)
    admin.add_view(OperatorPhoneAdmin)
    admin.add_view(OnlineCallsAdmin)
    # admin.add_view(PostCallProcessAdmin)
    # admin.add_view(EventAdmin)
    
