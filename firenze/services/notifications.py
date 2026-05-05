"""Outbound notifications via the Daleks email queue.

Failures (network, auth, missing config) are swallowed and logged - sending
a notification must never break the call path that triggered it.
"""

import logging

from daleks.contrib.client import DaleksClient

from firenze.config import settings

logger = logging.getLogger("firenze")


def notify(subject: str, body: str) -> None:
    """Send a notification email through the configured Daleks server.

    No-op (with a log line) when DALEKS_URL is unset. Any send error is
    caught and logged at WARNING.
    """
    if not settings.DALEKS_URL or not settings.DALEKS_FROM or not settings.DALEKS_TO:
        logger.info("daleks notify skipped (config missing): %s", subject)
        return

    recipients = [
        addr.strip() for addr in settings.DALEKS_TO.split(",") if addr.strip()
    ]
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
