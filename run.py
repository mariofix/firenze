from firenze import create_app
from firenze.config import settings
import sentry_sdk
from sentry_sdk.integrations.asgi import SentryAsgiMiddleware

if settings.SENTRY_ENABLED:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        traces_sample_rate=0.1,
        release=settings.SENTRY_RELEASE,
        environment=settings.SENTRY_ENVIRONMENT,
        request_bodies="always",
    )
app = create_app()
if settings.SENTRY_ENABLED:
    app = SentryAsgiMiddleware(app)
