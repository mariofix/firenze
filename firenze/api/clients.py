"""Client CRUD endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Security
from sqlalchemy.orm import Session

from firenze.auth import loggedin_user
from firenze.dependencies import get_db
from firenze.schemas.client import (
    ClientCreateRequest,
    ClientDeleteResponse,
    ClientResponse,
    ClientUpdateRequest,
)
from firenze.services.client_service import (
    ClientAlreadyExists,
    ClientNotFound,
    InvalidClientExtraConfig,
    ServiceNotFound,
    create_client,
    delete_client,
    get_client,
    update_client_record,
)

logger = logging.getLogger("firenze")

clientsRouter = APIRouter(prefix="/api/v1/clients", tags=["clients"])


@clientsRouter.get(
    "/{service}/{client_id}",
    response_model=ClientResponse,
    summary="Get client",
)
def clients_get(
    service: str,
    client_id: int,
    db: Session = Depends(get_db),
    _user_id: int = Security(loggedin_user, scopes=["firenze"]),
):
    try:
        return get_client(db, service, client_id)
    except ServiceNotFound as exc:
        logger.warning("clients_get: ServiceNotFound for service=%r: %s", service, exc)
        raise HTTPException(status_code=404, detail=str(exc))
    except ClientNotFound as exc:
        logger.warning(
            "clients_get: ClientNotFound for service=%r client_id=%s: %s",
            service,
            client_id,
            exc,
        )
        raise HTTPException(status_code=404, detail=str(exc))


@clientsRouter.post(
    "/{service}",
    response_model=ClientResponse,
    summary="Create client",
)
def clients_create(
    service: str,
    payload: ClientCreateRequest,
    db: Session = Depends(get_db),
    _user_id: int = Security(loggedin_user, scopes=["firenze"]),
):
    extra_config = (
        payload.extra_config.model_dump(exclude_none=True)
        if payload.extra_config is not None
        else None
    )
    try:
        return create_client(
            db,
            service,
            client_id=payload.client_id,
            full_name=payload.full_name,
            email=payload.email,
            pin=payload.pin,
            credits=payload.credits,
            extra_config=extra_config,
        )
    except ServiceNotFound as exc:
        logger.warning("clients_create: ServiceNotFound for service=%r: %s", service, exc)
        raise HTTPException(status_code=404, detail=str(exc))
    except ClientAlreadyExists as exc:
        logger.warning(
            "clients_create: ClientAlreadyExists for service=%r client_id=%s: %s",
            service,
            payload.client_id,
            exc,
        )
        raise HTTPException(status_code=409, detail=str(exc))
    except InvalidClientExtraConfig as exc:
        logger.warning(
            "clients_create: InvalidClientExtraConfig for service=%r client_id=%s: %s",
            service,
            payload.client_id,
            exc,
        )
        raise HTTPException(status_code=422, detail=str(exc))

@clientsRouter.patch(
    "/{service}/{client_id}",
    response_model=ClientResponse,
    summary="Update client",
)
def clients_update(
    service: str,
    client_id: int,
    payload: ClientUpdateRequest,
    db: Session = Depends(get_db),
    _user_id: int = Security(loggedin_user, scopes=["firenze"]),
):
    extra_config_provided = "extra_config" in payload.model_fields_set
    extra_config = (
        payload.extra_config.model_dump(exclude_none=True)
        if payload.extra_config is not None
        else None
    )
    try:
        return update_client_record(
            db,
            service,
            client_id=client_id,
            full_name=payload.full_name,
            email=payload.email,
            pin=payload.pin,
            credits=payload.credits,
            extra_config=extra_config,
            extra_config_provided=extra_config_provided,
        )
    except ServiceNotFound as exc:
        logger.warning("clients_update: ServiceNotFound for service=%r: %s", service, exc)
        raise HTTPException(status_code=404, detail=str(exc))
    except ClientNotFound as exc:
        logger.warning(
            "clients_update: ClientNotFound for service=%r client_id=%s: %s",
            service,
            client_id,
            exc,
        )
        raise HTTPException(status_code=404, detail=str(exc))
    except InvalidClientExtraConfig as exc:
        logger.warning(
            "clients_update: InvalidClientExtraConfig for service=%r client_id=%s: %s",
            service,
            client_id,
            exc,
        )
        raise HTTPException(status_code=422, detail=str(exc))

@clientsRouter.delete(
    "/{service}/{client_id}",
    response_model=ClientDeleteResponse,
    summary="Delete client",
)
def clients_delete(
    service: str,
    client_id: int,
    db: Session = Depends(get_db),
    _user_id: int = Security(loggedin_user, scopes=["firenze"]),
):
    try:
        return delete_client(db, service, client_id=client_id)
    except ServiceNotFound as exc:
        logger.warning("clients_delete: ServiceNotFound for service=%r: %s", service, exc)
        raise HTTPException(status_code=404, detail=str(exc))
    except ClientNotFound as exc:
        logger.warning(
            "clients_delete: ClientNotFound for service=%r client_id=%s: %s",
            service,
            client_id,
            exc,
        )
        raise HTTPException(status_code=404, detail=str(exc))
