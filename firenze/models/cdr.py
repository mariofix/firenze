import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from firenze.extensions import db


class AsteriskCDR(db.Model):
    """Mapeo de solo lectura para la tabla CDR de Asterisk."""

    __tablename__ = "cdr"
    __table_args__ = (
        Index("idx_zvn_operator", "zvn_operator"),
        {"schema": "zvn_asterisk"},
    )

    cdrid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    calldate: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    clid: Mapped[str] = mapped_column(String(80), nullable=False)
    src: Mapped[str] = mapped_column(String(80), nullable=False)
    dst: Mapped[str] = mapped_column(String(80), nullable=False)
    dcontext: Mapped[str] = mapped_column(String(80), nullable=False)
    channel: Mapped[str] = mapped_column(String(80), nullable=False)
    dstchannel: Mapped[str] = mapped_column(String(80), nullable=False)
    lastapp: Mapped[str] = mapped_column(String(80), nullable=False)
    lastdata: Mapped[str] = mapped_column(String(80), nullable=False)
    duration: Mapped[int] = mapped_column(Integer, nullable=False)
    billsec: Mapped[int] = mapped_column(Integer, nullable=False)
    disposition: Mapped[str] = mapped_column(String(45), nullable=False)
    amaflags: Mapped[int] = mapped_column(Integer, nullable=False)
    accountcode: Mapped[str] = mapped_column(String(20), nullable=False)
    uniqueid: Mapped[str] = mapped_column(String(32), nullable=False)
    userfield: Mapped[str] = mapped_column(String(255), nullable=False)
    zvn_clientid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    zvn_client_ani: Mapped[str | None] = mapped_column(String(32), nullable=True)
    zvn_operator: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    answer: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    end: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)

    def __str__(self) -> str:
        return f"{self.cdrid}:{self.src}->{self.dst}"
