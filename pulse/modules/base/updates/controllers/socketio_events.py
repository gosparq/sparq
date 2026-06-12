# -----------------------------------------------------------------------------
# sparQ - Sync Module SocketIO Events
#
# Real-time chat using flask-socketio (compatible with the main server)
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

import time
import uuid
from typing import TYPE_CHECKING

from flask import current_app, g, render_template, session
from flask_login import current_user
from flask_socketio import SocketIO, join_room, leave_room

from modules.base.resources.models.attachment_link import AttachmentLink

from ..models import DMReaction, UpdatePostAck, UpdatePostReaction

if TYPE_CHECKING:
    from ..models import DM, DMThread

# Room prefixes
USER_ROOM_PREFIX = "user_"


def _channel_room(channel_name: str) -> str:
    """Build a workspace-scoped channel room name."""
    ts_id = getattr(g, "workspace_id", "unknown")
    return f"chat_channel_{ts_id}_{channel_name}"


def _ensure_workspace_context() -> None:
    """Set g.workspace_id for SocketIO event handlers.

    Flask's before_request hooks don't run for SocketIO events, and g is
    per-request-context so values set in handle_connect don't carry over.
    Mirrors the resolution order in request_hooks.set_workspace_context.
    """
    if getattr(g, "workspace_id", None):
        return

    # 1. Session (web users — no DB query)
    active_ts = session.get("active_workspace_id")
    if active_ts:
        if isinstance(active_ts, str):
            try:
                active_ts = uuid.UUID(active_ts)
            except ValueError:
                active_ts = None
        if active_ts:
            g.workspace_id = active_ts
            return

    # 2. Membership fallback
    if current_user.is_authenticated:
        from modules.base.core.models.workspace_user import WorkspaceUser

        membership = WorkspaceUser.query.filter_by(
            user_id=current_user.id
        ).order_by(WorkspaceUser.created_at.desc()).first()
        if membership:
            g.workspace_id = membership.workspace_id

# Track connected users (in-memory)
connected_users: set[int] = set()

# Track what each user is currently viewing: {user_id: {"type": "channel"|"dm", "id": channel_name|thread_id}}
user_viewing: dict[int, dict] = {}

# Map SocketIO session IDs to user IDs (for JWT disconnect handling)
sid_to_user: dict[str, int] = {}


