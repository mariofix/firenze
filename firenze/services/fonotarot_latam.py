from typing import Optional
from fastapi import APIRouter, Security, Depends, Query, Request
from fastapi_crudrouter import SQLAlchemyCRUDRouter as CRUDRouter
from firenze.database import SessionLocal
from firenze.schemas import (
    FonotarotLatam as TheSchema,
    NuevoFonotarotLatam as TheNewSchema,
    Message,
)
from firenze.models import FonotarotLatam as TheModel
from firenze.auth import loggedin_user


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Usamos el slug definido en servicios
app = CRUDRouter(
    prefix="/fonotarot-latam",
    schema=TheSchema,
    create_schema=TheNewSchema,
    db_model=TheModel,
    db=get_db,
    tags=["Fonotarot Latam"],
    get_all_route=False,
    delete_all_route=False,
    delete_one_route=False,
    dependencies=[Security(loggedin_user, scopes=["firenze"])],
)


@app.get(
    "/search",
    description="Busca registro",
    response_model=TheSchema,
    responses={404: {"model": Message}},
    summary="Busca registro",
    dependencies=[Depends(get_db)],
    response_model_exclude_unset=True,
)
def ftl_search(
    request: Request,
    correo: Optional[str] = Query(None, max_length=512),
    telefono: Optional[str] = Query(None, max_length=16),
    client_id: Optional[int] = Query(None),
    pin: Optional[int] = Query(None),
    uid=Security(loggedin_user, scopes=["firenze"]),
):
    pass
