# -----------------------------------------------------------------------------
# sparQ — Sync API Routes
#
# Channel and message endpoints for mobile chat. Read-heavy: channel lists,
# message history, unread counts. Essential writes: send message, mark read.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from flask import Blueprint, g, jsonify, request

from system.api.decorators import jwt_required
from system.api.errors import api_error_response, validate_required
from system.api.pagination import paginated_response
from system.middleware.ratelimit import rate_limit

sync_bp = Blueprint("api_sync_channels", __name__, url_prefix="/sync")


@sync_bp.route("/channels", methods=["GET"])
@jwt_required
@rate_limit(limit=120, window=60)
def list_channels():
    """List all channels with unread counts for the current user."""
    from modules.base.updates.models.channel import UpdateChannel
    from modules.base.updates.models.channel_read_state import UpdateChannelReadState
    from modules.base.core.models.workspace_user import WorkspaceUser

    member = WorkspaceUser.get_by_user_id(g.current_user.id)
    member_id = member.id if member else 0
    channels = UpdateChannel.get_all()

    result = []
    for ch in channels:
        unread = UpdateChannelReadState.get_unread_count(member_id, ch.id)
        mention_count = UpdateChannelReadState.get_mention_count(member_id, ch.id)
        ch_dict = ch.to_dict()
        ch_dict["unread_count"] = unread
        ch_dict["mention_count"] = mention_count
        result.append(ch_dict)

    return jsonify({"channels": result}), 200


@sync_bp.route("/channels/<int:channel_id>", methods=["GET"])
@jwt_required
@rate_limit(limit=120, window=60)
def get_channel(channel_id):
    """Get channel details."""
    from modules.base.updates.models.channel import UpdateChannel

    channel = UpdateChannel.get_by_id(channel_id)
    if not channel:
        return api_error_response("NOT_FOUND", "Channel not found", 404)

    return jsonify(channel.to_dict()), 200


@sync_bp.route("/channels/<int:channel_id>/messages", methods=["GET"])
@jwt_required
@rate_limit(limit=120, window=60)
def list_messages(channel_id):
    """Paginated message history for a channel (reads from unified sync_post)."""
    from modules.base.updates.models.channel import UpdateChannel
    from modules.base.updates.models.post import UpdatePost

    channel = UpdateChannel.get_by_id(channel_id)
    if not channel:
        return api_error_response("NOT_FOUND", "Channel not found", 404)

    query = UpdatePost.scoped().filter(
        UpdatePost.channel_id == channel_id
    ).order_by(UpdatePost.created_at.desc())

    def serialize_post(post):
        """Compat shim: flatten payload["content"] as top-level content field."""
        d = {
            "id": post.id,
            "content": (post.payload or {}).get("content", ""),
            "created_at": post.created_at.isoformat() if post.created_at else None,
            "channel_id": post.channel_id,
            "member_id": post.member_id,
            "post_type": post.post_type,
        }
        if post.member and post.member.user:
            d["author"] = {
                "id": post.member.user.id,
                "first_name": post.member.user.first_name,
                "last_name": post.member.user.last_name,
                "avatar_color": post.member.user.avatar_color,
            }
        return d

    return paginated_response(query, serialize=serialize_post)


@sync_bp.route("/channels/<int:channel_id>/messages", methods=["POST"])
@jwt_required
@rate_limit(limit=60, window=60)
def send_message(channel_id):
    """Send a message to a channel (REST fallback for when SocketIO unavailable)."""
    from modules.base.updates.models.channel import UpdateChannel
    from modules.base.updates.models.post import UpdatePost
    from modules.base.core.models.workspace_user import WorkspaceUser

    channel = UpdateChannel.get_by_id(channel_id)
    if not channel:
        return api_error_response("NOT_FOUND", "Channel not found", 404)

    data = request.get_json(silent=True)
    errors = validate_required(data, ["content"])
    if errors:
        return api_error_response("VALIDATION_ERROR", "Missing required fields", 400, errors)

    member = WorkspaceUser.get_by_user_id(g.current_user.id)
    post = UpdatePost.create_with_mentions(
        content=data["content"],
        member_id=member.id if member else None,
        channel_id=channel_id,
    )

    return jsonify({
        "id": post.id,
        "content": post.content,
        "created_at": post.created_at.isoformat() if post.created_at else None,
        "channel_id": post.channel_id,
        "member_id": post.member_id,
    }), 201


@sync_bp.route("/channels/<int:channel_id>/read", methods=["POST"])
@jwt_required
@rate_limit(limit=120, window=60)
def mark_channel_read(channel_id):
    """Mark all messages in a channel as read."""
    from modules.base.updates.models.channel import UpdateChannel
    from modules.base.updates.models.channel_read_state import UpdateChannelReadState
    from modules.base.core.models.workspace_user import WorkspaceUser

    channel = UpdateChannel.get_by_id(channel_id)
    if not channel:
        return api_error_response("NOT_FOUND", "Channel not found", 404)

    member = WorkspaceUser.get_by_user_id(g.current_user.id)
    UpdateChannelReadState.mark_channel_read(member.id if member else 0, channel_id)
    return jsonify({"status": "ok"}), 200


@sync_bp.route("/unread", methods=["GET"])
@jwt_required
@rate_limit(limit=120, window=60)
def get_unread_count():
    """Total unread message count across all channels (for app badge)."""
    from modules.base.updates.models.channel_read_state import UpdateChannelReadState
    from modules.base.core.models.workspace_user import WorkspaceUser

    member = WorkspaceUser.get_by_user_id(g.current_user.id)
    total = UpdateChannelReadState.get_total_unread_count(member.id if member else 0)
    return jsonify({"total_unread": total}), 200
