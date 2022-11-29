# api.py
"""
Main wrapper for web related inputs.

This file runs the Starlette application that supports:  
- `FastAPI` - Main exposed REST API, available at `/api`  
- `sqladmin` - Admin site, available at `/admin`  


This file shouldn't run by itself, instead run it using uvicorn
```bash
poetry run uvicorn api:app
```
"""
from firenze.starlette_app import create_app
from firenze.config import settings
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


if __name__ == "__main__":
    app.run()
