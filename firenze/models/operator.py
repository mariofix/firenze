from __future__ import annotations
import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from firenze.extensions import db
from firenze.models.base import TimestampMixin


class Operator(db.Model, TimestampMixin):
    __tablename__ = "operator"

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[int] = mapped_column(unique=True)
    name: Mapped[str] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(LONGTEXT, default=None)
    loggedin: Mapped[bool] = mapped_column(default=False)
    available: Mapped[bool] = mapped_column(default=False)
    lastcall: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    option: Mapped[str] = mapped_column(String(2), unique=True)
    audio_file: Mapped[str | None] = mapped_column(String(255), default=None)
    numbers: Mapped[list[OperatorPhone]] = relationship(back_populates="operator")

    def __str__(self):
        return f"{self.number}"


class OperatorPhone(db.Model, TimestampMixin):
    __tablename__ = "operator_phone"

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(16))
    enabled: Mapped[bool] = mapped_column(default=True)
    contact: Mapped[bool] = mapped_column(default=False)
    pin: Mapped[str | None] = mapped_column(String(4))
    trunk: Mapped[str | None] = mapped_column(String(32))
    operator_id: Mapped[int | None] = mapped_column(
        ForeignKey("operator.id", ondelete="CASCADE", onupdate="CASCADE"),
    )
    operator: Mapped[Operator | None] = relationship(back_populates="numbers")

    def __str__(self):
        return f"{self.number}@{self.trunk}"
