from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from firenze.database import Base
from firenze.models.base import TimestampMixin

if TYPE_CHECKING:
    from firenze.models.user import User


class ApiCredential(Base, TimestampMixin):
    __tablename__ = "api_credential"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE", onupdate="CASCADE"),
        index=True,
    )
    name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    api_key: Mapped[str] = mapped_column(String(96), unique=True, index=True)
    api_secret_hash: Mapped[str] = mapped_column(String(255))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    last_used_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship(back_populates="api_credentials")

    def __str__(self):
        return f"{self.api_key[:6]}...{self.api_key[-5:]}"
