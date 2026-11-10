from pathlib import Path
from typing import Any

BASE_DIR: Any = Path(__file__).resolve().parent.parent
SECRET_KEY: str
DEBUG: bool = False
LOG_LEVEL: str = "DEBUG" if DEBUG else "INFO"
TRUSTED_HOSTS: list[str] = [
    "localhost",
    "tardis.local",
]
SESSION_COOKIE_NAME: str = "new_firenze"

# API
CORS_ORIGINS: list[str] = ["http://localhost", "http://*.local"]
CORS_SUPPORTS_CREDENTIALS: bool = True
CORS_ALLOW_HEADERS: str = "*"
CORS_METHODS: list[str] = ["GET", "POST", "PATCH", "DELETE", "OPTIONS"]
AGI_PATH_PREFIX: str = "/agi"
AGI_ALLOWED_NETWORKS: list[str] = ["127.0.0.1/32", "10.0.0.0/24"]

# Old Firenze
LEGACY_API_URL: str = "http://localhost:9002"
LEGACY_API_USER: str = ""
LEGACY_API_PASSWORD: str = ""

SQLALCHEMY_DATABASE_URI: str = "sqlite:///:memory:"
SQLALCHEMY_RECORD_QUERIES: bool = True
SQLALCHEMY_ECHO = False
SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 1800}

# Flask-Security
SECURITY_EMAIL_SENDER = ""
SECURITY_PASSWORD_SALT = ""  # nosec B105 - overridden via env in prod
SECURITY_LOGIN_URL = "/login/"
SECURITY_LOGOUT_URL = "/logout/"
SECURITY_POST_LOGIN_VIEW = "/"
SECURITY_POST_LOGOUT_VIEW = "/"
SECURITY_AUTO_LOGIN_AFTER_CONFIRM = True
SECURITY_ANONYMOUS_USER_DISABLED = True
SECURITY_SEND_REGISTER_EMAIL = False
SECURITY_USERNAME_ENABLE = True
SECURITY_USERNAME_REQUIRED = True
SECURITY_REGISTERABLE = False
SECURITY_CONFIRMABLE = False
SECURITY_RECOVERABLE = False
SECURITY_OAUTH_ENABLE = False


# Flask Debugtoolbar
DEBUG_TB_ENABLED = True
DEBUG_TB_INTERCEPT_REDIRECTS = False
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
TEMPLATES_AUTO_RELOAD = True
EXPLAIN_TEMPLATE_LOADING = False

# Daleks
DALEKS_URL: str
DALEKS_FROM_ADDRESS: str = SECURITY_EMAIL_SENDER
DALEKS_SMTP_ACCOUNT: str = "mariofix"

# Flask-Alembic
ALEMBIC = {
    "post_write_hooks": {
        "hooks": "black",
        "black.type": "console_scripts",
        "black.entrypoint": "black",
    }
}


API_TITLE: str = "Firenze"
API_VERSION: str = "2026.9.0"
OPENAPI_VERSION: str = "3.1.1"
OPENAPI_URL_PREFIX: str = "/api/v1"
OPENAPI_SWAGGER_UI_PATH: str = "/docs"
OPENAPI_SWAGGER_UI_URL: str = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"
