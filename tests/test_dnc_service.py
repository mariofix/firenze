"""Tests for firenze.services.dnc_service — Do Not Call lookups."""

from unittest.mock import MagicMock

from firenze.services.dnc_service import check_dnc


class TestCheckDnc:
    def test_returns_true_when_found(self):
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = MagicMock()  # a row

        assert check_dnc(db, "56912345678") is True

    def test_returns_false_when_not_found(self):
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = None

        assert check_dnc(db, "56900000000") is False
