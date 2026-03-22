"""Online call tracking — insert, delete, update, and active-call lookup.

Both the API and CLI call these functions — no business logic lives in
routers or CLI commands.
"""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from firenze.models.call import OnlineCalls


def insert_call(
    db: Session,
    service: str,
    ani: str,
    did: str,
    client_id: int,
    operator: int = 0,
) -> dict:
    """Insert an online call record.

    Returns ``{"ok": False, "reason": "call-already-active"}`` if a call for
    this ANI is already registered for the service (duplicate call protection).
    Idempotent on the happy path — the unique constraint on ``(service, ani)``
    is the authority.
    """
    call = OnlineCalls(
        service=service, ani=ani, did=did, client_id=client_id, operator=operator
    )
    db.add(call)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return {"ok": False, "reason": "call-already-active"}
    return {"ok": True}


def delete_call(db: Session, service: str, ani: str) -> dict:
    """Delete an online call record.

    Idempotent — no error if the record does not exist (covers cases where
    the dialplan h-handler fires even if insert never ran).
    """
    call = db.query(OnlineCalls).filter_by(service=service, ani=ani).first()
    if call:
        db.delete(call)
        db.commit()
    return {"ok": True}


def update_call_operator(
    db: Session, service: str, ani: str, operator: int
) -> dict:
    """Update the assigned operator number on an active call record.

    Called after the operator has been selected and before the dial begins.
    Returns ``{"ok": False}`` if no matching call is found.
    """
    call = db.query(OnlineCalls).filter_by(service=service, ani=ani).first()
    if not call:
        return {"ok": False, "reason": "call-not-found"}
    call.operator = operator
    db.commit()
    return {"ok": True}


def get_active_call(db: Session, service: str, ani: str) -> dict:
    """Check whether an ANI already has an active call for the service.

    Returns ``{"llamada_activa": "true"}`` or ``{"llamada_activa": "false"}``.
    String values match the Asterisk dialplan convention for JSON_DECODE comparisons.
    """
    call = db.query(OnlineCalls).filter_by(service=service, ani=ani).first()
    return {"llamada_activa": "true" if call else "false"}
