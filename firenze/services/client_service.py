"""Client lookup and credit management.

Used by AGI endpoints - Asterisk dialplan calls these via CURL.
"""

import datetime
import logging

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from firenze.models.client import Client, ClientAni, _generate_pin
from firenze.models.operator import Operator
from firenze.models.service import Service
from firenze.services.notifications import notify

logger = logging.getLogger("firenze")

_MAX_PIN_SELECTION_ATTEMPTS = 256


class ClientNotFound(Exception):
    pass


class ServiceNotFound(Exception):
    pass


class ClientAlreadyExists(Exception):
    pass


class InvalidClientExtraConfig(Exception):
    pass


def _get_service(db: Session, slug: str) -> Service:
    svc = db.query(Service).filter_by(slug=slug).first()
    if not svc:
        raise ServiceNotFound(f"Service '{slug}' not found")
    return svc


def lookup(db: Session, service_slug: str, identifier: str) -> dict:
    """Look up a client by service slug and identifier (PIN or ANI).

    len(identifier) == 8: PIN (current PIN format)
    else : ANI

    Returns dict with ``clientid`` and ``segundos`` matching the contract
    the Asterisk dialplan expects.
    """
    svc = _get_service(db, service_slug)
    client = None

    if len(identifier) == 8:
        client = db.query(Client).filter_by(service_id=svc.id, pin=identifier).first()
    else:
        client_id = db.query(ClientAni).filter_by(ani=identifier, service_id=svc.id).first()
        if client_id:
            client = db.query(Client).filter_by(service_id=svc.id, client_id=client_id.client_id).first()

    if not client:
        return {"clientid": 0, "segundos": 0}
    return {"clientid": client.client_id, "segundos": client.credits}


def deduct_credits(db: Session, service_slug: str, client_id: int, seconds: int) -> dict:
    """Deduct seconds from a client's credit balance.

    Returns dict with ``ok`` and ``remaining``.
    """
    svc = _get_service(db, service_slug)
    client = db.query(Client).filter_by(service_id=svc.id, client_id=client_id).first()
    if not client:
        raise ClientNotFound(f"Client {client_id} not found in service '{service_slug}'")
    if client.credits <= 0:
        # Per-client one-call-at-a-time enforcement upstream should make this
        # unreachable. If we land here, the customer made a call without
        # credits - log loudly and notify, but don't fail the deduction.
        logger.warning(f"deduct_credits called with no balance: {service_slug=} {client_id=} {seconds=} {credits=}")
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


def update_ani_stats(db: Session, service_slug: str, ani: str) -> None:
    """Update client_ani.q_calls y client_ani.lastcall"""
    svc = _get_service(db, service_slug)

    ani = db.query(ClientAni).filter_by(ani=ani, service_id=svc.id).first()
    if ani:
        ani.q_calls = ani.q_calls + 1
        ani.last_call = datetime.datetime.now()
        db.flush()
        db.commit()


def _next_client_id(db: Session, service_id: int) -> int:
    current = db.query(func.max(Client.client_id)).filter_by(service_id=service_id).scalar()
    return (current or 0) + 1


def _client_anis(db: Session, service_id: int, client_id: int) -> list[str]:
    return [
        row.ani
        for row in db.query(ClientAni)
        .filter_by(service_id=service_id, client_id=client_id)
        .order_by(ClientAni.id.asc())
        .all()
    ]


def _client_payload(client: Client, service_slug: str, anis: list[str]) -> dict:
    return {
        "id": client.id,
        "service": service_slug,
        "client_id": client.client_id,
        "full_name": client.full_name,
        "email": client.email,
        "pin": client.pin,
        "credits": client.credits,
        "extra_config": client.extra_config,
        "anis": anis,
        "created_at": client.created_at,
        "modified_at": client.modified_at,
    }


def _pin_in_use(db: Session, service_id: int, pin: str, *, exclude_client_id: int | None = None) -> bool:
    query = db.query(Client).filter(Client.service_id == service_id, Client.pin == pin)
    if exclude_client_id is not None:
        query = query.filter(Client.client_id != exclude_client_id)
    return query.first() is not None


