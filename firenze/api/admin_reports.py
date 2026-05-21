"""Protected admin report endpoints."""

import asyncio

from fastapi import APIRouter, Query, Security
from fastapi.encoders import jsonable_encoder

from firenze.admin import FirenzeAdmin
from firenze.auth import loggedin_user

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
    _user_id: int = Security(loggedin_user, scopes=["admin", "reports"]),
):
    top_ani_limit = top_ani if top_ani in {5, 10, 15} else 10
    normalized_operator_period = (
        operator_period if operator_period in {"current_month", "last_month", "last_3_months"} else "current_month"
    )
    data = await asyncio.to_thread(FirenzeAdmin._collect_data, top_ani_limit, normalized_operator_period)
    return jsonable_encoder(data)
