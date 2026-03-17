"""Tests for firenze.redis.operator_state — Redis hash operations."""

from unittest.mock import MagicMock

import redis

from firenze.redis.operator_state import _key, get_state, set_state


class TestOperatorStateKey:
    def test_key_format(self):
        assert _key(1001) == "firenze:operator:1001"


class TestSetState:
    def test_writes_hash_and_sets_ttl(self):
        conn = MagicMock()
        set_state(conn, 1001, loggedin=True, available=True, lastcall=0)

        conn.hset.assert_called_once_with(
            "firenze:operator:1001",
            mapping={"loggedin": 1, "available": 1, "lastcall": 0},
        )
        conn.expire.assert_called_once_with("firenze:operator:1001", 86400)

    def test_writes_logged_out_state(self):
        conn = MagicMock()
        set_state(conn, 1001, loggedin=False, available=False, lastcall=12345)

        conn.hset.assert_called_once_with(
            "firenze:operator:1001",
            mapping={"loggedin": 0, "available": 0, "lastcall": 12345},
        )


class TestGetState:
    def test_returns_parsed_dict(self):
        conn = MagicMock()
        conn.hgetall.return_value = {
            "loggedin": "1",
            "available": "0",
            "lastcall": "99999",
        }

        result = get_state(conn, 1001)
        assert result == {"loggedin": True, "available": False, "lastcall": 99999}

    def test_returns_none_when_key_missing(self):
        conn = MagicMock()
        conn.hgetall.return_value = {}

        assert get_state(conn, 9999) is None

    def test_returns_none_when_redis_unavailable(self):
        conn = MagicMock()
        conn.hgetall.side_effect = redis.ConnectionError("Connection refused")

        assert get_state(conn, 1001) is None


class TestSetStateErrorHandling:
    def test_silently_returns_when_redis_unavailable(self):
        conn = MagicMock()
        conn.hset.side_effect = redis.ConnectionError("Connection refused")

        # Should not raise
        set_state(conn, 1001, loggedin=True, available=True)
