from pydantic import BaseSettings
from functools import lru_cache
from typing import Set


class Settings(BaseSettings):
    ENVIRONMENT: str
    SQLALCHEMY_DATABASE_URL: str
    VERSION: str
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    STATIC_DIR: str = "static"
    SENTRY_ENABLED: bool = False
    SENTRY_RELEASE: str
    SENTRY_DSN: str
    SENTRY_ENVIRONMENT: str
    SECRET_KEY: str = "secret_key"
    SECRET_ALGO: str = "HS256"
    SECRET_EXPIRES: int = 1
    AUDIOTEX_DSN: str
    ALLOWED_DOMAINS: Set[str] = set()
    API_PREFIX: str = ""

    class Config:
        env_file = ".env"
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
            "level": settings.LOG_LEVEL,
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": "logs/firenze.log",
            "formatter": "verbose",
            "when": "midnight",
            "interval": 1,
        },
        "console": {
            "level": settings.LOG_LEVEL,
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "loggers": {
        "firenze": {
            "handlers": ["file", "console"],
            "level": settings.LOG_LEVEL,
            "propagate": True,
        },
    },
}
