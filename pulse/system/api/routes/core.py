# -----------------------------------------------------------------------------
# sparQ — Core API Routes
#
# Profile read/update and company settings for the mobile app.
# Read-heavy: profile view, settings. One write: profile update (name, phone).
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from flask import Blueprint, g, jsonify, request

from system.api.decorators import jwt_required
from system.api.errors import api_error_response
from system.middleware.ratelimit import rate_limit

core_bp = Blueprint("api_core", __name__, url_prefix="/core")


@core_bp.route("/profile", methods=["GET"])
@jwt_required
@rate_limit(limit=120, window=60)
def get_profile():
    """Return the current user's profile."""
    return jsonify(g.current_user.to_dict()), 200


@core_bp.route("/profile", methods=["PUT"])
@jwt_required
@rate_limit(limit=60, window=60)
def update_profile():
    """Update limited profile fields (name, phone only — no email/password on mobile)."""
    data = request.get_json(silent=True)
    if not data:
        return api_error_response("VALIDATION_ERROR", "Request body required", 400)

    user = g.current_user
    allowed_fields = {"first_name", "last_name", "phone_number"}
    updated = False

    for field in allowed_fields:
        if field in data:
            setattr(user, field, data[field])
            updated = True

    if not updated:
        return api_error_response("VALIDATION_ERROR", "No valid fields to update", 400)

    from system.db.database import db
    db.session.commit()

    return jsonify(user.to_dict()), 200


@core_bp.route("/settings", methods=["GET"])
@jwt_required
@rate_limit(limit=120, window=60)
def get_settings():
    """Return company settings (timezone, currency, branding, enabled modules)."""
    from modules.base.core.models.workspace_settings import WorkspaceSettings

    settings = WorkspaceSettings.get_instance()
    return jsonify(settings.to_dict()), 200
