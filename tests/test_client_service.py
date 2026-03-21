"""Tests for firenze.services.client_service — client lookup and credit deduction."""

from unittest.mock import MagicMock

import pytest

from firenze.services.client_service import (
    ClientNotFound,
    InsufficientCredits,
    ServiceNotFound,
    deduct_credits,
    lookup,
)


def _make_service(id=1, slug="fonotarot-latam"):
    svc = MagicMock()
    svc.id = id
    svc.slug = slug
    return svc


def _make_client(client_id=100, pin="12345678", ani=None, credits=600):
    client = MagicMock()
    client.client_id = client_id
    client.pin = pin
    client.ani = ani
    client.credits = credits
    return client


def _mock_session_for_lookup(service=None, client=None):
    """Mock session for lookup — uses .filter().first() chain."""
    session = MagicMock()
    # _get_service uses filter_by
    svc_chain = MagicMock()
    svc_chain.first.return_value = service
    # lookup uses .filter() (with or_)
    client_chain = MagicMock()
    client_chain.first.return_value = client

    query_mock = session.query.return_value
    query_mock.filter_by.return_value = svc_chain
    query_mock.filter.return_value = client_chain
    return session


def _mock_session_for_deduct(service=None, client=None):
    """Mock session for deduct — uses two filter_by().first() calls."""
    session = MagicMock()
    chain = session.query.return_value.filter_by.return_value
    chain.first.side_effect = [service, client] if service else [None]
    return session


class TestLookup:
    def test_returns_clientid_and_credits_by_pin(self):
        svc = _make_service()
        client = _make_client(client_id=42, pin="12345678", credits=1800)
        session = _mock_session_for_lookup(svc, client)

        result = lookup(session, "fonotarot-latam", "12345678")

        assert result == {"clientid": 42, "segundos": 1800}

    def test_returns_clientid_and_credits_by_ani(self):
        svc = _make_service()
        client = _make_client(client_id=42, ani="56912345678", credits=900)
        session = _mock_session_for_lookup(svc, client)

        result = lookup(session, "fonotarot-latam", "56912345678")

        assert result == {"clientid": 42, "segundos": 900}

    def test_returns_zeros_when_client_not_found(self):
        svc = _make_service()
        session = _mock_session_for_lookup(svc, None)

        result = lookup(session, "fonotarot-latam", "99999999")

        assert result == {"clientid": 0, "segundos": 0}

    def test_raises_service_not_found(self):
        session = _mock_session_for_lookup(None)

        with pytest.raises(ServiceNotFound):
            lookup(session, "nonexistent", "12345678")


class TestDeductCredits:
    def test_deducts_and_returns_remaining(self):
        svc = _make_service()
        client = _make_client(credits=1000)
        session = _mock_session_for_deduct(svc, client)

        result = deduct_credits(session, "fonotarot-latam", 100, 300)

        assert client.credits == 700
        session.commit.assert_called_once()
        assert result == {"ok": True, "remaining": 700}

    def test_deduct_exact_balance(self):
        svc = _make_service()
        client = _make_client(credits=500)
        session = _mock_session_for_deduct(svc, client)

        result = deduct_credits(session, "fonotarot-latam", 100, 500)

        assert client.credits == 0
        assert result == {"ok": True, "remaining": 0}

    def test_raises_insufficient_credits(self):
        svc = _make_service()
        client = _make_client(credits=100)
        session = _mock_session_for_deduct(svc, client)

        with pytest.raises(InsufficientCredits):
            deduct_credits(session, "fonotarot-latam", 100, 500)

    def test_raises_client_not_found(self):
        svc = _make_service()
        session = _mock_session_for_deduct(svc, None)

        with pytest.raises(ClientNotFound):
            deduct_credits(session, "fonotarot-latam", 999, 100)

    def test_raises_service_not_found(self):
        session = _mock_session_for_deduct(None)

        with pytest.raises(ServiceNotFound):
            deduct_credits(session, "nonexistent", 100, 300)
