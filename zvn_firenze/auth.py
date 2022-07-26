from fastapi import Depends, APIRouter, Request, HTTPException, Security
from fastapi.security import (
    OAuth2PasswordBearer,
    OAuth2PasswordRequestForm,
    SecurityScopes,
)
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from zvn_firenze.database import SessionLocal
from zvn_firenze import crud, schemas, models
from zvn_firenze.config import settings
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/token",
    scopes={
        "core": "Core related endpoints",
        "audiotex": "VoiceWorks related endpoints",
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
    final_scopes = list(set(user.scopes).intersection(form_data.scopes))
    # No se puede guardar un int en sub 🤷
    token_info = {"sub": str(user.id), "scopes": final_scopes}
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

    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": authenticate_value},
    )

    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.SECRET_ALGO]
        )
    except JWTError as e:
        request.app.logger.error(e)
        raise credentials_exception

    token_user_id: int = payload.get("sub")
    if not token_user_id:
        request.app.logger.error(f"{token_user_id=}")
        raise credentials_exception
    user = crud.get_user(db, token_user_id)
    if not user:
        raise credentials_exception

    token_scopes = payload.get("scopes", [])
    for scope in security_scopes.scopes:
        if scope not in token_scopes:
            raise HTTPException(
                status_code=401,
                detail=f"Can't access this (scope '{security_scopes.scope_str}' not found)",
                headers={"WWW-Authenticate": authenticate_value},
            )

    return user.id
