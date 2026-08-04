"""AGI — llamados por el dialplan de Asterisk a través de CURL().

Estos retornan dicts JSON planos con los nombres de variable exactos que el dialplan espera.
Sin autenticación JWT — protegido por enlace solo a localhost / LAN.
"""

import time
from hashlib import sha256

from flask import abort, current_app
from flask.views import MethodView
from flask_smorest import Blueprint
from sqlalchemy import text

from ..extensions import db

# from ..services.audit_service import create_audit
from ..services.call_service import (
    delete_call,
    get_active_call,
    insert_call,
    update_call_operator,
)

# from ..services.client_service import (
#     ClientNotFound,
#     ServiceNotFound,
# )
# from ..services.client_service import deduct_credits as svc_deduct
# from ..services.client_service import lookup as svc_lookup
# from ..services.client_service import update_ani_stats as svc_ani_stats
# from ..services.credit_service import compute_call_limit
from ..services.did_service import resolve_did
from ..services.dnc_service import check_dnc
from .schema import (
    ActiveCallSchema,
    CallAssignFormSchema,
    CallCloseFormSchema,
    CallInsertFormSchema,
    CallResultSchema,
    DidLookupResponseSchema,
    DidQueryArgsSchema,
    DncQueryArgsSchema,
    DncResponseSchema,
)

# from ..services.measurement_service import send_measurement_event
# from ..services.operator_service import OperatorNotFound
# from ..services.operator_service import get_menu as svc_get_menu
# from ..services.operator_service import info_operator as svc_operator
# from ..services.operator_service import login_by_phone, logout_by_phone
# from ..services.operator_service import release_operator as svc_release
# from ..services.operator_service import select_operator as svc_select


bp = Blueprint(
    "agi",
    __name__,
    url_prefix="/agi",
    description="Endpoints AGI — llamados por el dialplan de Asterisk a través de CURL()",
)


