# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

from datetime import datetime, timedelta, timezone

from flask import current_app, g, jsonify, render_template, request


def utc_to_local_date(utc_dt):
    """Convert a UTC datetime to local date for date divider comparisons."""
    if utc_dt is None:
        return None
    utc_aware = utc_dt.replace(tzinfo=timezone.utc)
    local_dt = utc_aware.astimezone()
    return local_dt.date()
from flask.typing import ResponseReturnValue
from flask_login import current_user, login_required

from modules.base.core.models.workspace_user import WorkspaceUser
from system.db.database import db
from system.device.template import render_device_template

from ..models import UpdateChannel, UpdateChannelReadState, UpdatePost, UpdatePostAck, UpdatePostReaction
from . import blueprint

# Import AttachmentLink for template context
from modules.base.resources.models.attachment_link import AttachmentLink


def _current_member() -> WorkspaceUser | None:
    """Resolve the current user's workspace membership."""
    return WorkspaceUser.get_by_user_id(current_user.id)


@blueprint.route("/chat")
@login_required
def chat_index() -> str:
    """Main chat page."""
    from ..models.dm import DMThread

    requested_channel = request.args.get("channel")
    if requested_channel:
        channel = UpdateChannel.get_by_name(requested_channel.lower())
        default_channel = channel if channel else UpdateChannel.get_or_create_default()
    else:
        default_channel = UpdateChannel.get_or_create_default()

    channels = UpdateChannel.get_all()

    # Check for DM view request from secondary nav
    dm_target_member_id = request.args.get("member", type=int)
    default_view = "dm" if request.args.get("view") == "dms" and dm_target_member_id else "channel"

    # Get unread counts for mobile badges
    member = _current_member()
    member_id = member.id if member else 0
    unread_channel_count = UpdateChannelReadState.get_total_unread_count(member_id)
    unread_dm_count = DMThread.get_total_unread_count(member_id)
    unread_mention_count = UpdateChannelReadState.get_total_mention_count(member_id)

    # Build channel follow state for the current member
    from ..models.follow import UpdateFollow

    channel_follow_ids = UpdateFollow.get_followed_ids("channel", member_id) if member_id else set()

    return render_device_template(
        "updates/desktop/chat/index.html",
        channels=channels,
        default_channel=default_channel,
        default_view=default_view,
        dm_target_member_id=dm_target_member_id,
        UpdateChannelReadState=UpdateChannelReadState,
        unread_channel_count=unread_channel_count,
        unread_dm_count=unread_dm_count,
        unread_mention_count=unread_mention_count,
        channel_follow_ids=channel_follow_ids,
        remaining_channel_slots=UpdateChannel.remaining_channel_slots(),
        dm_direct_id=request.args.get("dm"),
        dm_direct_name=request.args.get("dn", ""),
        dm_direct_color=request.args.get("dc", "#6b7280"),
        active_page="chat",
        module_home="sync_bp.index",
    )


@blueprint.route("/chat/channels")
@login_required
def get_channels() -> str:
    """Get channel list partial (HTMX)."""
    channels = UpdateChannel.get_all()
    return render_template(
        "updates/desktop/chat/partials/_channel_list.html",
        channels=channels,
        UpdateChannelReadState=UpdateChannelReadState,
    )


