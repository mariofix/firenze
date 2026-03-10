"""Shared FastAPI dependencies — single source of truth."""

from firenze.database import SessionLocal


def get_db():
    """Yield a SQLAlchemy session, closing it when done."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
