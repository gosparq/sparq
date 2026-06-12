# -----------------------------------------------------------------------------
# sparQ - Sync Module Direct Message Routes
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

import re

from flask import current_app, g, jsonify, render_template, request
from flask.typing import ResponseReturnValue
from flask_login import current_user, login_required

from modules.base.core.models.workspace import Workspace
from modules.base.core.models.workspace_user import WorkspaceUser
from modules.base.resources.models.attachment_link import AttachmentLink
from system.db.database import db

from ..models import DM, DMThread, DMReaction
from . import blueprint


def _current_member() -> WorkspaceUser | None:
    """Resolve the current user's workspace membership."""
    return WorkspaceUser.get_by_user_id(current_user.id)


def _organization_dm_candidates(exclude_user_id: int) -> list[WorkspaceUser]:
    """Return one active WorkspaceUser per user across the current organization.

    DMs are organization-scoped (§12.4) — the picker must surface every person
    in the org, not just members of the active workspace. Since DMThread FKs
    still point at workspace_user.id (Q3), we return a representative
    WorkspaceUser row for each user (the oldest active membership in the org).

    Excludes by User.id (not WorkspaceUser.id) so the current user never
    appears in their own list even if they have memberships in multiple
    workspaces within the same organization.
    """
    organization_id = getattr(g, "organization_id", None)
    if organization_id is None:
        return []

    # Pull all active workspace_user rows in any workspace of this organization,
    # excluding every membership row belonging to the current user. Ordered by
    # user_id then by primary key (id ascending = chronological since
    # WorkspaceUser.id is an auto-increment integer — no created_at column).
    from sqlalchemy.orm import joinedload
    rows: list[WorkspaceUser] = (
        WorkspaceUser.query
        .options(joinedload(WorkspaceUser.user))
        .join(Workspace, Workspace.id == WorkspaceUser.workspace_id)
        .filter(Workspace.organization_id == organization_id)
        .filter(WorkspaceUser.deleted_at.is_(None))
        .filter(WorkspaceUser.user_id != exclude_user_id)
        .order_by(WorkspaceUser.user_id, WorkspaceUser.id.asc())
        .all()
    )

    # Deduplicate by user_id — one representative WorkspaceUser per person.
    seen_users: set[int] = set()
    members: list[WorkspaceUser] = []
    for m in rows:
        if m.user_id in seen_users:
            continue
        if not m.user or not m.user.is_active:
            continue
        seen_users.add(m.user_id)
        members.append(m)
    return members


def _is_mobile_request() -> bool:
    """Check if request is from a mobile device based on User-Agent."""
    user_agent = request.headers.get("User-Agent", "").lower()
    mobile_keywords = ["mobile", "android", "iphone", "ipad", "ipod"]
    return any(keyword in user_agent for keyword in mobile_keywords)


@blueprint.route("/chat/dms/sparqy")
@login_required
def get_sparqy_dm() -> ResponseReturnValue:
    """Get sparQy AI chat view (HTMX partial)."""
    from system.ai.llm import is_llm_configured

    return render_template(
        "updates/desktop/chat/partials/_agent_message_list.html",
        llm_configured=is_llm_configured(),
    )


@blueprint.route("/chat/dms/sparqy/messages", methods=["POST"])
@login_required
def send_sparqy_message() -> ResponseReturnValue:
    """Send a message to sparQy AI bot."""
    import uuid
    from datetime import datetime

    content = request.form.get("content")
    if not content or not content.strip():
        return "Content is required", 400

    from modules.base.updates.controllers.socketio_events import broadcast_agent_message

    temp_id = f"msg-{uuid.uuid4().hex[:8]}"
    message_data = {
        "temp_id": temp_id,
        "content": content,
        "author_id": current_user.id,
        "author_name": f"{current_user.first_name} {current_user.last_name}",
        "avatar_color": current_user.avatar_color,
        "is_ai": False,
        "timestamp": datetime.now().strftime("%I:%M %p"),
    }
    broadcast_agent_message(
        current_app.socketio,
        message_data,
        current_user.id,
    )

    if content.strip():
        try:
            from modules.base.ai.service import handle_agent_message

            handle_agent_message(content, current_user)
        except Exception as ai_error:
            current_app.logger.error(f"AI processing error: {ai_error}")

    return "", 204


