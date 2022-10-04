from typing import Text
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    func,
    Boolean,
    ForeignKey,
    Float,
    Enum,
    text,
)
from sqlalchemy.orm import relation, relationship, declarative_mixin
from sqlalchemy.dialects.mysql import LONGTEXT, JSON
from firenze.database import Base
import datetime
import enum


@declarative_mixin
class TimestampMixin:
    created_at = Column(
        DateTime(timezone=True),
        default=datetime.datetime.now,
        server_default=func.now(),
    )
    modified_at = Column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )


class User(Base):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True)
    login = Column(String(64), unique=True, nullable=False)
    email = Column(String(255), nullable=False)
    password = Column(String(255), nullable=False)
    allowed_ips = Column(JSON, nullable=True)
    enabled = Column(Boolean, default=True)
    scopes = Column(JSON, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=datetime.datetime.now,
        server_default=func.now(),
        nullable=False,
    )
    modified_at = Column(
        DateTime(timezone=True),
        default=datetime.datetime.now,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        nullable=False,
    )

    def __str__(self):
        return self.login

    def __repr__(self):
        return f"User({self.id=}, {self.login=}, {self.email=}, {self.enabled=})"


class Event(Base):
    __tablename__ = "event"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), index=True, nullable=False)
    ip = Column(String(16), index=True, nullable=True)
    port = Column(Integer(), nullable=True)
    verb = Column(String(10), index=True, nullable=False)
    url = Column(String(255), index=True, nullable=False)
    data = Column(LONGTEXT, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        default=datetime.datetime.now,
        server_default=func.now(),
    )
    modified_at = Column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )

    def __str__(self):
        return self.name

    def __repr__(self):
        return (
            f"Event({self.id=}, {self.name=}, {self.verb=}, {self.url=}, {self.data=})"
        )


class Service(Base, TimestampMixin):
    __tablename__ = "service"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), index=True, nullable=False)
    numbers = relationship("ServiceNumber", back_populates="service")

    def __str__(self):
        return self.name


class ServiceNumber(Base, TimestampMixin):
    __tablename__ = "service_did"

    id = Column(Integer, primary_key=True)
    did = Column(String(32), unique=True, nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    asterisk_context = Column(String(32), nullable=False)
    service_id = Column(
        Integer,
        ForeignKey("service.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=False,
    )
    service = relationship("Service", back_populates="numbers")

    def __str__(self):
        return self.did

    def __repr__(self):
        return f"DID<{self.did=}, {self.active=}, {self.asterisk_context=}, {self.service_id=}>"


class DoNotCall(Base, TimestampMixin):
    __tablename__ = "dnc"

    id = Column(Integer, primary_key=True)
    ani = Column(String(32), index=True, nullable=False)
    reason = Column(String(255), nullable=False)

    def __str__(self):
        return self.ani


class OnlineCalls(Base, TimestampMixin):
    __tablename__ = "onlinecalls"

    id = Column(Integer, primary_key=True)
    service = Column(String(32), nullable=False)
    ani = Column(String(32), nullable=False)
    did = Column(String(32), nullable=False)
    operator = Column(Integer, nullable=False)
    client_id = Column(Integer, nullable=False)

    def __str__(self):
        return self.client_id
