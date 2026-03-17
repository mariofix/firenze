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


class DNCAdmin(ModelView, model=DoNotCall):
    column_list = [DoNotCall.ani, DoNotCall.reason, DoNotCall.created_at]
    column_searchable_list = [DoNotCall.ani]
    name = "DNC"
    name_plural = "DNC List"
    column_labels = {DoNotCall.created_at: "Date Created"}
    form_widget_args = {
        "created_at": {"readonly": True},
        "modified_at": {"readonly": True},
    }


class ServiceAdmin(ModelView, model=Service):
    column_list = [Service.id, Service.name, Service.slug, Service.created_at]
    column_searchable_list = [Service.name, Service.slug]
    name = "Service"
    name_plural = "Services"
    form_widget_args = {
        "created_at": {"readonly": True},
        "modified_at": {"readonly": True},
    }


class ServiceNumberAdmin(ModelView, model=ServiceNumber):
    column_list = [
        ServiceNumber.did,
        ServiceNumber.active,
        ServiceNumber.asterisk_context,
        ServiceNumber.service,
    ]
    column_searchable_list = [ServiceNumber.did, ServiceNumber.asterisk_context]
    name = "DID"
    name_plural = "Service DIDs"
    form_widget_args = {
        "created_at": {"readonly": True},
        "modified_at": {"readonly": True},
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
    name = "Operator"
    name_plural = "Operators"
    form_widget_args = {
        "created_at": {"readonly": True},
        "modified_at": {"readonly": True},
    }


class OperatorPhoneAdmin(ModelView, model=OperatorPhone):
    column_list = [
        OperatorPhone.number,
        OperatorPhone.enabled,
        OperatorPhone.contact,
        OperatorPhone.operator,
    ]
    column_searchable_list = [OperatorPhone.number]
    name = "Operator Phone"
    name_plural = "Operator Phones"
    form_widget_args = {
        "created_at": {"readonly": True},
        "modified_at": {"readonly": True},
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
    name = "FonoTarot Latam Client"
    name_plural = "FonoTarot Latam Clients"
    form_widget_args = {
        "pin_code": {"readonly": True},
        "created_at": {"readonly": True},
        "modified_at": {"readonly": True},
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
    name = "Post-Call Process"
    name_plural = "Post-Call Processes"


class UserAdmin(ModelView, model=User):
    column_list = [User.id, User.login, User.email, User.enabled, User.scopes]
    column_searchable_list = [User.login, User.email]
    name = "API User"
    name_plural = "API Users"
    form_excluded_columns = [User.password]
    form_widget_args = {
        "created_at": {"readonly": True},
        "modified_at": {"readonly": True},
    }


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
