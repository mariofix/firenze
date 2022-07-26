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
from sqlalchemy.orm import relation, relationship
from sqlalchemy.dialects.mysql import LONGTEXT, JSON
from zvn_firenze.database import Base
import datetime
import enum


class User(Base):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True)
    login = Column(String(64), unique=True)
    email = Column(String(255))
    password = Column(String(255))
    allowed_ips = Column(JSON, nullable=True)
    enabled = Column(Boolean, default=True)
    scopes = Column(JSON, nullable=True)
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
        return f"User({self.id=}, {self.login=}, {self.email=}, {self.enabled=})"

    def __repr__(self):
        return f"User({self.id=}, {self.login=}, {self.email=}, {self.enabled=})"


class Event(Base):
    __tablename__ = "event"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), index=True)
    ip = Column(String(16), index=True)
    port = Column(Integer())
    verb = Column(String(10), index=True)
    url = Column(String(255), index=True)
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
        return (
            f"Event({self.id=}, {self.name=}, {self.verb=}, {self.url=}, {self.data=})"
        )

    def __repr__(self):
        return (
            f"Event({self.id=}, {self.name=}, {self.verb=}, {self.url=}, {self.data=})"
        )


class GenericError(Exception):
    pass


class ProcessError(GenericError):
    pass