def init_socketio_handlers(socketio) -> None:
    """Register SocketIO event handlers for chat."""

    @socketio.on("connect", namespace="/sync")
    def handle_connect(auth=None):
        """Handle client connection to chat namespace.

        Supports two auth modes:
        1. JWT token via auth payload: {"token": "jwt..."} (mobile app)
        2. Session cookie via Flask-Login (web browser)

        If auth.token is present, it must be valid — no fallthrough to session.
        """
        from flask import request as flask_request

        user = None

        # Mode 1: JWT auth from mobile app
        if auth and auth.get("token"):
            from system.api.jwt import verify_access_token
            from modules.base.core.models.user import User

            payload = verify_access_token(auth["token"])
            if not payload:
                return False  # Invalid/expired JWT — reject

            user = User.get_by_id(payload["user_id"])
            if not user or not user.is_active:
                return False
        else:
            # Mode 2: Session auth from web browser
            if not current_user.is_authenticated:
                return False  # Reject connection
            user = current_user

        user_id = user.id
        connected_users.add(user_id)

        # Set workspace + organization context for scoped queries (before_request
        # hooks don't run for SocketIO events, so we replicate resolution here).
        active_ts = session.get("active_workspace_id") if not (auth and auth.get("token")) else None
        if active_ts:
            if isinstance(active_ts, str):
                try:
                    active_ts = uuid.UUID(active_ts)
                except ValueError:
                    active_ts = None
            g.workspace_id = active_ts

        if not getattr(g, "workspace_id", None):
            from modules.base.core.models.workspace_user import WorkspaceUser

            # JWT auth can include workspace_id in the payload
            if auth and auth.get("token") and auth.get("workspace_id"):
                ts_id = auth["workspace_id"]
                if isinstance(ts_id, str):
                    try:
                        ts_id = uuid.UUID(ts_id)
                    except ValueError:
                        ts_id = None
                if ts_id:
                    membership = WorkspaceUser.query.filter_by(
                        user_id=user_id, workspace_id=ts_id
                    ).first()
                    if membership:
                        g.workspace_id = ts_id

        if not getattr(g, "workspace_id", None):
            # Final fallback: pick most recently created membership
            from modules.base.core.models.workspace_user import WorkspaceUser
            membership = WorkspaceUser.query.filter_by(
                user_id=user_id
            ).order_by(WorkspaceUser.created_at.desc()).first()
            if membership:
                g.workspace_id = membership.workspace_id

        # Always derive g.organization_id from the resolved workspace so
        # OrganizationMixin.scoped() has its tenant boundary.
        if getattr(g, "workspace_id", None) and not getattr(g, "organization_id", None):
            from modules.base.core.models.workspace import Workspace
            ts = Workspace.query.get(g.workspace_id)
            if ts is not None:
                g.organization_id = ts.organization_id

        if not getattr(g, "organization_id", None):
            # No workspace resolved — reject rather than leak across orgs.
            return False

        # Track SID→user mapping for disconnect handling (JWT users)
        sid = getattr(flask_request, "sid", None)
        if sid:
            sid_to_user[sid] = user_id

        # Update last_seen
        user.update_last_seen()

        current_app.logger.debug(f"Chat SocketIO connected: user={user_id}")

        # Join user's personal room for DM delivery
        join_room(USER_ROOM_PREFIX + str(user_id))

        # Join all channels by default
        from ..models import UpdateChannel

        for channel in UpdateChannel.get_all():
            room = _channel_room(channel.name)
            join_room(room)

        # Broadcast presence update to all
        broadcast_presence_update(socketio, user_id, "online")

    @socketio.on("disconnect", namespace="/sync")
    def handle_disconnect():
        """Handle client disconnection.

        Supports both session-authenticated (web) and JWT-authenticated (mobile)
        users. For JWT users, current_user is anonymous, so we resolve the user
        from the SID→user mapping stored during connect.
        """
        from flask import request as flask_request
        from modules.base.core.models.user import User

        user_id = None

        # Try session auth first (web browser)
        sid = getattr(flask_request, "sid", None)
        if current_user.is_authenticated:
            user_id = current_user.id
        else:
            # JWT path: look up user from SID mapping
            if sid:
                user_id = sid_to_user.pop(sid, None)

        # Clean up SID mapping
        if sid:
            sid_to_user.pop(sid, None)

        if not user_id:
            return

        connected_users.discard(user_id)
        user_viewing.pop(user_id, None)

        # Update last_seen
        user = User.get_by_id(user_id)
        if user:
            user.update_last_seen()

        # Leave user room
        leave_room(USER_ROOM_PREFIX + str(user_id))

        # Broadcast presence update
        broadcast_presence_update(socketio, user_id, "offline")

        current_app.logger.debug(f"Chat SocketIO disconnected: user={user_id}")

    @socketio.on("heartbeat", namespace="/sync")
    def handle_heartbeat():
        """Handle periodic heartbeat to update presence."""
        if current_user.is_authenticated:
            current_user.update_last_seen()
            if current_user.id in user_viewing:
                user_viewing[current_user.id]["at"] = time.time()

    @socketio.on("join_channel", namespace="/sync")
    def handle_join_channel(data):
        """Join a specific channel room."""
        channel_name = data.get("channel")
        if channel_name:
            room = _channel_room(channel_name)
            join_room(room)

    @socketio.on("leave_channel", namespace="/sync")
    def handle_leave_channel(data):
        """Leave a specific channel room."""
        channel_name = data.get("channel")
        if channel_name:
            room = _channel_room(channel_name)
            leave_room(room)

    @socketio.on("viewing", namespace="/sync")
    def handle_viewing(data):
        """Track what channel/DM the user is currently viewing."""
        if not current_user.is_authenticated:
            return

        view_type = data.get("type")  # "channel" or "dm"
        view_id = data.get("id")  # channel name or thread ID

        if view_type and view_id:
            user_viewing[current_user.id] = {"type": view_type, "id": view_id, "at": time.time()}
        else:
            # User left chat or viewing nothing
            user_viewing.pop(current_user.id, None)

    @socketio.on("typing", namespace="/sync")
    def handle_typing(data):
        """Broadcast typing indicator to channel or DM."""
        if not current_user.is_authenticated:
            return
        _ensure_workspace_context()

        channel_name = data.get("channel")
        dm_thread_id = data.get("dm_thread_id")

        user_info = {
            "user_id": current_user.id,
            "user_name": current_user.first_name,
        }

        if channel_name:
            # Channel typing
            room = _channel_room(channel_name)
            socketio.emit(
                "user_typing",
                {"channel": channel_name, **user_info},
                namespace="/sync",
                room=room,
                include_self=False,
            )
        elif dm_thread_id:
            # DM typing - send to the other user
            from ..models import DMThread

            thread = DMThread.get_by_id(dm_thread_id)
            if thread:
                other_user_id = (
                    thread.member2.user_id
                    if thread.member1 and thread.member1.user_id == current_user.id
                    else thread.member1.user_id if thread.member1 else None
                )
                room = USER_ROOM_PREFIX + str(other_user_id)
                socketio.emit(
                    "user_typing_dm",
                    {"thread_id": dm_thread_id, **user_info},
                    namespace="/sync",
                    room=room,
                )

    @socketio.on("stop_typing", namespace="/sync")
    def handle_stop_typing(data):
        """Broadcast stop typing indicator."""
        if not current_user.is_authenticated:
            return
        _ensure_workspace_context()

        channel_name = data.get("channel")
        dm_thread_id = data.get("dm_thread_id")

        user_info = {"user_id": current_user.id}

        if channel_name:
            room = _channel_room(channel_name)
            socketio.emit(
                "user_stop_typing",
                {"channel": channel_name, **user_info},
                namespace="/sync",
                room=room,
                include_self=False,
            )
        elif dm_thread_id:
            from ..models import DMThread

            thread = DMThread.get_by_id(dm_thread_id)
            if thread:
                other_user_id = (
                    thread.member2.user_id
                    if thread.member1 and thread.member1.user_id == current_user.id
                    else thread.member1.user_id if thread.member1 else None
                )
                room = USER_ROOM_PREFIX + str(other_user_id)
                socketio.emit(
                    "user_stop_typing_dm",
                    {"thread_id": dm_thread_id, **user_info},
                    namespace="/sync",
                    room=room,
                )


