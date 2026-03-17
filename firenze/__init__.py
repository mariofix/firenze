import logging

from fastapi import FastAPI
from sqladmin import Admin
from starlette.middleware.sessions import SessionMiddleware

from firenze.admin import register_admin
from firenze.api.agi import agiRouter
from firenze.auth import AdminAuth
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

    app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)

    # sqladmin
    authentication_backend = AdminAuth(secret_key=settings.SECRET_KEY)
    admin = Admin(
        app,
        engine,
        base_url="/boss",
        title="Firenze Admin",
        authentication_backend=authentication_backend,
    )
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