@blueprint.route("/chat/dms")
@login_required
def get_dm_threads() -> str:
    """Get DM thread list partial (HTMX)."""
    member = _current_member()
    member_id = member.id if member else 0
    is_mobile = request.args.get("mobile") == "1"

    if is_mobile and request.args.get("sheet") == "1":
        all_members = _organization_dm_candidates(exclude_user_id=current_user.id)
        thread_map = DMThread.get_thread_map_for_member(member_id)
        return render_template(
            "updates/mobile/chat/partials/_dm_sheet.html",
            members=all_members,
            thread_map=thread_map,
        )

    if is_mobile:
        threads = DMThread.get_threads_for_member(member_id)
        # Filter out threads with inactive/terminated members
        threads = [
            t for t in threads
            if (other := t.get_other_member(member_id))
            and other.user
            and other.user.is_active
            and "admin" not in other.user.email.lower()
        ]
        return render_template(
            "updates/mobile/chat/partials/_dm_list.html", threads=threads
        )

    # Desktop: show every other person in the organization (DMs are org-scoped
    # per §12.4) with their thread/unread info. Exclude by User.id so the
    # current user never appears in their own list across any of their
    # workspace memberships.
    all_members = _organization_dm_candidates(exclude_user_id=current_user.id)
    threads = DMThread.get_threads_for_member(member_id)

    # Build a lookup: member_id -> (thread, unread_count) for template display
    thread_map = {}
    for thread in threads:
        other = thread.get_other_member(member_id)
        if other:
            thread_map[other.id] = (thread, thread.get_unread_count(member_id))

    # Popup-specific compact list
    if request.args.get("popup") == "1":
        return render_template(
            "updates/desktop/chat/partials/_dm_popup_list.html",
            members=all_members,
            thread_map=thread_map,
        )

    return render_template(
        "updates/desktop/chat/partials/_dm_list.html",
        members=all_members,
        thread_map=thread_map,
    )


@blueprint.route("/chat/dms/<int:target_member_id>")
@login_required
def get_or_create_dm(target_member_id: int) -> ResponseReturnValue:
    """Get or create DM thread with a member, return messages."""
    member = _current_member()
    if not member:
        return "Membership not found", 400

    if target_member_id == member.id:
        return "Cannot DM yourself", 400

    # Targets can live in any workspace of the current organization (DMs are
    # org-scoped per §12.4). Verify the target is in the same org as the caller.
    from sqlalchemy.orm import joinedload

    target = (
        WorkspaceUser.query
        .options(joinedload(WorkspaceUser.user))
        .join(Workspace, Workspace.id == WorkspaceUser.workspace_id)
        .filter(WorkspaceUser.id == target_member_id)
        .filter(Workspace.organization_id == g.organization_id)
        .filter(WorkspaceUser.deleted_at.is_(None))
        .first()
    )
    if not target:
        return "Member not found", 404

    thread = DMThread.get_or_create(member.id, target_member_id)

    # Get recent messages (same pattern as channel messages)
    messages = thread.messages.order_by(DM.created_at.desc()).limit(50).all()
    messages = messages[::-1]  # Reverse to chronological order

    # Mark messages as read
    DM.mark_thread_read(thread.id, member.id)

    # Popup-specific compact messages view
    if request.args.get("popup") == "1":
        return render_template(
            "updates/desktop/chat/partials/_dm_popup_messages.html",
            thread=thread,
            messages=messages,
            other_user=target.user,
            current_member_id=member.id,
        )

    # Check for mobile request (via User-Agent or query param)
    is_mobile = request.args.get("mobile") == "1" or _is_mobile_request()
    template = (
        "updates/mobile/chat/partials/_dm_thread.html"
        if is_mobile
        else "updates/desktop/chat/partials/_dm_thread.html"
    )

    return render_template(
        template,
        thread=thread,
        messages=messages,
        other_user=target.user,
        AttachmentLink=AttachmentLink,
        DMReaction=DMReaction,
    )


@blueprint.route("/chat/dms/<int:thread_id>/messages", methods=["POST"])
@login_required
def send_dm(thread_id: int) -> ResponseReturnValue:
    """Send a direct message."""
    member = _current_member()
    if not member:
        return "Membership not found", 400

    thread = DMThread.get_by_id(thread_id)
    if not thread:
        return "Thread not found", 404

    # Verify member is part of thread
    if not thread.has_member(member.id):
        return "Unauthorized", 403

    content = request.form.get("content")
    attachment_ids = request.form.get("attachment_ids", "")

    if (not content or not content.strip()) and not attachment_ids:
        return "Content or attachment required", 400

    try:
        # Extract mentioned member IDs from content
        mentioned_ids = [int(m) for m in re.findall(r"@\[(\d+)\]", content or "")]

        message = DM.create(
            thread_id=thread_id,
            member_id=member.id,
            content=content or "",
        )

        # Store mentioned member IDs
        if mentioned_ids:
            message.mentioned_member_ids = mentioned_ids
            db.session.commit()

        # Link attachments if any
        if attachment_ids:
            for att_id in attachment_ids.split(","):
                att_id = att_id.strip()
                if att_id.isdigit():
                    AttachmentLink.create(
                        attachment_id=int(att_id),
                        entity_type="direct_message",
                        entity_id=message.id,
                    )

        # Get recipient member info. DM threads can span workspaces within the
        # same organization (§12.4), so look up the recipient's WorkspaceUser
        # row unscoped — the thread already enforces org isolation.
        other_member_id = (
            thread.member2_id if thread.member1_id == member.id else thread.member1_id
        )
        other_member = WorkspaceUser.query.get(other_member_id)
        recipient_user_id = other_member.user_id if other_member else None

        # Truncate message preview for push notification (resolve mentions first)
        plain = message.plain_text_content
        preview = (plain[:50] + "...") if plain and len(plain) > 50 else plain

        # Send push notification to recipient (if offline)
        # Note: In-app notifications handled by real-time WebSocket + badges + sound
        from modules.base.core.services.push_notification import send_push_dm

        if recipient_user_id:
            send_push_dm(
                recipient_id=recipient_user_id,
                sender_id=current_user.id,
                message_preview=preview or "",
                thread_id=thread.id,
            )

        # Broadcast to both sender and recipient (using user_id for SocketIO rooms)
        from .socketio_events import broadcast_dm_message

        # Broadcast to sender (so they see their own message appended)
        broadcast_dm_message(current_app.socketio, current_user.id, message, thread)

        # Broadcast to recipient
        if recipient_user_id:
            broadcast_dm_message(current_app.socketio, recipient_user_id, message, thread)

        return "", 204

    except Exception as e:
        current_app.logger.error(f"Error sending DM: {str(e)}")
        return "Failed to send message", 500


