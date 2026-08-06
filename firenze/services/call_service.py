"""Seguimiento de llamadas en línea - insertar, eliminar, actualizar, y búsqueda de llamadas activas.

Tanto la API como la CLI llaman a estas funciones - ninguna lógica comercial vive en
enrutadores o comandos CLI.
"""

import logging

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError

from ..models.call import OnlineCalls

logger = logging.getLogger("firenze")


def insert_call(
    db: SQLAlchemy,
    service: str,
    ani: str,
    did: str,
    client_id: int,
    operator: int = 0,
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

    return {"ok": True}


def delete_call(
    db: SQLAlchemy,
    service: str,
    ani: str,
) -> dict:
    """Elimina un registro de llamada en línea.

    Idempotente - sin error si el registro no existe (cubre casos donde
    el manejador h de dialplan se dispara incluso si insert nunca se ejecutó).
    """
    call = db.query(OnlineCalls).filter_by(service=service, ani=ani).first()
    if call:
        db.delete(call)
        db.commit()

    return {"ok": True}


def update_call_operator(
    db: SQLAlchemy,
    service: str,
    ani: str,
    operator: int,
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

    return {"ok": True}


def get_active_call(db: SQLAlchemy, service: str, ani: str) -> dict:
    """Verifica si un ANI ya tiene una llamada activa para el servicio.

    Retorna ``{"llamada_activa": "true"}`` o ``{"llamada_activa": "false"}``.
    Los valores de cadena coinciden con la convención de dialplan de Asterisk para comparaciones JSON_DECODE.
    """
    call = db.query(OnlineCalls).filter_by(service=service, ani=ani).first()
    return {"llamada_activa": "true" if call else "false"}
