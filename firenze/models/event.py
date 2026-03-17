from typing import Optional

from sqlalchemy import String
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column

from firenze.database import Base
from firenze.models.base import TimestampMixin


class Event(Base, TimestampMixin):
    __tablename__ = "event"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    ip: Mapped[Optional[str]] = mapped_column(String(16), index=True)
    port: Mapped[Optional[int]] = mapped_column()
    verb: Mapped[str] = mapped_column(String(10), index=True)
    url: Mapped[str] = mapped_column(String(255), index=True)
    data: Mapped[Optional[str]] = mapped_column(LONGTEXT)

    def __str__(self):
        return self.name
