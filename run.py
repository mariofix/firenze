from zvn_firenze import create_app
from zvn_firenze.config import settings
import sentry_sdk
from sentry_sdk.integrations.asgi import SentryAsgiMiddleware

if settings.SENTRY_ENABLED:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        traces_sample_rate=1.0,
        release=settings.SENTRY_RELEASE,
        environment=settings.SENTRY_ENVIRONMENT,
        request_bodies="always",
    )
app = create_app()
if settings.SENTRY_ENABLED:
    app = SentryAsgiMiddleware(app)
