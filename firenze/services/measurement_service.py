"""Google Measurement Protocol event helpers."""

import logging
from typing import Any

import requests

from firenze.config import settings

logger = logging.getLogger("firenze")

MEASUREMENT_ENDPOINT = "https://www.google-analytics.com/mp/collect"


def send_measurement_event(
    event_name: str,
    params: dict[str, Any] | None = None,
    client_id: str | None = None,
) -> None:
    """Send a GA4 Measurement Protocol event when tracking is configured."""
    measurement_id = settings.GA4_MEASUREMENT_ID
    api_secret = settings.GA4_API_SECRET

    if not measurement_id or not api_secret:
        logger.info("measurement event skipped (config missing): %s", event_name)
        return

    payload = {
        "client_id": client_id or settings.GA4_CLIENT_ID,
        "events": [
            {
                "name": event_name,
                "params": params or {},
            }
        ],
    }

    try:
        response = requests.post(
            MEASUREMENT_ENDPOINT,
            params={"measurement_id": measurement_id, "api_secret": api_secret},
            json=payload,
            timeout=2,
        )
        if response.status_code >= 400:
            logger.warning(
                "measurement event failed (%s): status=%s body=%s",
                event_name,
                response.status_code,
                response.text[:300],
            )
    except requests.RequestException as exc:
        logger.warning("measurement event failed (%s): %s", event_name, exc)
