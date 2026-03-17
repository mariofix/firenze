from sqlalchemy.orm import Session

from firenze.models import ServiceNumber


def resolve_did(db: Session, did: str) -> str:
    """Return the asterisk_context for a DID, or empty string if not found."""
    number = db.query(ServiceNumber).filter_by(did=did, active=True).first()
    return number.asterisk_context if number else ""
