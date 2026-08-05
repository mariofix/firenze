"""Inicio de sesión de operador, cierre de sesión, administración de disponibilidad y selección de tiempo de llamada.

Tanto la API como la CLI llaman a estas funciones — ninguna lógica comercial vive en
enrutadores o comandos CLI.
"""

import datetime
import logging
import secrets
import time

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
    """Busca un operador por su dígito de opción del menú IVR.

    ``Operator.option`` es una columna ``String(2)`` pero los valores se almacenan
    sin ceros a la izquierda ('1', '2', ..., '99'). El dialplan puede enviar
    '1' o '01', así que comparamos numéricamente: convertimos tanto la columna
    como la entrada a int. Coincide con el comportamiento de ``select_operator``.
    """
    try:
        option_int = int(option)
    except (TypeError, ValueError):
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


def login(db: Session, number: int, redis_conn: redis.Redis | None = None) -> Operator:
    """Marca el operador como conectado y disponible en DB y Redis."""
    op = _get_operator(db, number)
    op.loggedin = True
    op.available = True
    db.commit()
    db.refresh(op)

    if op.enable_valkey and redis_conn:
        operator_state.set_state(redis_conn, op.number, loggedin=True, available=True, lastcall=0)

    return op


def logout(db: Session, number: int, redis_conn: redis.Redis | None = None) -> Operator:
    """Marca el operador como desconectado e indisponible en DB y Redis."""
    op = _get_operator(db, number)
    op.loggedin = False
    op.available = False
    db.commit()
    db.refresh(op)

    if op.enable_valkey and redis_conn:
        operator_state.set_state(redis_conn, op.number, loggedin=False, available=False)

    return op


def login_by_phone(db: Session, ani: str, redis_conn: redis.Redis | None = None) -> Operator:
    """Busca operador por ANI de teléfono y marca como conectado y disponible."""
    op = _get_operator_by_phone(db, ani)
    return login(db, op.number, redis_conn)


def logout_by_phone(db: Session, ani: str, redis_conn: redis.Redis | None = None) -> Operator:
    """Busca operador por ANI de teléfono y marca como desconectado e indisponible."""
    op = _get_operator_by_phone(db, ani)
    return logout(db, op.number, redis_conn)


def get_menu(db: Session, redis_conn: redis.Redis | None = None) -> dict:
    """Retorna conteo de operadores disponibles y una cadena de audio lista para Playback.

    La cadena de audio se une con ``&`` desde ``Operator.audio_file``, ordenada por
    ``Operator.option``. Los operadores sin ``audio_file`` se cuentan en
    ``disponibles`` pero se omiten de la cadena de audio.

    Usado por ``GET /agi/operators/menu``.
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
    number: int | None = None,
    ani: str | None = None,
    option: str | None = None,
) -> Operator:
    """Busca un operador por uno de tres identificadores.

    Exactamente uno de ``number``, ``ani`` u ``option`` debe ser proporcionado.
    Se intenta en ese orden, así que si se pasan más de uno, el primero
    no vacío gana.

    Args:
        number: el número interno del operador (p. ej. 1001). Utilizado por el
            panel de administración y herramientas CLI.
        ani: un número de teléfono registrado para el operador (en cualquier formato
            almacenado en ``OperatorPhone.number``). Utilizado por el
            flujo ``[tarotista-login]`` que identifica al operador por
            la línea desde la que llama.
        option: el dígito del menú IVR que presionó la persona que llama (p. ej. "1" o "01").
            Utilizado por el dialplan después de que la persona que llama elige un operador del
            menú representado por ``/operators/menu``. Rellenado con ceros
            internamente; tanto "1" como "01" se resuelven al mismo operador.

    Retorna:
        El objeto ORM ``Operator`` coincidente, o ``None`` si ningún
        identificador fue proporcionado.

    Genera:
        OperatorNotFound: si el identificador proporcionado no coincide con ningún
            operador.
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
    redis_conn: redis.Redis | None = None,
    selection: str | None = None,
) -> dict:
    """Verifica atómicamente disponibilidad del operador, marca como ocupado, y retorna info del operador.

    ``mode`` es ``"option"`` (la persona que llama eligió un operador específico por dígito IVR)
    o ``"random"`` (selección automática). Para modo ``"option"``, ``selection``
    debe ser el valor ``Operator.option`` (p. ej. ``"01"``).

    Usa ``SELECT FOR UPDATE`` para prevenir que dos llamadas concurrentes agarren
    el mismo operador.

    Retorna un dict con detalles del operador en caso de éxito, o ``{"ok": False, ...}``
    si ningún operador adecuado está disponible.
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
            "select_operator: operator number=%s option=%r has no contact+enabled "
            "OperatorPhone; rolling availability back",
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


def release_operator(db: Session, number: int, redis_conn: redis.Redis | None = None) -> Operator:
    """Marca el operador como disponible de nuevo después de que termina una llamada.

    Estampa ``lastcall`` en Redis para que podamos ver cuándo fue la última vez que el operador
    terminó una llamada (utilizado para detección de "olvidó desconectarse" e informes de actividad).
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
    redis_conn: redis.Redis | None = None,
    lastcall: int | None = None,
) -> Operator:
    """Cambia disponibilidad sin cambiar estado de conexión.

    Cuando ``lastcall`` se proporciona, se escribe en Redis; de lo contrario, la
    marca de tiempo existente se preserva por ``operator_state.set_state``.
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
