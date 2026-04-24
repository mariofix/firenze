"""Client lookup and credit management.

Used by AGI endpoints — Asterisk dialplan calls these via CURL.
"""

from sqlalchemy.orm import Session

from firenze.models.client import Client, ClientAni
from firenze.models.service import Service


class ClientNotFound(Exception):
    pass


class ServiceNotFound(Exception):
    pass


class InsufficientCredits(Exception):
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
        client_ani = db.query(ClientAni).filter_by(service_id=svc.id, ani=identifier).first()
        if client_ani:
            client = db.query(Client).filter_by(service_id=svc.id, client_id=client_ani.client_id).first()

    if not client:
        return {"clientid": 0, "segundos": 0, "a": 1}
    return {"clientid": client.client_id, "segundos": client.credits}


def deduct_credits(db: Session, service_slug: str, client_id: int, seconds: int) -> dict:
    """Deduct seconds from a client's credit balance.

    Returns dict with ``ok`` and ``remaining``.
    """
    svc = _get_service(db, service_slug)
    client = (
        db.query(Client)
        .filter_by(service_id=svc.id, client_id=client_id)
        .first()
    )
    if not client:
        raise ClientNotFound(f"Client {client_id} not found in service '{service_slug}'")
    if client.credits < seconds:
        raise InsufficientCredits(
            f"Client {client_id} has {client.credits}s, needs {seconds}s"
        )
    client.credits -= seconds
    db.commit()
    db.refresh(client)
    return {"ok": True, "remaining": client.credits}
