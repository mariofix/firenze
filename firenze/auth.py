from fastapi import Depends, APIRouter, Request, HTTPException, Security
from fastapi.security import (
    OAuth2PasswordBearer,
    OAuth2PasswordRequestForm,
    SecurityScopes,
)
from starlette.responses import RedirectResponse
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from sqladmin.authentication import AuthenticationBackend
from firenze.database import SessionLocal
from firenze import crud, schemas, models
from firenze.config import settings
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional
import logging

logger = logging.getLogger("firenze")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/token",
    scopes={
        "core": "Core related endpoints",
        "audiotex": "VoiceWorks related endpoints(legacy)",
        "asterisk": "Asterisk related endpoints",
        "firenze": "Firenze related endpoints",
        "admin": "Admin Powers",
    },
)
authRouter = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=1)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.SECRET_ALGO
    )
    return encoded_jwt


@authRouter.post(
    "/token",
    name="Get Token",
    description="Get Token",
    include_in_schema=True,
    responses={401: {"model": schemas.Message}},
    tags=["auth"],
)
def token(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    user = crud.get_user_by_login(db, form_data.username)
    if (not user) or (not pwd_context.verify(form_data.password, user.password)):
        raise HTTPException(
            status_code=401,
            detail="User not found or invalid password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.enabled == 0:
        raise HTTPException(
            status_code=401,
            detail="User disabled",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=settings.SECRET_EXPIRES)
    # No se puede guardar un int en sub 🤷
    token_info = {"sub": str(user.id)}
    token = create_access_token(data=token_info, expires_delta=access_token_expires)

    return {"access_token": token, "token_type": "bearer"}


async def loggedin_user(
    request: Request,
    security_scopes: SecurityScopes,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    if security_scopes.scopes:
        authenticate_value = f'Bearer scope="{security_scopes.scope_str}"'
    else:
        authenticate_value = "Bearer"

    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.SECRET_ALGO]
        )
    except JWTError as e:
        request.app.logger.warning(e)
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": authenticate_value},
        )

    token_user_id: int = payload.get("sub")
    if not token_user_id:
        request.app.logger.warning(f"{token_user_id=}")
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": authenticate_value},
        )
    user = crud.get_user(db, token_user_id)
    if not user:
        request.app.logger.warning(f"{user=}")
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": authenticate_value},
        )

    if not user.scopes:
        request.app.logger.warning(f"{user=} no tiene scopes definidos")
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": authenticate_value},
        )
    if "admin" in user.scopes:
        request.app.logger.info(f"{user=} is admin")
        return user.id

    request.app.logger.info(f"{user.scopes=}")
    for scope in security_scopes.scopes:
        if scope not in user.scopes:
            raise HTTPException(
                status_code=401,
                detail=f"Can't access this (scope '{security_scopes.scope_str}' not found)",
                headers={"WWW-Authenticate": authenticate_value},
            )

    return user.id


class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        db = SessionLocal()
        user: models.User = crud.get_user_by_login(db, form["username"])
        logger.info(f"{user=}")
        if (not user) or (not pwd_context.verify(form["password"], user.password)):
            logger.warning("User not found or invalid password")
            return False
        if user.enabled == 0:
            logger.warning("User disabled")
            return False
        access_token_expires = timedelta(minutes=settings.SECRET_EXPIRES)
        token_info = {"sub": str(user.id)}
        token = create_access_token(data=token_info, expires_delta=access_token_expires)
        request.session.update({"token": token})
        return True

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> Optional[RedirectResponse]:
        token = request.session.get("token")
        if not token:
            logger.warning(f"{token=}")
            return RedirectResponse(request.url_for("admin:login"), status_code=302)
        try:
            payload = jwt.decode(
                token, settings.SECRET_KEY, algorithms=[settings.SECRET_ALGO]
            )
        except JWTError as e:
            logger.warning(e)
            return RedirectResponse(request.url_for("admin:login"), status_code=302)

        token_user_id: int = payload.get("sub")
        if not token_user_id:
            logger.warning(f"{token_user_id=}")
            return RedirectResponse(request.url_for("admin:login"), status_code=302)

        db = SessionLocal()
        user: models.User = crud.get_user(db, token_user_id)
        if not user:
            logger.warning(f"{user=}")
            return RedirectResponse(request.url_for("admin:logout"), status_code=302)

        if not user.scopes:
            logger.warning(f"{user.scopes=}")
            return RedirectResponse(request.url_for("admin:logout"), status_code=302)

        if "admin" not in user.scopes:
            logger.warning(f"{user=} is not admin")
            return RedirectResponse(request.url_for("admin:logout"), status_code=302)

        return True
