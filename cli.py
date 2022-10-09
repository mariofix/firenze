#!/opt/zvn-firenze/firenze-t7_AZ976-py3.10/bin/python
import typer
import pystrix
from firenze.cli import cli
from firenze.config import settings
import sentry_sdk

if settings.SENTRY_ENABLED:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        traces_sample_rate=0.01,
        release=f"{settings.SENTRY_RELEASE}-cli",
        environment=settings.SENTRY_ENVIRONMENT,
    )


if __name__ == "__main__":
    cli()
