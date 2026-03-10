from sqladmin import ModelView

from firenze.models import DoNotCall


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


def register_admin(admin):
    admin.add_view(DNCAdmin)
