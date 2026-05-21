import secrets
from datetime import UTC, datetime, timedelta

import bcrypt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from daleks.contrib.client import DaleksClient
from sqlalchemy import or_
from sqlalchemy.orm import Session

from firenze import crud, models
from firenze.config import settings
from firenze.models.auth_login_code import AuthLoginCode

_argon2_hasher = PasswordHasher()


def hash_secret(secret: str) -> str:
    return _argon2_hasher.hash(secret)


def verify_secret(secret: str, secret_hash: str) -> bool:
    try:
        return _argon2_hasher.verify(secret_hash, secret)
    except VerifyMismatchError, VerificationError, InvalidHashError:
        return False


def generate_api_key() -> str:
    return f"fk_{secrets.token_urlsafe(24)}"


def generate_api_secret() -> str:
    return secrets.token_urlsafe(48)


def _is_credential_active(credential: models.ApiCredential) -> bool:
    now = datetime.now(UTC)
    if not credential.enabled:
        return False
    if credential.revoked_at:
        return False
    expires_at = credential.expires_at
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at and expires_at <= now:
        return False
    return True


def create_api_credential(
    db: Session,
    user: models.User,
    name: str | None = None,
    expires_at: datetime | None = None,
) -> tuple[models.ApiCredential, str]:
    api_secret = generate_api_secret()
    api_key = generate_api_key()
    # Retry collisions defensively; key is public identifier.
    for _ in range(5):
        exists = db.query(models.ApiCredential).filter(models.ApiCredential.api_key == api_key).first()
        if not exists:
            break
        api_key = generate_api_key()
    else:
        raise RuntimeError("Could not generate unique API key")

    credential = models.ApiCredential(
        user_id=user.id,
        name=name,
        api_key=api_key,
        api_secret_hash=hash_secret(api_secret),
        enabled=True,
        expires_at=expires_at,
        revoked_at=None,
    )
    db.add(credential)
    db.commit()
    db.refresh(credential)
    return credential, api_secret


def revoke_api_credential(db: Session, credential: models.ApiCredential) -> models.ApiCredential:
    credential.enabled = False
    credential.revoked_at = datetime.now(UTC)
    db.commit()
    db.refresh(credential)
    return credential


def authenticate_api_credential(
    db: Session, api_key: str, api_secret: str
) -> tuple[models.User, models.ApiCredential] | None:
    credential = db.query(models.ApiCredential).filter(models.ApiCredential.api_key == api_key).first()
    if not credential:
        return None
    if not _is_credential_active(credential):
        return None
    if not verify_secret(api_secret, credential.api_secret_hash):
        return None
    user = crud.get_user(db, credential.user_id)
    if not user or not user.enabled:
        return None
    credential.last_used_at = datetime.now(UTC)
    db.commit()
    return user, credential


def hash_user_password(password: str) -> str:
    return hash_secret(password)


def verify_password(password: str, password_hash: str) -> bool:
    if password_hash.startswith("$argon2"):
        return verify_secret(password, password_hash)
    return bcrypt.checkpw(password.encode("utf-8")[:72], password_hash.encode("utf-8"))


def authenticate_password_user(db: Session, login: str, password: str) -> models.User | None:
    user = crud.get_user_by_login(db, login)
    if not user:
        return None
    if not verify_password(password, user.password):
        return None
    if not user.enabled:
        return None
    return user


def has_required_scopes(user: models.User, required_scopes: list[str]) -> bool:
    if not user.scopes:
        return False
    if "admin" in user.scopes:
        return True
    for scope in required_scopes:
        if scope not in user.scopes:
            return False
    return True


def find_user_for_passwordless_identifier(db: Session, identifier: str) -> models.User | None:
    return db.query(models.User).filter(or_(models.User.login == identifier, models.User.email == identifier)).first()


