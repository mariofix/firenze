"""Extremos públicos"""

import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from firenze.dependencies import get_db
from firenze.models.operator import Operator
from firenze.schemas import Message
from firenze.schemas.operators import ConnectedOperators
from firenze.services.client_service import maybe_send_post_call_email

logger = logging.getLogger("firenze")

publicRouter = APIRouter(prefix="/api/v1/public", tags=["public"])


@publicRouter.get(
    "/ejecutivos",
    description="Lista ejecutivos conectados",
    response_model=list[ConnectedOperators],
    responses={404: {"model": Message}},
    summary="Lista ejecutivos conectados",
)
def connected_operators(
    db: Session = Depends(get_db),
):
    operators = db.query(Operator).filter_by(loggedin=1).all()
    connected = []
    for op in operators:
        connected.append(
            ConnectedOperators(
                nombre=op.name,
                opcion=int(op.option),
                ingreso=op.loggedin,
                disponible=op.available,
                descripcion=op.description,
            )
        )
    logger.debug(f"{connected=}")
    return connected


@publicRouter.get(
    "/test-email",
    description="Prueba Email",
    response_model=None,
    responses={404: {"model": Message}},
    summary="Prueba de correo",
)
def test_email(
    request: Request,
    db: Session = Depends(get_db),
):
    from firenze.models.client import Client
    from firenze.services.client_service import _get_service

    svc = _get_service(db, "fonotarot-cl")
    client = db.query(Client).filter_by(service_id=svc.id, client_id=1654).first()

    if client:
        maybe_send_post_call_email(
            client,
            svc,
            template_env=request.app.state.admin.templates.env,
            subject="[Prueba] Gracias por tu llamada.",
        )
