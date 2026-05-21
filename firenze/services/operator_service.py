"""Operator login, logout, availability management, and call-time selection.

Both the API and CLI call these functions — no business logic lives in
routers or CLI commands.
"""

import datetime
import logging
import secrets
import time
from typing import Optional

import redis
from sqlalchemy import Integer, cast
from sqlalchemy.orm import Session

from firenze.models import Operator
from firenze.models.operator import OperatorPhone
from firenze.redis import operator_state

logger = logging.getLogger("firenze")


class OperatorNotFound(Exception):
    pass


class OperatorUnavailable(Exception):
    pass


class OperatorNoPhone(Exception):
    pass


def _get_operator(db: Session, number: int) -> Operator:
    op = db.query(Operator).filter_by(number=number).first()
    if not op:
        logger.warning("_get_operator: no operator with number=%r", number)
        raise OperatorNotFound(f"Operator {number} not found")
    return op


def _get_operator_by_phone(db: Session, ani: str) -> Operator:
    phone = db.query(OperatorPhone).filter_by(number=ani, enabled=True).first()
    if not phone:
        logger.warning(
            "_get_operator_by_phone: no enabled OperatorPhone with number=%r",
            ani,
        )
        raise OperatorNotFound(f"No operator found for phone {ani}")
    if not phone.operator:
        logger.warning(
            "_get_operator_by_phone: OperatorPhone id=%s number=%r has no linked operator",
            phone.id,
            ani,
        )
        raise OperatorNotFound(f"No operator found for phone {ani}")
    return phone.operator


def _get_operator_by_option(db: Session, option: str) -> Operator:
    """Look up an operator by their IVR menu option digit.

    ``Operator.option`` is a ``String(2)`` column but values are stored
    without leading zeros ('1', '2', ..., '99'). The dialplan may send
    either '1' or '01', so we compare numerically: cast both the column
    and the input to int. Matches ``select_operator``'s behavior.
    """
    try:
        option_int = int(option)
    except TypeError, ValueError:
        logger.warning(
            "_get_operator_by_option: non-numeric option=%r",
            option,
        )
        raise OperatorNotFound(f"No operator with option {option}")
    op = db.query(Operator).filter(cast(Operator.option, Integer) == option_int).first()
    if not op:
        logger.warning(
            "_get_operator_by_option: no operator with option=%d (raw input=%r)",
            option_int,
            option,
        )
        raise OperatorNotFound(f"No operator with option {option}")
    return op


def login(db: Session, number: int, redis_conn: Optional[redis.Redis] = None) -> Operator:
    """Mark operator as logged in and available in DB and Redis."""
    op = _get_operator(db, number)
    op.loggedin = True
    op.available = True
    db.commit()
    db.refresh(op)

    if op.enable_valkey and redis_conn:
        operator_state.set_state(redis_conn, op.number, loggedin=True, available=True, lastcall=0)

    return op


def logout(db: Session, number: int, redis_conn: Optional[redis.Redis] = None) -> Operator:
    """Mark operator as logged out and unavailable in DB and Redis."""
    op = _get_operator(db, number)
    op.loggedin = False
    op.available = False
    db.commit()
    db.refresh(op)

    if op.enable_valkey and redis_conn:
        operator_state.set_state(redis_conn, op.number, loggedin=False, available=False)

    return op


def login_by_phone(db: Session, ani: str, redis_conn: Optional[redis.Redis] = None) -> Operator:
    """Look up operator by phone ANI and mark as logged in and available."""
    op = _get_operator_by_phone(db, ani)
    return login(db, op.number, redis_conn)


def logout_by_phone(db: Session, ani: str, redis_conn: Optional[redis.Redis] = None) -> Operator:
    """Look up operator by phone ANI and mark as logged out and unavailable."""
    op = _get_operator_by_phone(db, ani)
    return logout(db, op.number, redis_conn)


def get_menu(db: Session, redis_conn: Optional[redis.Redis] = None) -> dict:
    """Return count of available operators and a Playback-ready audio string.

    Audio string is ``&``-joined from ``Operator.audio_file``, ordered by
    ``Operator.option``. Operators with no ``audio_file`` are counted in
    ``disponibles`` but omitted from the audio string.

    Used by ``GET /agi/operators/menu``.
    """
    operators = db.query(Operator).filter_by(loggedin=True, available=True).all()
    operators.sort(key=lambda op: int(op.option))

    audio_parts = [op.audio_file for op in operators if op.audio_file]
    return {
        "disponibles": len(operators),
        "audio_str": "&".join(audio_parts),
    }


