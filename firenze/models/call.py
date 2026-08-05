from __future__ import annotations
from sqlalchemy import String, UniqueConstraint
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from firenze.models.base import TimestampMixin

from ..extensions import db


class OnlineCalls(db.Model, TimestampMixin):
    __tablename__ = "onlinecalls"

    id: Mapped[int] = mapped_column(primary_key=True)
    service: Mapped[str] = mapped_column(String(32))
    ani: Mapped[str] = mapped_column(String(32))
    did: Mapped[str] = mapped_column(String(32))
    operator: Mapped[int] = mapped_column()
    client_id: Mapped[int] = mapped_column()

    __table_args__ = (UniqueConstraint("service", "ani", name="oc_unique_ani"),)

    def __str__(self):
        return self.ani


class PostCallProcess(db.Model, TimestampMixin):
    __tablename__ = "post_call_process"

    id: Mapped[int] = mapped_column(primary_key=True)
    service: Mapped[str] = mapped_column(String(32))
    process_name: Mapped[str] = mapped_column(String(32))
    parameters: Mapped[dict | None] = mapped_column(JSON)
    client_id: Mapped[int] = mapped_column()
    processed: Mapped[bool] = mapped_column(default=False)

    __table_args__ = (UniqueConstraint("service", "client_id", name="oc_unique_process"),)

    def __str__(self):
        return str(self.id)
