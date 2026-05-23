"""Buscar clientes y aplicar compras completadas.

Consumido por ``firenze.api.payments`` - la tienda (nuevo-fonotarot) llama
a estos a través de HTTP. Firenze no es la autoridad sobre los pagos en sí; solo
registra el delta de crédito resultante.
"""

import logging

from sqlalchemy import func
from sqlalchemy.orm import Session

from firenze.models.client import Client, ClientAni
from firenze.models.service import Service
from firenze.services.client_service import (
    ClientNotFound,
    ServiceNotFound,
    _pick_unique_pin,
)

logger = logging.getLogger("firenze")

PHONE_ERASE_SENTINEL = "::EMPTY::"


class AniAlreadyTaken(Exception):
    """Se genera cuando el ANI pertenece a otro cliente en el mismo servicio."""


class ClientAniNotFound(Exception):
    """Se genera cuando una fila de ANI no existe para el cliente destino."""


def _get_service(db: Session, slug: str) -> Service:
    svc = db.query(Service).filter_by(slug=slug).first()
    if not svc:
        raise ServiceNotFound(f"Service '{slug}' not found")
    return svc


def _next_client_id(db: Session, service_id: int) -> int:
    """Elige el siguiente ``client_id`` para un servicio.

    Simple ``MAX(client_id)+1`` por servicio. El llamador serializa alrededor de la
    transacción de inserción, así que esto es seguro bajo la concurrencia esperada de la tienda
    (compras de un solo dígito por día). Si la contención crece, esto
    debería pasar a una tabla de secuencia por servicio o ser reemplazado por usar la
    PK sustituta como identificador comercial.
    """
    current = db.query(func.max(Client.client_id)).filter_by(service_id=service_id).scalar()
    return (current or 0) + 1


