import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from firenze.database import Base
from firenze.models.base import TimestampMixin


class Operator(Base, TimestampMixin):
    __tablename__ = "operator"

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[int] = mapped_column(unique=True)
    name: Mapped[str] = mapped_column(String(64))
    description: Mapped[Optional[str]] = mapped_column(LONGTEXT, default=None)
    enable_valkey: Mapped[bool] = mapped_column(default=True)
    loggedin: Mapped[bool] = mapped_column(default=False)
    available: Mapped[bool] = mapped_column(default=False)
    lastcall: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    option: Mapped[str] = mapped_column(String(2), unique=True)
    audio_file: Mapped[Optional[str]] = mapped_column(String(255), default=None)
    numbers: Mapped[list["OperatorPhone"]] = relationship(back_populates="operator")

    def __str__(self):
        return f"{self.number}"


class OperatorPhone(Base, TimestampMixin):
    __tablename__ = "operator_phone"

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(16))
    enabled: Mapped[bool] = mapped_column(default=True)
    contact: Mapped[bool] = mapped_column(default=False)
    pin: Mapped[Optional[str]] = mapped_column(String(4))
    trunk: Mapped[Optional[str]] = mapped_column(String(32))
    operator_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("operator.id", ondelete="CASCADE", onupdate="CASCADE"),
    )
    operator: Mapped[Optional["Operator"]] = relationship(back_populates="numbers")

    def __str__(self):
        return f"{self.number}@{self.trunk}"
