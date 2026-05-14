"""Redis/Valkey read and write for active online call state.

Key format : firenze:call:{service}:{ani}  (Redis hash)
Fields     : did, operator, client_id, created_at (unix timestamp)
TTL        : 86400s - safety net if the dialplan h-handler never fires.

Mirrors firenze.redis.operator_state. The PHP reader at
asterisk_config/legacy-php/onlinecalls_redis.php consumes these keys.
"""

import logging
import time
from typing import Iterator, Optional

import redis

_KEY_PREFIX = "firenze:call"
_TTL = 86400
_log = logging.getLogger("firenze")


def _key(service: str, ani: str) -> str:
    return f"{_KEY_PREFIX}:{service}:{ani}"


def set_call(
    conn: redis.Redis,
    service: str,
    ani: str,
    *,
    did: str,
    operator: int,
    client_id: int,
    created_at: Optional[int] = None,
) -> None:
    """Write call state to Redis and (re)set the 24h TTL.

    Silently logs and returns if Redis is unreachable - MySQL is the source
    of truth, Redis is a hot cache.
    """
    if created_at is None:
        created_at = int(time.time())
    try:
        conn.hset(
            _key(service, ani),
            mapping={
                "did": did,
                "operator": int(operator),
                "client_id": int(client_id),
                "created_at": int(created_at),
            },
        )
        conn.expire(_key(service, ani), _TTL)
    except redis.RedisError as exc:
        _log.warning("Redis unavailable - call state not persisted: %s", exc)


def delete_call(conn: redis.Redis, service: str, ani: str) -> None:
    """Remove the call hash. Idempotent."""
    try:
        conn.delete(_key(service, ani))
    except redis.RedisError as exc:
        _log.warning("Redis unavailable - call state not removed: %s", exc)


def update_operator(conn: redis.Redis, service: str, ani: str, operator: int) -> None:
    """Update only the operator field on an existing call hash.

    No-op if the hash does not exist (hset on a missing key would create a
    partial record without the other fields).
    """
    try:
        if conn.exists(_key(service, ani)):
            conn.hset(_key(service, ani), "operator", int(operator))
            conn.expire(_key(service, ani), _TTL)
    except redis.RedisError as exc:
        _log.warning("Redis unavailable - call operator not updated: %s", exc)


def get_call(conn: redis.Redis, service: str, ani: str) -> Optional[dict]:
    """Return the call dict, or None if the key is absent or Redis is down."""
    try:
        data = conn.hgetall(_key(service, ani))
    except redis.RedisError as exc:
        _log.warning("Redis unavailable - call state not readable: %s", exc)
        return None
    if not data:
        return None
    return {
        "service": service,
        "ani": ani,
        "did": data.get("did", ""),
        "operator": int(data.get("operator", 0) or 0),
        "client_id": int(data.get("client_id", 0) or 0),
        "created_at": int(data.get("created_at", 0) or 0),
    }


def scan_calls(conn: redis.Redis, service: str) -> Iterator[dict]:
    """Yield all active call dicts for a service. Uses SCAN, never KEYS."""
    pattern = f"{_KEY_PREFIX}:{service}:*"
    try:
        for key in conn.scan_iter(match=pattern, count=100):
            data = conn.hgetall(key)
            if not data:
                continue
            ani = key.split(":", 3)[3] if key.count(":") >= 3 else ""
            yield {
                "service": service,
                "ani": ani,
                "did": data.get("did", ""),
                "operator": int(data.get("operator", 0) or 0),
                "client_id": int(data.get("client_id", 0) or 0),
                "created_at": int(data.get("created_at", 0) or 0),
            }
    except redis.RedisError as exc:
        _log.warning("Redis unavailable - call scan aborted: %s", exc)
