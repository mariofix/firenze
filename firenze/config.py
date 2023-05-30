from functools import lru_cache
from pathlib import Path
from typing import Any, Set

from pydantic import BaseSettings, HttpUrl

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    ENVIRONMENT: str = "production"
    CORS_ORIGINS: list[HttpUrl] = ["http://tardis.local:8080"]
    SQLALCHEMY_DATABASE_URL: str
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    VERSION: str = "1.0.8"
    STATIC_DIR: str = "static"
    SENTRY_ENABLED: bool = False
    SENTRY_RELEASE: str = None
    SENTRY_DSN: str = None
    SENTRY_ENVIRONMENT: str = None
    SECRET_KEY: str = "secret_key"
    SECRET_ALGO: str = "HS256"
    SECRET_EXPIRES: int = 30
    AUDIOTEX_DSN: str = None
    ALLOWED_DOMAINS: list[str] = ["*.local", "192.168.100.19"]
    API_PREFIX: str = ""
    BASE_DIR: Any = BASE_DIR

    class Config:
        env_file = f"{BASE_DIR}/.env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings():
    return Settings()


settings = get_settings()

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
            "level": "DEBUG" if settings.DEBUG else settings.LOG_LEVEL,
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "loggers": {
        "firenze": {
            "handlers": ["file", "console"],
        },
    },
}


LOGGING_CONFIG_CLI = {
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
        "cli": {
            "level": "DEBUG" if settings.DEBUG else settings.LOG_LEVEL,
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": f"{settings.BASE_DIR}/logs/firenze-cli.log",
            "formatter": "verbose",
            "when": "midnight",
            "interval": 1,
        },
        "console": {
            "level": "DEBUG" if settings.DEBUG else settings.LOG_LEVEL,
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "loggers": {
        "firenze-cli": {
            "handlers": ["cli", "console"],
        },
    },
}
