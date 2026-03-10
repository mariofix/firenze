"""AGI endpoints — called by Asterisk dialplan via CURL().

These return flat JSON dicts with the exact variable names the dialplan expects.
No JWT auth — protected by binding to localhost / LAN only.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from firenze.dependencies import get_db
from firenze.services.credit_service import compute_call_limit
from firenze.services.dnc_service import check_dnc

agiRouter = APIRouter(prefix="/agi", tags=["agi"])


@agiRouter.get("/dnc/{ani}")
def agi_dnc_check(ani: str, db: Session = Depends(get_db)):
    """Check if ANI is in the Do Not Call list."""
    in_dnc = check_dnc(db, ani)
    return {"dnc": "YES" if in_dnc else "NO"}


@agiRouter.get("/credits/limit")
def agi_credit_limit(seconds: int = Query(..., description="Credit balance in seconds")):
    """Compute call timeout and audio file for a given credit balance.

    Replaces the 150-line limite-saldo dialplan ladder.
    """
    return compute_call_limit(seconds)