def _session_client_id(uniqueid: str | None = None, channel: str | None = None) -> str | None:
    session_source = uniqueid or channel
    if not session_source:
        return None
    return sha256(session_source.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# DNC
# ---------------------------------------------------------------------------
@bp.route("/dnc/<string:ani>")
class DncCheck(MethodView):
    @bp.arguments(DncQueryArgsSchema, location="query")
    @bp.response(200, DncResponseSchema)
    @bp.doc(summary="Verifica si el ANI está en la lista de No Llamar")
    def get(self, args, ani):
        in_dnc = check_dnc(db, ani)
        return {"dnc": "YES" if in_dnc else "NO"}


# ---------------------------------------------------------------------------
# Service / DID resolution
# ---------------------------------------------------------------------------


@bp.route("/services/did/<string:did>")
class DidLookup(MethodView):
    @bp.arguments(DidQueryArgsSchema, location="query")
    @bp.response(200, DidLookupResponseSchema)
    @bp.doc(
        summary="Resuelve un DID a su configuración de servicio",
        description=(
            "Retorna el conjunto completo de variables de canal que el contexto "
            "dialplan unificado `[prepago-service]` necesita — una llamada CURL "
            "en lugar de múltiples spawns de AGI."
        ),
    )
    def get(self, args, did):
        # uniqueid/channel not used in original — kept for parity/logging hooks.
        # If you need session_client_id here too (e.g. for a resolve_did miss
        # measurement event), it's already parsed in args.
        data = resolve_did(db, did)
        if data is None:
            abort(404, message=f"DID '{did}' not found or not configured")
        return data


# ---------------------------------------------------------------------------
# Credits
# # ---------------------------------------------------------------------------


# @bp.get("/credits/limit")
# def agi_credit_limit(
#     seconds: int = Query(..., description="Credit balance in seconds"),
#     uniqueid: str | None = Query(default=None, description="Asterisk UNIQUEID for this call session"),
#     channel: str | None = Query(default=None, description="Asterisk channel name for this call session"),
# ):
#     """Calcula timeout de llamada y archivo de audio para un saldo de crédito dado.

#     Reemplaza la escalera ``[limite-saldo]`` de dialplan de 150 líneas.
#     """
#     session_client_id = _session_client_id(uniqueid=uniqueid, channel=channel)
#     started_at = time.perf_counter()
#     result = compute_call_limit(seconds)
#     query_duration_ms = round((time.perf_counter() - started_at) * 1000, 3)
#     send_measurement_event(
#         "credit_compute",
#         {
#             "requested_seconds": seconds,
#             "minutes": result.get("minutes"),
#             "query_duration_ms": query_duration_ms,
#         },
#         client_id=session_client_id,
#     )
#     return result


# # ---------------------------------------------------------------------------
# # Client lookup and deduction
# # ---------------------------------------------------------------------------


# @bp.get("/clients/lookup")
# def agi_client_lookup(
#     service: str = Query(..., description="Service slug, e.g. fonotarot-latam"),
#     identifier: str = Query(..., description="Client identifier (ANI or PIN)"),
# ):
#     """Busca un cliente por servicio e identificador.

#     Retorna ``{clientid, segundos}`` — el contrato que el dialplan espera.
#     Retorna ``{clientid: 0, segundos: 0}`` si no se encuentra (el dialplan lo maneja).
#     """
#     svc_ani_stats(db, service, identifier)
#     try:
#         data = svc_lookup(db, service, identifier)
#         more_data = compute_call_limit(data["segundos"])
#         data.update(more_data)
#         return data
#     except ServiceNotFound as e:
#         current_app.logger.warning(
#             "agi_client_lookup: ServiceNotFound for service=%r identifier=%r: %s",
#             service,
#             identifier,
#             e,
#         )
#         raise abort(404, detail=str(e))


# @bp.post("/clients/{service}/{client_id}/deduct")
# def agi_client_deduct(
#     service: str,
#     client_id: int,
#     seconds: int = Form(..., description="Seconds to deduct"),
#     operator: str | None = Form(default=None, description="Operator Name"),
#     uniqueid: str | None = Query(default=None, description="Asterisk UNIQUEID for this call session"),
#     channel: str | None = Query(default=None, description="Asterisk channel name for this call session"),
# ):
#     """Descuenta créditos (segundos) del saldo de un cliente.

#     Llamado desde el manejador hangup ``[llama-operador]`` después de que termina una llamada.
#     """
#     segundos = None
#     if channel:
#         current_app.logger.debug(f"agi_client_deduct: Calculando nuevo billsec con CEL y channelname='{channel}'")
#         query = text("""
#             SELECT
#                 TIMESTAMPDIFF(SECOND,
#                     MAX(CASE WHEN eventtype = 'BRIDGE_ENTER' THEN eventtime END),
#                     MAX(CASE WHEN eventtype = 'BRIDGE_EXIT'  THEN eventtime END)
#                 ) AS duration_seconds
#             FROM zvn_asterisk.cel
#             WHERE channame = :channel
#         """)
#         try:
#             row = db.execute(query, {"channel": channel}).first()
#             if row and row.duration_seconds is not None:
#                 current_app.logger.info(f"agi_client_deduct: Nuevos segundos calculados para {channel}: {row.duration_seconds}")
#                 segundos = int(row.duration_seconds)
#         except Exception as e:
#             current_app.logger.warning(e)

#     try:
#         session_client_id = _session_client_id(uniqueid=uniqueid, channel=channel)
#         started_at = time.perf_counter()
#         data_out = svc_deduct(db, service, client_id, segundos or seconds)
#         query_duration_ms = round((time.perf_counter() - started_at) * 1000, 3)
#         data_out.update({"client_id": client_id, "service": service})
#         create_audit(
#             db, title="resta_saldo", category="INFO", called_from="firenze.api.agi.agi_client_deduct()", data=data_out
#         )
#         send_measurement_event(
#             "call_ended",
#             {
#                 "client_id": client_id,
#                 "tarotista": operator,
#                 "call_duration_seconds": segundos or seconds,
#                 "query_duration_ms": query_duration_ms,
#             },
#             client_id=session_client_id,
#         )
#         return data_out
#     except ServiceNotFound as e:
#         current_app.logger.warning(
#             "agi_client_deduct: ServiceNotFound for service=%r client_id=%s seconds=%s: %s",
#             service,
#             client_id,
#             segundos or seconds,
#             e,
#         )
#         raise abort(404, detail=str(e))
#     except ClientNotFound as e:
#         current_app.logger.warning(
#             "agi_client_deduct: ClientNotFound for service=%r client_id=%s seconds=%s: %s",
#             service,
#             client_id,
#             segundos or seconds,
#             e,
#         )
#         raise abort(404, detail=str(e))


# ---------------------------------------------------------------------------
# Online call tracking
# ---------------------------------------------------------------------------


@bp.route("/calls/online")
class CallInsert(MethodView):
    @bp.arguments(CallInsertFormSchema, location="form")
    @bp.response(200, CallResultSchema)
    @bp.doc(
        summary="Inserta un registro de llamada en línea",
        description=(
            "Llamado desde `[auth-ani]` / `[auth-pin]` después de pasar "
            "verificaciones de autenticación y crédito. Retorna "
            '`{"ok": false, "reason": "call-already-active"}` en caso de duplicado.'
        ),
    )
    def post(self, args):
        return insert_call(
            db,
            args["service"],
            args["ani"],
            args["did"],
            args["client_id"],
            args["operator"],
        )


@bp.route("/calls/online/<string:service>/<string:ani>/close")
class CallClose(MethodView):
    @bp.arguments(CallCloseFormSchema, location="form")
    @bp.response(200, CallResultSchema)
    @bp.doc(
        summary="Elimina un registro de llamada en línea",
        description=(
            "Idempotente — seguro para llamar desde múltiples manejadores `h`. "
            "Llamado vía `POST /calls/online/{service}/{ani}/close` con cuerpo "
            "`_=1` ya que CURL() de Asterisk solo soporta de forma fiable GET "
            "y POST-con-cuerpo."
        ),
    )
    def post(self, args, service, ani):
        return delete_call(db, service, ani)


@bp.route("/calls/online/<string:service>/<string:ani>/assign")
class CallAssignOperator(MethodView):
    @bp.arguments(CallAssignFormSchema, location="form")
    @bp.response(200, CallResultSchema)
    @bp.doc(
        summary="Actualiza el operador asignado a una llamada activa",
        description=(
            "Llamado después de que `[selecciona-operador]` se completa y "
            "antes de marcar. Acepta `operator` como un campo de cuerpo de "
            "formulario."
        ),
    )
    def post(self, args, service, ani):
        return update_call_operator(db, service, ani, args["operator"])


@bp.route("/calls/online/<string:service>/<string:ani>")
class CallGet(MethodView):
    @bp.response(200, ActiveCallSchema)
    @bp.doc(
        summary="Verifica si un ANI tiene una llamada activa para el servicio",
        description='Retorna `{"llamada_activa": "true"}` o `{"llamada_activa": "false"}`.',
    )
    def get(self, service, ani):
        return get_active_call(db, service, ani)


# # ---------------------------------------------------------------------------
# # Operator selection
# # ---------------------------------------------------------------------------


# @bp.get("/operators/menu")
# def agi_operators_menu(
#     redis_conn: redis.Redis | None = Depends(get_redis),
# ):
#     """Retorna conteo de operadores disponibles y una cadena de audio lista para Playback.

#     Reemplaza ``Agi(${AUDIOTEX},ejecutivos_disponibles,7)`` en el dialplan.

#     Respuesta:
#         disponibles  — número de operadores disponibles
#         audio_str    — cadena Playback unida con ``&`` de archivos de audio de operador
#     """
#     return svc_get_menu(db, redis_conn)


# @bp.post("/operators/select")
# def agi_operator_select(
#     mode: str = Form(..., description='"random" or "option"'),
#     selection: str | None = Form(default=None, description="Operator option digits, required when mode=option"),
#     client_id: int | None = Form(default=None, description="Internal client ID for measurement tracking"),
#     uniqueid: str | None = Query(default=None, description="Asterisk UNIQUEID for this call session"),
#     channel: str | None = Query(default=None, description="Asterisk channel name for this call session"),
#     redis_conn: redis.Redis | None = Depends(get_redis),
# ):
#     """Selecciona atómicamente un operador disponible y lo marca como ocupado.

#     Reemplaza ``Agi(${AUDIOTEX},ejecutivo_aleatorio,7)`` y
#     ``Agi(${AUDIOTEX},info_ejecutivo,opcion,...)`` en el dialplan.

#     Respuesta en caso de éxito:
#         ok                — verdadero
#         operador_numero   — número interno del operador
#         operador_nombre   — nombre del operador
#         operador_telefono — número de teléfono de contacto del operador
#         operador_trunk    — troncal SIP por el que marcar

#     Respuesta en caso de fallo:
#         ok      — falso
#         reason  — "operator-busy" | "no-operators" | "no-phone-configured"
#     """
#     result = svc_select(db, mode=mode, selection=selection, redis_conn=redis_conn)
#     if result.get("ok"):
#         session_client_id = _session_client_id(uniqueid=uniqueid, channel=channel)
#         send_measurement_event(
#             "call_dialed",
#             {
#                 "client_id": client_id,
#                 "tarotista": result.get("operador_nombre"),
#             },
#             client_id=session_client_id,
#         )
#     return result


# # ---------------------------------------------------------------------------
# # Operator info
# # ---------------------------------------------------------------------------


# @bp.get("/operators/by-option/{option}")
# def agi_operator_info_by_option(
#     option: str,
#     redis_conn: redis.Redis | None = Depends(get_redis),
# ):
#     """Traduce un dígito de menú IVR en la información de contacto del operador.

#     Utilizado por el dialplan después de que la persona que llama elige un operador del menú
#     reproducido por ``/operators/menu``. El dialplan necesita el
#     número interno del operador (para pasar a ``/operators/select``), nombre (para logs y
#     CDR), teléfono (para ``Dial()``), y troncal (para la
#     tecnología de canal de salida). Este extremo proporciona los cuatro en un viaje redondo
#     y NO reclama el operador -- el reclamo atómico sucede más tarde a través de
#     ``/operators/select``.

#     La división existe porque típicamente hay una ventana de 5-10 segundos
#     entre renderizar menú y Dial (la persona que llama oye opciones, elige una, el audio
#     termina). Reclamar en la selección bloquearía un operador durante esa
#     ventana completa incluso si la llamada se abandona después. Reclamar
#     justo antes de Dial mantiene a los operadores libres el mayor tiempo posible al
#     costo de una pequeña ventana de condición de carrera que ``/operators/select`` resuelve con
#     ``SELECT FOR UPDATE``.

#     Parámetro de ruta:
#         option: el dígito de menú que presionó la persona que llama, p. ej. "1" o "01".
#                 Comparado numéricamente; ambas formas funcionan sin importar cómo
#                 se almacena la columna.

#     Respuesta en caso de éxito:
#         ok                : verdadero
#         operador_numero   : número interno del operador (cadena,
#                             pasar a ``/operators/select`` como ``selection``)
#         operador_nombre   : nombre de visualización del operador
#         operador_telefono : número de teléfono de contacto del operador para Dial()
#         operador_trunk    : troncal SIP por el que marcar, puede ser cadena vacía
#         loggedin          : verdadero/falso, si el operador está conectado
#                             (asesor: el reclamo real está en ``/operators/select``)
#         available         : verdadero/falso, si el operador está libre actualmente
#                             (asesor: el reclamo real está en ``/operators/select``)

#     Respuesta en caso de fallo:
#         ok      : falso
#         reason  : "not-found"           - ningún operador tiene este dígito de opción
#                   "no-phone-configured" - el operador existe pero no tiene
#                                           teléfono de contacto habilitado para Dial()
#     """
#     try:
#         op = svc_operator(db, option=option)
#     except OperatorNotFound as e:
#         current_app.logger.warning(
#             "agi_operator_info_by_option: OperatorNotFound for option=%r: %s",
#             option,
#             e,
#         )
#         return {"ok": False, "reason": "not-found"}

#     phone = next((p for p in op.numbers if p.contact and p.enabled), None)
#     if not phone:
#         current_app.logger.warning(
#             "agi_operator_info_by_option: operator number=%s option=%r "
#             "has no contact+enabled OperatorPhone (numbers=%d)",
#             op.number,
#             option,
#             len(op.numbers),
#         )
#         return {"ok": False, "reason": "no-phone-configured"}

#     ok_status = True
#     ok_meessage = None
#     if op.available == 0 or op.loggedin == 0:
#         ok_status = False
#         ok_meessage = f"{op.loggedin=} {op.available=}"
#     return {
#         "ok": ok_status,
#         "operador_numero": str(op.number),
#         "operador_nombre": op.name,
#         "operador_telefono": phone.number,
#         "operador_trunk": phone.trunk or "",
#         "loggedin": op.loggedin,
#         "available": op.available,
#         "reason": ok_meessage,
#     }


# @bp.get("/operators/by-ani/{ani}")
# def agi_operator_info_by_ani(
#     ani: str,
#     redis_conn: redis.Redis | None = Depends(get_redis),
# ):
#     """Busca un operador por uno de sus números de teléfono registrados (ANI).

#     Utilizado cuando el número de teléfono de la persona que llama identifica al operador,
#     p. ej. un operador que llama desde su propia línea. Coincide contra
#     ``OperatorPhone.number`` donde ``enabled=True``.

#     Retorna la misma forma plana que ``/operators/by-option/{option}`` así
#     el dialplan puede ``JSON_DECODE`` los mismos nombres de campo sin importar
#     qué búsqueda utilizó. El campo ``operador_telefono`` es el
#     teléfono de contacto del operador (el marcado con ``contact=True`` y
#     ``enabled=True``), que puede diferir del ANI de entrada -- el ANI
#     es solo el identificador, el teléfono de contacto es lo que ``Dial()``.

#     Parámetro de ruta:
#         ani: número de teléfono en el formato almacenado en ``OperatorPhone.number``.

#     Respuesta en caso de éxito:
#         ok                : verdadero
#         operador_numero   : número interno del operador (cadena)
#         operador_nombre   : nombre de visualización del operador
#         operador_telefono : teléfono de contacto del operador para Dial()
#         operador_trunk    : troncal SIP por el que marcar, puede ser cadena vacía
#         loggedin          : verdadero/falso, si el operador está conectado
#         available         : verdadero/falso, si el operador está libre actualmente

#     Respuesta en caso de fallo:
#         ok      : falso
#         reason  : "not-found"           - ningún teléfono habilitado coincide con el ANI
#                   "no-phone-configured" - el operador existe pero no tiene
#                                           teléfono de contacto habilitado para Dial()
#     """
#     try:
#         op = svc_operator(db, ani=ani)
#     except OperatorNotFound as e:
#         current_app.logger.warning(
#             "agi_operator_info_by_ani: OperatorNotFound for ani=%r: %s",
#             ani,
#             e,
#         )
#         return {"ok": False, "reason": "not-found"}

#     phone = next((p for p in op.numbers if p.contact and p.enabled), None)
#     if not phone:
#         current_app.logger.warning(
#             "agi_operator_info_by_ani: operator number=%s ani=%r has no contact+enabled OperatorPhone (numbers=%d)",
#             op.number,
#             ani,
#             len(op.numbers),
#         )
#         return {"ok": False, "reason": "no-phone-configured"}

#     return {
#         "ok": True,
#         "operador_numero": str(op.number),
#         "operador_nombre": op.name,
#         "operador_telefono": phone.number,
#         "operador_trunk": phone.trunk or "",
#         "loggedin": op.loggedin,
#         "available": op.available,
#     }


# @bp.post("/operators/{number}/release")
# def agi_operator_release(
#     number: int,
#     redis_conn: redis.Redis | None = Depends(get_redis),
# ):
#     """Marca un operador como disponible de nuevo después de que termina una llamada.

#     Llamado desde el manejador hangup ``[llama-operador]`` y en fallo de marcación.
#     Reemplaza ``Agi(${AUDIOTEX},cambia_estado,${OPERATOR_NUM},1)``.
#     """
#     try:
#         svc_release(db, number, redis_conn)
#     except OperatorNotFound as e:
#         current_app.logger.warning(
#             "agi_operator_release: OperatorNotFound for number=%s: %s",
#             number,
#             e,
#         )
#         raise abort(404, detail=str(e))
#     return {"ok": True}


# # ---------------------------------------------------------------------------
# # Operator login / logout (from dialplan)
# # ---------------------------------------------------------------------------


# @bp.post("/operators/by-phone/{ani}/login")
# def agi_operator_login(
#     ani: str,
#     uniqueid: str | None = Query(default=None, description="Asterisk UNIQUEID for this call session"),
#     channel: str | None = Query(default=None, description="Asterisk channel name for this call session"),
#     redis_conn: redis.Redis | None = Depends(get_redis),
# ):
#     """Marca el operador como conectado por su número de teléfono (ANI).

#     Llamado desde el contexto dialplan ``[tarotista-login]``.
#     """
#     session_client_id = _session_client_id(uniqueid=uniqueid, channel=channel)
#     started_at = time.perf_counter()
#     try:
#         tarotista = login_by_phone(db, ani, redis_conn)
#         query_duration_ms = round((time.perf_counter() - started_at) * 1000, 3)
#         send_measurement_event(
#             "operator_login",
#             {
#                 "tarotista": tarotista.name,
#                 "query_duration_ms": query_duration_ms,
#             },
#             client_id=session_client_id,
#         )
#         create_audit(
#             db,
#             title="operator_login",
#             category="INFO",
#             called_from="firenze.api.agi.agi_operator_login()",
#             data={"ani": ani},
#         )
#     except OperatorNotFound as e:
#         current_app.logger.warning(
#             "agi_operator_login: OperatorNotFound for ani=%r: %s",
#             ani,
#             e,
#         )
#         raise abort(404, detail=str(e))

#     return {"ok": True}


# @bp.post("/operators/by-phone/{ani}/logout")
# def agi_operator_logout(
#     ani: str,
#     uniqueid: str | None = Query(default=None, description="Asterisk UNIQUEID for this call session"),
#     channel: str | None = Query(default=None, description="Asterisk channel name for this call session"),
#     redis_conn: redis.Redis | None = Depends(get_redis),
# ):
#     """Marca el operador como desconectado por su número de teléfono (ANI).

#     Llamado desde el contexto dialplan ``[tarotista-logout]``.
#     """
#     session_client_id = _session_client_id(uniqueid=uniqueid, channel=channel)
#     started_at = time.perf_counter()
#     try:
#         tarotista = logout_by_phone(db, ani, redis_conn)
#         query_duration_ms = round((time.perf_counter() - started_at) * 1000, 3)
#         send_measurement_event(
#             "operator_logout",
#             {
#                 "tarotista": tarotista.name,
#                 "query_duration_ms": query_duration_ms,
#             },
#             client_id=session_client_id,
#         )
#     except OperatorNotFound as e:
#         current_app.logger.warning(
#             "agi_operator_logout: OperatorNotFound for ani=%r: %s",
#             ani,
#             e,
#         )
#         raise abort(404, detail=str(e))

#     create_audit(
#         db,
#         title="operator_logout",
#         category="INFO",
#         called_from="firenze.api.agi.agi_operator_logout()",
#         data={"ani": ani},
#     )
#     return {"ok": True}