@blueprint.route("/chat/channels/<channel_name>/messages")
@login_required
def get_channel_messages(channel_name: str) -> ResponseReturnValue:
    """Get messages for a specific channel (HTMX partial)."""
    try:
        before_id = request.args.get("before_id", type=int)
        limit = request.args.get("limit", 20, type=int)
        pinned_only = request.args.get("pinned", type=int)
        search = request.args.get("search", "")

        channel = UpdateChannel.get_by_name(channel_name)
        if not channel:
            return f"Channel {channel_name} not found", 404

        from sqlalchemy.orm import joinedload

        # Build query against UpdatePost
        query = (
            UpdatePost.scoped()
            .options(joinedload(UpdatePost.member).joinedload(WorkspaceUser.user))
            .filter(UpdatePost.channel_id == channel.id)
        )

        if pinned_only:
            query = query.filter(UpdatePost.pinned == True)

        if search:
            # Search in payload->content for chat messages
            query = query.filter(
                db.cast(UpdatePost.payload["content"], db.Text).ilike(f"%{search}%")
            )

        # Pagination
        if not before_id:
            messages = query.order_by(UpdatePost.created_at.desc()).limit(limit + 1).all()
        else:
            messages = (
                query.filter(UpdatePost.id < before_id)
                .order_by(UpdatePost.created_at.desc())
                .limit(limit + 1)
                .all()
            )

        has_more = len(messages) > limit
        if has_more:
            messages = messages[:limit]
        messages = messages[::-1]
        oldest_id = messages[0].id if messages else None

        # Mark newest message as read
        member = _current_member()
        if messages and member:
            UpdateChannelReadState.mark_post_read(member.id, messages[-1].id)

        today = datetime.now().date()
        return render_device_template(
            "updates/desktop/chat/partials/_message_list.html",
            messages=messages,
            channel=channel,
            has_more=has_more,
            oldest_id=oldest_id,
            AttachmentLink=AttachmentLink,
            UpdatePostReaction=UpdatePostReaction,
            UpdatePostAck=UpdatePostAck,
            today=today,
            yesterday=today - timedelta(days=1),
            utc_to_local_date=utc_to_local_date,
        )

    except Exception as e:
        current_app.logger.error(f"Error getting channel messages: {str(e)}")
        return "Failed to load messages", 500


@blueprint.route("/chat/channels", methods=["POST"])
@login_required
def create_channel() -> ResponseReturnValue:
    """Create a new channel (admin only)."""
    try:
        if not current_user.is_admin:
            return "Unauthorized: Only administrators can create channels", 403

        name = request.form.get("name")
        if not name:
            return "Channel name is required", 400

        if not UpdateChannel.can_create_channel():
            return f"Channel limit reached ({UpdateChannel.MAX_CHANNELS} max). Remove a custom channel first.", 400

        name = name.lower().replace(" ", "-")
        description = request.form.get("description")
        is_private = bool(request.form.get("is_private", False))
        require_ten_four = request.form.get("require_ten_four") in ("true", "1", "on")

        existing = UpdateChannel.get_by_name(name)
        if existing:
            return "Channel already exists", 400

        member = _current_member()
        channel = UpdateChannel.create(
            name=name,
            description=description,
            created_by_id=member.id if member else None,
            is_private=is_private,
            require_ten_four=require_ten_four,
        )

        # Broadcast to all connected clients via SocketIO
        from .socketio_events import broadcast_channel_created

        broadcast_channel_created(current_app.socketio, channel)

        return jsonify({"id": channel.id, "name": channel.name})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating channel: {str(e)}")
        return "Failed to create channel", 400


@blueprint.route("/chat/messages", methods=["POST"])
@login_required
def create_message() -> ResponseReturnValue:
    """Create a new chat message."""
    try:
        content = request.form.get("content")
        channel_name = request.form.get("channel", "general")
        attachment_ids = request.form.get("attachment_ids", "")

        if (not content or not content.strip()) and not attachment_ids:
            return "Content or attachment is required", 400

        channel = UpdateChannel.get_by_name(channel_name)
        if not channel:
            return f"Channel {channel_name} not found", 404

        # Save as UpdatePost with mention extraction
        member = _current_member()
        try:
            chat = UpdatePost.create_with_mentions(
                content=content or "",
                member_id=member.id if member else None,
                channel_id=channel.id,
            )
        except PermissionError:
            return "Channel is locked because its project is closed.", 403

        # Link attachments if any
        if attachment_ids:
            from modules.base.resources.models.attachment_link import AttachmentLink

            for att_id in attachment_ids.split(","):
                att_id = att_id.strip()
                if att_id.isdigit():
                    AttachmentLink.create(
                        attachment_id=int(att_id),
                        entity_type="chat_message",
                        entity_id=chat.id,
                    )

        # Mark as read for author
        if member:
            UpdateChannelReadState.mark_post_read(member.id, chat.id)

        # Follow notifications — email channel followers
        from system.email.sync_notifications import notify_followers, notify_mention

        notify_followers("channel", channel.id, chat, member)

        # In-app notifications for project followers
        if getattr(channel, "project", None):
            try:
                channel.project.notify_followers_new_post(chat, member)
            except Exception as e:
                current_app.logger.error("notify_followers_new_post failed: %s", e, exc_info=True)

        # @mention notifications — immediate email
        for mid in (chat.mentioned_member_ids or []):
            notify_mention(mid, chat, member)

        # Truncate message preview for push notification
        plain = chat.plain_text_content
        preview = (plain[:50] + "...") if plain and len(plain) > 50 else plain

        # Send push notifications to offline users
        from modules.base.core.services.push_notification import send_push_to_channel

        send_push_to_channel(
            channel_id=channel.id,
            sender_id=current_user.id,
            message_preview=preview or "",
            channel_name=channel_name,
        )

        # Broadcast to channel via SocketIO
        from .socketio_events import broadcast_new_message

        broadcast_new_message(current_app.socketio, channel_name, chat)

        return "", 204

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating chat: {str(e)}")
        return "Failed to send message", 400


