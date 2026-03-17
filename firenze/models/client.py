import secrets
import string
from typing import Optional

from sqlalchemy import Integer, String, UniqueConstraint, event
from sqlalchemy.orm import Mapped, mapped_column

from firenze.database import Base
from firenze.models.base import TimestampMixin


def _generate_pin() -> str:
    """Generate a random 8-digit PIN string."""
    return "".join(secrets.choice(string.digits) for _ in range(8))


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
