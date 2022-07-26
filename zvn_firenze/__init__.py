from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from zvn_firenze.config import settings, LOGGING_CONFIG
from zvn_firenze.auth import authRouter
from zvn_firenze.core import coreRouter
from zvn_firenze.audiotex import audiotexRouter

import logging


def create_app():
    app = FastAPI(
        title="Firenze",
        description="Servicio de comunicacion y administracion para servicio Tatot",
        version=settings.VERSION,
        debug=settings.DEBUG,
    )
    logging.config.dictConfig(LOGGING_CONFIG)
    app.logger = logging.getLogger("firenze")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_DOMAINS)
    # Static Folder
    app.mount(
        f"/{settings.STATIC_DIR}",
        StaticFiles(directory=settings.STATIC_DIR),
        name=settings.STATIC_DIR,
    )

    # Lo relacionado con Auth
    app.include_router(authRouter)

    # Incluimos gestion basica
    app.include_router(coreRouter)

    # audiotex
    app.include_router(audiotexRouter)

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
