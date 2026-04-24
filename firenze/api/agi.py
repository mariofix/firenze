"""AGI endpoints — called by Asterisk dialplan via CURL().

These return flat JSON dicts with the exact variable names the dialplan expects.
No JWT auth — protected by binding to localhost / LAN only.
"""

from typing import Optional

import redis
from fastapi import APIRouter, Depends, Form, HTTPException, Query
from sqlalchemy.orm import Session

from firenze.dependencies import get_db, get_redis
from firenze.services.call_service import (
    delete_call,
    get_active_call,
    insert_call,
    update_call_operator,
)
from firenze.services.client_service import (
    ClientNotFound,
    InsufficientCredits,
    ServiceNotFound,
)
from firenze.services.client_service import deduct_credits as svc_deduct
from firenze.services.client_service import lookup as svc_lookup
from firenze.services.credit_service import compute_call_limit
from firenze.services.did_service import resolve_did
from firenze.services.dnc_service import check_dnc
from firenze.services.operator_service import OperatorNotFound, OperatorUnavailable
from firenze.services.operator_service import get_menu as svc_get_menu
from firenze.services.operator_service import login_by_phone, logout_by_phone
from firenze.services.operator_service import release_operator as svc_release
from firenze.services.operator_service import select_operator as svc_select
from firenze.services.operator_service import info_operator as svc_operator

agiRouter = APIRouter(prefix="/agi", tags=["agi"])


# ---------------------------------------------------------------------------
# DNC
# ---------------------------------------------------------------------------


@agiRouter.get("/dnc/{ani}")
def agi_dnc_check(ani: str, db: Session = Depends(get_db)):
    """Check if ANI is in the Do Not Call list."""
    in_dnc = check_dnc(db, ani)
    return {"dnc": "YES" if in_dnc else "NO"}


# ---------------------------------------------------------------------------
# Service / DID resolution
# ---------------------------------------------------------------------------


@agiRouter.get("/services/did/{did}")
def agi_did_lookup(did: str, db: Session = Depends(get_db)):
    """Resolve a DID to its service config.

    Returns the full set of channel variables the unified ``[prepago-service]``
    dialplan context needs — one CURL call instead of multiple AGI spawns.

    Response fields:
        siguiente    — Asterisk context to Goto (``"prepago-service"`` for all new DIDs)
        servicio     — service slug (e.g. ``"alotarot"``, ``"fonotarot-cl"``)
        auth_method  — ``"ani"`` or ``"pin"``
        intro_audio  — Playback-compatible string (e.g. ``"zvn/intro-alotarot"``)
    """
    return resolve_did(db, did)


# ---------------------------------------------------------------------------
# Credits
# ---------------------------------------------------------------------------


@agiRouter.get("/credits/limit")
def agi_credit_limit(seconds: int = Query(..., description="Credit balance in seconds")):
    """Compute call timeout and audio file for a given credit balance.

    Replaces the 150-line ``[limite-saldo]`` dialplan ladder.
    """
    return compute_call_limit(seconds)


# ---------------------------------------------------------------------------
# Client lookup and deduction
# ---------------------------------------------------------------------------


@agiRouter.get("/clients/lookup")
def agi_client_lookup(
    service: str = Query(..., description="Service slug, e.g. fonotarot-latam"),
    identifier: str = Query(..., description="Client identifier (ANI or PIN)"),
    db: Session = Depends(get_db),
):
    """Look up a client by service and identifier.

    Returns ``{clientid, segundos}`` — the contract the dialplan expects.
    Returns ``{clientid: 0, segundos: 0}`` if not found (dialplan handles this).
    """
    try:
        return svc_lookup(db, service, identifier)
    except ServiceNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))


@agiRouter.post("/clients/{service}/{client_id}/deduct")
def agi_client_deduct(
    service: str,
    client_id: int,
    seconds: int = Form(..., description="Seconds to deduct"),
    db: Session = Depends(get_db),
):
    """Deduct credits (seconds) from a client's balance.

    Called from ``[llama-operador]`` hangup handler after a call ends.
    """
    try:
        return svc_deduct(db, service, client_id, seconds)
    except ServiceNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ClientNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InsufficientCredits as e:
        raise HTTPException(status_code=409, detail=str(e))


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
):
    """Insert an online call record.

    Called from ``[auth-ani]`` / ``[auth-pin]`` after auth and credit checks pass.
    Returns ``{"ok": false, "reason": "call-already-active"}`` on duplicate.
    """
    return insert_call(db, service, ani, did, client_id, operator)


