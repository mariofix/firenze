"""Tests for firenze.services.client_service - client lookup and credit deduction."""

from unittest.mock import MagicMock, patch

import pytest

from firenze.services.client_service import (
    ClientNotFound,
    ServiceNotFound,
    create_client,
    deduct_credits,
    lookup,
    update_client_record,
)


def _make_service(id=1, slug="fonotarot-latam"):
    svc = MagicMock()
    svc.id = id
    svc.slug = slug
    return svc


def _make_client(client_id=100, pin="12345678", credits=600):
    client = MagicMock()
    client.client_id = client_id
    client.pin = pin
    client.credits = credits
    return client


def _make_ani_row(client_id=100, service_id=1, ani="56912345678"):
    row = MagicMock()
    row.client_id = client_id
    row.service_id = service_id
    row.ani = ani
    return row


def _mock_session_for_lookup(service=None, client=None, ani_row=None):
    """Mock session for lookup — all paths use filter_by().first()."""
    session = MagicMock()

    # Each call to session.query(X).filter_by(...).first() is a separate chain.
    # We use side_effect on filter_by to return results in call order:
    #   1st call: _get_service → service
    #   2nd call: Client by pin → client (or None when not found)
    #   3rd call: ClientAni by ani → ani_row (ANI path only)
    #   4th call: Client by client_id → client (ANI path only)
    if ani_row:
        # service → ani_row hit → client
        side_effects = [service, ani_row, client]
    elif client is None:
        # service → pin miss → ani miss (not found)
        side_effects = [service, None, None]
    else:
        # service → pin hit
        side_effects = [service, client]

    fb_chain = MagicMock()
    fb_chain.first.side_effect = side_effects
    session.query.return_value.filter_by.return_value = fb_chain
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
        svc = _make_service(id=2, slug="fonotarot-cl")
        client = _make_client(client_id=42, pin=None, credits=900)
        ani_row = _make_ani_row(client_id=42, service_id=2, ani="56912345678")
        session = _mock_session_for_lookup(svc, client, ani_row)

        result = lookup(session, "fonotarot-cl", "56912345678")

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
        assert result == {"ok": True, "remaining": 700, "before": 1000}

    def test_triggers_post_call_email_after_commit(self):
        svc = _make_service()
        client = _make_client(credits=1000)
        session = _mock_session_for_deduct(svc, client)

        with patch("firenze.services.client_service.maybe_send_post_call_email") as mock_email:
            result = deduct_credits(session, "fonotarot-latam", 100, 300)

        mock_email.assert_called_once_with(client, svc)
        assert result == {"ok": True, "remaining": 700, "before": 1000}

    def test_deduct_exact_balance(self):
        svc = _make_service()
        client = _make_client(credits=500)
        session = _mock_session_for_deduct(svc, client)

        result = deduct_credits(session, "fonotarot-latam", 100, 500)

        assert client.credits == 0
        assert result == {"ok": True, "remaining": 0, "before": 500}

    def test_overdraft_clamps_to_zero(self):
        svc = _make_service()
        client = _make_client(credits=100)
        session = _mock_session_for_deduct(svc, client)

        result = deduct_credits(session, "fonotarot-latam", 100, 500)

        assert client.credits == 0
        session.commit.assert_called_once()
        assert result == {"ok": True, "remaining": 0, "before": 100}

    def test_zero_balance_notifies_and_returns_ok(self):
        svc = _make_service()
        client = _make_client(credits=0)
        session = _mock_session_for_deduct(svc, client)

        with patch("firenze.services.client_service.notify") as mock_notify:
            result = deduct_credits(session, "fonotarot-latam", 100, 300)

        mock_notify.assert_called_once()
        session.commit.assert_called_once()
        assert result == {"ok": True, "remaining": 0, "before": 0, "warning": True}

    def test_raises_client_not_found(self):
        svc = _make_service()
        session = _mock_session_for_deduct(svc, None)

        with pytest.raises(ClientNotFound):
            deduct_credits(session, "fonotarot-latam", 999, 100)

    def test_raises_service_not_found(self):
        session = _mock_session_for_deduct(None)

        with pytest.raises(ServiceNotFound):
            deduct_credits(session, "nonexistent", 100, 300)


