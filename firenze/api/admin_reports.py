"""Extremos de reportes de administrador protegidos."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, Security
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from firenze.old_admin import FirenzeAdmin
from firenze.auth import admin_loggedin_user
from firenze.dependencies import get_db
from firenze.schemas.admin_reports import (
    SystemStatusClientCreditRequest,
    SystemStatusClientCreditResponse,
)
from firenze.services.client_service import ClientNotFound, ServiceNotFound, get_client
from firenze.services.payment_service import apply_purchase

adminReportsRouter = APIRouter(prefix="/api/v1/admin", tags=["admin-reports"])


@adminReportsRouter.get(
    "/system-status",
    summary="SQLAdmin index data",
    description="Returns the same data payload used by the SQLAdmin System Status index view.",
)
async def admin_system_status(
    top_ani: int = Query(default=10, description="Top client_id rows. Allowed values: 5, 10, 15."),
    operator_period: str = Query(
        default="current_month",
        description="Operator period. Allowed values: current_month, last_month, last_3_months.",
    ),
    _user_id: int = Security(admin_loggedin_user, scopes=["admin", "reports"]),
):
    top_ani_limit = top_ani if top_ani in {5, 10, 15} else 10
    normalized_operator_period = (
        operator_period if operator_period in {"current_month", "last_month", "last_3_months"} else "current_month"
    )
    data = await asyncio.to_thread(FirenzeAdmin._collect_data, top_ani_limit, normalized_operator_period)
    return jsonable_encoder(data)


@adminReportsRouter.get(
    "/system-status/client-credit/preview",
    response_model=SystemStatusClientCreditResponse,
    summary="Preview client credit top-up",
)
def admin_system_status_client_credit_preview(
    service_slug: str = Query(..., min_length=1),
    client_id: int = Query(..., gt=0),
    credits_to_add: int = Query(..., gt=0),
    db: Session = Depends(get_db),
    _user_id: int = Security(admin_loggedin_user, scopes=["admin", "reports"]),
):
    try:
        client = get_client(db, service_slug, client_id)
    except ServiceNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ClientNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    current_credits = int(client["credits"])
    return SystemStatusClientCreditResponse(
        ok=True,
        saved=False,
        service_slug=service_slug,
        client_id=client_id,
        email=client.get("email"),
        current_credits=current_credits,
        credits_to_add=credits_to_add,
        new_credits=current_credits + credits_to_add,
    )


@adminReportsRouter.post(
    "/system-status/client-credit",
    response_model=SystemStatusClientCreditResponse,
    summary="Apply client credit top-up",
)
def admin_system_status_client_credit_apply(
    payload: SystemStatusClientCreditRequest,
    db: Session = Depends(get_db),
    _user_id: int = Security(admin_loggedin_user, scopes=["admin", "reports"]),
):
    try:
        client = get_client(db, payload.service_slug, payload.client_id)
    except ServiceNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ClientNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    result = apply_purchase(
        db,
        service_slug=payload.service_slug,
        client_id=payload.client_id,
        credits=payload.credits_to_add,
    )
    current_credits = int(result["credits_before"])
    return SystemStatusClientCreditResponse(
        ok=True,
        saved=True,
        service_slug=payload.service_slug,
        client_id=payload.client_id,
        email=client.get("email"),
        current_credits=current_credits,
        credits_to_add=payload.credits_to_add,
        new_credits=int(result["credits_after"]),
    )
