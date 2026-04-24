"""Redis/Valkey connection factory."""

import logging
from typing import Optional

import redis

from firenze.config import settings

_log = logging.getLogger(__name__)


def get_redis() -> Optional[redis.Redis]:
    """Return a Redis connection, or None if Redis is unreachable.

    Applies socket connect/read timeouts from settings so an unreachable
    Redis host fails fast instead of hanging on the OS default TCP timeout.
    """
    try:
        conn = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=settings.REDIS_SOCKET_CONNECT_TIMEOUT,
            socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
        )
        conn.ping()
        return conn
    except redis.RedisError as exc:
        _log.warning("Redis unavailable: %s", exc)
        return None
