"""Registros de auditoria"""

from typing import Any

from sqlalchemy.orm import Session

from firenze.models import Audit


def create_audit(db: Session, title: str, category: str, called_from: str | None = None, data: Any = None) -> dict:
    """Crea un registro de auditoria"""
    registro = Audit(title=title, category=category, called_from=called_from, data=data)
    db.add(registro)
    db.commit()

    return registro.to_dict()
