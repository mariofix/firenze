"""Operator login, logout, and availability management.

Both the API and CLI call these functions — no business logic lives in
routers or CLI commands.
"""

from typing import Optional

import redis
from sqlalchemy.orm import Session

from firenze.models import Operator
from firenze.models.operator import OperatorPhone
from firenze.redis import operator_state


class OperatorNotFound(Exception):
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