@blueprint.route("/chat/messages/<int:message_id>/pin", methods=["POST"])
@login_required
def toggle_pin(message_id: int) -> ResponseReturnValue:
    """Toggle pin status of a message."""
    try:
        chat = UpdatePost.get_by_id(message_id)
        if not chat:
            return jsonify({"error": "Message not found"}), 404

        if not current_user.is_admin and not chat.is_author:
            return jsonify({"error": "Unauthorized"}), 403

        is_pinned = UpdatePost.toggle_pin(message_id)

        # Broadcast pin change via SocketIO
        from .socketio_events import broadcast_message_updated

        # Refresh to get updated state
        db.session.refresh(chat)
        broadcast_message_updated(current_app.socketio, chat.channel.name, chat)

        return jsonify({"pinned": is_pinned})
    except Exception as e:
        current_app.logger.error(f"Error toggling pin: {str(e)}")
        return jsonify({"error": "Failed to toggle pin"}), 400


@blueprint.route("/chat/messages/<int:message_id>/react", methods=["POST"])
@login_required
def toggle_reaction(message_id: int) -> ResponseReturnValue:
    """Toggle an emoji reaction on a message."""
    try:
        emoji = request.form.get("emoji")
        if not emoji:
            return jsonify({"error": "Emoji is required"}), 400

        chat = UpdatePost.get_by_id(message_id)
        if not chat:
            return jsonify({"error": "Message not found"}), 404

        member = _current_member()
        added, count = UpdatePostReaction.toggle(message_id, member.id if member else 0, emoji)

        # Get updated reactions for the message
        reactions = UpdatePostReaction.get_for_message(message_id)

        # Broadcast reaction update via SocketIO
        from .socketio_events import broadcast_reaction_update

        broadcast_reaction_update(
            current_app.socketio,
            chat.channel.name,
            message_id,
            reactions,
        )

        return jsonify({"added": added, "count": count, "reactions": reactions})
    except PermissionError:
        return jsonify({"error": "Channel is locked because its project is closed."}), 403
    except Exception as e:
        current_app.logger.error(f"Error toggling reaction: {str(e)}")
        return jsonify({"error": "Failed to toggle reaction"}), 400


@blueprint.route("/chat/channels/<channel_name>/ten-four", methods=["POST"])
@login_required
def toggle_channel_ten_four(channel_name: str) -> ResponseReturnValue:
    """Toggle 10-4 requirement on a channel (admin only)."""
    try:
        if not current_user.is_admin:
            return jsonify({"error": "Unauthorized"}), 403

        channel = UpdateChannel.get_by_name(channel_name)
        if not channel:
            return jsonify({"error": "Channel not found"}), 404

        channel.require_ten_four = not channel.require_ten_four
        db.session.commit()

        return jsonify({"require_ten_four": channel.require_ten_four})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error toggling 10-4: {str(e)}")
        return jsonify({"error": "Failed to toggle 10-4"}), 400


