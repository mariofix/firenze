"""Search clients and apply completed purchases.

Consumed by ``firenze.api.payments`` - the storefront (nuevo-fonotarot) calls
these via HTTP. Firenze is not authoritative on payments themselves; it just
records the resulting credit delta.
"""

import logging
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from firenze.models.client import Client, ClientAni
from firenze.models.service import Service
from firenze.services.client_service import ClientNotFound, ServiceNotFound

logger = logging.getLogger("firenze")

PHONE_ERASE_SENTINEL = "::EMPTY::"


class PinAlreadyTaken(Exception):
    """Raised when a PIN update would collide with another client in the service."""


class AniAlreadyTaken(Exception):
    """Raised when ANI belongs to another client in the same service."""


class ClientAniNotFound(Exception):
    """Raised when an ANI row does not exist for the target client."""


def _get_service(db: Session, slug: str) -> Service:
    svc = db.query(Service).filter_by(slug=slug).first()
    if not svc:
        raise ServiceNotFound(f"Service '{slug}' not found")
    return svc


def _next_client_id(db: Session, service_id: int) -> int:
    """Pick the next ``client_id`` for a service.

    Plain ``MAX(client_id)+1`` per service. The caller serializes around the
    inserting transaction, so this is safe under the storefront's expected
    concurrency (single-digit purchases per day). If contention grows this
    should move to a per-service sequence table or be replaced by using the
    surrogate PK as the business identifier.
    """
    current = (
        db.query(func.max(Client.client_id)).filter_by(service_id=service_id).scalar()
    )
    return (current or 0) + 1


def search_client(
    db: Session,
    service_slug: str,
    *,
    client_id: Optional[int] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    ani: Optional[str] = None,
    pin: Optional[str] = None,
) -> Optional[Client]:
    """Find a client in ``service_slug`` matching any of the provided fields.

    Lookup order: pin, email, phone_number, ClientAni.ani. Returns the first
    match (or ``None``). Raises ``ServiceNotFound`` if the slug is unknown.
    """
    svc = _get_service(db, service_slug)

    if client_id:
        client = db.query(Client).filter_by(service_id=svc.id, client_id=client_id).first()
        if client:
            return client

    if pin:
        client = db.query(Client).filter_by(service_id=svc.id, pin=pin).first()
        if client:
            return client

    if email:
        client = db.query(Client).filter_by(service_id=svc.id, email=email).first()
        if client:
            return client

    if phone:
        client = (
            db.query(Client).filter_by(service_id=svc.id, phone_number=phone).first()
        )
        if client:
            return client

    if ani:
        ani_row = db.query(ClientAni).filter_by(service_id=svc.id, ani=ani).first()
        if ani_row:
            return (
                db.query(Client)
                .filter_by(service_id=svc.id, client_id=ani_row.client_id)
                .first()
            )

    return None


def apply_purchase(
    db: Session,
    *,
    service_slug: str,
    credits: int,
    client_id: Optional[int] = None,
    email: Optional[str] = None,
    full_name: Optional[str] = None,
    phone_number: Optional[str] = None,
    ani: Optional[str] = None,
    transaction_id: Optional[str] = None,
) -> dict:
    """Apply a completed purchase: create the client or top up an existing one.

    When ``client_id`` is provided, the matching ``Client`` row is updated and
    ``credits`` is added to its balance. Otherwise a new ``Client`` is inserted
    with a freshly generated ``client_id`` and the supplied profile fields, and
    ``credits`` becomes its initial balance. If ``ani`` is provided it is
    registered against the client (skipped silently when already taken by
    someone else within the same service).

    Returns a dict suitable for ``PurchaseResponse``.
    """
    svc = _get_service(db, service_slug)
    created = False

    if client_id is not None:
        client = (
            db.query(Client).filter_by(service_id=svc.id, client_id=client_id).first()
        )
        if not client:
            raise ClientNotFound(
                f"Client {client_id} not found in service '{service_slug}'"
            )
        before = client.credits
        # Mientras tanto credits es el total del usuario
        # client.credits = before + credits
        client.credits = credits
    else:
        new_id = _next_client_id(db, svc.id)
        client = Client(
            service_id=svc.id,
            client_id=new_id,
            email=email,
            full_name=full_name,
            phone_number=phone_number,
            credits=credits,
        )
        db.add(client)
        db.flush()
        before = 0
        created = True

    if ani:
        existing_ani = db.query(ClientAni).filter_by(service_id=svc.id, ani=ani).first()
        if existing_ani is None:
            db.add(ClientAni(service_id=svc.id, client_id=client.client_id, ani=ani))
        elif existing_ani.client_id != client.client_id:
            logger.warning(
                "apply_purchase: ANI %r already registered to client_id=%s in service=%r; skipping registration for client_id=%s",
                ani,
                existing_ani.client_id,
                service_slug,
                client.client_id,
            )

    db.commit()
    db.refresh(client)

    logger.info(
        "apply_purchase: service=%r client_id=%s created=%s credits_before=%s credits_added=%s credits_after=%s transaction_id=%r",
        service_slug,
        client.client_id,
        created,
        before,
        credits,
        client.credits,
        transaction_id,
    )

    return {
        "ok": True,
        "client_id": client.client_id,
        "service": service_slug,
        "created": created,
        "credits_before": before,
        "credits_added": credits,
        "credits_after": client.credits,
    }


