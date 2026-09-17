from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from firenze.extensions import db
from firenze.models.base import TimestampMixin

if TYPE_CHECKING:
    from firenze.models.api_credential import ApiCredential


class User(db.Model, TimestampMixin):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    login: Mapped[str] = mapped_column(String(64), unique=True)
    email: Mapped[str] = mapped_column(String(255))
    password: Mapped[str] = mapped_column(String(255))
    allowed_ips: Mapped[list | None] = mapped_column(JSON, nullable=True)
    enabled: Mapped[bool] = mapped_column(default=True)
    scopes: Mapped[list | None] = mapped_column(JSON, nullable=True)
    api_credentials: Mapped[list[ApiCredential]] = relationship(back_populates="user", cascade="all, delete-orphan")

    def __str__(self):
        return self.login
