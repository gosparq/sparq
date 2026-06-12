# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

"""WebSocket handlers for real-time chat (flask-sock + HTMX)."""

import json
import threading
from typing import TYPE_CHECKING

from flask import current_app, render_template

if TYPE_CHECKING:
    from simple_websocket import Server as WebSocket
    from ..models import UpdateChannel

# Store active WebSocket connections per user
_user_connections: dict[int, dict] = {}
_connections_lock = threading.Lock()


def init_websocket_routes(sock) -> None:
    """Register WebSocket routes with flask-sock."""

    @sock.route("/sync/chat/ws")
    def sync_chat_websocket(ws: "WebSocket") -> None:
        """Single WebSocket endpoint per user for all chat activity."""
        from flask_login import current_user

        if not current_user.is_authenticated:
            ws.close()
            return

        user_id = current_user.id
        current_app.logger.info(f"WebSocket connected: user={user_id}")

        from ..models import UpdateChannel

        all_channels = {c.name for c in UpdateChannel.get_all()}

        with _connections_lock:
            _user_connections[user_id] = {
                "ws": ws,
                "subscribed_channels": all_channels,
            }

        try:
            while True:
                data = ws.receive()
                if data is None:
                    break

                try:
                    message_data = json.loads(data)
                    _handle_incoming_message(ws, user_id, message_data)
                except json.JSONDecodeError:
                    current_app.logger.warning(f"Invalid JSON received: {data}")
                except Exception as e:
                    current_app.logger.error(f"Error handling message: {e}")

        except Exception as e:
            current_app.logger.error(f"WebSocket error: {e}")
        finally:
            with _connections_lock:
                _user_connections.pop(user_id, None)

            current_app.logger.info(f"WebSocket disconnected: user={user_id}")


def _handle_incoming_message(ws: "WebSocket", user_id: int, data: dict) -> None:
    """Handle incoming WebSocket message from HTMX ws-send form."""
    from modules.base.core.models.workspace_user import WorkspaceUser
    from ..models import UpdateChannel, UpdateChannelReadState
    from ..models.post import UpdatePost

    # Remove HEADERS that HTMX sends
    data.pop("HEADERS", None)

    msg_type = data.get("type", "message")
    channel_name = data.get("channel", "").strip()

    if msg_type == "subscribe":
        with _connections_lock:
            if user_id in _user_connections:
                _user_connections[user_id]["subscribed_channels"].add(channel_name)
        return

    if msg_type == "unsubscribe":
        with _connections_lock:
            if user_id in _user_connections:
                _user_connections[user_id]["subscribed_channels"].discard(channel_name)
        return

    # Default: handle as message
    content = data.get("content", "").strip()
    if not content or not channel_name:
        return

    channel = UpdateChannel.get_by_name(channel_name)
    if not channel:
        return

    member = WorkspaceUser.get_by_user_id(user_id)
    if not member:
        return

    # Create as UpdatePost directly (no more dual-write)
    chat = UpdatePost.create_channel_message(
        content=content,
        member_id=member.id,
        channel_id=channel.id,
    )

    # Mark as read for author
    UpdateChannelReadState.mark_post_read(member.id, chat.id)

    # Broadcast to all users subscribed to this channel
    broadcast_new_message(channel_name, chat)


def broadcast_new_message(channel_name: str, chat) -> None:
    """Broadcast a new message to all users subscribed to the channel."""
    html = render_template(
        "updates/desktop/chat/partials/_message.html",
        message=chat,
        channel_name=channel_name,
        oob_swap=True,
    )

    _broadcast_to_channel_subscribers(channel_name, html)


def broadcast_message_updated(channel_name: str, chat) -> None:
    """Broadcast an updated message (e.g., pin status changed)."""
    html = render_template(
        "updates/desktop/chat/partials/_message.html",
        message=chat,
        channel_name=channel_name,
        oob_swap=True,
        replace=True,
    )

    _broadcast_to_channel_subscribers(channel_name, html)


def broadcast_message_deleted(channel_name: str, message_id: int) -> None:
    """Broadcast a message deletion."""
    html = f'<div id="message-{message_id}" hx-swap-oob="delete" data-channel="{channel_name}"></div>'
    _broadcast_to_channel_subscribers(channel_name, html)


def broadcast_channel_created(channel: "UpdateChannel") -> None:
    """Broadcast new channel creation to all connected users."""
    html = render_template(
        "updates/desktop/chat/partials/_channel_item.html",
        channel=channel,
        oob_swap=True,
    )

    with _connections_lock:
        for user_id, conn in _user_connections.items():
            conn["subscribed_channels"].add(channel.name)

    _broadcast_to_all(html)


def broadcast_channel_deleted(channel_name: str) -> None:
    """Broadcast channel deletion to all connected users."""
    html = f'<div id="channel-{channel_name}" hx-swap-oob="delete"></div>'

    with _connections_lock:
        for user_id, conn in _user_connections.items():
            conn["subscribed_channels"].discard(channel_name)

    _broadcast_to_all(html)


def _broadcast_to_channel_subscribers(channel_name: str, html: str) -> None:
    """Send HTML to all users subscribed to a specific channel."""
    with _connections_lock:
        subscribers = [
            (user_id, conn["ws"])
            for user_id, conn in _user_connections.items()
            if channel_name in conn["subscribed_channels"]
        ]

    for user_id, ws in subscribers:
        try:
            ws.send(html)
        except Exception as e:
            current_app.logger.error(f"Error broadcasting to user {user_id}: {e}")


def _broadcast_to_all(html: str) -> None:
    """Send HTML to all connected users."""
    with _connections_lock:
        all_connections = [(user_id, conn["ws"]) for user_id, conn in _user_connections.items()]

    for user_id, ws in all_connections:
        try:
            ws.send(html)
        except Exception as e:
            current_app.logger.error(f"Error broadcasting to user {user_id}: {e}")
