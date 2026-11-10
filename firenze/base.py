from ipaddress import ip_address, ip_network

from flask import Flask, jsonify, request
from werkzeug.exceptions import Forbidden
from werkzeug.middleware.proxy_fix import ProxyFix

from .admin import FirenzeAdminIndexView, setup_admin
from .api import agi_bp
from .extensions import admin, api, babel, cors, db, debugtoolbar, migrate, theme
from .version import __version__


def create_app(base_settings: str | None):
    app = Flask("firenze", instance_relative_config=True)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    if base_settings:
        app.config.from_object(base_settings)
    app.config.from_prefixed_env()

    # Extensions
    debugtoolbar.init_app(app)
    api.init_app(app)
    cors.init_app(app)
    db.init_app(app)
    migrate.init_app(app, db)
    babel.init_app(app)

    # Flask-Admin
    theme.init_app(app)
    admin.init_app(
        app, index_view=FirenzeAdminIndexView(name="Estado Sistema", menu_icon_type="ti", menu_icon_value="dashboard")
    )
    setup_admin(app)

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