def search_client(
    db: Session,
    service_slug: str,
    *,
    client_id: int | None = None,
    email: str | None = None,
    phone: str | None = None,
    ani: str | None = None,
    pin: str | None = None,
) -> Client | None:
    """Encuentra un cliente en ``service_slug`` que coincida con cualquiera de los campos proporcionados.

    Orden de búsqueda: pin, email, ClientAni.ani. ``phone`` se acepta para
    compatibilidad hacia atrás pero se ignora. Retorna la primera coincidencia (o ``None``).
    Genera ``ServiceNotFound`` si el slug es desconocido.
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

    if ani:
        ani_row = db.query(ClientAni).filter_by(service_id=svc.id, ani=ani).first()
        if ani_row:
            return db.query(Client).filter_by(service_id=svc.id, client_id=ani_row.client_id).first()

    return None


def apply_purchase(
    db: Session,
    *,
    service_slug: str,
    credits: int,
    client_id: int | None = None,
    email: str | None = None,
    full_name: str | None = None,
    phone_number: str | None = None,
    ani: str | None = None,
    transaction_id: str | None = None,
) -> dict:
    """Aplica una compra completada: crea el cliente o recarga el existente.

    Cuando se proporciona ``client_id``, la fila ``Client`` coincidente se actualiza y
    ``credits`` se suma a su saldo. De lo contrario, se inserta un nuevo ``Client``
    con un ``client_id`` recién generado y los campos de perfil suministrados, y
    ``credits`` se convierte en su saldo inicial. Si se proporciona ``ani``, se registra
    contra el cliente (se omite silenciosamente cuando ya está tomado por
    alguien más dentro del mismo servicio).

    Retorna un dict adecuado para ``PurchaseResponse``.
    """
    svc = _get_service(db, service_slug)
    created = False

    if client_id is not None:
        client = db.query(Client).filter_by(service_id=svc.id, client_id=client_id).first()
        if not client:
            raise ClientNotFound(f"Client {client_id} not found in service '{service_slug}'")
        before = client.credits
        client.credits = before + credits
    else:
        new_id = _next_client_id(db, svc.id)
        client = Client(
            service_id=svc.id,
            client_id=new_id,
            email=email,
            full_name=full_name,
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
                "apply_purchase: ANI %r already registered to client_id=%s in service=%r; "
                "skipping registration for client_id=%s",
                ani,
                existing_ani.client_id,
                service_slug,
                client.client_id,
            )

    db.commit()
    db.refresh(client)

    logger.info(
        "apply_purchase: service=%r client_id=%s created=%s credits_before=%s "
        "credits_added=%s credits_after=%s transaction_id=%r",
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
    full_name: str | None = None,
    email: str | None = None,
    pin: str | None = None,
    phone: str | None = None,
) -> dict:
    """Actualiza campos de perfil en un cliente existente.

    Todas las entradas son opcionales. Comportamiento del teléfono:
    - ``phone is None``: no hace nada.
    - ``phone == PHONE_ERASE_SENTINEL``: elimina cada ``ClientAni`` para este
      cliente.
    - otro valor: agrega a ``ClientAni`` si no está en este cliente. Si el
      número ya está registrado para un cliente diferente en el mismo servicio,
      omítalo con una advertencia e informe el motivo en la respuesta (sin excepción
      para que el resto de la actualización siga aplicándose).

    Genera ``ServiceNotFound`` o ``ClientNotFound``.
    """
    svc = _get_service(db, service_slug)
    client = db.query(Client).filter_by(service_id=svc.id, client_id=client_id).first()
    if not client:
        raise ClientNotFound(f"Client {client_id} not found in service '{service_slug}'")

    if pin is not None and pin != client.pin:
        client.pin = _pick_unique_pin(db, svc.id, pin, exclude_client_id=client_id)

    if full_name is not None:
        client.full_name = full_name
    if email is not None:
        client.email = email

    phones_added = 0
    phones_removed = 0
    phone_skipped_reason: str | None = None

    if phone is not None:
        if phone == PHONE_ERASE_SENTINEL:
            phones_removed = (
                db.query(ClientAni).filter_by(service_id=svc.id, client_id=client_id).delete(synchronize_session=False)
            )
        else:
            existing_for_client = (
                db.query(ClientAni).filter_by(service_id=svc.id, client_id=client_id, ani=phone).first()
            )
            if existing_for_client is None:
                taken = db.query(ClientAni).filter_by(service_id=svc.id, ani=phone).first()
                if taken is None:
                    db.add(ClientAni(service_id=svc.id, client_id=client_id, ani=phone))
                    phones_added = 1
                else:
                    phone_skipped_reason = "phone-registered-to-another-client"
                    logger.warning(
                        "update_client: phone %r already registered to client_id=%s in service=%r; "
                        "skipped for client_id=%s",
                        phone,
                        taken.client_id,
                        service_slug,
                        client_id,
                    )

    db.commit()
    db.refresh(client)

    phones = [row.ani for row in db.query(ClientAni).filter_by(service_id=svc.id, client_id=client_id).all()]

    logger.info(
        "update_client: service=%r client_id=%s full_name_set=%s email_set=%s pin_set=%s "
        "phones_added=%s phones_removed=%s",
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


def list_client_anis(db: Session, *, service_slug: str, client_id: int) -> dict:
    """Lista cada ANI registrado para un cliente en un servicio."""
    svc = _get_service(db, service_slug)
    client = db.query(Client).filter_by(service_id=svc.id, client_id=client_id).first()
    if not client:
        raise ClientNotFound(f"Client {client_id} not found in service '{service_slug}'")

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


def create_client_ani(db: Session, *, service_slug: str, client_id: int, ani: str) -> dict:
    """Crea (o agrega de forma idempotente) un mapeo de ANI para un cliente existente."""
    svc = _get_service(db, service_slug)
    client = db.query(Client).filter_by(service_id=svc.id, client_id=client_id).first()
    if not client:
        raise ClientNotFound(f"Client {client_id} not found in service '{service_slug}'")

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


def delete_client_ani(db: Session, *, service_slug: str, client_id: int, ani: str) -> dict:
    """Elimina un mapeo de ANI de un cliente."""
    svc = _get_service(db, service_slug)
    client = db.query(Client).filter_by(service_id=svc.id, client_id=client_id).first()
    if not client:
        raise ClientNotFound(f"Client {client_id} not found in service '{service_slug}'")

    ani_row = db.query(ClientAni).filter_by(service_id=svc.id, client_id=client_id, ani=ani).first()
    if not ani_row:
        raise ClientAniNotFound(f"ANI {ani} not found for client {client_id} in service '{service_slug}'")

    db.delete(ani_row)
    db.commit()

    return {
        "ok": True,
        "service": service_slug,
        "client_id": client_id,
        "ani": ani,
        "deleted": True,
    }
