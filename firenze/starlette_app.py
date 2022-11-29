from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from starlette.middleware import Middleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from sqladmin import Admin
from firenze import __version__
from firenze.config import settings, LOGGING_CONFIG
from firenze.database import engine
import logging.config

logger = logging.getLogger("firenze")


async def startup():
    logger.info(f"Starting firenze-{__version__}-{settings.ENVIRONMENT}")


async def shutdown():
    logger.info(f"Stopping firenze-{__version__}-{settings.ENVIRONMENT}")


def create_app():
    routes = [
        Mount("/static", StaticFiles(directory="static")),
    ]
    middleware = [
        Middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_DOMAINS)
    ]

    app = Starlette(
        debug=settings.DEBUG,
        routes=routes,
        middleware=middleware,
        on_startup=[startup],
        on_shutdown=[shutdown],
    )

    app.sqladmin = Admin(
        app,
        engine,
        base_url="/boss",
        title="Firenze Admin",
        # authentication_backend=admin_auth,
    )

    logging.config.dictConfig(LOGGING_CONFIG)
    app.logger = logger

    return app
