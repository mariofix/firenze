"""Redis/Valkey connection factory."""

import redis

from firenze.config import settings


def get_redis() -> redis.Redis:
    """Return a Redis connection using REDIS_URL from settings."""
    return redis.from_url(settings.REDIS_URL, decode_responses=True)
