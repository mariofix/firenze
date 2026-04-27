"""Payment endpoints called by the storefront (nuevo-fonotarot).

Two-step contract:

1. ``GET  /api/v1/clients/search`` - look up an existing client so the
   storefront can attach the resulting ``client_id`` to its checkout state.
2. ``POST /api/v1/payments/complete`` - fired by the payment provider's
   webhook after a successful charge. Creates a new client or tops one up.

No auth: this prefix is intentionally open while we wire up nuevo-fonotarot.
JWT (or a shared secret) goes in before production. See ``tasks.md`` step 6.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from firenze.dependencies import get_db
from firenze.schemas.payment import (
    ClientSearchResponse,
    ClientUpdateRequest,
    ClientUpdateResponse,
    PurchaseRequest,
    PurchaseResponse,
)
from firenze.services.client_service import ClientNotFound, ServiceNotFound
from firenze.services.payment_service import (
    PinAlreadyTaken,
    apply_purchase,
    search_client,
    update_client,
)

logger = logging.getLogger("firenze")

paymentsRouter = APIRouter(prefix="/api/v1", tags=["payments"])


@paymentsRouter.get("/clients/search", response_model=ClientSearchResponse)
def clients_search(
    service: str = Query(..., description="Service slug, e.g. fonotarot-cl"),
    email: str | None = Query(default=None),
    phone: str | None = Query(default=None, description="Profile phone (Client.phone_number)"),
    ani: str | None = Query(default=None, description="Caller-ID registered to ClientAni"),
    pin: str | None = Query(default=None, description="PIN for PIN-auth services"),
    db: Session = Depends(get_db),
):
    """Search for a client in ``service`` by any combination of identifiers.

    The storefront calls this before checkout. On a hit it stores the
    returned ``client_id`` so the subsequent purchase webhook tops up the
    correct account instead of creating a duplicate.
    """
    if not any([email, phone, ani, pin]):
        raise HTTPException(
            status_code=400,
            detail="At least one of email, phone, ani, pin is required",
        )

    try:
        client = search_client(db, service, email=email, phone=phone, ani=ani, pin=pin)
    except ServiceNotFound as e:
        logger.warning("clients_search: ServiceNotFound for service=%r: %s", service, e)
        raise HTTPException(status_code=404, detail=str(e))

    if client is None:
        return ClientSearchResponse(found=False)

    return ClientSearchResponse(
        found=True,
        client_id=client.client_id,
        service=service,
        credits=client.credits,
        email=client.email,
        full_name=client.full_name,
        phone_number=client.phone_number,
    )


@paymentsRouter.post("/payments/complete", response_model=PurchaseResponse)
def payments_complete(
    payload: PurchaseRequest,
    db: Session = Depends(get_db),
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
    except PinAlreadyTaken as e:
        logger.warning(
            "clients_update: PinAlreadyTaken for service=%r client_id=%s: %s",
            service,
            client_id,
            e,
        )
        raise HTTPException(status_code=409, detail=str(e))

    return ClientUpdateResponse(**result)
