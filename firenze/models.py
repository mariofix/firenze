import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
    event,
)
from sqlalchemy.dialects.mysql import JSON, LONGTEXT
from sqlalchemy.orm import declarative_mixin, relationship, column_property
from .crud import generate_pin
from .database import Base, SessionLocal
from fastapi import Depends

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@declarative_mixin
class TimestampMixin:
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


class User(Base, TimestampMixin):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True)
    login = Column(String(64), unique=True, nullable=False)
    email = Column(String(255), nullable=False)
    password = Column(String(255), nullable=False)
    allowed_ips = Column(JSON, nullable=True)
    enabled = Column(Boolean, default=True)
    scopes = Column(JSON, nullable=True)

    def __str__(self):
        return self.login


class Event(Base, TimestampMixin):
    __tablename__ = "event"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), index=True, nullable=False)
    ip = Column(String(16), index=True, nullable=True)
    port = Column(Integer(), nullable=True)
    verb = Column(String(10), index=True, nullable=False)
    url = Column(String(255), index=True, nullable=False)
    data = Column(LONGTEXT, nullable=True)

    def __str__(self):
        return self.name


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
        nullable=True,
    )
    service = relationship("Service", back_populates="numbers")

    def __str__(self):
        return self.did


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

    __table_args__ = (UniqueConstraint("service", "ani", name="oc_unique_ani"),)

    def __str__(self):
        return self.ani


class PostCallProcess(Base, TimestampMixin):
    __tablename__ = "post_call_process"

    id = Column(Integer, primary_key=True)
    service = Column(String(32), nullable=False)
    process_name = Column(String(32), nullable=False)
    parameters = Column(JSON, nullable=True, default=None)
    client_id = Column(Integer, nullable=False)
    processed = Column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint("service", "client_id", name="oc_unique_process"),
    )

    def __str__(self):
        return self.id


class FonoTarotLatamClient(Base, TimestampMixin):
    __tablename__ = "fonotarot_latam"

    client_id = Column(Integer, primary_key=True)
    full_name = Column(String(128), nullable=True, default=None)
    email = Column(String(512), nullable=False)
    phone_number = Column(String(16), nullable=True, default=None)
    pin_code = Column(String(8), index=True)
    credits = Column(Integer, nullable=False, default=0)

    __table_args__ = (UniqueConstraint("pin_code", "client_id", name="oc_unique_pin"),)

    def __str__(self):
        return self.client_id


@event.listens_for(FonoTarotLatamClient, 'before_insert')
def crea_pin(mapper, connection, target):
    target.pin_code = generate_pin()
    if not target.full_name:
        target.full_name = target.email.split("@").pop(0)