def broadcast_new_message(socketio, channel_name: str, chat) -> None:
    """Broadcast a new message to all users in the channel.

    Note: current_member is not available in broadcast context (rendered once
    for all recipients), so 10-4 current_user_acked is resolved client-side.
    """
    html = render_template(
        "updates/desktop/chat/partials/_message.html",
        message=chat,
        channel=chat.channel,
        channel_name=channel_name,
        oob_swap=True,
        AttachmentLink=AttachmentLink,
        UpdatePostReaction=UpdatePostReaction,
        UpdatePostAck=UpdatePostAck,
    )

    room = _channel_room(channel_name)
    socketio.emit(
        "new_message",
        {
            "channel": channel_name,
            "html": html,
            "message_id": chat.id,
            "author_id": chat.author_id,  # compat property → user_id
            "target_user_id": chat.target_user_id,
            "mentioned_member_ids": chat.mentioned_member_ids or [],
        },
        namespace="/sync",
        room=room,
    )


def broadcast_message_updated(socketio, channel_name: str, chat) -> None:
    """Broadcast an updated message (e.g., pin status changed)."""
    html = render_template(
        "updates/desktop/chat/partials/_message.html",
        message=chat,
        channel=chat.channel,
        channel_name=channel_name,
        oob_swap=True,
        replace=True,
        AttachmentLink=AttachmentLink,
        UpdatePostReaction=UpdatePostReaction,
        UpdatePostAck=UpdatePostAck,
    )

    room = _channel_room(channel_name)
    socketio.emit(
        "message_updated",
        {"channel": channel_name, "html": html, "message_id": chat.id},
        namespace="/sync",
        room=room,
    )


def broadcast_message_deleted(socketio, channel_name: str, message_id: int) -> None:
    """Broadcast a message deletion."""
    room = _channel_room(channel_name)
    socketio.emit(
        "message_deleted",
        {"channel": channel_name, "message_id": message_id},
        namespace="/sync",
        room=room,
    )


def broadcast_reaction_update(
    socketio, channel_name: str, message_id: int, reactions: dict
) -> None:
    """Broadcast a reaction update to all users in the channel."""
    room = _channel_room(channel_name)
    socketio.emit(
        "reaction_update",
        {"channel": channel_name, "message_id": message_id, "reactions": reactions},
        namespace="/sync",
        room=room,
    )


def broadcast_ten_four_update(
    socketio, channel_name: str, message_id: int, ack_data: dict
) -> None:
    """Broadcast a 10-4 acknowledgment update to all users in the channel."""
    room = _channel_room(channel_name)
    socketio.emit(
        "ten_four_update",
        {"channel": channel_name, "message_id": message_id, "ack_data": ack_data},
        namespace="/sync",
        room=room,
    )


def broadcast_channel_created(socketio, channel) -> None:
    """Broadcast new channel creation to all connected users."""
    html = render_template(
        "updates/desktop/chat/partials/_channel_item.html",
        channel=channel,
        oob_swap=True,
    )

    # Broadcast to all connected clients
    socketio.emit(
        "channel_created",
        {"channel": channel.name, "html": html},
        namespace="/sync",
    )


def broadcast_channel_deleted(socketio, channel_name: str) -> None:
    """Broadcast channel deletion to all connected users."""
    socketio.emit(
        "channel_deleted",
        {"channel": channel_name},
        namespace="/sync",
    )