def update_client(
    db: Session,
    *,
    service_slug: str,
    client_id: int,
    full_name: Optional[str] = None,
    email: Optional[str] = None,
    pin: Optional[str] = None,
    phone: Optional[str] = None,
) -> dict:
    """Update profile fields on an existing client.

    All inputs are optional. Phone behavior:
    - ``phone is None``: do nothing.
    - ``phone == PHONE_ERASE_SENTINEL``: delete every ``ClientAni`` for this
      client.
    - other value: add to ``ClientAni`` if not already on this client. If the
      number is already registered to a different client in the same service,
      skip with a warning and report the reason in the response (no exception
      so the rest of the update still applies).

    Raises ``ServiceNotFound``, ``ClientNotFound``, or ``PinAlreadyTaken``.
    """
    svc = _get_service(db, service_slug)
    client = db.query(Client).filter_by(service_id=svc.id, client_id=client_id).first()
    if not client:
        raise ClientNotFound(
            f"Client {client_id} not found in service '{service_slug}'"
        )

    if pin is not None and pin != client.pin:
        collision = (
            db.query(Client)
            .filter(
                Client.service_id == svc.id,
                Client.pin == pin,
                Client.client_id != client_id,
            )
            .first()
        )
        if collision:
            raise PinAlreadyTaken(
                f"PIN already in use by client_id={collision.client_id} in service '{service_slug}'"
            )
        client.pin = pin

    if full_name is not None:
        client.full_name = full_name
    if email is not None:
        client.email = email

    phones_added = 0
    phones_removed = 0
    phone_skipped_reason: Optional[str] = None

    if phone is not None:
        if phone == PHONE_ERASE_SENTINEL:
            phones_removed = (
                db.query(ClientAni)
                .filter_by(service_id=svc.id, client_id=client_id)
                .delete(synchronize_session=False)
            )
        else:
            existing_for_client = (
                db.query(ClientAni)
                .filter_by(service_id=svc.id, client_id=client_id, ani=phone)
                .first()
            )
            if existing_for_client is None:
                taken = (
                    db.query(ClientAni).filter_by(service_id=svc.id, ani=phone).first()
                )
                if taken is None:
                    db.add(ClientAni(service_id=svc.id, client_id=client_id, ani=phone))
                    phones_added = 1
                else:
                    phone_skipped_reason = "phone-registered-to-another-client"
                    logger.warning(
                        "update_client: phone %r already registered to client_id=%s in service=%r; skipped for client_id=%s",
                        phone,
                        taken.client_id,
                        service_slug,
                        client_id,
                    )

    db.commit()
    db.refresh(client)

    phones = [
        row.ani
        for row in db.query(ClientAni)
        .filter_by(service_id=svc.id, client_id=client_id)
        .all()
    ]

    logger.info(
        "update_client: service=%r client_id=%s full_name_set=%s email_set=%s pin_set=%s phones_added=%s phones_removed=%s",
        service_slug,
        client_id,
        full_name is not None,
        email is not None,
        pin is not None,
        phones_added,
        phones_removed,
    )

    return {
        "ok": True,
        "client_id": client.client_id,
        "service": service_slug,
        "full_name": client.full_name,
        "email": client.email,
        "pin": client.pin,
        "phones": phones,
        "phones_added": phones_added,
        "phones_removed": phones_removed,
        "phone_skipped_reason": phone_skipped_reason,
    }


def list_client_anis(
    db: Session, *, service_slug: str, client_id: int
) -> dict:
    """List every ANI registered to a client in a service."""
    svc = _get_service(db, service_slug)
    client = db.query(Client).filter_by(service_id=svc.id, client_id=client_id).first()
    if not client:
        raise ClientNotFound(
            f"Client {client_id} not found in service '{service_slug}'"
        )

    anis = [
        row.ani
        for row in db.query(ClientAni)
        .filter_by(service_id=svc.id, client_id=client_id)
        .order_by(ClientAni.id.asc())
        .all()
    ]

    return {
        "ok": True,
        "service": service_slug,
        "client_id": client_id,
        "anis": anis,
    }


def create_client_ani(
    db: Session, *, service_slug: str, client_id: int, ani: str
) -> dict:
    """Create (or idempotently add) one ANI mapping for an existing client."""
    svc = _get_service(db, service_slug)
    client = db.query(Client).filter_by(service_id=svc.id, client_id=client_id).first()
    if not client:
        raise ClientNotFound(
            f"Client {client_id} not found in service '{service_slug}'"
        )

    existing = db.query(ClientAni).filter_by(service_id=svc.id, ani=ani).first()
    if existing:
        if existing.client_id == client_id:
            return {
                "ok": True,
                "service": service_slug,
                "client_id": client_id,
                "ani": ani,
                "created": False,
            }
        raise AniAlreadyTaken(
            f"ANI {ani} already registered to client_id={existing.client_id} in service '{service_slug}'"
        )

    db.add(ClientAni(service_id=svc.id, client_id=client_id, ani=ani))
    db.commit()

    return {
        "ok": True,
        "service": service_slug,
        "client_id": client_id,
        "ani": ani,
        "created": True,
    }


def delete_client_ani(
    db: Session, *, service_slug: str, client_id: int, ani: str
) -> dict:
    """Delete one ANI mapping from a client."""
    svc = _get_service(db, service_slug)
    client = db.query(Client).filter_by(service_id=svc.id, client_id=client_id).first()
    if not client:
        raise ClientNotFound(
            f"Client {client_id} not found in service '{service_slug}'"
        )

    ani_row = (
        db.query(ClientAni)
        .filter_by(service_id=svc.id, client_id=client_id, ani=ani)
        .first()
    )
    if not ani_row:
        raise ClientAniNotFound(
            f"ANI {ani} not found for client {client_id} in service '{service_slug}'"
        )

    db.delete(ani_row)
    db.commit()

    return {
        "ok": True,
        "service": service_slug,
        "client_id": client_id,
        "ani": ani,
        "deleted": True,
    }
