from fastapi import (
    Depends,
    APIRouter,
    Request,
    HTTPException,
    BackgroundTasks,
    Security,
)
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from thankyou import give_thanks
from typing import List
from firenze import crud, schemas, auth
from firenze.models import Event
from firenze.exceptions import GenericError, ProcessError
from firenze.database import SessionLocal
import datetime
import json

coreRouter = APIRouter()
jinjaEngine = Jinja2Templates(directory="templates")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@coreRouter.get("/", include_in_schema=False, response_class=HTMLResponse)
def index(request: Request):
    return jinjaEngine.TemplateResponse("home.html", {"request": request})


@coreRouter.get(
    "/thanks",
    name="Thanks",
    description='"Thanks" in a random language.',
    include_in_schema=True,
    tags=["core"],
)
def thanks():
    thanks = give_thanks()
    return {"message": thanks, "time": datetime.datetime.now()}


@coreRouter.post(
    "/users/",
    name="Create User",
    response_model=schemas.User,
    responses={409: {"model": schemas.Message}},
    tags=["core"],
    include_in_schema=True,
)
def create_user(
    user: schemas.UserCreate,
    uid=Depends(auth.loggedin_user),
    db: Session = Depends(get_db),
):
    db_user = crud.get_user_by_login(db, login=user.login)
    if db_user:
        raise HTTPException(status_code=409, detail="User Exists")
    return crud.create_user(db=db, user=user)


@coreRouter.get(
    "/users/",
    name="List Users",
    response_model=List[schemas.User],
    tags=["core"],
    include_in_schema=True,
)
def read_users(
    uid=Security(auth.loggedin_user, scopes=["core"]),
    db: Session = Depends(get_db),
):
    users = crud.get_users(db)
    return users


@coreRouter.get(
    "/users/{user_id}",
    name="Read User",
    response_model=schemas.User,
    responses={404: {"model": schemas.Message}},
    include_in_schema=True,
    tags=["core"],
)
def read_user(
    user_id: int,
    uid=Security(auth.loggedin_user, scopes=["core"]),
    db: Session = Depends(get_db),
):
    db_user = crud.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user


@coreRouter.get(
    "/events/",
    name="List Events",
    response_model=List[schemas.Event],
    tags=["core"],
    include_in_schema=True,
)
def get_events(
    uid=Security(auth.loggedin_user, scopes=["core"]), db: Session = Depends(get_db)
):
    events = crud.get_events(db)

    return events


@coreRouter.post(
    "/events/{event_name}/{extra}",
    name="Create Event",
    response_model=schemas.Message,
    tags=["core"],
    include_in_schema=True,
)
async def create_event(
    event_name: str,
    extra: str,
    request: Request,
    tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    if "application/json" in request.headers.get("content-type"):
        data = await request.body()
    else:
        data = await request.form()
        data = json.dumps(data._dict)

    try:
        event = crud.create_event(event_name, extra, data, request, db)
    except Exception as e:
        HTTPException(status_code=500, detail=f"Unable to create Event: {e}")

    return {"message": "OK", "detail": give_thanks()}


@coreRouter.get(
    "/events/{event_id}/process",
    name="Process Event",
    response_model=schemas.Message,
    tags=["core"],
    include_in_schema=True,
)
async def process_event(
    event_id: int,
    request: Request,
    tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event does not exist")
    request.app.logger.debug(f"{event=}")
