#!.venv/bin/python
# cli.py
"""
Main wrapper for cli related inputs.

This file runs the Typer application that supports:  
- `users` - User Manager    
- `services` - Services Manager  
- `online-calls` - OnlineCalls Manager  
- `dnc-search` - DNC Number Search  
- `test` - Tests DB Connection


```bash
poetry run firenze test
```
"""
from firenze.cli import cli
from firenze.config import settings
import sentry_sdk

if settings.SENTRY_ENABLED:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        traces_sample_rate=0.1,
        release=f"{settings.SENTRY_RELEASE}-cli",
        environment=settings.SENTRY_ENVIRONMENT,
    )


if __name__ == "__main__":
    cli()
