"""Extremos AGI — llamados por el dialplan de Asterisk a través de CURL().

Estos retornan dicts JSON planos con los nombres de variable exactos que el dialplan espera.
Sin autenticación JWT — protegido por enlace solo a localhost / LAN.
"""

import logging
import time
from hashlib import sha256

import redis
from fastapi import APIRouter, Depends, Form, HTTPException, Query
from sqlalchemy.orm import Session

from firenze.dependencies import get_db, get_redis
from firenze.services.audit_service import create_audit
from firenze.services.call_service import (
    delete_call,
    get_active_call,
    insert_call,
    update_call_operator,
)
from firenze.services.client_service import (
    ClientNotFound,
    ServiceNotFound,
)
from firenze.services.client_service import deduct_credits as svc_deduct
from firenze.services.client_service import lookup as svc_lookup
from firenze.services.client_service import update_ani_stats as svc_ani_stats
from firenze.services.credit_service import compute_call_limit
from firenze.services.did_service import resolve_did
from firenze.services.dnc_service import check_dnc
from firenze.services.measurement_service import send_measurement_event
from firenze.services.operator_service import OperatorNotFound, login_by_phone, logout_by_phone
from firenze.services.operator_service import get_menu as svc_get_menu
from firenze.services.operator_service import info_operator as svc_operator
from firenze.services.operator_service import release_operator as svc_release
from firenze.services.operator_service import select_operator as svc_select

logger = logging.getLogger("firenze")

agiRouter = APIRouter(prefix="/agi", tags=["agi"])


