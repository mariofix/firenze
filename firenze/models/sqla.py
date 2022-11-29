from __future__ import annotations
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    func,
    Boolean,
    ForeignKey,
    text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship, declarative_mixin, registry
from sqlalchemy.dialects.mysql import LONGTEXT, JSON
from firenze.database import Base
import datetime
from dataclasses import dataclass, field


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

    def __repr__(self):
        id = self.id
        did = self.did
        active = self.active
        asterisk_context = self.asterisk_context
        service_id = self.service_id
        created_at = self.created_at
        return f"DID<{id=}, \
                    {did=}, \
                    {active=}, \
                    {asterisk_context=}, \
                    {service_id=}, \
                    {created_at=}>"


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

    def __repr__(self):
        id = self.id
        service = self.service
        ani = self.ani
        did = self.did
        operator = self.operator
        client_id = self.client_id
        return f"Call<{id=}, {service=}, {ani=}, {did=}, {operator=}, {client_id=}>"


class FonotarotLatam(Base, TimestampMixin):
    __tablename__ = "fonotarot_latam"

    client_id = Column(Integer, primary_key=True)
    nombres = Column(String(255), nullable=True)
    correo = Column(String(1024), nullable=False)
    telefono = Column(String(32), nullable=True)
    pin = Column(Integer, unique=True, nullable=False)
    creditos = Column(Integer, default=0, nullable=False)

    def __str__(self):
        return self.client_id

    def __repr__(self):
        client_id = self.client_id
        nombres = self.nombres
        correo = self.correo
        telefono = self.telefono
        pin = self.pin
        creditos = self.creditos
        created_at = self.created_at
        return f"FonotarotLatam<{client_id=}, \
                {nombres=}, \
                {correo=}, \
                {telefono=}, \
                {pin=}, \
                {creditos=}, \
                {created_at=}>"


class Fonotarot(Base, TimestampMixin):
    __tablename__ = "fonotarot"

    client_id = Column(Integer, primary_key=True)
    nombres = Column(String(255), nullable=True)
    correo = Column(String(1024), nullable=True)
    telefonos = Column(JSON, nullable=False)
    pin = Column(Integer, unique=True, nullable=False)
    creditos = Column(Integer, default=0, nullable=False)

    def __str__(self):
        return self.client_id

    def __repr__(self):
        client_id = self.client_id
        nombres = self.nombres
        correo = self.correo
        telefonos = self.telefonos
        pin = self.pin
        creditos = self.creditos
        created_at = self.created_at
        return f"Fonotarot<{client_id=}, \
                {nombres=}, \
                {correo=}, \
                {telefono=}, \
                {pin=}, \
                {creditos=}, \
                {created_at=}>"


class Alotarot(Base, TimestampMixin):
    __tablename__ = "alotarot"

    client_id = Column(Integer, primary_key=True)
    nombres = Column(String(255), nullable=True)
    correo = Column(String(1024), nullable=True)
    telefonos = Column(JSON, nullable=False)
    pin = Column(Integer, unique=True, nullable=False)
    creditos = Column(Integer, default=0, nullable=False)

    def __str__(self):
        return self.client_id

    def __repr__(self):
        client_id = self.client_id
        nombres = self.nombres
        correo = self.correo
        telefonos = self.telefonos
        pin = self.pin
        creditos = self.creditos
        created_at = self.created_at
        return f"Alotarot<{client_id=}, \
                {nombres=}, \
                {correo=}, \
                {telefono=}, \
                {pin=}, \
                {creditos=}, \
                {created_at=}>"
