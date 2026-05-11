"""Client lookup and credit management.

Used by AGI endpoints - Asterisk dialplan calls these via CURL.
"""

import logging

from sqlalchemy.orm import Session

from firenze.models.client import Client, ClientAni
from firenze.models.service import Service
from firenze.services.notifications import notify

logger = logging.getLogger("firenze")


class ClientNotFound(Exception):
    pass


class ServiceNotFound(Exception):
    pass


def _get_service(db: Session, slug: str) -> Service:
    svc = db.query(Service).filter_by(slug=slug).first()
    if not svc:
        raise ServiceNotFound(f"Service '{slug}' not found")
    return svc


def lookup(db: Session, service_slug: str, identifier: str) -> dict:
    """Look up a client by service slug and identifier (PIN or ANI).

    len(identifier) == 6: PIN (phone numbers are never length 6)
    else : ANI

    Returns dict with ``clientid`` and ``segundos`` matching the contract
    the Asterisk dialplan expects.
    """
    svc = _get_service(db, service_slug)
    client = None

    if len(identifier) == 6:
        client = db.query(Client).filter_by(service_id=svc.id, pin=identifier).first()
    else:
        client = (
            db.query(Client)
            .filter_by(service_id=svc.id, phone_number=identifier)
            .first()
        )
        if not client:
            client_id = db.query(ClientAni).filter_by(ani=identifier, service_id=svc.id).first()
            if client_id:
                client = db.query(Client).filter_by(service_id=svc.id, client_id=client_id.client_id).first()

    if not client:
        return {"clientid": 0, "segundos": 0}
    return {"clientid": client.client_id, "segundos": client.credits}


def deduct_credits(
    db: Session, service_slug: str, client_id: int, seconds: int
) -> dict:
    """Deduct seconds from a client's credit balance.

    Returns dict with ``ok`` and ``remaining``.
    """
    svc = _get_service(db, service_slug)
    client = db.query(Client).filter_by(service_id=svc.id, client_id=client_id).first()
    if not client:
        raise ClientNotFound(
            f"Client {client_id} not found in service '{service_slug}'"
        )
    if client.credits <= 0:
        # Per-client one-call-at-a-time enforcement upstream should make this
        # unreachable. If we land here, the customer made a call without
        # credits - log loudly and notify, but don't fail the deduction.
        logger.warning(
            f"deduct_credits called with no balance: {service_slug=} {client_id=} {seconds=} {credits=}"
        )
        notify(
            subject=f"[firenze] deduct on zero balance: client {client_id}",
            body=(
                f"deduct_credits was called for a client with no credits.\n\n"
                f"service: {service_slug}\n"
                f"client_id: {client_id}\n"
                f"seconds requested: {seconds}\n"
                f"current credits: {client.credits}\n\n"
                f"This should be unreachable - the per-client call lock upstream "
                f"is supposed to prevent a second call from starting. Investigate."
            ),
        )
        return {"ok": True, "remaining": 0, "before": client.credits}
    before_call = client.credits
    client.credits -= seconds
    if client.credits < 0:
        client.credits = 0
    db.commit()
    db.refresh(client)
    return {"ok": True, "remaining": client.credits, "before": before_call}
