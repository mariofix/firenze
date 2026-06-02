"""Extremos públicos"""

import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from firenze.dependencies import get_db
from firenze.models.operator import Operator
from firenze.schemas import Message
from firenze.schemas.operators import ConnectedOperators

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
    from daleks.contrib.client import DaleksClient
    from firenze.config import settings

    if not settings.DALEKS_URL or not settings.DALEKS_FROM:
        logger.info("daleks notify skipped (config missing)")
        return

    from firenze.models.client import Client
    from firenze.services.client_service import _get_service

    svc = _get_service(db, "fonotarot-cl")
    client = db.query(Client).filter_by(service_id=svc.id, client_id=1654).first()

    if (
        client
        and client.extra_config.get("promo_post_llamada", False)
        and client.email
        and client.credits < 600
    ):
        html_body = (
            request.app.state.admin.templates.env
            .get_template("emails/post_llamada.html")
            .render(client=client, service=svc)
        )
        try:
            with DaleksClient(settings.DALEKS_URL, smtp_account=settings.DALEKS_SMTP_ACCOUNT) as dalek:
                dalek.send_email(
                    from_address=settings.DALEKS_FROM,
                    to=client.email,
                    subject="[Prueba] Gracias por tu llamada.",
                    html_body=html_body,
                )
        except Exception as exc:
            logger.warning("daleks notify failed (%s): %s", type(exc).__name__, exc)