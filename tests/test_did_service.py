"""Tests for firenze.services.did_service - DID resolution."""

from unittest.mock import MagicMock

from firenze.services.did_service import resolve_did


class TestResolveDid:
    def test_returns_full_config_when_found(self):
        db = MagicMock()
        row = MagicMock()
        row.asterisk_context = "prepago-service"
        row.service.slug = "fonotarot-cl"
        row.service.auth_method = "ani"
        row.service.intro_audio = "zvn/intro-fonotarot-cl"
        db.query.return_value.filter_by.return_value.first.return_value = row

        assert resolve_did(db, "56229402147") == {
            "siguiente": "prepago-service",
            "servicio": "fonotarot-cl",
            "auth_method": "ani",
            "intro_audio": "zvn/intro-fonotarot-cl",
        }

    def test_returns_empty_fields_when_not_found(self):
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = None

        assert resolve_did(db, "0000000000") == {
            "siguiente": "",
            "servicio": "",
            "auth_method": "",
            "intro_audio": "",
        }

    def test_returns_empty_fields_when_service_link_missing(self):
        db = MagicMock()
        row = MagicMock()
        row.service = None
        db.query.return_value.filter_by.return_value.first.return_value = row

        assert resolve_did(db, "56229402147") == {
            "siguiente": "",
            "servicio": "",
            "auth_method": "",
            "intro_audio": "",
        }
