from sqlalchemy.orm import Session

from firenze.models import ServiceNumber


def resolve_did(db: Session, did: str) -> dict:
    """Return full service config for a DID, or empty strings if not found.

    Used by ``GET /agi/services/did/{did}`` — Asterisk dialplan reads all
    fields in one call and sets them as channel variables.

    Returns:
        siguiente    — Asterisk context to Goto (e.g. "prepago-service")
        servicio     — service slug (e.g. "alotarot", "fonotarot-cl")
        auth_method  — "ani" or "pin"
        intro_audio  — Playback-compatible string (e.g. "zvn/intro-alotarot")
    """
    number = db.query(ServiceNumber).filter_by(did=did, active=True).first()
    if not number or not number.service:
        return {"siguiente": "", "servicio": "", "auth_method": "", "intro_audio": ""}
    svc = number.service
    return {
        "siguiente": number.asterisk_context,
        "servicio": svc.slug,
        "auth_method": svc.auth_method,
        "intro_audio": svc.intro_audio,
    }
