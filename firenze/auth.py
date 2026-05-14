import logging
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Security, status
from fastapi.security import (
    OAuth2PasswordBearer,
    OAuth2PasswordRequestForm,
    SecurityScopes,
)
from jwt import PyJWTError
from sqladmin.authentication import AuthenticationBackend
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from firenze import crud, schemas
from firenze.config import settings
from firenze.database import SessionLocal
from firenze.dependencies import get_db
from firenze.services import auth_service

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
    return auth_service.create_access_token(data=data, expires_delta=expires_delta)


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
    if not settings.AUTH_PASSWORD_LOGIN_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Password login is disabled",
        )

    user = auth_service.authenticate_password_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="User not found or invalid password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=settings.SECRET_EXPIRES),
    )
    return {"access_token": access_token, "token_type": "bearer"}


@authRouter.post(
    "/passwordless/request",
    response_model=schemas.PasswordlessRequestResponse,
    summary="Request one-time login code",
)
def passwordless_request(
    payload: schemas.PasswordlessRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    if not settings.AUTH_PASSWORDLESS_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Passwordless login is disabled",
        )

    detail = "If the account exists, a login code has been sent."
    user = auth_service.find_user_for_passwordless_identifier(db, payload.identifier)
    if not user or not user.enabled or not user.email:
        return {"ok": True, "detail": detail}

    request_ip = request.client.host if request.client else ""
    user_agent = request.headers.get("user-agent", "")
    if not auth_service.can_issue_passwordless_code(db, user, request_ip):
        return {"ok": True, "detail": detail}

    code = auth_service.create_passwordless_code(db, user, request_ip, user_agent)
    auth_service.send_passwordless_code_email(user.email, code)
    return {"ok": True, "detail": detail}


@authRouter.post(
    "/passwordless/verify",
    summary="Verify one-time login code",
)
def passwordless_verify(
    payload: schemas.PasswordlessVerify,
    db: Session = Depends(get_db),
):
    if not settings.AUTH_PASSWORDLESS_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Passwordless login is disabled",
        )

    user = auth_service.verify_passwordless_code(db, payload.identifier, payload.code)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired code",
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
        payload = auth_service.decode_access_token(token)
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

    if not user.enabled:
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

    if not auth_service.has_required_scopes(user, security_scopes.scopes):
        missing = [scope for scope in security_scopes.scopes if scope not in user.scopes]
        if missing:
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient scope: '{missing[0]}' required",
                headers={"WWW-Authenticate": authenticate_value},
            )
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
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
        if not settings.AUTH_PASSWORD_LOGIN_ENABLED:
            logger.warning("AdminAuth: password login is disabled")
            return False

        form = await request.form()
        db = SessionLocal()
        try:
            user = auth_service.authenticate_password_user(
                db, form["username"], form["password"]
            )
            if not user:
                logger.warning(
                    "AdminAuth: bad credentials for %r", form.get("username")
                )
                return False
            if not auth_service.has_required_scopes(user, ["admin"]):
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

        db = SessionLocal()
        try:
            user = auth_service.get_user_from_token(db, token)
            if not user:
                return RedirectResponse(request.url_for("admin:login"), status_code=302)
            if not auth_service.has_required_scopes(user, ["admin"]):
                return RedirectResponse(
                    request.url_for("admin:logout"), status_code=302
                )
            return True
        finally:
            db.close()
