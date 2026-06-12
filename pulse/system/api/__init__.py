# -----------------------------------------------------------------------------
# sparQ — Mobile API Foundation
#
# Package initialization and registration for the /api/v1/ REST API layer.
# Provides JWT authentication, serialization, pagination, and error handling
# for the Flutter mobile application.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from flask import Blueprint, Flask, request


def register_api(app: Flask) -> None:
    """Register the mobile API blueprint and error handlers.

    Called from create_app() after OAuth init and before CSRF.
    Wires auth endpoints and JSON error handlers onto /api/v1/.

    Args:
        app: Flask application instance.
    """
    from system.api.auth import auth_bp
    from system.api.errors import register_api_error_handlers
    from system.api.push import push_bp
    from system.api.routes.sync import sync_bp as sync_channels_bp
    from system.api.routes.core import core_bp
    from system.api.routes.dashboard import dashboard_bp
    from system.api.routes.presence import presence_bp
    from system.api.sync import sync_bp
    import system.api.models  # noqa: F401 — ensure RefreshToken is in metadata
    import system.api.push  # noqa: F401 — ensure DeviceToken is in metadata

    api_bp = Blueprint("api", __name__, url_prefix="/api/v1")
    api_bp.register_blueprint(auth_bp)
    api_bp.register_blueprint(core_bp)
    api_bp.register_blueprint(dashboard_bp)
    api_bp.register_blueprint(sync_channels_bp)
    api_bp.register_blueprint(presence_bp)
    api_bp.register_blueprint(push_bp)
    api_bp.register_blueprint(sync_bp)
    register_api_error_handlers(api_bp)

    # CORS for Flutter web dev only — never in production
    if app.debug:

        @api_bp.after_request
        def add_cors_headers(response):
            origin = request.headers.get("Origin", "")
            if origin.startswith("http://localhost:"):
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
                response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            return response

    app.register_blueprint(api_bp)
