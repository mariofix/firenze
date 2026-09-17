from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from firenze.extensions import db
from firenze.models.base import TimestampMixin


class AuthLoginCode(db.Model, TimestampMixin):
    __tablename__ = "auth_login_code"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True, nullable=False)
    channel: Mapped[str] = mapped_column(String(16), default="email", nullable=False)
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    requested_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    requested_ua: Mapped[str | None] = mapped_column(String(255), nullable=True)
