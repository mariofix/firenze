import logging
import secrets
import string

from sqlalchemy.orm import Session

from firenze import models, schemas
from firenze.services import auth_service

logger = logging.getLogger("firenze")


def get_user(db: Session, user_id: int):
    logger.debug(f"get_user(db, {user_id})")
    return db.query(models.User).filter(models.User.id == user_id).first()


def get_user_by_login(db: Session, login: str):
    logger.debug(f"get_user_by_login(db, {login})")
    return db.query(models.User).filter(models.User.login == login).first()


def get_users(db: Session, skip: int = 0, limit: int = 100):
    logger.debug(f"get_users(db, {skip}, {limit})")
    return db.query(models.User).offset(skip).limit(limit).all()


def create_user(db: Session, user: schemas.UserCreate):
    pwd_hash = auth_service.hash_user_password(user.password)
    db_user = models.User(
        email=user.email,
        login=user.login,
        password=pwd_hash,
        scopes=user.scopes,
        allowed_ips=user.allowed_ips,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    logger.debug(f"Created {db_user=}")
    return db_user


def get_events(db: Session, skip: int = 0, limit: int = 100):
    logger.debug(f"get_events(db, {skip}, {limit})")
    return db.query(models.Event).order_by(models.Event.id.desc()).offset(skip).limit(limit).all()


def create_event(event_name: str, extra: str, data: str, request: Request, db: Session):
    event = models.Event(
        name=event_name,
        ip=request.client.host,
        port=request.client.port,
        verb=request.method,
        url=request.url,
        data=data,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    logger.debug(f"Created {event=}")
    return event


def check_pin(db: Session, pin) -> bool:
    logger.debug(f"check_pin({pin})")
    # return db.query(models.FonoTarotLatamClient).filter(models.FonoTarotLatamClient.pin_code == pin).exists()
    return False


# def generate_pin() -> int:
#     from ..core import get_db

#     db = get_db()
#     logger.debug("generate_pin()")
#     random_pin = int("".join(secrets.choice(string.digits) for i in range(8)))
#     if check_pin(db, random_pin):
#         raise Exception(f"{random_pin=} ya existe")
#     else:
#         return random_pin
