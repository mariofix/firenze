"""AGI endpoints — called by Asterisk dialplan via CURL().

These return flat JSON dicts with the exact variable names the dialplan expects.
No JWT auth — protected by binding to localhost / LAN only.
"""

from typing import Optional

import redis
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from firenze.dependencies import get_db, get_redis
from firenze.services.credit_service import compute_call_limit
from firenze.services.did_service import resolve_did
from firenze.services.dnc_service import check_dnc
from firenze.services.operator_service import OperatorNotFound
from firenze.services.operator_service import login_by_phone, logout_by_phone

agiRouter = APIRouter(prefix="/agi", tags=["agi"])


@agiRouter.get("/dnc/{ani}")
def agi_dnc_check(ani: str, db: Session = Depends(get_db)):
    """Check if ANI is in the Do Not Call list."""
    in_dnc = check_dnc(db, ani)
    return {"dnc": "YES" if in_dnc else "NO"}


@agiRouter.get("/services/did/{did}")
def agi_did_lookup(did: str, db: Session = Depends(get_db)):
    """Resolve a DID to an Asterisk context.

    Returns {"siguiente": "prepago-fonotarot-cl"} on match,
    {"siguiente": ""} if not found.
    """
    return {"siguiente": resolve_did(db, did)}


@agiRouter.get("/credits/limit")
def agi_credit_limit(seconds: int = Query(..., description="Credit balance in seconds")):
    """Compute call timeout and audio file for a given credit balance.

    Replaces the 150-line limite-saldo dialplan ladder.
    """
    return compute_call_limit(seconds)


@agiRouter.post("/operators/by-phone/{ani}/login")
def agi_operator_login(
    ani: str,
    db: Session = Depends(get_db),
    redis_conn: Optional[redis.Redis] = Depends(get_redis),
):
    """Mark operator as logged in by their phone number (ANI).

    Called from the [tarotista-login] dialplan context.
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

    Called from the [tarotista-logout] dialplan context.
    """
    try:
        logout_by_phone(db, ani, redis_conn)
    except OperatorNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"ok": True}
