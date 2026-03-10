"""Do Not Call list lookups."""

from sqlalchemy.orm import Session

from firenze.models import DoNotCall


def check_dnc(db: Session, ani: str) -> bool:
    """Return True if the ANI is in the Do Not Call list."""
    return db.query(DoNotCall).filter_by(ani=ani).first() is not None
