# -----------------------------------------------------------------------------
# sparQ - Sync Module: Follow Controller
#
# Routes for content follow/unfollow toggle.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from flask import jsonify, request
from flask_login import current_user, login_required

from modules.base.core.models.workspace_user import WorkspaceUser

from . import blueprint
from ..models.follow import UpdateFollow


@blueprint.route("/follow/toggle", methods=["POST"])
@login_required
def follow_toggle():
    """Toggle follow state for an entity. Returns JSON {is_following: bool}."""
    entity_type = request.form.get("entity_type", "").strip()
    entity_id = request.form.get("entity_id", type=int)

    if entity_type not in ("channel", "status_template", "board_template") or not entity_id:
        return jsonify({"error": "Invalid entity"}), 400

    member = WorkspaceUser.get_by_user_id(current_user.id)
    if not member:
        return jsonify({"error": "Not a member"}), 403

    try:
        is_following, _ = UpdateFollow.toggle(entity_type, entity_id, member.id)
    except PermissionError:
        return jsonify({"error": "Channel is locked because its project is closed."}), 403
    return jsonify({"is_following": is_following})
