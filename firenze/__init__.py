import logging

from fastapi import FastAPI

from firenze.api.agi import agiRouter
from firenze.config import LOGGING_CONFIG, settings


def create_app():
    app = FastAPI(
        title="Firenze",
        description="Servicio de comunicacion y administracion para servicio Tatot",
        version=settings.VERSION,
        debug=settings.DEBUG,
        docs_url="/office",
    )
    logging.config.dictConfig(LOGGING_CONFIG)
    app.logger = logging.getLogger("firenze")

    # AGI endpoints (called by Asterisk dialplan via CURL)
    app.include_router(agiRouter)

    @app.on_event("startup")
    async def startup():
        app.logger.info(
            f"Starting ZVN-Firenze-{settings.VERSION}-{settings.ENVIRONMENT}"
        )

    @app.on_event("shutdown")
    async def shutdown():
        app.logger.info(
            f"Stopping ZVN-Firenze-{settings.VERSION}-{settings.ENVIRONMENT}"
        )

    return app
