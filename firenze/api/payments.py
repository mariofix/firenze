"""Extremos de pago llamados por la tienda (nuevo-fonotarot)."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Security
from sqlalchemy.orm import Session

from firenze.auth import loggedin_user
from firenze.dependencies import get_db
from firenze.schemas.payment import (
    ClientUpdateRequest,
    ClientUpdateResponse,
    PurchaseRequest,
    PurchaseResponse,
)
from firenze.services.audit_service import create_audit
from firenze.services.client_service import ClientNotFound, ServiceNotFound
from firenze.services.payment_service import (
    apply_purchase,
    update_client,
)

logger = logging.getLogger("firenze")

paymentsRouter = APIRouter(prefix="/api/v1", tags=["payments"])


@paymentsRouter.post("/payments/complete", response_model=PurchaseResponse)
def payments_complete(
    payload: PurchaseRequest,
    db: Session = Depends(get_db),
    # _user_id: int = Security(loggedin_user, scopes=["firenze"]),
):
    """Apply a completed purchase.

    With ``client_id`` set: tops up the existing client.
    Without ``client_id``: creates a new client (``email`` is required by the
    request schema in that case) and uses ``credits`` as the initial balance.
    """
    try:
        result = apply_purchase(
            db,
            service_slug=payload.service,
            credits=payload.credits,
            client_id=payload.client_id,
            email=payload.email,
            full_name=payload.full_name,
            phone_number=payload.phone_number,
            ani=payload.ani,
            transaction_id=payload.transaction_id,
        )
    except ServiceNotFound as e:
        logger.warning(
            "payments_complete: ServiceNotFound for service=%r transaction_id=%r: %s",
            payload.service,
            payload.transaction_id,
            e,
        )
        raise HTTPException(status_code=404, detail=str(e))
    except ClientNotFound as e:
        logger.warning(
            "payments_complete: ClientNotFound for service=%r client_id=%s transaction_id=%r: %s",
            payload.service,
            payload.client_id,
            payload.transaction_id,
            e,
        )
        raise HTTPException(status_code=404, detail=str(e))
    logger.info(f"payments_complete: NewPayment: {result=}")
    audit_data = {"payload": payload.model_dump_json(), "apply_purchase": result}
    create_audit(
        db,
        title="nuevo_pago",
        category="INFO",
        called_from="firenze.api.payments.payments_complete()",
        data=audit_data,
    )
    return PurchaseResponse(**result)


@paymentsRouter.patch(
    "/clients/{service}/{client_id}",
    response_model=ClientUpdateResponse,
)
def clients_update(
    service: str,
    client_id: int,
    payload: ClientUpdateRequest,
    db: Session = Depends(get_db),
    _user_id: int = Security(loggedin_user, scopes=["firenze"]),
):
    """Patch profile fields on an existing client.

    ``phone`` accepts a normal phone string (added to the client's ANI list
    if not already present) or the literal sentinel ``::EMPTY::`` (deletes
    every ANI registered to the client).
    """
    try:
        result = update_client(
            db,
            service_slug=service,
            client_id=client_id,
            full_name=payload.full_name,
            email=payload.email,
            pin=payload.pin,
            phone=payload.phone,
        )
    except ServiceNotFound as e:
        logger.warning("clients_update: ServiceNotFound for service=%r: %s", service, e)
        raise HTTPException(status_code=404, detail=str(e))
    except ClientNotFound as e:
        logger.warning(
            "clients_update: ClientNotFound for service=%r client_id=%s: %s",
            service,
            client_id,
            e,
        )
        raise HTTPException(status_code=404, detail=str(e))
    return ClientUpdateResponse(**result)
