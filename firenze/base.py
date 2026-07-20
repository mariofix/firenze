
from ipaddress import ip_address, ip_network

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_debugtoolbar import DebugToolbarExtension
from werkzeug.exceptions import Forbidden

from .config import Settings
from .database import SessionLocal, engine, migrations

from .version import __version__


def create_app():
    app = Flask(__name__)
    app.config.from_object(Settings)
    app.config.from_prefixed_env()

    allowed_domains = set(app.config.get("ALLOWED_DOMAINS", []))
    agi_networks = [ip_network(cidr) for cidr in app.config.get("AGI_ALLOWED_NETWORKS", [])]
    app.extensions["db_engine"] = engine
    app.extensions["db_session_factory"] = SessionLocal

    CORS(
        app,
        origins=app.config.get("CORS_ORIGINS", []),
        supports_credentials=True,
        allow_headers=["*"],
        methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    )
    DebugToolbarExtension(app)

    # Extensions
    migrations.init_app(app)

    @app.before_request
    def enforce_request_guards():
        host = request.host.split(":", 1)[0] if request.host else ""
        if allowed_domains and host not in allowed_domains:
            raise Forbidden("Host not allowed")

        path_prefix = app.config.get("AGI_PATH_PREFIX", "/agi")
        if request.path.startswith(path_prefix):
            peer = request.remote_addr
            if not peer:
                raise Forbidden("Forbidden")
            try:
                addr = ip_address(peer)
            except ValueError as exc:
                raise Forbidden("Forbidden") from exc
            if not any(addr in network for network in agi_networks):
                raise Forbidden("Forbidden")

    @app.get("/")
    def root_index():
        return jsonify({"status": "ok"})

    return app
