from __future__ import annotations
from sqlalchemy import String
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column

from firenze.extensions import db
from firenze.models.base import TimestampMixin


class Event(db.Model, TimestampMixin):
    __tablename__ = "event"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    ip: Mapped[str | None] = mapped_column(String(16), index=True)
    port: Mapped[int | None] = mapped_column()
    verb: Mapped[str] = mapped_column(String(10), index=True)
    url: Mapped[str] = mapped_column(String(255), index=True)
    data: Mapped[str | None] = mapped_column(LONGTEXT)

    def __str__(self):
        return self.name
