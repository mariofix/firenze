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
from ..services.audit_service import create_audit
from ..services.call_service import (
    delete_call,
    get_active_call,
    insert_call,
    update_call_operator,
)
from ..services.client_service import (
    ClientNotFound,
    ServiceNotFound,
)
from ..services.client_service import deduct_credits as svc_deduct
from ..services.client_service import lookup as svc_lookup
from ..services.client_service import update_ani_stats as svc_ani_stats
from ..services.credit_service import compute_call_limit
from ..services.did_service import resolve_did
from ..services.dnc_service import check_dnc
from ..services.measurement_service import send_measurement_event
from ..services.operator_service import OperatorNotFound, login_by_phone, logout_by_phone
from ..services.operator_service import get_menu as svc_get_menu
from ..services.operator_service import info_operator as svc_operator
from ..services.operator_service import release_operator as svc_release
from ..services.operator_service import select_operator as svc_select
from .schema import (
    ActiveCallSchema,
    CallAssignFormSchema,
    CallCloseFormSchema,
    CallInsertFormSchema,
    CallResultSchema,
    ClientDeductFormSchema,
    ClientLookupArgsSchema,
    CreditLimitArgsSchema,
    DidLookupResponseSchema,
    DidQueryArgsSchema,
    DncQueryArgsSchema,
    DncResponseSchema,
    OperatorSelectFormSchema,
    SessionArgsSchema,
)

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
# ---------------------------------------------------------------------------


@bp.route("/credits/limit")
class CreditLimit(MethodView):
    @bp.arguments(CreditLimitArgsSchema, location="query")
    @bp.doc(summary="Calcula timeout de llamada y archivo de audio para un saldo de crédito dado")
    def get(self, args):
        seconds = args["seconds"]
        uniqueid = args.get("uniqueid")
        channel = args.get("channel")
        session_client_id = _session_client_id(uniqueid=uniqueid, channel=channel)
        started_at = time.perf_counter()
        result = compute_call_limit(seconds)
        query_duration_ms = round((time.perf_counter() - started_at) * 1000, 3)
        send_measurement_event(
            "credit_compute",
            {
                "requested_seconds": seconds,
                "minutes": result.get("minutes"),
                "query_duration_ms": query_duration_ms,
            },
            client_id=session_client_id,
        )
        return result


# ---------------------------------------------------------------------------
# Client lookup and deduction
# ---------------------------------------------------------------------------


@bp.route("/clients/lookup")
class ClientLookup(MethodView):
    @bp.arguments(ClientLookupArgsSchema, location="query")
    @bp.doc(summary="Busca un cliente por servicio e identificador")
    def get(self, args):
        service = args["service"]
        identifier = args["identifier"]
        svc_ani_stats(db, service, identifier)
        try:
            data = svc_lookup(db, service, identifier)
            more_data = compute_call_limit(data["segundos"])
            data.update(more_data)
            return data
        except ServiceNotFound as e:
            current_app.logger.warning(
                "agi_client_lookup: ServiceNotFound for service=%r identifier=%r: %s",
                service,
                identifier,
                e,
            )
            abort(404, message=str(e))


@bp.route("/clients/<string:service>/<int:client_id>/deduct")
class ClientDeduct(MethodView):
    @bp.arguments(SessionArgsSchema, location="query")
    @bp.arguments(ClientDeductFormSchema, location="form")
    @bp.doc(summary="Descuenta créditos (segundos) del saldo de un cliente")
    def post(self, form_args, query_args, service, client_id):
        seconds = form_args["seconds"]
        operator = form_args.get("operator")
        uniqueid = query_args.get("uniqueid")
        channel = query_args.get("channel")

        segundos = None
        if channel:
            current_app.logger.debug(f"agi_client_deduct: Calculando nuevo billsec con CEL y channelname='{channel}'")
            query = text("""
                SELECT
                    TIMESTAMPDIFF(SECOND,
                        MAX(CASE WHEN eventtype = 'BRIDGE_ENTER' THEN eventtime END),
                        MAX(CASE WHEN eventtype = 'BRIDGE_EXIT'  THEN eventtime END)
                    ) AS duration_seconds
                FROM zvn_asterisk.cel
                WHERE channame = :channel
            """)
            try:
                row = db.session.execute(query, {"channel": channel}).first()
                if row and row.duration_seconds is not None:
                    current_app.logger.info(
                        f"agi_client_deduct: Nuevos segundos calculados para {channel}: {row.duration_seconds}"
                    )
                    segundos = int(row.duration_seconds)
            except Exception as e:
                current_app.logger.warning(e)

        try:
            session_client_id = _session_client_id(uniqueid=uniqueid, channel=channel)
            started_at = time.perf_counter()
            data_out = svc_deduct(db, service, client_id, segundos or seconds)
            query_duration_ms = round((time.perf_counter() - started_at) * 1000, 3)
            data_out.update({"client_id": client_id, "service": service})
            create_audit(
                db,
                title="resta_saldo",
                category="INFO",
                called_from="firenze.api.agi.agi_client_deduct()",
                data=data_out,
            )
            send_measurement_event(
                "call_ended",
                {
                    "client_id": client_id,
                    "tarotista": operator,
                    "call_duration_seconds": segundos or seconds,
                    "query_duration_ms": query_duration_ms,
                },
                client_id=session_client_id,
            )
            return data_out
        except ServiceNotFound as e:
            current_app.logger.warning(
                "agi_client_deduct: ServiceNotFound for service=%r client_id=%s seconds=%s: %s",
                service,
                client_id,
                segundos or seconds,
                e,
            )
            abort(404, message=str(e))
        except ClientNotFound as e:
            current_app.logger.warning(
                "agi_client_deduct: ClientNotFound for service=%r client_id=%s seconds=%s: %s",
                service,
                client_id,
                segundos or seconds,
                e,
            )
            abort(404, message=str(e))


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


