from passlib.context import CryptContext
from sqladmin import ModelView

from firenze.models import (
    DoNotCall,
    Event,
    FonoTarotLatamClient,
    OnlineCalls,
    Operator,
    OperatorPhone,
    PostCallProcess,
    Service,
    ServiceNumber,
    User,
)

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

_TIMESTAMP_EXCLUDED = ["created_at", "modified_at"]


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
        "slug": {"description": "Unique identifier used in dialplan and API, e.g. fonotarot-cl"},
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
        "asterisk_context": {"description": "Asterisk dialplan context to route this DID to, e.g. prepago-fonotarot-cl"},
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
    form_excluded_columns = _TIMESTAMP_EXCLUDED
    name = "Operator"
    name_plural = "Operators"
    form_args = {
        "number": {"description": "Internal SIP extension number, e.g. 1001"},
        "name": {"description": "Operator display name, used in IVR audio and logs"},
        "description": {"description": "Internal notes about this operator (optional)"},
        "option": {"description": "1-2 digit code the caller presses to select this operator, e.g. 01"},
        "enable_valkey": {"description": "Use Redis/Valkey for real-time availability state (recommended)"},
        "loggedin": {"description": "Whether the operator is currently logged in"},
        "available": {"description": "Whether the operator is available to receive calls"},
        "lastcall": {"description": "Timestamp of last call received"},
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
        "contact": {"description": "Mark as the primary contact number for this operator"},
        "pin": {"description": "4-digit PIN used for operator login from phone (optional)"},
        "trunk": {"description": "Outbound SIP trunk to use for this number, e.g. claro1, didww-mia-out. Leave blank to use the default trunk"},
    }


class FonoTarotLatamClientAdmin(ModelView, model=FonoTarotLatamClient):
    column_list = [
        FonoTarotLatamClient.client_id,
        FonoTarotLatamClient.full_name,
        FonoTarotLatamClient.email,
        FonoTarotLatamClient.pin_code,
        FonoTarotLatamClient.credits,
    ]
    column_searchable_list = [
        FonoTarotLatamClient.email,
        FonoTarotLatamClient.pin_code,
        FonoTarotLatamClient.full_name,
    ]
    column_sortable_list = [FonoTarotLatamClient.credits, FonoTarotLatamClient.client_id]
    form_excluded_columns = _TIMESTAMP_EXCLUDED + ["pin_code"]
    name = "FonoTarot Latam Client"
    name_plural = "FonoTarot Latam Clients"
    form_args = {
        "full_name": {"description": "Client display name (auto-filled from email if blank)"},
        "email": {"description": "Client email address — used as login identifier"},
        "phone_number": {"description": "Client phone number in E.164 format (optional)"},
        "credits": {"description": "Balance in seconds, e.g. 1800 = 30 minutes"},
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
        "password": {"description": "Plain text — will be hashed automatically on save"},
        "allowed_ips": {"description": "JSON list of allowed IPs, e.g. [\"10.0.0.1\"]. Leave empty to allow all"},
        "enabled": {"description": "Uncheck to disable API access without deleting the user"},
        "scopes": {"description": 'JSON list of scopes, e.g. ["core", "admin"]. Available: core, audiotex, asterisk, firenze, admin'},
    }

    async def on_model_change(self, data, model, is_created, request):
        if data.get("password"):
            data["password"] = _pwd_context.hash(data["password"])
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


def register_admin(admin):
    admin.add_view(DNCAdmin)
    admin.add_view(ServiceAdmin)
    admin.add_view(ServiceNumberAdmin)
    admin.add_view(OperatorAdmin)
    admin.add_view(OperatorPhoneAdmin)
    admin.add_view(FonoTarotLatamClientAdmin)
    admin.add_view(OnlineCallsAdmin)
    admin.add_view(PostCallProcessAdmin)
    admin.add_view(UserAdmin)
    admin.add_view(EventAdmin)
