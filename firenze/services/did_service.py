from flask_sqlalchemy import SQLAlchemy

from firenze.models import ServiceNumber


def resolve_did(db: SQLAlchemy, did: str) -> dict:
    """Retorna la configuración completa del servicio para un DID, o cadenas vacías si no se encuentra.

    Usado por ``GET /agi/services/did/{did}`` — el dialplan de Asterisk lee todos
    los campos en una llamada y los establece como variables de canal.

    Retorna:
        siguiente    — contexto de Asterisk para Goto (p. ej. "prepago-service")
        servicio     — slug del servicio (p. ej. "alotarot", "fonotarot-cl")
        auth_method  — "ani" o "pin"
        intro_audio  — cadena compatible con Playback (p. ej. "zvn/intro-alotarot")
    """
    number = db.query(ServiceNumber).filter_by(did=did, active=True).first()
    if not number or not number.service:
        return {"siguiente": "", "servicio": "", "auth_method": "", "intro_audio": ""}
    svc = number.service
    return {
        "siguiente": number.asterisk_context,
        "servicio": svc.slug,
        "auth_method": svc.auth_method,
        "intro_audio": svc.intro_audio,
    }
