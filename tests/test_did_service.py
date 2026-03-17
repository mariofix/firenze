"""Tests for firenze.services.did_service — DID resolution."""

from unittest.mock import MagicMock

from firenze.services.did_service import resolve_did


class TestResolveDid:
    def test_returns_context_when_found(self):
        db = MagicMock()
        row = MagicMock()
        row.asterisk_context = "prepago-fonotarot-cl"
        db.query.return_value.filter_by.return_value.first.return_value = row

        assert resolve_did(db, "56229402147") == "prepago-fonotarot-cl"

    def test_returns_empty_string_when_not_found(self):
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = None

        assert resolve_did(db, "0000000000") == ""
