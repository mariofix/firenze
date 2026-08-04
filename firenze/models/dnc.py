from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from firenze.models.base import TimestampMixin

from ..extensions import db


class DoNotCall(db.Model, TimestampMixin):
    __tablename__ = "dnc"

    id: Mapped[int] = mapped_column(primary_key=True)
    ani: Mapped[str] = mapped_column(String(32), index=True)
    reason: Mapped[str] = mapped_column(String(255))

    def __str__(self):
        return self.ani
