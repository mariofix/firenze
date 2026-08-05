from __future__ import annotations
from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import TimestampMixin


class Service(db.Model, TimestampMixin):
    __tablename__ = "service"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(255), index=True)
    auth_method: Mapped[str] = mapped_column(String(8), default="ani")
    intro_audio: Mapped[str] = mapped_column(String(255), default="")
    numbers: Mapped[list[ServiceNumber]] = relationship(back_populates="service")

    def __str__(self):
        return self.name


class ServiceNumber(db.Model, TimestampMixin):
    __tablename__ = "service_did"

    id: Mapped[int] = mapped_column(primary_key=True)
    did: Mapped[str] = mapped_column(String(32), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    asterisk_context: Mapped[str] = mapped_column(String(32))
    service_id: Mapped[int | None] = mapped_column(
        ForeignKey("service.id", ondelete="SET NULL", onupdate="CASCADE"),
    )
    service: Mapped[Service | None] = relationship(back_populates="numbers")

    def __str__(self):
        return self.did