def info_operator(
    db: Session,
    number: Optional[int] = None,
    ani: Optional[str] = None,
    option: Optional[str] = None,
) -> Operator:
    """Look up an operator by one of three identifiers.

    Exactly one of ``number``, ``ani``, or ``option`` should be provided.
    They are tried in that order, so if more than one is passed the first
    non-empty wins.

    Args:
        number: the operator's internal number (e.g. 1001). Used by the
            admin panel and CLI tools.
        ani: a phone number registered to the operator (in any format
            stored on ``OperatorPhone.number``). Used by the
            ``[tarotista-login]`` flow that identifies the operator by
            the line they are calling from.
        option: the IVR menu digit the caller pressed (e.g. "1" or "01").
            Used by the dialplan after the caller picks an operator from
            the menu rendered by ``/operators/menu``. Zero-padded
            internally; both "1" and "01" resolve to the same operator.

    Returns:
        The matching ``Operator`` ORM object, or ``None`` if no
        identifier was provided.

    Raises:
        OperatorNotFound: if the provided identifier doesn't match any
            operator.
    """
    op = None
    if number:
        op = _get_operator(db, number)
    elif ani:
        op = _get_operator_by_phone(db, ani)
    elif option:
        op = _get_operator_by_option(db, option)
    return op


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
        try:
            selection_int = int(selection)
        except (TypeError, ValueError) as exc:
            logger.error(
                "select_operator: invalid selection=%r for mode=option (%s)",
                selection,
                exc,
            )
            return {"ok": False, "reason": "invalid-selection"}
        op = (
            db.query(Operator)
            .filter(
                cast(Operator.option, Integer) == selection_int,
                Operator.loggedin.is_(True),
                Operator.available.is_(True),
            )
            .with_for_update()
            .first()
        )
        if not op:
            logger.warning(
                "select_operator: no available operator with option=%r (loggedin=True, available=True)",
                selection_int,
            )
            return {"ok": False, "reason": "operator-busy"}
    else:
        # Get candidates without lock first to avoid locking the whole table.
        candidate_numbers = [
            row[0] for row in db.query(Operator.number).filter_by(loggedin=True, available=True).all()
        ]
        if not candidate_numbers:
            logger.warning("select_operator: no candidates (no operator has loggedin=True AND available=True)")
            return {"ok": False, "reason": "no-operators"}

        remaining = list(candidate_numbers)
        op = None
        while remaining:
            num = secrets.choice(remaining)
            remaining.remove(num)
            candidate = (
                db.query(Operator).filter_by(number=num, loggedin=True, available=True).with_for_update().first()
            )
            if candidate:
                op = candidate
                break

        if not op:
            logger.warning(
                "select_operator: all %d candidates lost the race (became unavailable between query and lock)",
                len(candidate_numbers),
            )
            return {"ok": False, "reason": "no-operators"}

    op.available = False
    db.commit()

    if redis_conn and op.enable_valkey:
        operator_state.set_state(
            redis_conn,
            op.number,
            loggedin=True,
            available=False,
            lastcall=int(time.time()),
        )

    phone = next((p for p in op.numbers if p.contact and p.enabled), None)
    if not phone:
        logger.error(
            "select_operator: operator number=%s option=%r has no contact+enabled OperatorPhone; rolling availability back",
            op.number,
            op.option,
        )
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


def release_operator(db: Session, number: int, redis_conn: Optional[redis.Redis] = None) -> Operator:
    """Mark operator as available again after a call ends.

    Stamps ``lastcall`` in Redis so we can see when the operator last wrapped
    up a call (used for "forgot to logout" detection and activity reports).
    """
    return set_availability(
        db,
        number,
        available=True,
        redis_conn=redis_conn,
        lastcall=int(time.time()),
    )


def set_availability(
    db: Session,
    number: int,
    available: bool,
    redis_conn: Optional[redis.Redis] = None,
    lastcall: Optional[int] = None,
) -> Operator:
    """Toggle availability without changing login state.

    When ``lastcall`` is provided it is written to Redis; otherwise the
    existing timestamp is preserved by ``operator_state.set_state``.
    """
    op = _get_operator(db, number)
    op.available = available
    if available:
        op.lastcall = datetime.datetime.now()
    db.commit()
    db.refresh(op)

    if op.enable_valkey and redis_conn:
        current = operator_state.get_state(redis_conn, op.number)
        loggedin = current["loggedin"] if current else op.loggedin
        operator_state.set_state(
            redis_conn,
            op.number,
            loggedin=loggedin,
            available=available,
            lastcall=lastcall,
        )

    return op