def broadcast_presence_update(socketio, user_id: int, status: str) -> None:
    """Broadcast user presence change to all connected clients."""
    from modules.base.core.models.user import User

    user = User.get_by_id(user_id)
    if user:
        socketio.emit(
            "presence_update",
            {
                "user_id": user_id,
                "status": status,
                "name": user.full_name,
            },
            namespace="/sync",
        )


def is_user_viewing_channel(user_id: int, channel_name: str) -> bool:
    """Check if a user is currently viewing a specific channel."""
    viewing = user_viewing.get(user_id)
    if viewing is None:
        return False
    # Expire stale entries (5 min) — safety net for dirty disconnects
    if time.time() - viewing.get("at", 0) > 300:
        user_viewing.pop(user_id, None)
        return False
    return viewing.get("type") == "channel" and viewing.get("id") == channel_name


def is_user_viewing_dm(user_id: int, thread_id: int) -> bool:
    """Check if a user is currently viewing a specific DM thread."""
    viewing = user_viewing.get(user_id)
    if viewing is None:
        return False
    # Expire stale entries (5 min) — safety net for dirty disconnects
    if time.time() - viewing.get("at", 0) > 300:
        user_viewing.pop(user_id, None)
        return False
    return viewing.get("type") == "dm" and viewing.get("id") == thread_id


def broadcast_agent_message(
    socketio: SocketIO,
    message_data: dict,
    target_user_id: int,
) -> None:
    """Broadcast a sparQy agent message to a specific user's room.

    message_data should contain:
        - content: str (the message content, may include AI_MESSAGE:: prefix)
        - author_id: int
        - author_name: str (display name)
        - avatar_color: str (hex color)
        - is_ai: bool (if True, uses AI styling)
        - timestamp: str (formatted time string)
        - temp_id: str (temporary ID for client-side tracking)
        - clear_storage: bool (if True, clear localStorage on client)
    """
    html = render_template(
        "updates/desktop/chat/partials/_agent_message.html",
        message=message_data,
    )

    room = USER_ROOM_PREFIX + str(target_user_id)
    socketio.emit(
        "agent_message",
        {
            "sparqy": True,
            "html": html,
            "temp_id": message_data.get("temp_id"),
            "author_id": message_data.get("author_id"),
            "target_user_id": target_user_id,
            "is_ai": message_data.get("is_ai", False),
            "content": message_data.get("content", ""),
            "clear_storage": message_data.get("clear_storage", False),
        },
        namespace="/sync",
        room=room,
    )


def broadcast_dm_message(
    socketio: SocketIO,
    recipient_id: int,
    message: "DM",
    thread: "DMThread",
) -> None:
    """Broadcast a new DM to a user (sender or recipient)."""
    html = render_template(
        "updates/desktop/chat/partials/_dm_message.html",
        message=message,
        AttachmentLink=AttachmentLink,
        DMReaction=DMReaction,
        viewing_user_id=recipient_id,
    )

    # Determine the "other user" from the perspective of the recipient
    # recipient_id here is a user_id (for SocketIO room routing)
    if thread.member1 and thread.member1.user_id == recipient_id:
        other_user_id = thread.member2.user_id if thread.member2 else None
    else:
        other_user_id = thread.member1.user_id if thread.member1 else None

    room = USER_ROOM_PREFIX + str(recipient_id)
    socketio.emit(
        "new_dm",
        {
            "thread_id": thread.id,
            "sender_id": message.author_id,  # compat property → user_id
            "other_user_id": other_user_id,
            "html": html,
            "message_id": message.id,
        },
        namespace="/sync",
        room=room,
    )


def broadcast_dm_deleted(
    socketio: SocketIO,
    thread: "DMThread",
    message_id: int,
) -> None:
    """Broadcast DM deletion to both users in the thread."""
    user_ids = []
    if thread.member1:
        user_ids.append(thread.member1.user_id)
    if thread.member2:
        user_ids.append(thread.member2.user_id)
    for user_id in user_ids:
        room = USER_ROOM_PREFIX + str(user_id)
        socketio.emit(
            "dm_deleted",
            {"message_id": message_id},
            namespace="/sync",
            room=room,
        )


def broadcast_dm_reaction_update(
    socketio: SocketIO,
    thread: "DMThread",
    message_id: int,
    reactions: dict,
) -> None:
    """Broadcast a DM reaction update to both users in the thread."""
    user_ids = []
    if thread.member1:
        user_ids.append(thread.member1.user_id)
    if thread.member2:
        user_ids.append(thread.member2.user_id)
    for user_id in user_ids:
        room = USER_ROOM_PREFIX + str(user_id)
        socketio.emit(
            "dm_reaction_update",
            {"message_id": message_id, "reactions": reactions},
            namespace="/sync",
            room=room,
        )
