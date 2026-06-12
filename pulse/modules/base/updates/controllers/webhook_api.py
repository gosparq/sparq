# -----------------------------------------------------------------------------
# sparQ - Webhook API (Public Receiver)
#
# Unauthenticated endpoint for incoming webhooks. CSRF exempt.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

import hashlib
import hmac
import time
from collections import defaultdict

from flask import Blueprint, current_app, g, request
from flask.typing import ResponseReturnValue

# Separate blueprint mounted at "" (root) - CSRF exempt
webhook_api_bp = Blueprint("webhook_api_bp", __name__)

# In-memory rate limiting: {token: [timestamps]}
_rate_limits: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT = 30  # requests per minute
_RATE_WINDOW = 60  # seconds


def _check_rate_limit(token: str) -> bool:
    """Check if webhook is within rate limit. Returns True if allowed."""
    now = time.time()
    timestamps = _rate_limits[token]

    # Remove old entries
    _rate_limits[token] = [t for t in timestamps if now - t < _RATE_WINDOW]

    if len(_rate_limits[token]) >= _RATE_LIMIT:
        return False

    _rate_limits[token].append(now)
    return True


def _verify_github_signature(payload_body: bytes, secret: str, signature_header: str) -> bool:
    """Verify GitHub X-Hub-Signature-256 header."""
    if not signature_header:
        return False
    expected = "sha256=" + hmac.new(
        secret.encode(), payload_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


@webhook_api_bp.route("/api/webhooks/<token>", methods=["POST"])
def receive_webhook(token: str) -> ResponseReturnValue:
    """Public endpoint for receiving webhook payloads."""
    from ..models import DM, UpdatePost, UpdateWebhook

    # Look up webhook by token
    webhook = UpdateWebhook.get_by_token(token)
    if not webhook:
        return "", 404

    if not webhook.is_active:
        return "", 404

    # Set org + workspace context from webhook so downstream models get the right
    # tenant — overrides any context left by curl-dev-bypass / stale sessions.
    g.organization_id = webhook.organization_id
    g.workspace_id = webhook.workspace_id

    # Rate limit
    if not _check_rate_limit(token):
        return "Rate limit exceeded", 429

    # Payload size check (1MB)
    if request.content_length and request.content_length > 1_048_576:
        return "Payload too large", 413

    # Check for GitHub event header
    github_event = request.headers.get("X-GitHub-Event")

    # Verify GitHub signature if secret is configured
    if webhook.github_secret and github_event:
        signature = request.headers.get("X-Hub-Signature-256", "")
        if not _verify_github_signature(request.get_data(), webhook.github_secret, signature):
            return "Invalid signature", 403

    try:
        payload = request.get_json(silent=True)
        if payload is None:
            # GitHub sends JSON in a "payload" form field when content type is urlencoded
            import json

            form_payload = request.form.get("payload")
            payload = json.loads(form_payload) if form_payload else {}
    except Exception:
        return "Invalid JSON", 400

    if github_event:
        # GitHub webhook
        from ..services.github_formatter import format_github_event

        content = format_github_event(github_event, payload)

        if content is None:
            # Ping or event that produces no message
            return "", 204

        content = "GITHUB_HTML::" + content
        username = "GitHub"
    else:
        # Discord-compatible generic webhook
        content = payload.get("content", "")
        username = payload.get("username")

        if not content:
            return "Content is required", 400

    # Truncate content
    content = content[:4000]

    # Create post (channel webhooks) or DM and broadcast
    if webhook.channel_id:
        # GitHub webhooks collapse into a single rolling thread per webhook.
        # First event creates the thread root; subsequent events become replies,
        # with older replies auto-trimmed to keep only the last 10.
        parent_id = None
        if github_event:
            root = UpdatePost.get_github_thread_root(webhook.channel_id, webhook.id)
            if root is not None:
                parent_id = root.id

        post = UpdatePost.create_from_webhook(
            content=content,
            channel_id=webhook.channel_id,
            webhook_id=webhook.id,
            username=username,
            parent_id=parent_id,
        )

        if github_event and parent_id is not None:
            # Trim to last 10 replies (+ the permanent root)
            try:
                UpdatePost.trim_github_thread_replies(parent_id, keep=10)
            except Exception as e:
                current_app.logger.error(f"Error trimming github thread: {e}")

        # Broadcast via the same pipeline as regular chat messages so connected
        # clients in the channel see the webhook post in real time.
        try:
            from .socketio_events import broadcast_new_message
            broadcast_new_message(current_app.socketio, webhook.channel.name, post)
        except Exception as e:
            current_app.logger.error(f"Error broadcasting webhook post: {e}")

    elif webhook.dm_thread_id:
        message = DM.create_from_webhook(
            content=content,
            thread_id=webhook.dm_thread_id,
            webhook_id=webhook.id,
            username=username,
        )

        # Broadcast to both users in the DM thread
        try:
            from .socketio_events import broadcast_dm_message

            thread = webhook.dm_thread
            for member in [thread.member1, thread.member2]:
                if member:
                    broadcast_dm_message(current_app.socketio, member.user_id, message, thread)
        except Exception as e:
            current_app.logger.error(f"Error broadcasting webhook DM: {e}")

    return "", 204