@blueprint.route("/chat/dms/<int:thread_id>/read", methods=["POST"])
@login_required
def mark_dm_read(thread_id: int) -> ResponseReturnValue:
    """Mark all messages in a DM thread as read."""
    member = _current_member()
    if not member:
        return "Membership not found", 400

    thread = DMThread.get_by_id(thread_id)
    if not thread:
        return "Thread not found", 404

    if not thread.has_member(member.id):
        return "Unauthorized", 403

    DM.mark_thread_read(thread_id, member.id)
    return "", 204


@blueprint.route("/chat/dms/messages/<int:message_id>", methods=["DELETE"])
@login_required
def delete_dm_message(message_id: int) -> ResponseReturnValue:
    """Delete a DM message (author only)."""
    from .socketio_events import broadcast_dm_deleted

    member = _current_member()
    message = DM.get_by_id(message_id)
    if not message:
        return "Message not found", 404

    # Only author can delete their own messages
    if not member or message.member_id != member.id:
        return "Unauthorized", 403

    thread = DMThread.get_by_id(message.thread_id)
    DM.delete_message(message_id)

    # Broadcast deletion to both users in the thread
    broadcast_dm_deleted(current_app.socketio, thread, message_id)

    return "", 204


@blueprint.route("/chat/dms/<int:thread_id>/messages")
@login_required
def get_dm_messages(thread_id: int) -> ResponseReturnValue:
    """Get messages for a DM thread (HTMX partial)."""
    member = _current_member()
    if not member:
        return "Membership not found", 400

    thread = DMThread.get_by_id(thread_id)
    if not thread:
        return "Thread not found", 404

    if not thread.has_member(member.id):
        return "Unauthorized", 403

    # Get messages with pagination
    before_id = request.args.get("before_id", type=int)
    limit = request.args.get("limit", 50, type=int)

    query = thread.messages

    if before_id:
        query = query.filter(DM.id < before_id)

    messages = query.order_by(DM.created_at.desc()).limit(limit).all()
    messages = messages[::-1]  # Reverse to chronological

    # Mark as read
    DM.mark_thread_read(thread_id, member.id)

    other_member = thread.get_other_member(member.id)
    other_user = other_member.user if other_member else None

    return render_template(
        "updates/desktop/chat/partials/_dm_thread.html",
        thread=thread,
        messages=messages,
        other_user=other_user,
        AttachmentLink=AttachmentLink,
        DMReaction=DMReaction,
    )


@blueprint.route("/chat/dms/messages/<int:message_id>/react", methods=["POST"])
@login_required
def toggle_dm_reaction(message_id: int) -> ResponseReturnValue:
    """Toggle an emoji reaction on a DM message."""
    try:
        emoji = request.form.get("emoji")
        if not emoji:
            return jsonify({"error": "Emoji is required"}), 400

        member = _current_member()
        message = DM.get_by_id(message_id)
        if not message:
            return jsonify({"error": "Message not found"}), 404

        thread = DMThread.get_by_id(message.thread_id)
        if not thread or not member or not thread.has_member(member.id):
            return jsonify({"error": "Unauthorized"}), 403

        added, count = DMReaction.toggle(message_id, member.id, emoji)

        reactions = DMReaction.get_for_message(message_id)

        from .socketio_events import broadcast_dm_reaction_update

        broadcast_dm_reaction_update(
            current_app.socketio,
            thread,
            message_id,
            reactions,
        )

        return jsonify({"added": added, "count": count, "reactions": reactions})
    except Exception as e:
        current_app.logger.error(f"Error toggling DM reaction: {str(e)}")
        return jsonify({"error": "Failed to toggle reaction"}), 400
