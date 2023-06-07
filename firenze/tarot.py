import datetime
import json
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, Security
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi_crudrouter import SQLAlchemyCRUDRouter
from sqlalchemy.orm import Session
from thankyou import give_thanks

from firenze.auth import loggedin_user

from .database import SessionLocal
from .exceptions import GenericError, ProcessError
from .models import FonoTarotLatamClient
from .schemas import FonoTarotLatam, NewFonotarotLatam, UpdateFonotarotLatam

tarotRouter = APIRouter(prefix="/tarot")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


fonotarot_latam = SQLAlchemyCRUDRouter(
    schema=FonoTarotLatam,
    create_schema=NewFonotarotLatam,
    update_schema=UpdateFonotarotLatam,
    db_model=FonoTarotLatamClient,
    db=get_db,
    prefix="fonotarot-latam",
    tags=["fonotarot-latam"],
    delete_all_route=False,
    delete_one_route=False,
    dependencies=[Security(loggedin_user, scopes=["tarot"])],
)

tarotRouter.include_router(fonotarot_latam)
