import secrets
import string
from typing import Optional

from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint, event
from sqlalchemy.orm import Mapped, mapped_column, relationship

from firenze.database import Base
from firenze.models.base import TimestampMixin


def _generate_pin() -> str:
    """Generate a random 8-digit PIN string."""
    return "".join(secrets.choice(string.digits) for _ in range(8))


class Client(Base, TimestampMixin):
    """Unified client model — one row per client per service.

    - ``client_id`` is the business-facing identifier, unique within a service.
    - ``pin`` is always set for pin-auth services (generated on purchase).
    - ``ani`` is set when the user registers their phone number.
    - A client can be looked up by either PIN or ANI.
    """

    __tablename__ = "client"

    id: Mapped[int] = mapped_column(primary_key=True)
    service_id: Mapped[int] = mapped_column(
        ForeignKey("service.id", ondelete="CASCADE", onupdate="CASCADE"),
    )
    client_id: Mapped[int] = mapped_column(Integer)
    pin: Mapped[Optional[str]] = mapped_column(String(8), default=None)
    ani: Mapped[Optional[str]] = mapped_column(String(16), default=None)
    full_name: Mapped[Optional[str]] = mapped_column(String(128), default=None)
    email: Mapped[Optional[str]] = mapped_column(String(512), default=None)
    phone_number: Mapped[Optional[str]] = mapped_column(String(16), default=None)
    credits: Mapped[int] = mapped_column(Integer, default=0)

    service: Mapped[Optional["Service"]] = relationship()

    __table_args__ = (
        UniqueConstraint("service_id", "client_id", name="uq_client_service_clientid"),
        Index("ix_client_pin", "service_id", "pin"),
        Index("ix_client_ani", "service_id", "ani"),
    )

    def __str__(self):
        return f"{self.service_id}:{self.client_id}"


# ---------------------------------------------------------------------------
# Legacy model — kept until Chile + Alotarot clients migrate to Client
# ---------------------------------------------------------------------------


class FonoTarotLatamClient(Base, TimestampMixin):
    __tablename__ = "fonotarot_latam"

    client_id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(128), default=None)
    email: Mapped[str] = mapped_column(String(512))
    phone_number: Mapped[Optional[str]] = mapped_column(String(16), default=None)
    pin_code: Mapped[Optional[str]] = mapped_column(String(8), index=True)
    credits: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (UniqueConstraint("pin_code", "client_id", name="oc_unique_pin"),)

    def __str__(self):
        return str(self.client_id)


@event.listens_for(FonoTarotLatamClient, "before_insert")
def _set_pin_and_name(mapper, connection, target):
    target.pin_code = _generate_pin()
    if not target.full_name:
        target.full_name = target.email.split("@")[0]
