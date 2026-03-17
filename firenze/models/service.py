from typing import Optional

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from firenze.database import Base
from firenze.models.base import TimestampMixin


class Service(Base, TimestampMixin):
    __tablename__ = "service"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(255), index=True)
    numbers: Mapped[list["ServiceNumber"]] = relationship(back_populates="service")

    def __str__(self):
        return self.name


class ServiceNumber(Base, TimestampMixin):
    __tablename__ = "service_did"

    id: Mapped[int] = mapped_column(primary_key=True)
    did: Mapped[str] = mapped_column(String(32), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    asterisk_context: Mapped[str] = mapped_column(String(32))
    service_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("service.id", ondelete="SET NULL", onupdate="CASCADE"),
    )
    service: Mapped[Optional["Service"]] = relationship(back_populates="numbers")

    def __str__(self):
        return self.did
