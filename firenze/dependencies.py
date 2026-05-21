"""Dependencias compartidas de FastAPI - fuente única de verdad."""

from firenze.database import SessionLocal
from firenze.redis import get_redis as get_redis

__all__ = ["get_db", "get_redis"]


def get_db():
    """Cede una sesión de SQLAlchemy, cerrándola cuando se realiza."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
