import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Security, status
from fastapi.security import SecurityScopes
from sqladmin.authentication import AuthenticationBackend
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from firenze import crud, schemas
from firenze.config import settings
from firenze.database import SessionLocal
from firenze.dependencies import get_db
from firenze.services import auth_service

logger = logging.getLogger("firenze")

authRouter = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@authRouter.post(
    "/passwordless/request",
    response_model=schemas.PasswordlessRequestResponse,
    summary="Solicitar código de inicio de sesión de una sola vez",
)
def passwordless_request(
    payload: schemas.PasswordlessRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    if not settings.AUTH_PASSWORDLESS_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El inicio de sesión sin contraseña está deshabilitado",
        )

    detail = "Si la cuenta existe, se ha enviado un código de inicio de sesión."
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


async def loggedin_user(
    security_scopes: SecurityScopes,
    db: Session = Depends(get_db),
    x_api_key: str | None = Header(default=None, alias="x-api-key"),
    x_api_secret: str | None = Header(default=None, alias="x-api-secret"),
):
    if not x_api_key or not x_api_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales de API faltantes",
        )

    auth_result = auth_service.authenticate_api_credential(db, x_api_key, x_api_secret)
    if not auth_result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales de API inválidas",
        )
    user, _credential = auth_result

    if not user.scopes:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se pudo validar credenciales",
        )

    if not auth_service.has_required_scopes(user, security_scopes.scopes):
        missing = [scope for scope in security_scopes.scopes if scope not in user.scopes]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Alcance insuficiente: '{missing[0]}' requerido",
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se pudo validar credenciales",
        )

    return user.id


@authRouter.get(
    "/me",
    response_model=schemas.User,
    responses={401: {"model": schemas.Message}},
    summary="Información del usuario actual",
    description="Retorna el perfil del usuario autenticado.",
)
def me(
    user_id: int = Security(loggedin_user, scopes=[]),
    db: Session = Depends(get_db),
):
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    return user


class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        if not settings.AUTH_PASSWORD_LOGIN_ENABLED:
            logger.warning("AdminAuth: password login is disabled")
            return False

        form = await request.form()
        db = SessionLocal()
        try:
            user = auth_service.authenticate_password_user(db, form["username"], form["password"])
            if not user:
                logger.warning("AdminAuth: bad credentials for %r", form.get("username"))
                return False
            if not auth_service.has_required_scopes(user, ["admin"]):
                logger.warning("AdminAuth: user %r lacks admin scope", user.login)
                return False
            request.session.update({"admin_user_id": user.id})
            return True
        finally:
            db.close()

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> RedirectResponse | None:
        user_id = request.session.get("admin_user_id")
        if not user_id:
            return RedirectResponse(request.url_for("admin:login"), status_code=302)

        db = SessionLocal()
        try:
            user = crud.get_user(db, user_id)
            if not user or not user.enabled:
                return RedirectResponse(request.url_for("admin:login"), status_code=302)
            if not auth_service.has_required_scopes(user, ["admin"]):
                return RedirectResponse(request.url_for("admin:logout"), status_code=302)
            return True
        finally:
            db.close()
