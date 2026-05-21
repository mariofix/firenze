from unittest.mock import MagicMock

from firenze.admin import AsteriskCDRAdmin, register_admin
from firenze.models.cdr import AsteriskCDR


def test_cdr_model_maps_to_asterisk_schema():
    assert AsteriskCDR.__tablename__ == "cdr"
    assert AsteriskCDR.__table__.schema == "zvn_asterisk"
    assert "zvn_client_ani" in AsteriskCDR.__table__.columns
    assert "calldate" in AsteriskCDR.__table__.columns


def test_register_admin_adds_cdr_view():
    admin = MagicMock()

    register_admin(admin)

    assert any(call.args[0] is AsteriskCDRAdmin for call in admin.add_view.call_args_list)
