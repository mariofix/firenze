from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=f"{BASE_DIR}/.env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    ENVIRONMENT: str = "production"
    SQLALCHEMY_DATABASE_URL: str = ""
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    SECRET_KEY: str = "CHANGE-ME-this-is-a-dev-only-default-key-replace-in-production"
    REDIS_URL: str = "redis://zvn-lin3.local:6379"
    REDIS_SOCKET_CONNECT_TIMEOUT: float = 2.0
    REDIS_SOCKET_TIMEOUT: float = 2.0
    ALLOWED_DOMAINS: list[str] = ["localhost", "tardis.local"]
    CORS_ORIGINS: list[str] = ["https://nuevo.fonotarot.com"]
    AGI_PATH_PREFIX: str = "/agi"
    AGI_ALLOWED_NETWORKS: list[str] = ["127.0.0.1/32"]
    BASE_DIR: Any = BASE_DIR
    LEGACY_API_URL: str = "https://firenze.156.cl"
    LEGACY_API_USER: str = ""
    LEGACY_API_PASSWORD: str = ""
    DALEKS_URL: str = ""
    DALEKS_FROM: str = ""
    DALEKS_TO: str = ""
    DALEKS_SMTP_ACCOUNT: str = ""
    AUTH_PASSWORD_LOGIN_ENABLED: bool = True
    AUTH_PASSWORDLESS_ENABLED: bool = True
    AUTH_PASSWORDLESS_CODE_TTL_MINUTES: int = 10
    AUTH_PASSWORDLESS_MAX_ATTEMPTS: int = 5
    AUTH_PASSWORDLESS_REQUEST_WINDOW_SECONDS: int = 600
    AUTH_PASSWORDLESS_MAX_REQUESTS_PER_WINDOW: int = 5
    AUTH_PASSWORDLESS_MAX_REQUESTS_PER_IP_PER_WINDOW: int = 20


@lru_cache
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