class TestClientPinCollisionHandling:
    def test_create_client_replaces_taken_pin(self):
        svc = _make_service()
        collision = _make_client(client_id=77, pin="22222222")
        session = MagicMock()
        session.query.return_value.filter_by.return_value.first.side_effect = [svc, None]
        session.query.return_value.filter.return_value.first.side_effect = [
            collision,
            None,
        ]
        session.query.return_value.filter_by.return_value.order_by.return_value.all.return_value = []
        added: list = []
        session.add.side_effect = lambda obj: added.append(obj)
        session.refresh.side_effect = lambda obj: None

        with patch("firenze.services.client_service._generate_pin", return_value="33333333"):
            result = create_client(
                session,
                "fonotarot-latam",
                client_id=42,
                pin="22222222",
            )

        assert len(added) == 1
        assert added[0].pin == "33333333"
        assert result["pin"] == "33333333"

    def test_update_client_record_replaces_taken_pin(self):
        svc = _make_service()
        client = _make_client(client_id=42, pin="11111111")
        collision = _make_client(client_id=77, pin="22222222")
        session = MagicMock()
        session.query.return_value.filter_by.return_value.first.side_effect = [
            svc,
            client,
        ]
        filter_chain = session.query.return_value.filter.return_value
        filter_chain.filter.return_value.first.side_effect = [collision, None]
        session.query.return_value.filter_by.return_value.order_by.return_value.all.return_value = []

        with patch("firenze.services.client_service._generate_pin", return_value="33333333"):
            result = update_client_record(
                session,
                "fonotarot-latam",
                client_id=42,
                pin="22222222",
            )

        assert client.pin == "33333333"
        assert result["pin"] == "33333333"

    def test_update_client_record_raises_when_pin_space_is_exhausted(self):
        svc = _make_service()
        client = _make_client(client_id=42, pin="11111111")
        collision = _make_client(client_id=77, pin="22222222")
        session = MagicMock()
        session.query.return_value.filter_by.return_value.first.side_effect = [
            svc,
            client,
        ]
        filter_chain = session.query.return_value.filter.return_value
        filter_chain.filter.return_value.first.return_value = collision
        session.query.return_value.filter_by.return_value.order_by.return_value.all.return_value = []

        with patch("firenze.services.client_service._generate_pin", return_value="22222222"):
            with pytest.raises(RuntimeError, match="Unable to allocate a unique PIN"):
                update_client_record(
                    session,
                    "fonotarot-latam",
                    client_id=42,
                    pin="22222222",
                )

    def test_create_client_uses_deterministic_fallback_after_repeated_collisions(self):
        svc = _make_service()
        collision = _make_client(client_id=77, pin="22222222")
        session = MagicMock()
        session.query.return_value.filter_by.return_value.first.side_effect = [svc, None]
        session.query.return_value.filter.return_value.first.side_effect = [
            collision,
            collision,
            collision,
            collision,
            collision,
            collision,
            collision,
            collision,
            collision,
            None,
        ]
        session.query.return_value.filter_by.return_value.order_by.return_value.all.return_value = []
        added: list = []
        session.add.side_effect = lambda obj: added.append(obj)
        session.refresh.side_effect = lambda obj: None

        with patch("firenze.services.client_service._generate_pin", return_value="22222222"):
            result = create_client(
                session,
                "fonotarot-latam",
                client_id=42,
                pin="22222222",
            )

        assert len(added) == 1
        assert added[0].pin == "22222223"
        assert result["pin"] == "22222223"


def test_update_client_record_clears_extra_config_when_explicitly_provided():
    svc = _make_service()
    client = _make_client(client_id=42, pin="11111111")
    client.extra_config = {"tarotista_favorita": 7001}
    session = MagicMock()
    session.query.return_value.filter_by.return_value.first.side_effect = [
        svc,
        client,
    ]
    session.query.return_value.filter_by.return_value.order_by.return_value.all.return_value = []

    result = update_client_record(
        session,
        "fonotarot-latam",
        client_id=42,
        extra_config=None,
        extra_config_provided=True,
    )

    assert client.extra_config is None
    assert result["extra_config"] is None
