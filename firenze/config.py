## DEPRECATED
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from .version import __version__

BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass
class Settings:
    ENVIRONMENT: str = "production"
    SQLALCHEMY_DATABASE_URL: str = ""
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    SECRET_KEY: str = "CHANGE-ME-this-is-a-dev-only-default-key-replace-in-production"
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_SOCKET_CONNECT_TIMEOUT: float = 2.0
    REDIS_SOCKET_TIMEOUT: float = 2.0
    ALLOWED_DOMAINS: list[str] = field(default_factory=lambda: ["localhost", "tardis.local"])
    CORS_ORIGINS: list[str] = ["http://localhost"]
    AGI_PATH_PREFIX: str = "/agi"
    AGI_ALLOWED_NETWORKS: list[str] = ["127.0.0.1/32"]
    BASE_DIR: Any = BASE_DIR
    LEGACY_API_URL: str = "http://localhost:9000"
    LEGACY_API_USER: str = ""
    LEGACY_API_PASSWORD: str = ""
    DALEKS_URL: str | None = None
    DALEKS_FROM: str | None = None
    DALEKS_TO: str | None = None
    DALEKS_SMTP_ACCOUNT: str | None = None
    AUTH_PASSWORD_LOGIN_ENABLED: bool = True
    AUTH_PASSWORDLESS_ENABLED: bool = True
    AUTH_PASSWORDLESS_CODE_TTL_MINUTES: int = 10
    AUTH_PASSWORDLESS_MAX_ATTEMPTS: int = 5
    AUTH_PASSWORDLESS_REQUEST_WINDOW_SECONDS: int = 600
    AUTH_PASSWORDLESS_MAX_REQUESTS_PER_WINDOW: int = 5
    AUTH_PASSWORDLESS_MAX_REQUESTS_PER_IP_PER_WINDOW: int = 20
    GA4_MEASUREMENT_ID: str | None = None
    GA4_API_SECRET: str | None = None
    GA4_CLIENT_ID: str = "firenze-api"
    GA4_DEBUG_URL_ENABLED: bool = True
    API_TITLE: str = "Firenze"
    API_VERSION: str = __version__
    OPENAPI_VERSION: str = "3.0.3"
    JSON_SORT_KEYS: bool = False
    DEBUG_TB_PANELS = (
        "flask_debugtoolbar.panels.versions.VersionDebugPanel",
        "flask_debugtoolbar.panels.timer.TimerDebugPanel",
        "flask_debugtoolbar.panels.headers.HeaderDebugPanel",
        "flask_debugtoolbar.panels.request_vars.RequestVarsDebugPanel",
        "flask_debugtoolbar.panels.config_vars.ConfigVarsDebugPanel",
        "flask_debugtoolbar.panels.template.TemplateDebugPanel",
        "flask_debugtoolbar.panels.sqlalchemy.SQLAlchemyDebugPanel",
        "flask_debugtoolbar.panels.logger.LoggingPanel",
        "flask_debugtoolbar.panels.route_list.RouteListDebugPanel",
        "flask_debugtoolbar.panels.profiler.ProfilerDebugPanel",
        "flask_debugtoolbar.panels.g.GDebugPanel",
        "flask_debugtoolbar_extrapanels.SignalsPanel",
    )


@lru_cache
def get_settings():
    return Settings()


settings = get_settings()


def build_flask_app_config(*, api_version: str) -> dict[str, Any]:
    return {
        "API_TITLE": "Firenze",
        "API_VERSION": api_version,
        "OPENAPI_VERSION": "3.0.3",
        "JSON_SORT_KEYS": False,
        "DEBUG_TB_ENABLED": settings.DEBUG,
    }


# Logger available at 'Request.app.logger' or logging.getLogger("firenze")

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {
            "format": "{levelname}:\t  {message}",
            "style": "{",
        },
        "verbose": {
            "format": "{asctime} {name}.{levelname} {filename}({lineno}) {message}",
            "style": "{",
        },
    },
    "handlers": {
        "file": {
            "level": "DEBUG" if settings.DEBUG else settings.LOG_LEVEL,
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": f"{settings.BASE_DIR}/logs/firenze-api.log",
            "formatter": "verbose",
            "when": "W0",
            "interval": 1,
        },
        "console": {
            "level": "DEBUG" if settings.DEBUG else "ERROR",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "loggers": {
        "firenze": {
            "handlers": ["file", "console"],
            "level": "DEBUG" if settings.DEBUG else settings.LOG_LEVEL,
            "propagate": False,
        },
    },
}