def _pick_unique_pin(
    db: Session, service_id: int, requested_pin: str | None, *, exclude_client_id: int | None = None
) -> str | None:
    if requested_pin is None:
        return None
    if not _pin_in_use(db, service_id, requested_pin, exclude_client_id=exclude_client_id):
        return requested_pin

    logger.warning(
        "pin collision in service_id=%s requested_pin=%r; generating replacement",
        service_id,
        requested_pin,
    )
    random_attempts = 8
    sequential_seed = int(requested_pin) if requested_pin.isdigit() else 0
    for attempts in range(_MAX_PIN_SELECTION_ATTEMPTS):
        if attempts < random_attempts:
            candidate = _generate_pin()
        else:
            # Deterministic fallback avoids pathological loops (e.g., mocked generator
            # constantly returning the same colliding PIN).
            offset = attempts - random_attempts + 1
            candidate = f"{(sequential_seed + offset) % 100_000_000:08d}"
        if not _pin_in_use(db, service_id, candidate, exclude_client_id=exclude_client_id):
            return candidate
    raise RuntimeError(
        f"Unable to allocate a unique PIN for service_id={service_id} after {_MAX_PIN_SELECTION_ATTEMPTS} attempts"
    )


def _validate_extra_config(db: Session, extra_config: dict | None) -> None:
    if not extra_config:
        return

    favorite_operator = extra_config.get("tarotista_favorita")
    if favorite_operator is None:
        return

    operator_exists = db.query(Operator).filter_by(number=favorite_operator).first()
    if not operator_exists:
        raise InvalidClientExtraConfig(
            f"extra_config.tarotista_favorita={favorite_operator} does not match any operator number"
        )


def get_client(db: Session, service_slug: str, client_id: int) -> dict:
    svc = _get_service(db, service_slug)
    client = db.query(Client).filter_by(service_id=svc.id, client_id=client_id).first()
    if not client:
        raise ClientNotFound(f"Client {client_id} not found in service '{service_slug}'")
    return _client_payload(client, service_slug, _client_anis(db, svc.id, client_id))


def create_client(
    db: Session,
    service_slug: str,
    *,
    client_id: int | None = None,
    full_name: str | None = None,
    email: str | None = None,
    pin: str | None = None,
    credits: int = 0,
    extra_config: dict | None = None,
) -> dict:
    svc = _get_service(db, service_slug)
    _validate_extra_config(db, extra_config)

    if client_id is None:
        client_id = _next_client_id(db, svc.id)
    else:
        existing = db.query(Client).filter_by(service_id=svc.id, client_id=client_id).first()
        if existing:
            raise ClientAlreadyExists(f"Client {client_id} already exists in service '{service_slug}'")

    pin = _pick_unique_pin(db, svc.id, pin)

    client = Client(
        service_id=svc.id,
        client_id=client_id,
        full_name=full_name,
        email=email,
        pin=pin,
        credits=credits,
        extra_config=extra_config,
    )
    db.add(client)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ClientAlreadyExists(f"Client {client_id} already exists in service '{service_slug}'") from exc
    db.refresh(client)
    return _client_payload(client, service_slug, [])


def update_client_record(
    db: Session,
    service_slug: str,
    *,
    client_id: int,
    full_name: str | None = None,
    email: str | None = None,
    pin: str | None = None,
    credits: int | None = None,
    extra_config: dict | None = None,
    extra_config_provided: bool = False,
) -> dict:
    svc = _get_service(db, service_slug)
    if extra_config_provided:
        _validate_extra_config(db, extra_config)
    client = db.query(Client).filter_by(service_id=svc.id, client_id=client_id).first()
    if not client:
        raise ClientNotFound(f"Client {client_id} not found in service '{service_slug}'")

    if pin is not None and pin != client.pin:
        pin = _pick_unique_pin(db, svc.id, pin, exclude_client_id=client_id)
        client.pin = pin

    if full_name is not None:
        client.full_name = full_name
    if email is not None:
        client.email = email
    if credits is not None:
        client.credits = credits
    if extra_config_provided:
        client.extra_config = extra_config

    db.commit()
    db.refresh(client)
    return _client_payload(client, service_slug, _client_anis(db, svc.id, client_id))


def delete_client(db: Session, service_slug: str, *, client_id: int) -> dict:
    svc = _get_service(db, service_slug)
    client = db.query(Client).filter_by(service_id=svc.id, client_id=client_id).first()
    if not client:
        raise ClientNotFound(f"Client {client_id} not found in service '{service_slug}'")

    db.delete(client)
    db.commit()
    return {"ok": True, "service": service_slug, "client_id": client_id, "deleted": True}
