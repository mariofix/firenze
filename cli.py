#!./.venv/bin/python
import sentry_sdk

from firenze.cli import cli
from firenze.config import settings

if settings.SENTRY_ENABLED:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        traces_sample_rate=0.1,
        release=f"{settings.SENTRY_RELEASE}-cli",
        environment=settings.SENTRY_ENVIRONMENT,
    )


if __name__ == "__main__":
    cli()
