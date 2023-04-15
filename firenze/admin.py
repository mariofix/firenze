from firenze.models import (
    User,
    Event,
    Service,
    ServiceNumber,
    DoNotCall,
    OnlineCalls,
    PostCallProcess,
)
from sqladmin import ModelView


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
    column_list = ["service", "process_name", "client_id", "processed"]
    column_default_sort = [("id", True)]

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