# ---------------------------------------------------------------------------
# Operator selection
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Operator selection
# ---------------------------------------------------------------------------


@bp.route("/operators/menu")
class OperatorsMenu(MethodView):
    @bp.doc(summary="Retorna conteo de operadores disponibles y una cadena de audio lista para Playback")
    def get(self):
        return svc_get_menu(db)


@bp.route("/operators/select")
class OperatorSelect(MethodView):
    @bp.arguments(SessionArgsSchema, location="query")
    @bp.arguments(OperatorSelectFormSchema, location="form")
    @bp.doc(summary="Selecciona atómicamente un operador disponible y lo marca como ocupado")
    def post(self, form_args, query_args):
        mode = form_args["mode"]
        selection = form_args.get("selection")
        client_id = form_args.get("client_id")
        uniqueid = query_args.get("uniqueid")
        channel = query_args.get("channel")

        result = svc_select(db, mode=mode, selection=selection)
        if result.get("ok"):
            session_client_id = _session_client_id(uniqueid=uniqueid, channel=channel)
            send_measurement_event(
                "call_dialed",
                {
                    "client_id": client_id,
                    "tarotista": result.get("operador_nombre"),
                },
                client_id=session_client_id,
            )
        return result


# ---------------------------------------------------------------------------
# Operator info
# ---------------------------------------------------------------------------


@bp.route("/operators/by-option/<string:option>")
class OperatorInfoByOption(MethodView):
    @bp.doc(summary="Traduce un dígito de menú IVR en la información de contacto del operador")
    def get(self, option):
        try:
            op = svc_operator(db, option=option)
        except OperatorNotFound as e:
            current_app.logger.warning(
                "agi_operator_info_by_option: OperatorNotFound for option=%r: %s",
                option,
                e,
            )
            return {"ok": False, "reason": "not-found"}

        phone = next((p for p in op.numbers if p.contact and p.enabled), None)
        if not phone:
            current_app.logger.warning(
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


@bp.route("/operators/by-ani/<string:ani>")
class OperatorInfoByAni(MethodView):
    @bp.doc(summary="Busca un operador por uno de sus números de teléfono registrados (ANI)")
    def get(self, ani):
        try:
            op = svc_operator(db, ani=ani)
        except OperatorNotFound as e:
            current_app.logger.warning(
                "agi_operator_info_by_ani: OperatorNotFound for ani=%r: %s",
                ani,
                e,
            )
            return {"ok": False, "reason": "not-found"}

        phone = next((p for p in op.numbers if p.contact and p.enabled), None)
        if not phone:
            current_app.logger.warning(
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


@bp.route("/operators/<int:number>/release")
class OperatorRelease(MethodView):
    @bp.doc(summary="Marca un operador como disponible de nuevo después de que termina una llamada")
    def post(self, number):
        try:
            svc_release(db, number)
        except OperatorNotFound as e:
            current_app.logger.warning(
                "agi_operator_release: OperatorNotFound for number=%s: %s",
                number,
                e,
            )
            abort(404, message=str(e))
        return {"ok": True}


# ---------------------------------------------------------------------------
# Operator login / logout (from dialplan)
# ---------------------------------------------------------------------------


@bp.route("/operators/by-phone/<string:ani>/login")
class OperatorLogin(MethodView):
    @bp.arguments(SessionArgsSchema, location="query")
    @bp.doc(summary="Marca el operador como conectado por su número de teléfono (ANI)")
    def post(self, query_args, ani):
        uniqueid = query_args.get("uniqueid")
        channel = query_args.get("channel")

        session_client_id = _session_client_id(uniqueid=uniqueid, channel=channel)
        started_at = time.perf_counter()
        try:
            tarotista = login_by_phone(db, ani)
            query_duration_ms = round((time.perf_counter() - started_at) * 1000, 3)
            send_measurement_event(
                "operator_login",
                {
                    "tarotista": tarotista.name,
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
        except OperatorNotFound as e:
            current_app.logger.warning(
                "agi_operator_login: OperatorNotFound for ani=%r: %s",
                ani,
                e,
            )
            abort(404, message=str(e))

        return {"ok": True}


@bp.route("/operators/by-phone/<string:ani>/logout")
class OperatorLogout(MethodView):
    @bp.arguments(SessionArgsSchema, location="query")
    @bp.doc(summary="Marca el operador como desconectado por su número de teléfono (ANI)")
    def post(self, query_args, ani):
        uniqueid = query_args.get("uniqueid")
        channel = query_args.get("channel")

        session_client_id = _session_client_id(uniqueid=uniqueid, channel=channel)
        started_at = time.perf_counter()
        try:
            tarotista = logout_by_phone(db, ani)
            query_duration_ms = round((time.perf_counter() - started_at) * 1000, 3)
            send_measurement_event(
                "operator_logout",
                {
                    "tarotista": tarotista.name,
                    "query_duration_ms": query_duration_ms,
                },
                client_id=session_client_id,
            )
        except OperatorNotFound as e:
            current_app.logger.warning(
                "agi_operator_logout: OperatorNotFound for ani=%r: %s",
                ani,
                e,
            )
            abort(404, message=str(e))

        create_audit(
            db,
            title="operator_logout",
            category="INFO",
            called_from="firenze.api.agi.agi_operator_logout()",
            data={"ani": ani},
        )
        return {"ok": True}
