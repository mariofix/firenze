"""Redis/Valkey read and write for operator availability state.

Key format : firenze:operator:{number}  (Redis hash)
Fields     : loggedin (0/1), available (0/1), lastcall (unix timestamp)
TTL        : 86400s — handles "forgot to logout" scenario
"""

import logging

import redis

_KEY_PREFIX = "firenze:operator"
_TTL = 86400  # 24 hours
_log = logging.getLogger("firenze")


def _key(number: int) -> str:
    return f"{_KEY_PREFIX}:{number}"


def set_state(
    conn: redis.Redis,
    number: int,
    *,
    loggedin: bool,
    available: bool,
    lastcall: int | None = None,
) -> None:
    """Write operator state to Redis and reset the 24h TTL.

    When ``lastcall`` is ``None`` the field is omitted from the write so
    callers that only toggle login/availability do not clobber the existing
    last-activity timestamp. Silently logs and returns if Redis is unreachable.
    """
    mapping = {
        "loggedin": int(loggedin),
        "available": int(available),
    }
    if lastcall is not None:
        mapping["lastcall"] = lastcall
    try:
        conn.hset(_key(number), mapping=mapping)
        conn.expire(_key(number), _TTL)
    except redis.RedisError as exc:
        _log.warning("Redis unavailable — operator state not persisted: %s", exc)


def get_state(conn: redis.Redis, number: int) -> dict | None:
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
        "lastcall": int(data.get("lastcall", 0)),
    }
