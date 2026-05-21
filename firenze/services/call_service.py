"""Seguimiento de llamadas en línea - insertar, eliminar, actualizar, y búsqueda de llamadas activas.

Tanto la API como la CLI llaman a estas funciones - ninguna lógica comercial vive en
enrutadores o comandos CLI. MySQL es la fuente de verdad; Redis es una
caché caliente consumida por lectores PHP heredados y tableros.
"""

import logging

import redis
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from firenze.models.call import OnlineCalls
from firenze.redis import call_state

logger = logging.getLogger("firenze")


def insert_call(
    db: Session,
    service: str,
    ani: str,
    did: str,
    client_id: int,
    operator: int = 0,
    redis_conn: redis.Redis | None = None,
) -> dict:
    """Inserta un registro de llamada en línea.

    Retorna ``{"ok": False, "reason": "call-already-active"}`` si una llamada para
    este ANI ya está registrada para el servicio (protección contra llamadas duplicadas).
    Idempotente en el camino feliz - la restricción única en ``(service, ani)``
    es la autoridad.
    """
    call = OnlineCalls(service=service, ani=ani, did=did, client_id=client_id, operator=operator)
    db.add(call)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        logger.warning(
            "insert_call: IntegrityError (likely duplicate active call) for service=%r ani=%r did=%r client_id=%s: %s",
            service,
            ani,
            did,
            client_id,
            exc,
        )
        return {"ok": False, "reason": "call-already-active"}
    db.refresh(call)

    if redis_conn is not None:
        call_state.set_call(
            redis_conn,
            service,
            ani,
            did=did,
            operator=operator,
            client_id=client_id,
            created_at=int(call.created_at.timestamp()) if call.created_at else None,
        )

    return {"ok": True}


def delete_call(
    db: Session,
    service: str,
    ani: str,
    redis_conn: redis.Redis | None = None,
) -> dict:
    """Elimina un registro de llamada en línea.

    Idempotente - sin error si el registro no existe (cubre casos donde
    el manejador h de dialplan se dispara incluso si insert nunca se ejecutó).
    """
    call = db.query(OnlineCalls).filter_by(service=service, ani=ani).first()
    if call:
        db.delete(call)
        db.commit()

    if redis_conn is not None:
        call_state.delete_call(redis_conn, service, ani)

    return {"ok": True}


def update_call_operator(
    db: Session,
    service: str,
    ani: str,
    operator: int,
    redis_conn: redis.Redis | None = None,
) -> dict:
    """Actualiza el número de operador asignado en un registro de llamada activa.

    Se llama después de que el operador ha sido seleccionado y antes de que comience la marcación.
    Retorna ``{"ok": False}`` si no se encuentra ninguna llamada coincidente.
    """
    call = db.query(OnlineCalls).filter_by(service=service, ani=ani).first()
    if not call:
        logger.warning(
            "update_call_operator: no active OnlineCalls row for service=%r ani=%r (operator=%s)",
            service,
            ani,
            operator,
        )
        return {"ok": False, "reason": "call-not-found"}
    call.operator = operator
    db.commit()

    if redis_conn is not None:
        call_state.update_operator(redis_conn, service, ani, operator)

    return {"ok": True}


def get_active_call(db: Session, service: str, ani: str) -> dict:
    """Verifica si un ANI ya tiene una llamada activa para el servicio.

    Retorna ``{"llamada_activa": "true"}`` o ``{"llamada_activa": "false"}``.
    Los valores de cadena coinciden con la convención de dialplan de Asterisk para comparaciones JSON_DECODE.
    """
    call = db.query(OnlineCalls).filter_by(service=service, ani=ani).first()
    return {"llamada_activa": "true" if call else "false"}