def _session_client_id(uniqueid: str | None = None, channel: str | None = None) -> str | None:
    session_source = uniqueid or channel
    if not session_source:
        return None
    return sha256(session_source.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# DNC
# ---------------------------------------------------------------------------


@agiRouter.get("/dnc/{ani}")
def agi_dnc_check(
    ani: str,
    uniqueid: str | None = Query(default=None, description="Asterisk UNIQUEID for this call session"),
    channel: str | None = Query(default=None, description="Asterisk channel name for this call session"),
    db: Session = Depends(get_db),
):
    """Verifica si el ANI está en la lista de No Llamar."""
    session_client_id = _session_client_id(uniqueid=uniqueid, channel=channel)
    started_at = time.perf_counter()
    in_dnc = check_dnc(db, ani)
    query_duration_ms = round((time.perf_counter() - started_at) * 1000, 3)
    send_measurement_event(
        "call_start",
        {
            "query_ani": ani,
            "query_duration_ms": query_duration_ms,
        },
        client_id=session_client_id,
    )
    return {"dnc": "YES" if in_dnc else "NO"}


# ---------------------------------------------------------------------------
# Service / DID resolution
# ---------------------------------------------------------------------------


@agiRouter.get("/services/did/{did}")
def agi_did_lookup(
    did: str,
    uniqueid: str | None = Query(default=None, description="Asterisk UNIQUEID for this call session"),
    channel: str | None = Query(default=None, description="Asterisk channel name for this call session"),
    db: Session = Depends(get_db),
):
    """Resuelve un DID a su configuración de servicio.

    Retorna el conjunto completo de variables de canal que el contexto
    dialplan unificado ``[prepago-service]`` necesita — una llamada CURL en lugar de
    múltiples spawns de AGI.

    Campos de respuesta:
        siguiente    — contexto de Asterisk para Goto (``"prepago-service"`` para todos los DIDs nuevos)
        servicio     — slug del servicio (p. ej. ``"alotarot"``, ``"fonotarot-cl"``)
        auth_method  — ``"ani"`` o ``"pin"``
        intro_audio  — cadena compatible con Playback (p. ej. ``"zvn/intro-alotarot"``)
    """
    session_client_id = _session_client_id(uniqueid=uniqueid, channel=channel)
    started_at = time.perf_counter()
    data = resolve_did(db, did)
    query_duration_ms = round((time.perf_counter() - started_at) * 1000, 3)
    send_measurement_event(
        "service_lookup",
        {
            "query_did": did,
            "assigned_context": data.get("siguiente", ""),
            "service": data.get("servicio", ""),
            "found": str(bool(data.get("servicio"))).lower(),
            "query_duration_ms": query_duration_ms,
        },
        client_id=session_client_id,
    )
    return data


# ---------------------------------------------------------------------------
# Credits
# ---------------------------------------------------------------------------


@agiRouter.get("/credits/limit")
def agi_credit_limit(
    seconds: int = Query(..., description="Credit balance in seconds"),
    uniqueid: str | None = Query(default=None, description="Asterisk UNIQUEID for this call session"),
    channel: str | None = Query(default=None, description="Asterisk channel name for this call session"),
):
    """Calcula timeout de llamada y archivo de audio para un saldo de crédito dado.

    Reemplaza la escalera ``[limite-saldo]`` de dialplan de 150 líneas.
    """
    session_client_id = _session_client_id(uniqueid=uniqueid, channel=channel)
    started_at = time.perf_counter()
    result = compute_call_limit(seconds)
    query_duration_ms = round((time.perf_counter() - started_at) * 1000, 3)
    send_measurement_event(
        "credit_compute",
        {
            "requested_seconds": seconds,
            "timeout": result.get("timeout"),
            "audio": result.get("audio", ""),
            "minutes": result.get("minutes"),
            "query_duration_ms": query_duration_ms,
        },
        client_id=session_client_id,
    )
    return result


# ---------------------------------------------------------------------------
# Client lookup and deduction
# ---------------------------------------------------------------------------


@agiRouter.get("/clients/lookup")
def agi_client_lookup(
    service: str = Query(..., description="Service slug, e.g. fonotarot-latam"),
    identifier: str = Query(..., description="Client identifier (ANI or PIN)"),
    db: Session = Depends(get_db),
):
    """Busca un cliente por servicio e identificador.

    Retorna ``{clientid, segundos}`` — el contrato que el dialplan espera.
    Retorna ``{clientid: 0, segundos: 0}`` si no se encuentra (el dialplan lo maneja).
    """
    svc_ani_stats(db, service, identifier)
    try:
        data = svc_lookup(db, service, identifier)
        more_data = compute_call_limit(data["segundos"])
        data.update(more_data)
        return data
    except ServiceNotFound as e:
        logger.warning(
            "agi_client_lookup: ServiceNotFound for service=%r identifier=%r: %s",
            service,
            identifier,
            e,
        )
        raise HTTPException(status_code=404, detail=str(e))


@agiRouter.post("/clients/{service}/{client_id}/deduct")
def agi_client_deduct(
    service: str,
    client_id: int,
    seconds: int = Form(..., description="Seconds to deduct"),
    db: Session = Depends(get_db),
):
    """Descuenta créditos (segundos) del saldo de un cliente.

    Llamado desde el manejador hangup ``[llama-operador]`` después de que termina una llamada.
    """
    try:
        data_out = svc_deduct(db, service, client_id, seconds)
        data_out.update({"client_id": client_id, "service": service})
        create_audit(db, title="resta_saldo", category="INFO", called_from="firenze.api.agi.agi_client_deduct()", data=data_out)
        return data_out
    except ServiceNotFound as e:
        logger.warning(
            "agi_client_deduct: ServiceNotFound for service=%r client_id=%s seconds=%s: %s",
            service,
            client_id,
            seconds,
            e,
        )
        raise HTTPException(status_code=404, detail=str(e))
    except ClientNotFound as e:
        logger.warning(
            "agi_client_deduct: ClientNotFound for service=%r client_id=%s seconds=%s: %s",
            service,
            client_id,
            seconds,
            e,
        )
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# Online call tracking
# ---------------------------------------------------------------------------


@agiRouter.post("/calls/online")
def agi_call_insert(
    service: str = Form(...),
    ani: str = Form(...),
    did: str = Form(...),
    client_id: int = Form(...),
    operator: int = Form(default=0),
    db: Session = Depends(get_db),
    redis_conn: redis.Redis | None = Depends(get_redis),
):
    """Inserta un registro de llamada en línea.

    Llamado desde ``[auth-ani]`` / ``[auth-pin]`` después de pasar verificaciones de autenticación y crédito.
    Retorna ``{"ok": false, "reason": "call-already-active"}`` en caso de duplicado.
    """
    return insert_call(db, service, ani, did, client_id, operator, redis_conn)


@agiRouter.post("/calls/online/{service}/{ani}/close")
def agi_call_close(
    service: str,
    ani: str,
    db: Session = Depends(get_db),
    redis_conn: redis.Redis | None = Depends(get_redis),
):
    """Elimina un registro de llamada en línea.

    Idempotente — seguro para llamar desde múltiples manejadores ``h``.
    Llamado vía ``POST /calls/online/{service}/{ani}/close`` con cuerpo ``_=1``
    ya que CURL() de Asterisk solo soporta de forma fiable GET y POST-con-cuerpo.
    """
    return delete_call(db, service, ani, redis_conn)


@agiRouter.post("/calls/online/{service}/{ani}/assign")
def agi_call_assign_operator(
    service: str,
    ani: str,
    operator: int = Form(..., description="Operator number assigned to this call"),
    db: Session = Depends(get_db),
    redis_conn: redis.Redis | None = Depends(get_redis),
):
    """Actualiza el operador asignado a una llamada activa.

    Llamado después de que ``[selecciona-operador]`` se completa y antes de marcar.
    Acepta ``operator`` como un campo de cuerpo de formulario.
    """
    return update_call_operator(db, service, ani, operator, redis_conn)


@agiRouter.get("/calls/online/{service}/{ani}")
def agi_call_get(service: str, ani: str, db: Session = Depends(get_db)):
    """Verifica si un ANI tiene una llamada activa para el servicio.

    Retorna ``{"llamada_activa": "true"}`` o ``{"llamada_activa": "false"}``.
    """
    return get_active_call(db, service, ani)


# ---------------------------------------------------------------------------
# Operator selection
# ---------------------------------------------------------------------------


@agiRouter.get("/operators/menu")
def agi_operators_menu(
    db: Session = Depends(get_db),
    redis_conn: redis.Redis | None = Depends(get_redis),
):
    """Retorna conteo de operadores disponibles y una cadena de audio lista para Playback.

    Reemplaza ``Agi(${AUDIOTEX},ejecutivos_disponibles,7)`` en el dialplan.

    Respuesta:
        disponibles  — número de operadores disponibles
        audio_str    — cadena Playback unida con ``&`` de archivos de audio de operador
    """
    return svc_get_menu(db, redis_conn)


@agiRouter.post("/operators/select")
def agi_operator_select(
    mode: str = Form(..., description='"random" or "option"'),
    selection: str | None = Form(default=None, description="Operator option digits, required when mode=option"),
    db: Session = Depends(get_db),
    redis_conn: redis.Redis | None = Depends(get_redis),
):
    """Selecciona atómicamente un operador disponible y lo marca como ocupado.

    Reemplaza ``Agi(${AUDIOTEX},ejecutivo_aleatorio,7)`` y
    ``Agi(${AUDIOTEX},info_ejecutivo,opcion,...)`` en el dialplan.

    Respuesta en caso de éxito:
        ok                — verdadero
        operador_numero   — número interno del operador
        operador_nombre   — nombre del operador
        operador_telefono — número de teléfono de contacto del operador
        operador_trunk    — troncal SIP por el que marcar

    Respuesta en caso de fallo:
        ok      — falso
        reason  — "operator-busy" | "no-operators" | "no-phone-configured"
    """
    return svc_select(db, mode=mode, selection=selection, redis_conn=redis_conn)


# ---------------------------------------------------------------------------
# Operator info
# ---------------------------------------------------------------------------


@agiRouter.get("/operators/by-option/{option}")
def agi_operator_info_by_option(
    option: str,
    db: Session = Depends(get_db),
    redis_conn: redis.Redis | None = Depends(get_redis),
):
    """Traduce un dígito de menú IVR en la información de contacto del operador.

    Utilizado por el dialplan después de que la persona que llama elige un operador del menú
    reproducido por ``/operators/menu``. El dialplan necesita el
    número interno del operador (para pasar a ``/operators/select``), nombre (para logs y
    CDR), teléfono (para ``Dial()``), y troncal (para la
    tecnología de canal de salida). Este extremo proporciona los cuatro en un viaje redondo
    y NO reclama el operador -- el reclamo atómico sucede más tarde a través de
    ``/operators/select``.

    La división existe porque típicamente hay una ventana de 5-10 segundos
    entre renderizar menú y Dial (la persona que llama oye opciones, elige una, el audio
    termina). Reclamar en la selección bloquearía un operador durante esa
    ventana completa incluso si la llamada se abandona después. Reclamar
    justo antes de Dial mantiene a los operadores libres el mayor tiempo posible al
    costo de una pequeña ventana de condición de carrera que ``/operators/select`` resuelve con
    ``SELECT FOR UPDATE``.

    Parámetro de ruta:
        option: el dígito de menú que presionó la persona que llama, p. ej. "1" o "01".
                Comparado numéricamente; ambas formas funcionan sin importar cómo
                se almacena la columna.

    Respuesta en caso de éxito:
        ok                : verdadero
        operador_numero   : número interno del operador (cadena,
                            pasar a ``/operators/select`` como ``selection``)
        operador_nombre   : nombre de visualización del operador
        operador_telefono : número de teléfono de contacto del operador para Dial()
        operador_trunk    : troncal SIP por el que marcar, puede ser cadena vacía
        loggedin          : verdadero/falso, si el operador está conectado
                            (asesor: el reclamo real está en ``/operators/select``)
        available         : verdadero/falso, si el operador está libre actualmente
                            (asesor: el reclamo real está en ``/operators/select``)

    Respuesta en caso de fallo:
        ok      : falso
        reason  : "not-found"           - ningún operador tiene este dígito de opción
                  "no-phone-configured" - el operador existe pero no tiene
                                          teléfono de contacto habilitado para Dial()
    """
    try:
        op = svc_operator(db, option=option)
    except OperatorNotFound as e:
        logger.warning(
            "agi_operator_info_by_option: OperatorNotFound for option=%r: %s",
            option,
            e,
        )
        return {"ok": False, "reason": "not-found"}

    phone = next((p for p in op.numbers if p.contact and p.enabled), None)
    if not phone:
        logger.warning(
            "agi_operator_info_by_option: operator number=%s option=%r "
            "has no contact+enabled OperatorPhone (numbers=%d)",
            op.number,
            option,
            len(op.numbers),
        )
        return {"ok": False, "reason": "no-phone-configured"}

    ok_status = True
    ok_meessage = None
    if op.available == 0 or op.loggedin == 0:
        ok_status = False
        ok_meessage = f"{op.loggedin=} {op.available=}"
    return {
        "ok": ok_status,
        "operador_numero": str(op.number),
        "operador_nombre": op.name,
        "operador_telefono": phone.number,
        "operador_trunk": phone.trunk or "",
        "loggedin": op.loggedin,
        "available": op.available,
        "reason": ok_meessage,
    }


@agiRouter.get("/operators/by-ani/{ani}")
def agi_operator_info_by_ani(
    ani: str,
    db: Session = Depends(get_db),
    redis_conn: redis.Redis | None = Depends(get_redis),
):
    """Busca un operador por uno de sus números de teléfono registrados (ANI).

    Utilizado cuando el número de teléfono de la persona que llama identifica al operador,
    p. ej. un operador que llama desde su propia línea. Coincide contra
    ``OperatorPhone.number`` donde ``enabled=True``.

    Retorna la misma forma plana que ``/operators/by-option/{option}`` así
    el dialplan puede ``JSON_DECODE`` los mismos nombres de campo sin importar
    qué búsqueda utilizó. El campo ``operador_telefono`` es el
    teléfono de contacto del operador (el marcado con ``contact=True`` y
    ``enabled=True``), que puede diferir del ANI de entrada -- el ANI
    es solo el identificador, el teléfono de contacto es lo que ``Dial()``.

    Parámetro de ruta:
        ani: número de teléfono en el formato almacenado en ``OperatorPhone.number``.

    Respuesta en caso de éxito:
        ok                : verdadero
        operador_numero   : número interno del operador (cadena)
        operador_nombre   : nombre de visualización del operador
        operador_telefono : teléfono de contacto del operador para Dial()
        operador_trunk    : troncal SIP por el que marcar, puede ser cadena vacía
        loggedin          : verdadero/falso, si el operador está conectado
        available         : verdadero/falso, si el operador está libre actualmente

    Respuesta en caso de fallo:
        ok      : falso
        reason  : "not-found"           - ningún teléfono habilitado coincide con el ANI
                  "no-phone-configured" - el operador existe pero no tiene
                                          teléfono de contacto habilitado para Dial()
    """
    try:
        op = svc_operator(db, ani=ani)
    except OperatorNotFound as e:
        logger.warning(
            "agi_operator_info_by_ani: OperatorNotFound for ani=%r: %s",
            ani,
            e,
        )
        return {"ok": False, "reason": "not-found"}

    phone = next((p for p in op.numbers if p.contact and p.enabled), None)
    if not phone:
        logger.warning(
            "agi_operator_info_by_ani: operator number=%s ani=%r has no contact+enabled OperatorPhone (numbers=%d)",
            op.number,
            ani,
            len(op.numbers),
        )
        return {"ok": False, "reason": "no-phone-configured"}

    return {
        "ok": True,
        "operador_numero": str(op.number),
        "operador_nombre": op.name,
        "operador_telefono": phone.number,
        "operador_trunk": phone.trunk or "",
        "loggedin": op.loggedin,
        "available": op.available,
    }


@agiRouter.post("/operators/{number}/release")
def agi_operator_release(
    number: int,
    db: Session = Depends(get_db),
    redis_conn: redis.Redis | None = Depends(get_redis),
):
    """Marca un operador como disponible de nuevo después de que termina una llamada.

    Llamado desde el manejador hangup ``[llama-operador]`` y en fallo de marcación.
    Reemplaza ``Agi(${AUDIOTEX},cambia_estado,${OPERATOR_NUM},1)``.
    """
    try:
        svc_release(db, number, redis_conn)
    except OperatorNotFound as e:
        logger.warning(
            "agi_operator_release: OperatorNotFound for number=%s: %s",
            number,
            e,
        )
        raise HTTPException(status_code=404, detail=str(e))
    return {"ok": True}


# ---------------------------------------------------------------------------
# Operator login / logout (from dialplan)
# ---------------------------------------------------------------------------


@agiRouter.post("/operators/by-phone/{ani}/login")
def agi_operator_login(
    ani: str,
    uniqueid: str | None = Query(default=None, description="Asterisk UNIQUEID for this call session"),
    channel: str | None = Query(default=None, description="Asterisk channel name for this call session"),
    db: Session = Depends(get_db),
    redis_conn: redis.Redis | None = Depends(get_redis),
):
    """Marca el operador como conectado por su número de teléfono (ANI).

    Llamado desde el contexto dialplan ``[tarotista-login]``.
    """
    session_client_id = _session_client_id(uniqueid=uniqueid, channel=channel)
    started_at = time.perf_counter()
    try:
        login_by_phone(db, ani, redis_conn)
    except OperatorNotFound as e:
        logger.warning(
            "agi_operator_login: OperatorNotFound for ani=%r: %s",
            ani,
            e,
        )
        raise HTTPException(status_code=404, detail=str(e))
    query_duration_ms = round((time.perf_counter() - started_at) * 1000, 3)
    send_measurement_event(
        "operator_login",
        {
            "operator_ani": ani,
            "query_duration_ms": query_duration_ms,
        },
        client_id=session_client_id,
    )
    create_audit(
        db,
        title="operator_login",
        category="INFO",
        called_from="firenze.api.agi.agi_operator_login()",
        data={"ani": ani},
    )
    return {"ok": True}


@agiRouter.post("/operators/by-phone/{ani}/logout")
def agi_operator_logout(
    ani: str,
    uniqueid: str | None = Query(default=None, description="Asterisk UNIQUEID for this call session"),
    channel: str | None = Query(default=None, description="Asterisk channel name for this call session"),
    db: Session = Depends(get_db),
    redis_conn: redis.Redis | None = Depends(get_redis),
):
    """Marca el operador como desconectado por su número de teléfono (ANI).

    Llamado desde el contexto dialplan ``[tarotista-logout]``.
    """
    session_client_id = _session_client_id(uniqueid=uniqueid, channel=channel)
    started_at = time.perf_counter()
    try:
        logout_by_phone(db, ani, redis_conn)
    except OperatorNotFound as e:
        logger.warning(
            "agi_operator_logout: OperatorNotFound for ani=%r: %s",
            ani,
            e,
        )
        raise HTTPException(status_code=404, detail=str(e))
    query_duration_ms = round((time.perf_counter() - started_at) * 1000, 3)
    send_measurement_event(
        "operator_logout",
        {
            "operator_ani": ani,
            "query_duration_ms": query_duration_ms,
        },
        client_id=session_client_id,
    )
    create_audit(
        db,
        title="operator_logout",
        category="INFO",
        called_from="firenze.api.agi.agi_operator_logout()",
        data={"ani": ani},
    )
    return {"ok": True}
