import logging
import logging.config

from debug_toolbar.middleware import DebugToolbarMiddleware
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from firenze.admin import FirenzeAdmin, register_admin
from firenze.api.admin_reports import adminReportsRouter
from firenze.api.agi import agiRouter
from firenze.api.clients import clientsRouter
from firenze.api.payments import paymentsRouter
from firenze.api.public import publicRouter
from firenze.auth import AdminAuth, authRouter
from firenze.config import LOGGING_CONFIG, Settings, settings
from firenze.database import engine
from firenze.middleware import InternalOnlyMiddleware

from .version import __version__


def create_app():
    app = FastAPI(
        title="Firenze",
        description="Servicio de comunicacion y administracion para servicio Tatot",
        version=__version__,
        debug=settings.DEBUG,
        docs_url="/api-docs",
    )
    logging.config.dictConfig(LOGGING_CONFIG)
    app.logger = logging.getLogger("firenze")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)
    app.add_middleware(DebugToolbarMiddleware, settings=[Settings()])
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_DOMAINS)
    app.add_middleware(
        InternalOnlyMiddleware,
        path_prefix=settings.AGI_PATH_PREFIX,
        allowed_networks=settings.AGI_ALLOWED_NETWORKS,
    )

    @app.get("/")
    def root_index():
        return {"status": "ok"}

    # sqladmin
    authentication_backend = AdminAuth(secret_key=settings.SECRET_KEY)
    admin = FirenzeAdmin(
        app,
        engine,
        title="Firenze Admin",
        authentication_backend=authentication_backend,
        templates_dir=str(settings.BASE_DIR / "firenze" / "templates"),
    )

    register_admin(admin)

    # AGI endpoints (called by Asterisk dialplan via CURL)
    app.include_router(agiRouter)

    # Auth endpoints (/api/v1/auth/me and passwordless request)
    app.include_router(authRouter)

    # Payment / storefront endpoints (called by nuevo-fonotarot)
    app.include_router(paymentsRouter)

    # Client CRUD endpoints
    app.include_router(clientsRouter)

    # public endpoints
    app.include_router(publicRouter)
    app.include_router(adminReportsRouter)

    return app
