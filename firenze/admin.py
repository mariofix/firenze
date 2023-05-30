from sqladmin import ModelView, action
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from firenze.models import (
    DoNotCall,
    Event,
    FonoTarotLatamClient,
    OnlineCalls,
    PostCallProcess,
    Service,
    ServiceNumber,
    User,
)


class UserAdmin(ModelView, model=User):
    column_list = ["login", "enabled", "scopes"]
    column_default_sort = [("login", False)]
    column_searchable_list = ["email", "scopes"]

    form_widget_args = {
        "created_at": {
            "readonly": True,
        },
        "modified_at": {
            "readonly": True,
        },
    }


class EventAdmin(ModelView, model=Event):
    column_list = ["name", "verb", "created_at"]
    column_default_sort = [("id", True)]
    column_searchable_list = ["name", "ip", "verb", "data"]

    form_widget_args = {
        "created_at": {
            "readonly": True,
        },
        "modified_at": {
            "readonly": True,
        },
    }


class ServiceAdmin(ModelView, model=Service):
    column_list = [Service.name, Service.slug, Service.numbers]
    form_widget_args = {
        "created_at": {
            "readonly": True,
        },
        "modified_at": {
            "readonly": True,
        },
    }


class DIDAdmin(ModelView, model=ServiceNumber):
    column_list = [
        ServiceNumber.did,
        ServiceNumber.service,
        ServiceNumber.active,
        ServiceNumber.asterisk_context,
    ]
    name = "Service Number"
    name_plural = "Service Numbers"
    form_widget_args = {
        "created_at": {
            "readonly": True,
        },
        "modified_at": {
            "readonly": True,
        },
    }


class DNCAdmin(ModelView, model=DoNotCall):
    column_list = [DoNotCall.ani, DoNotCall.created_at]
    name = "DNC List"
    name_plural = "DNC List"
    column_labels = {DoNotCall.created_at: "Date Created"}
    form_widget_args = {
        "created_at": {
            "readonly": True,
        },
        "modified_at": {
            "readonly": True,
        },
    }


class CallsAdmin(ModelView, model=OnlineCalls):
    name = "Online Calls"
    name_plural = "Online Calls"
    can_create = False
    can_edit = False
    can_export = False
    can_delete = False
    can_view_details = False
    column_labels = {
        OnlineCalls.created_at: "Fecha Llamada",
        OnlineCalls.service: "Servicio",
        OnlineCalls.did: "DID",
        OnlineCalls.ani: "ANI",
        OnlineCalls.operator: "Tarotista",
    }
    column_list = [
        OnlineCalls.created_at,
        OnlineCalls.service,
        OnlineCalls.did,
        OnlineCalls.ani,
        OnlineCalls.client_id,
        OnlineCalls.operator,
    ]


class PostCallAdmin(ModelView, model=PostCallProcess):
    # https://wa.me/1XXXXXXXXXX
    # sms:+19725551212?body=hello%20there
    column_list = ["service", "process_name", "client_id", "processed"]
    column_default_sort = [("id", True)]

    @action(
        name="SMS",
        label="SMS",
        add_in_detail=True,
        add_in_list=False,
    )
    async def sms(self, request: Request) -> Response:
        call_id = request.query_params.get("pks")
        from urllib.parse import urlencode

        from .database import SessionLocal

        db = SessionLocal()
        call_info = (
            db.query(PostCallProcess).filter(PostCallProcess.id == call_id).first()
        )
        print(
            f"sms:+56{call_info.parameters['destination']}?body={call_info.parameters['text']}"
        )
        return RedirectResponse(
            f"sms:+56{call_info.parameters['destination']}?body={call_info.parameters['text']}"
        )

    @action(
        name="Whastapp",
        label="Whastapp",
        add_in_detail=True,
        add_in_list=False,
    )
    async def whatsapp(self, request: Request) -> Response:
        call_id = request.query_params.get("pks")
        from urllib.parse import urlencode

        from .database import SessionLocal

        db = SessionLocal()
        call_info = (
            db.query(PostCallProcess).filter(PostCallProcess.id == call_id).first()
        )
        print(
            f"https://wa.me/56{call_info.parameters['destination']}?text={call_info.parameters['text']}"
        )
        return RedirectResponse(
            f"https://wa.me/56{call_info.parameters['destination']}?text={call_info.parameters['text']}"
        )

    form_widget_args = {
        "created_at": {
            "readonly": True,
        },
        "modified_at": {
            "readonly": True,
        },
    }


class FonoTarotLatamAdmin(ModelView, model=FonoTarotLatamClient):
    column_list = ["client_id", "email", "pin_code", "credits"]
    name = "Fonotarot Latam"
    name_plural = "Fonotarot Latam"
    can_export = False
    can_view_details = True
    form_widget_args = {
        "created_at": {
            "readonly": True,
        },
        "modified_at": {
            "readonly": True,
        },
    }


def register_admin(the_app):
    the_app.sqladmin.add_view(UserAdmin)
    the_app.sqladmin.add_view(EventAdmin)
    the_app.sqladmin.add_view(ServiceAdmin)
    the_app.sqladmin.add_view(DIDAdmin)
    the_app.sqladmin.add_view(DNCAdmin)
    the_app.sqladmin.add_view(CallsAdmin)
    the_app.sqladmin.add_view(PostCallAdmin)
    the_app.sqladmin.add_view(FonoTarotLatamAdmin)
