"""Public endpoints"""

import logging

from fastapi import APIRouter, Depends
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
