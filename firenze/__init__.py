import logging

from fastapi import FastAPI
from sqladmin import Admin

from firenze.admin import register_admin
from firenze.api.agi import agiRouter
from firenze.config import LOGGING_CONFIG, settings
from firenze.database import engine


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

    # sqladmin
    admin = Admin(app, engine, base_url="/boss", title="Firenze Admin")
    register_admin(admin)

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
