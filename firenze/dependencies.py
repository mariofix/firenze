"""Shared FastAPI dependencies — single source of truth."""

from typing import Optional

import redis

from firenze.config import settings
from firenze.database import SessionLocal


def get_db():
    """Yield a SQLAlchemy session, closing it when done."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_redis() -> Optional[redis.Redis]:
    """Return a Redis connection, or None if Redis is unreachable."""
    try:
        conn = redis.from_url(settings.REDIS_URL, decode_responses=True)
        conn.ping()
        return conn
    except redis.RedisError:
        return None
