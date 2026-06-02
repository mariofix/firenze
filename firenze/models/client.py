from __future__ import annotations

import datetime
import secrets
import string
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from firenze.database import Base
from firenze.models.base import TimestampMixin

if TYPE_CHECKING:
    from firenze.models.service import Service


def _generate_pin() -> str:
    """Genera una cadena de PIN aleatoria de 8 dígitos."""
    return "".join(secrets.choice(string.digits) for _ in range(8))


class Client(Base, TimestampMixin):
    """Modelo de cliente unificado — una fila por cliente por servicio.

    - ``client_id`` es el identificador orientado al negocio, único dentro de un servicio.
    - ``pin`` se establece para servicios con autenticación PIN (fonotarot-latam); clave de búsqueda en tiempo de llamada.
    - La búsqueda basada en ANI pasa por ``ClientAni`` (soporta múltiples ANIs por cliente).
    """

    __tablename__ = "client"

    id: Mapped[int] = mapped_column(primary_key=True)
    service_id: Mapped[int] = mapped_column(
        ForeignKey("service.id", ondelete="CASCADE", onupdate="CASCADE"),
    )
    client_id: Mapped[int] = mapped_column(Integer)
    pin: Mapped[str | None] = mapped_column(String(8), default=None)
    full_name: Mapped[str | None] = mapped_column(String(128), default=None)
    email: Mapped[str | None] = mapped_column(String(512), default=None)
    credits: Mapped[int] = mapped_column(Integer, default=0)
    extra_config: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=None)

    service: Mapped[Service | None] = relationship()
    anis: Mapped[list[ClientAni]] = relationship(back_populates="client", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("service_id", "client_id", name="uq_client_service_clientid"),
        Index("ix_client_pin", "service_id", "pin"),
    )

    def __str__(self):
        return f"<Cliente: {self.id=}/{self.service_id=}/{self.client_id=}>"

    def humanize_credits(self):
        total = int(self.credits)
        hours, remainder = divmod(total, 3600)
        minutes, seconds = divmod(remainder, 60)

        parts = []
        if hours:
            parts.append(f"{hours} {'hora' if hours == 1 else 'horas'}")
        if minutes:
            parts.append(f"{minutes} {'minuto' if minutes == 1 else 'minutos'}")
        if seconds or not parts:
            parts.append(f"{seconds} {'segundo' if seconds == 1 else 'segundos'}")

        if len(parts) == 1:
            return parts[0]
        return ", ".join(parts[:-1]) + f" y {parts[-1]}"


class ClientAni(Base):
    """Mapea ANI (ID de llamada) a un cliente dentro de un servicio.

    - Un cliente puede tener múltiples ANIs (usuarios registrados con varios teléfonos).
    - Los clientes anónimos tienen exactamente una fila ANI.
    - ``UNIQUE(service_id, ani)`` se aplica a nivel de BD — seguro para escrituras directas en BD.
    - FK compuesto ``(service_id, client_id)`` → ``Client`` previene inserciones entre servicios.
    """

    __tablename__ = "client_ani"

    id: Mapped[int] = mapped_column(primary_key=True)
    service_id: Mapped[int] = mapped_column(Integer, nullable=False)
    client_id: Mapped[int] = mapped_column(Integer, nullable=False)
    ani: Mapped[str] = mapped_column(String(16), nullable=False)
    q_calls: Mapped[int] = mapped_column(Integer, nullable=False, default="0")
    last_call: Mapped[datetime.datetime] = mapped_column(nullable=True, default=None)
    client: Mapped[Client] = relationship(back_populates="anis")

    __table_args__ = (
        ForeignKeyConstraint(
            ["service_id", "client_id"],
            ["client.service_id", "client.client_id"],
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_client_ani_composite",
        ),
        UniqueConstraint("service_id", "ani", name="uq_client_ani_service_ani"),
        Index("ix_client_ani_lookup", "service_id", "ani"),
    )

    def __str__(self):
        return f"{self.ani} ({self.q_calls})"