def can_issue_passwordless_code(db: Session, user: models.User, request_ip: str) -> bool:
    now = datetime.now(UTC)
    cutoff = now - timedelta(seconds=settings.AUTH_PASSWORDLESS_REQUEST_WINDOW_SECONDS)
    user_count = (
        db.query(AuthLoginCode)
        .filter(
            AuthLoginCode.user_id == user.id,
            AuthLoginCode.channel == "email",
            AuthLoginCode.created_at >= cutoff,
        )
        .count()
    )
    if user_count >= settings.AUTH_PASSWORDLESS_MAX_REQUESTS_PER_WINDOW:
        return False

    if request_ip:
        ip_count = (
            db.query(AuthLoginCode)
            .filter(
                AuthLoginCode.channel == "email",
                AuthLoginCode.requested_ip == request_ip,
                AuthLoginCode.created_at >= cutoff,
            )
            .count()
        )
        if ip_count >= settings.AUTH_PASSWORDLESS_MAX_REQUESTS_PER_IP_PER_WINDOW:
            return False

    return True


def create_passwordless_code(db: Session, user: models.User, request_ip: str, user_agent: str) -> str:
    now = datetime.now(UTC)
    db.query(AuthLoginCode).filter(
        AuthLoginCode.user_id == user.id,
        AuthLoginCode.channel == "email",
        AuthLoginCode.consumed_at.is_(None),
        AuthLoginCode.expires_at > now,
    ).update({"consumed_at": now}, synchronize_session=False)

    plain_code = str(secrets.randbelow(900000) + 100000)
    code_hash = bcrypt.hashpw(plain_code.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    code = AuthLoginCode(
        user_id=user.id,
        channel="email",
        code_hash=code_hash,
        expires_at=now + timedelta(minutes=settings.AUTH_PASSWORDLESS_CODE_TTL_MINUTES),
        consumed_at=None,
        attempts=0,
        max_attempts=settings.AUTH_PASSWORDLESS_MAX_ATTEMPTS,
        requested_ip=request_ip,
        requested_ua=(user_agent or "")[:255],
    )
    db.add(code)
    db.commit()
    return plain_code


def send_passwordless_code_email(recipient: str, code: str) -> None:
    if not settings.DALEKS_URL:
        raise RuntimeError("DALEKS_URL is not configured")
    if not settings.DALEKS_FROM:
        raise RuntimeError("DALEKS_FROM is not configured")
    smtp_account = settings.DALEKS_SMTP_ACCOUNT or None
    with DaleksClient(settings.DALEKS_URL, smtp_account=smtp_account) as client:
        client.send_email(
            from_address=settings.DALEKS_FROM,
            to=[recipient],
            subject="Your Firenze login code",
            text_body=(
                f"Your Firenze login code is: {code}\n\n"
                f"It expires in {settings.AUTH_PASSWORDLESS_CODE_TTL_MINUTES} minutes."
            ),
        )


def verify_passwordless_code(db: Session, identifier: str, code: str) -> models.User | None:
    now = datetime.now(UTC)
    user = find_user_for_passwordless_identifier(db, identifier)
    if not user or not user.enabled:
        return None

    login_code = (
        db.query(AuthLoginCode)
        .filter(
            AuthLoginCode.user_id == user.id,
            AuthLoginCode.channel == "email",
            AuthLoginCode.consumed_at.is_(None),
            AuthLoginCode.expires_at > now,
        )
        .order_by(AuthLoginCode.created_at.desc())
        .first()
    )
    if not login_code:
        return None

    if login_code.attempts >= login_code.max_attempts:
        login_code.consumed_at = now
        db.commit()
        return None

    if not bcrypt.checkpw(code.encode("utf-8"), login_code.code_hash.encode("utf-8")):
        login_code.attempts += 1
        if login_code.attempts >= login_code.max_attempts:
            login_code.consumed_at = now
        db.commit()
        return None

    login_code.consumed_at = now
    db.commit()
    return user
