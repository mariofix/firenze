"""Tests for firenze.services.payment_service - search and apply_purchase."""

from unittest.mock import MagicMock, patch

import pytest

from firenze.services.client_service import ClientNotFound, ServiceNotFound
from firenze.services.payment_service import (
    PHONE_ERASE_SENTINEL,
    apply_purchase,
    search_client,
    update_client,
)


def _make_service(id=1, slug="fonotarot-cl"):
    svc = MagicMock()
    svc.id = id
    svc.slug = slug
    return svc


def _make_client(client_id=42, pin=None, email=None, phone_number=None, full_name=None, credits=0):
    client = MagicMock()
    client.client_id = client_id
    client.pin = pin
    client.email = email
    client.phone_number = phone_number
    client.full_name = full_name
    client.credits = credits
    return client


def _session_with_filter_results(results: list):
    """Mock session whose filter_by(...).first() returns ``results`` in order."""
    session = MagicMock()
    chain = session.query.return_value.filter_by.return_value
    chain.first.side_effect = list(results)
    return session


class TestSearchClient:
    def test_returns_client_by_email(self):
        svc = _make_service()
        client = _make_client(client_id=42, email="buyer@example.com")
        # service hit, pin path skipped (no pin arg), email hit
        session = _session_with_filter_results([svc, client])

        result = search_client(session, "fonotarot-cl", email="buyer@example.com")

        assert result is client

    def test_ignores_phone_lookup_when_email_misses(self):
        svc = _make_service()
        # service, email miss. The phone argument is ignored, so no extra query.
        session = _session_with_filter_results([svc, None])

        result = search_client(
            session,
            "fonotarot-cl",
            email="other@example.com",
            phone="56912345678",
        )

        assert result is None

    def test_returns_client_by_ani_via_clientani(self):
        svc = _make_service()
        ani_row = MagicMock(client_id=42)
        client = _make_client(client_id=42)
        # service, ani_row hit, client hit
        session = _session_with_filter_results([svc, ani_row, client])

        result = search_client(session, "fonotarot-cl", ani="56987654321")

        assert result is client

    def test_returns_none_when_nothing_matches(self):
        svc = _make_service()
        # service, email miss, phone miss, ani miss
        session = _session_with_filter_results([svc, None, None, None])

        result = search_client(
            session,
            "fonotarot-cl",
            email="ghost@example.com",
            phone="0",
            ani="0",
        )

        assert result is None

    def test_pin_takes_priority_over_email(self):
        svc = _make_service()
        client = _make_client(client_id=42, pin="12345678")
        # service, pin hit (email never queried)
        session = _session_with_filter_results([svc, client])

        result = search_client(
            session,
            "fonotarot-cl",
            pin="12345678",
            email="buyer@example.com",
        )

        assert result is client

    def test_raises_service_not_found(self):
        session = _session_with_filter_results([None])

        with pytest.raises(ServiceNotFound):
            search_client(session, "nope", email="x@x.com")