@blueprint.route("/chat/messages/<int:message_id>/acknowledge", methods=["POST"])
@login_required
def toggle_acknowledgment(message_id: int) -> ResponseReturnValue:
    """Toggle 10-4 acknowledgment on a message."""
    try:
        chat = UpdatePost.get_by_id(message_id)
        if not chat:
            return jsonify({"error": "Message not found"}), 404

        channel = chat.channel
        wh = chat._get_webhook()
        is_webhook_ten_four = chat.webhook_id and wh and wh.enable_ten_four
        if not channel.require_ten_four and not is_webhook_ten_four:
            return jsonify({"error": "10-4 not enabled"}), 400

        member = _current_member()
        if not member:
            return jsonify({"error": "Not a team member"}), 403

        ack_data = UpdatePostAck.acknowledge(message_id, member.id)

        # Broadcast via SocketIO
        from .socketio_events import broadcast_ten_four_update

        broadcast_ten_four_update(
            current_app.socketio,
            channel.name,
            message_id,
            ack_data,
        )

        return jsonify({"ack_data": ack_data})
    except PermissionError:
        return jsonify({"error": "Channel is locked because its project is closed."}), 403
    except Exception as e:
        current_app.logger.error(f"Error toggling acknowledgment: {str(e)}")
        return jsonify({"error": "Failed to toggle acknowledgment"}), 400


@blueprint.route("/chat/messages/<int:message_id>", methods=["DELETE"])
@login_required
def delete_message(message_id: int) -> ResponseReturnValue:
    """Delete a chat message (admin only)."""
    try:
        chat = UpdatePost.get_by_id(message_id)
        if not chat:
            return jsonify({"error": "Message not found"}), 404

        if not current_user.is_admin:
            return jsonify({"error": "Unauthorized"}), 403

        channel_name = chat.channel.name

        UpdatePost.delete_message(message_id)

        # Broadcast deletion via SocketIO
        from .socketio_events import broadcast_message_deleted

        broadcast_message_deleted(current_app.socketio, channel_name, message_id)

        return "", 204
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting message: {str(e)}")
        return jsonify({"error": "Failed to delete message"}), 400


@blueprint.route("/chat/channels/<channel_name>/mark_read", methods=["POST"])
@login_required
def mark_channel_read(channel_name: str) -> ResponseReturnValue:
    """Mark all messages in a channel as read."""
    try:
        channel = UpdateChannel.get_by_name(channel_name)
        if not channel:
            return jsonify({"error": f"Channel {channel_name} not found"}), 404

        member = _current_member()
        success = UpdateChannelReadState.mark_channel_read(member.id if member else 0, channel.id)
        if success:
            return "", 204
        else:
            return jsonify({"error": "Failed to mark channel as read"}), 500

    except Exception as e:
        current_app.logger.error(f"Error marking channel as read: {str(e)}")
        return jsonify({"error": "Failed to mark channel as read"}), 500


@blueprint.route("/chat/emojis")
@login_required
def get_emoji_list() -> ResponseReturnValue:
    """Get list of available emojis for the picker."""
    from ..utils.emoji import get_emoji_list

    return jsonify(get_emoji_list())


@blueprint.route("/chat/users")
@login_required
def get_user_list() -> str:
    """Get member list for DM sidebar (HTMX)."""
    member = _current_member()
    member_id = member.id if member else 0
    from sqlalchemy.orm import joinedload

    members = WorkspaceUser.scoped().options(
        joinedload(WorkspaceUser.user)
    ).filter(
        WorkspaceUser.id != member_id
    ).all()
    is_mobile = request.args.get("mobile") == "1"
    template = (
        "updates/mobile/chat/partials/_user_list.html"
        if is_mobile
        else "updates/desktop/chat/partials/_user_list.html"
    )
    return render_template(template, members=members)


@blueprint.route("/chat/channels/<channel_name>", methods=["DELETE"])
@login_required
def delete_channel(channel_name: str) -> ResponseReturnValue:
    """Delete a channel and all its messages (admin only)."""
    try:
        if channel_name == "general":
            return jsonify({"error": f"Cannot delete the {channel_name} channel"}), 400

        channel = UpdateChannel.get_by_name(channel_name)
        if not channel:
            return jsonify({"error": f"Channel {channel_name} not found"}), 404

        if not current_user.is_admin:
            return jsonify({"error": "Unauthorized"}), 403

        UpdateChannel.delete_channel(channel.id)

        # Broadcast channel deletion via SocketIO
        from .socketio_events import broadcast_channel_deleted

        broadcast_channel_deleted(current_app.socketio, channel_name)

        return "", 204
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting channel: {str(e)}")
        return jsonify({"error": "Failed to delete channel"}), 400


