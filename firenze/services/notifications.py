"""Notificaciones salientes a través de la cola de correo de Daleks.

Los fallos (red, autenticación, configuración faltante) se ignoran y registran - enviar
una notificación nunca debe interrumpir el camino de llamadas que la gatilló.
"""

import logging

from daleks.contrib.client import DaleksClient

from firenze.config import settings

logger = logging.getLogger("firenze")


def notify(subject: str, body: str) -> None:
    """Envía una notificación de correo a través del servidor Daleks configurado.

    Sin operación (con una línea de registro) cuando DALEKS_URL no está configurada. Cualquier error de envío se
    captura y registra en ADVERTENCIA.
    """
    if not settings.DALEKS_URL or not settings.DALEKS_FROM or not settings.DALEKS_TO:
        logger.info("daleks notify skipped (config missing): %s", subject)
        return

    recipients = [addr.strip() for addr in settings.DALEKS_TO.split(",") if addr.strip()]
    smtp_account = settings.DALEKS_SMTP_ACCOUNT or None

    try:
        with DaleksClient(settings.DALEKS_URL, smtp_account=smtp_account) as client:
            client.send_email(
                from_address=settings.DALEKS_FROM,
                to=recipients,
                subject=subject,
                text_body=body,
            )
    except Exception as exc:
        logger.warning("daleks notify failed (%s): %s", type(exc).__name__, exc)