@agiRouter.post("/calls/online/{service}/{ani}/close")
def agi_call_close(service: str, ani: str, db: Session = Depends(get_db)):
    """Delete an online call record.

    Idempotent — safe to call from multiple ``h`` handlers.
    Called via ``POST /calls/online/{service}/{ani}/close`` with body ``_=1``
    since Asterisk's CURL() only reliably supports GET and POST-with-body.
    """
    return delete_call(db, service, ani)


@agiRouter.post("/calls/online/{service}/{ani}/assign")
def agi_call_assign_operator(
    service: str,
    ani: str,
    operator: int = Form(..., description="Operator number assigned to this call"),
    db: Session = Depends(get_db),
):
    """Update the operator assigned to an active call.

    Called after ``[selecciona-operador]`` completes and before dialling.
    Accepts ``operator`` as a form body field.
    """
    return update_call_operator(db, service, ani, operator)


@agiRouter.get("/calls/online/{service}/{ani}")
def agi_call_get(service: str, ani: str, db: Session = Depends(get_db)):
    """Check whether an ANI has an active call for the service.

    Returns ``{"llamada_activa": "true"}`` or ``{"llamada_activa": "false"}``.
    """
    return get_active_call(db, service, ani)



# ---------------------------------------------------------------------------
# Operator selection
# ---------------------------------------------------------------------------


@agiRouter.get("/operators/menu")
def agi_operators_menu(
    db: Session = Depends(get_db),
    redis_conn: Optional[redis.Redis] = Depends(get_redis),
):
    """Return available operator count and a Playback-ready audio string.

    Replaces ``Agi(${AUDIOTEX},ejecutivos_disponibles,7)`` in the dialplan.

    Response:
        disponibles  — number of available operators
        audio_str    — ``&``-joined Playback string of operator audio files
    """
    return svc_get_menu(db, redis_conn)


@agiRouter.post("/operators/select")
def agi_operator_select(
    mode: str = Form(..., description='"random" or "option"'),
    selection: Optional[str] = Form(default=None, description="Operator option digits, required when mode=option"),
    db: Session = Depends(get_db),
    redis_conn: Optional[redis.Redis] = Depends(get_redis),
):
    """Atomically select an available operator and mark them busy.

    Replaces ``Agi(${AUDIOTEX},ejecutivo_aleatorio,7)`` and
    ``Agi(${AUDIOTEX},info_ejecutivo,opcion,...)`` in the dialplan.

    Response on success:
        ok                — true
        operador_numero   — operator's internal number
        operador_nombre   — operator's name
        operador_telefono — operator's contact phone number
        operador_trunk    — SIP trunk to dial via

    Response on failure:
        ok      — false
        reason  — "operator-busy" | "no-operators" | "no-phone-configured"
    """
    return svc_select(db, mode=mode, selection=selection, redis_conn=redis_conn)

# ---------------------------------------------------------------------------
# Operator info
# ---------------------------------------------------------------------------

@agiRouter.post("/operators/{ani}")
def agi_operator_info(
    ani: str,
    db: Session = Depends(get_db),
    redis_conn: Optional[redis.Redis] = Depends(get_redis),
):
    """Find operator info
    """
    try:
        op = svc_operator(db, ani)
    except OperatorNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    return op


@agiRouter.post("/operators/{number}/release")
def agi_operator_release(
    number: int,
    db: Session = Depends(get_db),
    redis_conn: Optional[redis.Redis] = Depends(get_redis),
):
    """Mark an operator as available again after a call ends.

    Called from the ``[llama-operador]`` hangup handler and on dial failure.
    Replaces ``Agi(${AUDIOTEX},cambia_estado,${OPERATOR_NUM},1)``.
    """
    try:
        svc_release(db, number, redis_conn)
    except OperatorNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"ok": True}


# ---------------------------------------------------------------------------
# Operator login / logout (from dialplan)
# ---------------------------------------------------------------------------


@agiRouter.post("/operators/by-phone/{ani}/login")
def agi_operator_login(
    ani: str,
    db: Session = Depends(get_db),
    redis_conn: Optional[redis.Redis] = Depends(get_redis),
):
    """Mark operator as logged in by their phone number (ANI).

    Called from the ``[tarotista-login]`` dialplan context.
    """
    try:
        login_by_phone(db, ani, redis_conn)
    except OperatorNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"ok": True}


@agiRouter.post("/operators/by-phone/{ani}/logout")
def agi_operator_logout(
    ani: str,
    db: Session = Depends(get_db),
    redis_conn: Optional[redis.Redis] = Depends(get_redis),
):
    """Mark operator as logged out by their phone number (ANI).

    Called from the ``[tarotista-logout]`` dialplan context.
    """
    try:
        logout_by_phone(db, ani, redis_conn)
    except OperatorNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"ok": True}
