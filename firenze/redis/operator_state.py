"""Redis/Valkey read and write for operator availability state.

Key format : firenze:operator:{number}  (Redis hash)
Fields     : loggedin (0/1), available (0/1), lastcall (unix timestamp)
TTL        : 86400s — handles "forgot to logout" scenario
"""

import logging
from typing import Optional

import redis

_KEY_PREFIX = "firenze:operator"
_TTL = 86400  # 24 hours
_log = logging.getLogger(__name__)


def _key(number: int) -> str:
    return f"{_KEY_PREFIX}:{number}"


def set_state(
    conn: redis.Redis,
    number: int,
    *,
    loggedin: bool,
    available: bool,
    lastcall: int = 0,
) -> None:
    """Write operator state to Redis and reset the 24h TTL.

    Silently logs and returns if Redis is unreachable.
    """
    try:
        conn.hset(
            _key(number),
            mapping={
                "loggedin": int(loggedin),
                "available": int(available),
                "lastcall": lastcall,
            },
        )
        conn.expire(_key(number), _TTL)
    except redis.RedisError as exc:
        _log.warning("Redis unavailable — operator state not persisted: %s", exc)


def get_state(conn: redis.Redis, number: int) -> Optional[dict]:
    """Return operator state dict, or None if the key does not exist or Redis is down."""
    try:
        data = conn.hgetall(_key(number))
    except redis.RedisError as exc:
        _log.warning("Redis unavailable — operator state not readable: %s", exc)
        return None
    if not data:
        return None
    return {
        "loggedin": bool(int(data["loggedin"])),
        "available": bool(int(data["available"])),
        "lastcall": int(data["lastcall"]),
    }