@blueprint.route("/chat/users/search")
@login_required
def search_users() -> ResponseReturnValue:
    """Search users for @mention autocomplete."""
    from modules.base.core.models.user import User
    from modules.base.core.models.workspace_user import WorkspaceUser

    q = request.args.get("q", "").strip()
    dm_member_id = request.args.get("dm_member_id", type=int)

    query = (
        User.query.join(WorkspaceUser, WorkspaceUser.user_id == User.id)
        .filter(
            WorkspaceUser.workspace_id == g.workspace_id,
            WorkspaceUser.deleted_at.is_(None),
            User.is_active == True,
            User.id != current_user.id,
        )
        .add_columns(WorkspaceUser.id.label("member_id"))
    )

    if dm_member_id:
        query = query.filter(WorkspaceUser.id == dm_member_id)

    if q:
        query = query.filter(
            db.or_(User.first_name.ilike(f"{q}%"), User.last_name.ilike(f"{q}%"))
        )

    results = query.order_by(User.first_name).limit(8).all()

    return jsonify(
        [
            {
                "id": u.id,
                "name": u.first_name,
                "full_name": u.full_name,
                "avatar_color": u.avatar_color,
                "member_id": member_id,
            }
            for u, member_id in results
        ]
    )


# Allowed file types for chat attachments
ALLOWED_EXTENSIONS = {
    "jpg", "jpeg", "png", "gif", "webp",
    "pdf", "doc", "docx", "xls", "xlsx", "txt", "csv", "rtf",
    "json", "xml", "html", "css", "js", "py", "yaml", "yml",
    "md", "log", "sql", "sh", "ini", "toml", "cfg", "env",
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@blueprint.route("/chat/upload", methods=["POST"])
@login_required
def upload_attachment() -> ResponseReturnValue:
    """Upload a file for chat attachment."""
    from modules.base.resources.models.attachment import Attachment
    from modules.base.resources.services import storage

    try:
        if "file" not in request.files:
            return jsonify({"error": "No file provided"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No file selected"}), 400

        if not allowed_file(file.filename):
            return jsonify({"error": "File type not allowed"}), 400

        file.seek(0, 2)
        size = file.tell()
        file.seek(0)

        if size > MAX_FILE_SIZE:
            return jsonify({"error": "File too large (max 10MB)"}), 400

        attachment = Attachment.create(
            filename=file.filename,
            mime_type=file.content_type or "application/octet-stream",
            size_bytes=size,
        )
        storage.save_to_attachments(file, attachment)

        return jsonify(
            {
                "id": attachment.id,
                "uuid": attachment.uuid,
                "filename": attachment.filename,
                "mime_type": attachment.mime_type,
                "size_display": attachment.size_display,
                "is_image": attachment.mime_type.startswith("image/"),
            }
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error uploading attachment: {str(e)}")
        return jsonify({"error": "Failed to upload file"}), 500


@blueprint.route("/chat/attachments/<uuid>")
@login_required
def download_attachment(uuid: str) -> ResponseReturnValue:
    """Download or view a chat attachment."""
    from flask import send_file
    import os

    from modules.base.resources.models.attachment import Attachment
    from modules.base.resources.services import storage

    attachment = Attachment.get_by_uuid(uuid)
    if not attachment:
        return jsonify({"error": "Attachment not found"}), 404

    file_path = storage.get_attachment_path(attachment)
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404

    force_download = request.args.get("download") == "1"
    is_inline = attachment.mime_type.startswith("image/") or attachment.mime_type.startswith("audio/")
    as_attachment = force_download or not is_inline
    mimetype = attachment.mime_type if is_inline else "application/octet-stream"

    return send_file(
        file_path,
        mimetype=mimetype,
        as_attachment=as_attachment,
        download_name=attachment.filename,
    )


@blueprint.route("/chat/unread-count")
@login_required
def unread_count() -> ResponseReturnValue:
    """Lightweight endpoint for badge polling (no WebSocket needed)."""
    from ..models.dm import DMThread

    member = _current_member()
    member_id = member.id if member else 0
    channel_unread = UpdateChannelReadState.get_total_unread_count(member_id)
    dm_unread = DMThread.get_total_unread_count(member_id)
    return jsonify({
        "count": channel_unread + dm_unread,
        "channel_count": channel_unread,
        "dm_count": dm_unread,
    })
