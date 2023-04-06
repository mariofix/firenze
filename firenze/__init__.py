from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.cors import CORSMiddleware
from firenze.config import settings, LOGGING_CONFIG
from firenze.auth import authRouter, AdminAuth
from firenze.core import coreRouter
from firenze.audiotex import audiotexRouter

# from firenze.services.fonotarot_latam import app as ftlRouter
from firenze.admin import register_admin
from firenze.database import engine
from sqladmin import Admin

import logging


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
    origins = [
        "https://fonotarot.com",
        "https://alotarot.cl",
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_DOMAINS)
    # Static Folder
    app.mount(
        f"/{settings.STATIC_DIR}",
        StaticFiles(directory=settings.STATIC_DIR),
        name=settings.STATIC_DIR,
    )

    # sqladmin
    admin_auth = AdminAuth(secret_key=settings.SECRET_KEY)
    app.sqladmin = Admin(
        app,
        engine,
        base_url="/boss",
        title="Firenze Admin",
        authentication_backend=admin_auth,
    )
    register_admin(app)

    # Lo relacionado con Auth
    app.include_router(authRouter)

    # Incluimos gestion basica
    app.include_router(coreRouter)

    # Fonotarot Latam
    # app.include_router(ftlRouter)

    # audiotex
    app.include_router(audiotexRouter)

    # asterisk
    # app.include_router(asteriskRouter)

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
