"""Búsquedas en la lista de No Llamar."""

from sqlalchemy.orm import Session

from firenze.models import DoNotCall


def check_dnc(db: Session, ani: str) -> bool:
    """Retorna Verdadero si el ANI está en la lista de No Llamar."""
    return db.query(DoNotCall).filter_by(ani=ani).first() is not None
