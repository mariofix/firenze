import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Security
from fastapi.security import (
    OAuth2PasswordBearer,
    OAuth2PasswordRequestForm,
    SecurityScopes,
)
from jwt import PyJWTError
from sqladmin.authentication import AuthenticationBackend
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from firenze import crud, models, schemas
from firenze.config import settings
from firenze.database import SessionLocal
from firenze.dependencies import get_db

logger = logging.getLogger("firenze")

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/token",
    scopes={
        "core": "Core related endpoints",
        "asterisk": "Asterisk related endpoints",
        "firenze": "Firenze related endpoints",
        "admin": "Admin Powers",
    },
)
authRouter = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta if expires_delta else timedelta(minutes=settings.SECRET_EXPIRES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.SECRET_ALGO)


@authRouter.post(
    "/token",
    name="Get Token",
    description="Exchange username + password for a Bearer token.",
    include_in_schema=True,
    responses={401: {"model": schemas.Message}},
)
def token(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    user = crud.get_user_by_login(db, form_data.username)
    if (not user) or (
        not bcrypt.checkpw(
            form_data.password.encode("utf-8")[:72], user.password.encode("utf-8")
        )
    ):
        raise HTTPException(
            status_code=401,
            detail="User not found or invalid password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.enabled:
        raise HTTPException(
            status_code=401,
            detail="User disabled",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=settings.SECRET_EXPIRES),
    )
    return {"access_token": access_token, "token_type": "bearer"}


async def loggedin_user(
    request: Request,
    security_scopes: SecurityScopes,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    authenticate_value = (
        f'Bearer scope="{security_scopes.scope_str}"'
        if security_scopes.scopes
        else "Bearer"
    )

    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.SECRET_ALGO]
        )
    except PyJWTError as e:
        logger.warning("JWT decode error: %s", e)
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": authenticate_value},
        )

    token_user_id: str = payload.get("sub")
    if not token_user_id:
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": authenticate_value},
        )

    user = crud.get_user(db, token_user_id)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": authenticate_value},
        )

    if not user.scopes:
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": authenticate_value},
        )

    # admin scope bypasses all per-endpoint scope checks
    if "admin" in user.scopes:
        return user.id

    for scope in security_scopes.scopes:
        if scope not in user.scopes:
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient scope: '{scope}' required",
                headers={"WWW-Authenticate": authenticate_value},
            )

    return user.id


@authRouter.get(
    "/me",
    response_model=schemas.User,
    responses={401: {"model": schemas.Message}},
    summary="Current user info",
    description="Return the profile of the authenticated user.",
)
def me(
    user_id: int = Security(loggedin_user, scopes=[]),
    db: Session = Depends(get_db),
):
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        db = SessionLocal()
        try:
            user: models.User = crud.get_user_by_login(db, form["username"])
            if (not user) or (
                not bcrypt.checkpw(
                    form["password"].encode("utf-8")[:72],
                    user.password.encode("utf-8"),
                )
            ):
                logger.warning(
                    "AdminAuth: bad credentials for %r", form.get("username")
                )
                return False
            if not user.enabled:
                logger.warning("AdminAuth: disabled user %r", user.login)
                return False
            if not user.scopes or "admin" not in user.scopes:
                logger.warning("AdminAuth: user %r lacks admin scope", user.login)
                return False
            access_token = create_access_token(
                data={"sub": str(user.id)},
                expires_delta=timedelta(minutes=settings.SECRET_EXPIRES),
            )
            request.session.update({"token": access_token})
            return True
        finally:
            db.close()

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> Optional[RedirectResponse]:
        token = request.session.get("token")
        if not token:
            return RedirectResponse(request.url_for("admin:login"), status_code=302)
        try:
            payload = jwt.decode(
                token, settings.SECRET_KEY, algorithms=[settings.SECRET_ALGO]
            )
        except PyJWTError as e:
            logger.warning("AdminAuth session token error: %s", e)
            return RedirectResponse(request.url_for("admin:login"), status_code=302)

        token_user_id = payload.get("sub")
        if not token_user_id:
            return RedirectResponse(request.url_for("admin:login"), status_code=302)

        db = SessionLocal()
        try:
            user: models.User = crud.get_user(db, token_user_id)
            if not user or not user.scopes or "admin" not in user.scopes:
                return RedirectResponse(
                    request.url_for("admin:logout"), status_code=302
                )
            return True
        finally:
            db.close()
