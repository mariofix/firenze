from typing import Optional

from sqlalchemy import String
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from firenze.database import Base
from firenze.models.base import TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    login: Mapped[str] = mapped_column(String(64), unique=True)
    email: Mapped[str] = mapped_column(String(255))
    password: Mapped[str] = mapped_column(String(255))
    allowed_ips: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    enabled: Mapped[bool] = mapped_column(default=True)
    scopes: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    def __str__(self):
        return self.login
