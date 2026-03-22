"""Operator login, logout, availability management, and call-time selection.

Both the API and CLI call these functions — no business logic lives in
routers or CLI commands.
"""

import secrets
from typing import Optional

import redis
from sqlalchemy.orm import Session

from firenze.models import Operator
from firenze.models.operator import OperatorPhone
from firenze.redis import operator_state


class OperatorNotFound(Exception):
    pass


class OperatorUnavailable(Exception):
    pass


class OperatorNoPhone(Exception):
    pass


def _get_operator(db: Session, number: int) -> Operator:
    op = db.query(Operator).filter_by(number=number).first()
    if not op:
        raise OperatorNotFound(f"Operator {number} not found")
    return op


def _get_operator_by_phone(db: Session, ani: str) -> Operator:
    phone = (
        db.query(OperatorPhone)
        .filter_by(number=ani, enabled=True)
        .first()
    )
    if not phone or not phone.operator:
        raise OperatorNotFound(f"No operator found for phone {ani}")
    return phone.operator


def login(
    db: Session, number: int, redis_conn: Optional[redis.Redis] = None
) -> Operator:
    """Mark operator as logged in and available in DB and Redis."""
    op = _get_operator(db, number)
    op.loggedin = True
    op.available = True
    db.commit()
    db.refresh(op)

    if op.enable_valkey and redis_conn:
        operator_state.set_state(
            redis_conn, op.number, loggedin=True, available=True, lastcall=0
        )

    return op


def logout(
    db: Session, number: int, redis_conn: Optional[redis.Redis] = None
) -> Operator:
    """Mark operator as logged out and unavailable in DB and Redis."""
    op = _get_operator(db, number)
    op.loggedin = False
    op.available = False
    db.commit()
    db.refresh(op)

    if op.enable_valkey and redis_conn:
        operator_state.set_state(
            redis_conn, op.number, loggedin=False, available=False
        )

    return op


def login_by_phone(
    db: Session, ani: str, redis_conn: Optional[redis.Redis] = None
) -> Operator:
    """Look up operator by phone ANI and mark as logged in and available."""
    op = _get_operator_by_phone(db, ani)
    return login(db, op.number, redis_conn)


def logout_by_phone(
    db: Session, ani: str, redis_conn: Optional[redis.Redis] = None
) -> Operator:
    """Look up operator by phone ANI and mark as logged out and unavailable."""
    op = _get_operator_by_phone(db, ani)
    return logout(db, op.number, redis_conn)


def get_menu(
    db: Session, redis_conn: Optional[redis.Redis] = None
) -> dict:
    """Return count of available operators and a Playback-ready audio string.

    Audio string is ``&``-joined from ``Operator.audio_file``, ordered by
    ``Operator.option``. Operators with no ``audio_file`` are counted in
    ``disponibles`` but omitted from the audio string.

    Used by ``GET /agi/operators/menu``.
    """
    operators = (
        db.query(Operator)
        .filter_by(loggedin=True)
        .order_by(Operator.option)
        .all()
    )

    available = []
    for op in operators:
        if redis_conn and op.enable_valkey:
            state = operator_state.get_state(redis_conn, op.number)
            is_available = state["available"] if state else op.available
        else:
            is_available = op.available
        if is_available:
            available.append(op)

    audio_parts = [op.audio_file for op in available if op.audio_file]
    return {
        "disponibles": len(available),
        "audio_str": "&".join(audio_parts),
    }


def select_operator(
    db: Session,
    mode: str,
    redis_conn: Optional[redis.Redis] = None,
    selection: Optional[str] = None,
) -> dict:
    """Atomically verify operator availability, mark busy, and return operator info.

    ``mode`` is ``"option"`` (caller picked a specific operator by IVR digit)
    or ``"random"`` (automatic selection).  For ``"option"`` mode, ``selection``
    must be the ``Operator.option`` value (e.g. ``"01"``).

    Uses ``SELECT FOR UPDATE`` to prevent two concurrent calls from grabbing
    the same operator.

    Returns a dict with operator details on success, or ``{"ok": False, ...}``
    if no suitable operator is available.
    """
    if mode == "option":
        op = (
            db.query(Operator)
            .filter_by(option=selection, loggedin=True, available=True)
            .with_for_update()
            .first()
        )
        if not op:
            return {"ok": False, "reason": "operator-busy"}
    else:
        # Get candidates without lock first to avoid locking the whole table.
        candidate_numbers = [
            row[0]
            for row in db.query(Operator.number)
            .filter_by(loggedin=True, available=True)
            .all()
        ]
        if not candidate_numbers:
            return {"ok": False, "reason": "no-operators"}

        remaining = list(candidate_numbers)
        op = None
        while remaining:
            num = secrets.choice(remaining)
            remaining.remove(num)
            candidate = (
                db.query(Operator)
                .filter_by(number=num, loggedin=True, available=True)
                .with_for_update()
                .first()
            )
            if candidate:
                op = candidate
                break

        if not op:
            return {"ok": False, "reason": "no-operators"}

    op.available = False
    db.commit()

    if redis_conn and op.enable_valkey:
        operator_state.set_state(
            redis_conn, op.number, loggedin=True, available=False
        )

    phone = next((p for p in op.numbers if p.contact and p.enabled), None)
    if not phone:
        op.available = True
        db.commit()
        return {"ok": False, "reason": "no-phone-configured"}

    return {
        "ok": True,
        "operador_numero": str(op.number),
        "operador_nombre": op.name,
        "operador_telefono": phone.number,
        "operador_trunk": phone.trunk or "",
    }


def release_operator(
    db: Session, number: int, redis_conn: Optional[redis.Redis] = None
) -> Operator:
    """Mark operator as available again after a call ends.

    Thin wrapper around ``set_availability`` — exists so the AGI endpoint
    has a clear, intent-named function to call.
    """
    return set_availability(db, number, available=True, redis_conn=redis_conn)


def set_availability(
    db: Session,
    number: int,
    available: bool,
    redis_conn: Optional[redis.Redis] = None,
) -> Operator:
    """Toggle availability without changing login state."""
    op = _get_operator(db, number)
    op.available = available
    db.commit()
    db.refresh(op)

    if op.enable_valkey and redis_conn:
        current = operator_state.get_state(redis_conn, op.number)
        loggedin = current["loggedin"] if current else op.loggedin
        operator_state.set_state(
            redis_conn, op.number, loggedin=loggedin, available=available
        )

    return op