class TestApplyPurchase:
    def test_tops_up_existing_client(self):
        svc = _make_service()
        client = _make_client(client_id=42, credits=600)
        # service, client lookup. ANI is None so no ClientAni query.
        session = _session_with_filter_results([svc, client])

        result = apply_purchase(
            session,
            service_slug="fonotarot-cl",
            credits=1800,
            client_id=42,
            transaction_id="khipu-001",
        )

        assert client.credits == 2400
        session.commit.assert_called_once()
        assert result == {
            "ok": True,
            "client_id": 42,
            "service": "fonotarot-cl",
            "created": False,
            "credits_before": 600,
            "credits_added": 1800,
            "credits_after": 2400,
        }

    def test_creates_new_client_when_no_client_id(self):
        svc = _make_service()
        # service hit, max(client_id) scalar -> 99, ANI is None
        session = MagicMock()
        chain = session.query.return_value.filter_by.return_value
        chain.first.return_value = svc
        session.query.return_value.filter_by.return_value.scalar.return_value = 99

        # db.add() captures the new Client; db.refresh() should leave .credits intact
        added: list = []
        session.add.side_effect = lambda obj: added.append(obj)

        def _refresh(obj):
            return None

        session.refresh.side_effect = _refresh

        result = apply_purchase(
            session,
            service_slug="fonotarot-cl",
            credits=1800,
            email="new@example.com",
            full_name="New Buyer",
            phone_number="56912345678",
        )

        assert len(added) == 1
        new_client = added[0]
        assert new_client.client_id == 100
        assert new_client.email == "new@example.com"
        assert new_client.credits == 1800
        session.commit.assert_called_once()
        assert result["created"] is True
        assert result["client_id"] == 100
        assert result["credits_before"] == 0
        assert result["credits_after"] == 1800

    def test_registers_ani_when_provided_and_unused(self):
        svc = _make_service()
        client = _make_client(client_id=42, credits=0)
        # service, client lookup, ani lookup -> None (free)
        session = _session_with_filter_results([svc, client, None])
        added: list = []
        session.add.side_effect = lambda obj: added.append(obj)

        apply_purchase(
            session,
            service_slug="fonotarot-cl",
            credits=600,
            client_id=42,
            ani="56999999999",
        )

        # Exactly one ClientAni added
        assert len(added) == 1
        assert added[0].ani == "56999999999"
        assert added[0].client_id == 42

    def test_skips_ani_when_already_taken_by_other_client(self):
        svc = _make_service()
        client = _make_client(client_id=42, credits=0)
        existing_ani = MagicMock(client_id=99, ani="56999999999")
        # service, client, existing ANI owned by 99
        session = _session_with_filter_results([svc, client, existing_ani])
        added: list = []
        session.add.side_effect = lambda obj: added.append(obj)

        apply_purchase(
            session,
            service_slug="fonotarot-cl",
            credits=600,
            client_id=42,
            ani="56999999999",
        )

        # No ClientAni added (collision with another client)
        assert added == []

    def test_raises_client_not_found_when_topping_up_missing_client(self):
        svc = _make_service()
        session = _session_with_filter_results([svc, None])

        with pytest.raises(ClientNotFound):
            apply_purchase(
                session,
                service_slug="fonotarot-cl",
                credits=600,
                client_id=999,
            )

    def test_raises_service_not_found(self):
        session = _session_with_filter_results([None])

        with pytest.raises(ServiceNotFound):
            apply_purchase(
                session,
                service_slug="nope",
                credits=600,
                client_id=1,
            )


def _make_phone_row(client_id: int, ani: str, service_id: int = 1):
    row = MagicMock()
    row.client_id = client_id
    row.ani = ani
    row.service_id = service_id
    return row


def _build_update_session(query_specs: list):
    """Build a mock session where each session.query() call returns a chain
    configured by ``query_specs``.

    Each spec is a dict accepting:
      - ``first``   - return value of ``filter_by(...).first()`` AND ``filter(...).first()``
      - ``all``     - return value of ``filter_by(...).all()``
      - ``delete``  - return value of ``filter_by(...).delete(...)``
    """
    session = MagicMock()
    chains = []
    for spec in query_specs:
        chain = MagicMock()
        if "first" in spec:
            chain.filter_by.return_value.first.return_value = spec["first"]
            chain.filter.return_value.first.return_value = spec["first"]
        if "all" in spec:
            chain.filter_by.return_value.all.return_value = spec["all"]
        if "delete" in spec:
            chain.filter_by.return_value.delete.return_value = spec["delete"]
        chains.append(chain)
    session.query.side_effect = chains
    return session


