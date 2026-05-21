import datetime
import json

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    Security,
)
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from thankyou import give_thanks

from firenze import auth, crud, schemas
from firenze.database import SessionLocal
from firenze.models import Event

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
@coreRouter.head(
    "/thanks",
    name="Thanks",
    description='"Thanks" in a random language.',
    include_in_schema=True,
    tags=["core"],
)
def thanks(
    db: Session = Depends(get_db),
):
    crud.get_users(db)
    return {"message": give_thanks(), "time": datetime.datetime.now()}


@coreRouter.get(
    "/events/",
    name="List Events",
    response_model=list[schemas.Event],
    tags=["core"],
    include_in_schema=True,
)
def get_events(uid=Security(auth.loggedin_user, scopes=["core"]), db: Session = Depends(get_db)):
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
    if "content-type" in request.headers and "application/json" in request.headers.get("content-type"):
        data = await request.body()
    else:
        data = await request.form()
        data = json.dumps(data._dict)

    try:
        crud.create_event(event_name, extra, data, request, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unable to create Event: {e}")

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
