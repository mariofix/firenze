"""Shared FastAPI dependencies - single source of truth."""

from firenze.database import SessionLocal
from firenze.redis import get_redis as get_redis

__all__ = ["get_db", "get_redis"]


def get_db():
    """Yield a SQLAlchemy session, closing it when done."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