class TestUpdateClient:
    def test_updates_name_email_and_pin(self):
        svc = _make_service()
        client = _make_client(client_id=42, pin="11111111", email="old@x.com", full_name="Old")
        # query order:
        #   1. _get_service -> svc
        #   2. fetch client -> client
        #   3. PIN collision check -> None (free)
        #   4. final phones list -> []
        session = _build_update_session([
            {"first": svc},
            {"first": client},
            {"first": None},
            {"all": []},
        ])

        result = update_client(
            session,
            service_slug="fonotarot-cl",
            client_id=42,
            full_name="New Name",
            email="new@example.com",
            pin="22222222",
        )

        assert client.full_name == "New Name"
        assert client.email == "new@example.com"
        assert client.pin == "22222222"
        session.commit.assert_called_once()
        assert result["ok"] is True
        assert result["full_name"] == "New Name"
        assert result["email"] == "new@example.com"
        assert result["pin"] == "22222222"
        assert result["phones_added"] == 0
        assert result["phones_removed"] == 0
        assert result["phone_skipped_reason"] is None

    def test_pin_collision_gets_replaced(self):
        svc = _make_service()
        client = _make_client(client_id=42, pin="11111111")
        # service, client, replacement pin lookup (collision then free)
        session = _build_update_session([
            {"first": svc},
            {"first": client},
            {"all": []},
        ])

        with patch("firenze.services.payment_service._pick_unique_pin", return_value="33333333") as mock_pick:
            result = update_client(
                session,
                service_slug="fonotarot-cl",
                client_id=42,
                pin="22222222",
            )

        mock_pick.assert_called_once_with(session, svc.id, "22222222", exclude_client_id=42)
        assert client.pin == "33333333"
        assert result["pin"] == "33333333"

    def test_pin_unchanged_skips_collision_check(self):
        svc = _make_service()
        client = _make_client(client_id=42, pin="11111111")
        # service, client, final phones list. No collision query because pin matches existing.
        session = _build_update_session([
            {"first": svc},
            {"first": client},
            {"all": []},
        ])

        result = update_client(
            session,
            service_slug="fonotarot-cl",
            client_id=42,
            pin="11111111",
        )

        assert result["pin"] == "11111111"

    def test_adds_phone_when_unused(self):
        svc = _make_service()
        client = _make_client(client_id=42)
        # service, client, ani lookup for-this-client -> None,
        # ani lookup any-client -> None, final phones list
        new_phone_row = _make_phone_row(client_id=42, ani="56912345678")
        session = _build_update_session([
            {"first": svc},
            {"first": client},
            {"first": None},
            {"first": None},
            {"all": [new_phone_row]},
        ])
        added: list = []
        session.add.side_effect = lambda obj: added.append(obj)

        result = update_client(
            session,
            service_slug="fonotarot-cl",
            client_id=42,
            phone="56912345678",
        )

        assert len(added) == 1
        assert added[0].ani == "56912345678"
        assert added[0].client_id == 42
        assert result["phones_added"] == 1
        assert result["phones_removed"] == 0
        assert result["phone_skipped_reason"] is None
        assert "56912345678" in result["phones"]

    def test_phone_already_on_client_is_idempotent(self):
        svc = _make_service()
        client = _make_client(client_id=42)
        existing_for_me = _make_phone_row(client_id=42, ani="56912345678")
        # service, client, existing ani for this client -> hit, final phones
        session = _build_update_session([
            {"first": svc},
            {"first": client},
            {"first": existing_for_me},
            {"all": [existing_for_me]},
        ])
        added: list = []
        session.add.side_effect = lambda obj: added.append(obj)

        result = update_client(
            session,
            service_slug="fonotarot-cl",
            client_id=42,
            phone="56912345678",
        )

        assert added == []
        assert result["phones_added"] == 0
        assert result["phone_skipped_reason"] is None

    def test_phone_taken_by_other_client_is_skipped(self):
        svc = _make_service()
        client = _make_client(client_id=42)
        taken_by_other = _make_phone_row(client_id=99, ani="56912345678")
        # service, client, ani for-this-client -> None, ani any-client -> taken_by_other, final phones
        session = _build_update_session([
            {"first": svc},
            {"first": client},
            {"first": None},
            {"first": taken_by_other},
            {"all": []},
        ])
        added: list = []
        session.add.side_effect = lambda obj: added.append(obj)

        result = update_client(
            session,
            service_slug="fonotarot-cl",
            client_id=42,
            phone="56912345678",
        )

        assert added == []
        assert result["phones_added"] == 0
        assert result["phone_skipped_reason"] == "phone-registered-to-another-client"

    def test_sentinel_erases_all_phones(self):
        svc = _make_service()
        client = _make_client(client_id=42)
        # service, client, delete phones (returns 3), final phones list (now empty)
        session = _build_update_session([
            {"first": svc},
            {"first": client},
            {"delete": 3},
            {"all": []},
        ])

        result = update_client(
            session,
            service_slug="fonotarot-cl",
            client_id=42,
            phone=PHONE_ERASE_SENTINEL,
        )

        assert result["phones_removed"] == 3
        assert result["phones_added"] == 0
        assert result["phones"] == []

    def test_raises_client_not_found(self):
        svc = _make_service()
        session = _build_update_session([
            {"first": svc},
            {"first": None},
        ])

        with pytest.raises(ClientNotFound):
            update_client(
                session,
                service_slug="fonotarot-cl",
                client_id=999,
                full_name="x",
            )

    def test_raises_service_not_found(self):
        session = _build_update_session([{"first": None}])

        with pytest.raises(ServiceNotFound):
            update_client(
                session,
                service_slug="nope",
                client_id=1,
                full_name="x",
            )
