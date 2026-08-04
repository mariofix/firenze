from ipaddress import ip_address, ip_network

from flask import Flask, jsonify, request
from flask_debugtoolbar import DebugToolbarExtension
from werkzeug.exceptions import Forbidden

from .api import agi_bp
from .extensions import alembic, api, cors, db
from .version import __version__


def create_app(base_settings: str | None):
    app = Flask("firenze")

    if base_settings:
        app.config.from_object(base_settings)
    app.config.from_prefixed_env()

    # Extensions
    if app.debug:
        DebugToolbarExtension(app)

    api.init_app(app)
    cors.init_app(app)
    db.init_app(app)
    alembic.init_app(app)
    app.config["agi_networks"] = [ip_network(cidr) for cidr in app.config.get("AGI_ALLOWED_NETWORKS", [])]

    api.register_blueprint(agi_bp)

    @app.before_request
    def enforce_request_guards():
        path_prefix = app.config.get("AGI_PATH_PREFIX", "/agi")
        if request.path.startswith(path_prefix):
            peer = request.remote_addr
            if not peer:
                raise Forbidden("Forbidden")
            try:
                addr = ip_address(peer)
            except ValueError as exc:
                raise Forbidden("Forbidden") from exc
            if not any(addr in network for network in app.config["agi_networks"]):
                raise Forbidden("Forbidden")

    @app.get("/")
    def root_index():
        return jsonify({"status": "ok"})

    return app
