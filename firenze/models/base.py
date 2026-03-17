"""Shared SQLAlchemy mixins."""

import datetime

from sqlalchemy import func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, declarative_mixin, mapped_column


@declarative_mixin
class TimestampMixin:
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.now,
        server_default=func.now(),
    )
    modified_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.now,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )
