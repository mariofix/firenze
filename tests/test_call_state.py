"""Tests for firenze.redis.call_state - Redis hash operations for online calls."""

from unittest.mock import MagicMock

import redis

from firenze.redis.call_state import (
    _key,
    delete_call,
    get_call,
    scan_calls,
    set_call,
    update_operator,
)


class TestCallStateKey:
    def test_key_format(self):
        assert _key("alotarot", "56912345678") == "firenze:call:alotarot:56912345678"


class TestSetCall:
    def test_writes_hash_and_sets_ttl(self):
        conn = MagicMock()
        set_call(
            conn,
            "alotarot",
            "56912345678",
            did="8005551234",
            operator=1001,
            client_id=42,
            created_at=1700000000,
        )

        conn.hset.assert_called_once_with(
            "firenze:call:alotarot:56912345678",
            mapping={
                "did": "8005551234",
                "operator": 1001,
                "client_id": 42,
                "created_at": 1700000000,
            },
        )
        conn.expire.assert_called_once_with("firenze:call:alotarot:56912345678", 86400)

    def test_defaults_created_at_to_now_when_omitted(self):
        conn = MagicMock()
        set_call(
            conn,
            "alotarot",
            "56912345678",
            did="8005551234",
            operator=0,
            client_id=1,
        )

        assert conn.hset.call_count == 1
        mapping = conn.hset.call_args.kwargs["mapping"]
        assert isinstance(mapping["created_at"], int)
        assert mapping["created_at"] > 0

    def test_silently_returns_when_redis_unavailable(self):
        conn = MagicMock()
        conn.hset.side_effect = redis.ConnectionError("Connection refused")

        set_call(
            conn,
            "alotarot",
            "56912345678",
            did="8005551234",
            operator=0,
            client_id=1,
            created_at=1,
        )


class TestDeleteCall:
    def test_deletes_key(self):
        conn = MagicMock()
        delete_call(conn, "alotarot", "56912345678")
        conn.delete.assert_called_once_with("firenze:call:alotarot:56912345678")

    def test_silently_returns_when_redis_unavailable(self):
        conn = MagicMock()
        conn.delete.side_effect = redis.ConnectionError("Connection refused")
        delete_call(conn, "alotarot", "56912345678")


class TestUpdateOperator:
    def test_updates_field_when_key_exists(self):
        conn = MagicMock()
        conn.exists.return_value = 1

        update_operator(conn, "alotarot", "56912345678", 2002)

        conn.hset.assert_called_once_with("firenze:call:alotarot:56912345678", "operator", 2002)
        conn.expire.assert_called_once_with("firenze:call:alotarot:56912345678", 86400)

    def test_noop_when_key_missing(self):
        conn = MagicMock()
        conn.exists.return_value = 0

        update_operator(conn, "alotarot", "56912345678", 2002)

        conn.hset.assert_not_called()
        conn.expire.assert_not_called()


class TestGetCall:
    def test_returns_parsed_dict(self):
        conn = MagicMock()
        conn.hgetall.return_value = {
            "did": "8005551234",
            "operator": "1001",
            "client_id": "42",
            "created_at": "1700000000",
        }

        result = get_call(conn, "alotarot", "56912345678")
        assert result == {
            "service": "alotarot",
            "ani": "56912345678",
            "did": "8005551234",
            "operator": 1001,
            "client_id": 42,
            "created_at": 1700000000,
        }

    def test_returns_none_when_key_missing(self):
        conn = MagicMock()
        conn.hgetall.return_value = {}
        assert get_call(conn, "alotarot", "unknown") is None

    def test_returns_none_when_redis_unavailable(self):
        conn = MagicMock()
        conn.hgetall.side_effect = redis.ConnectionError("Connection refused")
        assert get_call(conn, "alotarot", "56912345678") is None


class TestScanCalls:
    def test_yields_dicts_for_matched_keys(self):
        conn = MagicMock()
        conn.scan_iter.return_value = iter(
            [
                "firenze:call:alotarot:56912345678",
                "firenze:call:alotarot:56987654321",
            ]
        )
        conn.hgetall.side_effect = [
            {"did": "d1", "operator": "1", "client_id": "10", "created_at": "100"},
            {"did": "d2", "operator": "2", "client_id": "20", "created_at": "200"},
        ]

        result = list(scan_calls(conn, "alotarot"))

        assert result == [
            {
                "service": "alotarot",
                "ani": "56912345678",
                "did": "d1",
                "operator": 1,
                "client_id": 10,
                "created_at": 100,
            },
            {
                "service": "alotarot",
                "ani": "56987654321",
                "did": "d2",
                "operator": 2,
                "client_id": 20,
                "created_at": 200,
            },
        ]

    def test_skips_empty_hashes(self):
        conn = MagicMock()
        conn.scan_iter.return_value = iter(["firenze:call:alotarot:x"])
        conn.hgetall.return_value = {}
        assert list(scan_calls(conn, "alotarot")) == []
