from sqlalchemy import String, JSON
from sqlalchemy.orm import Mapped, mapped_column

from firenze.database import Base
from firenze.models.base import TimestampMixin


class Audit(Base, TimestampMixin):
    __tablename__ = "audit"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(64))
    category: Mapped[str] = mapped_column(String(64))
    called_from: Mapped[str | None] = mapped_column(String(255), nullable=True, default=None)
    data: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=None)

    def __str__(self):
        return f"{self.title}"

    def to_dict(self):
        return {"id": self.id, "title": self.title, "category": self.category, "called_from": self.called_from, "data": self.data,}