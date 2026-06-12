# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Web Push notification service. Sends push notifications to users'
#     browsers/devices using the Web Push Protocol with VAPID authentication.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def is_push_configured() -> bool:
    """Check if Web Push is configured with VAPID keys."""
    return bool(
        os.environ.get("VAPID_PUBLIC_KEY")
        and os.environ.get("VAPID_PRIVATE_KEY")
    )


def get_vapid_public_key() -> Optional[str]:
    """Get the VAPID public key for client subscription."""
    return os.environ.get("VAPID_PUBLIC_KEY")


def send_push(
    user_id: int,
    title: str,
    body: str,
    url: Optional[str] = None,
    icon: Optional[str] = None,
    badge_count: Optional[int] = None,
) -> int:
    """Send a push notification to all of a user's active subscriptions.

    Args:
        user_id: The user to notify
        title: Notification title
        body: Notification body text
        url: URL to open when notification is clicked
        icon: Icon URL (defaults to app icon)
        badge_count: Total unread count for app icon badge

    Returns:
        Number of notifications successfully sent
    """
    if not is_push_configured():
        logger.debug("Push notifications not configured, skipping")
        return 0

    # Import here to avoid circular imports and allow graceful degradation
    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        logger.warning("pywebpush not installed, push notifications disabled")
        return 0

    from modules.base.core.models.push_subscription import PushSubscription

    subscriptions = PushSubscription.get_active_for_user(user_id)
    if not subscriptions:
        return 0

    vapid_private_key = os.environ.get("VAPID_PRIVATE_KEY")
    vapid_claims_email = os.environ.get("VAPID_CLAIMS_EMAIL", "admin@example.com")

    # Default icon
    if icon is None:
        icon = "/assets/core/images/pwa/icon-192x192.png"

    payload = json.dumps({
        "title": title,
        "body": body,
        "url": url or "/",
        "icon": icon,
        "badge_count": badge_count,
    })

    sent_count = 0
    for subscription in subscriptions:
        try:
            webpush(
                subscription_info=subscription.to_subscription_info(),
                data=payload,
                vapid_private_key=vapid_private_key,
                vapid_claims={"sub": f"mailto:{vapid_claims_email}"},
            )
            sent_count += 1
        except WebPushException as e:
            logger.warning(f"Push failed for subscription {subscription.id}: {e}")
            # Deactivate invalid subscriptions (410 Gone or 404 Not Found)
            response_code = getattr(e.response, "status_code", None) if e.response else None
            if response_code in (404, 410):
                try:
                    PushSubscription.deactivate_by_id(subscription.id)
                    logger.info(f"Deactivated invalid subscription {subscription.id}")
                except Exception as deactivate_err:
                    logger.error(f"Failed to deactivate subscription {subscription.id}: {deactivate_err}")
        except Exception as e:
            logger.error(f"Unexpected error sending push to {subscription.id}: {e}")

    return sent_count


def send_push_to_channel(
    channel_id: int,
    sender_id: int,
    message_preview: str,
    channel_name: str,
) -> int:
    """Send push notifications to all users subscribed to a channel.

    Excludes the sender.

    Args:
        channel_id: The channel where the message was sent
        sender_id: The user who sent the message (excluded from notifications)
        message_preview: Preview of the message content
        channel_name: Name of the channel for the notification

    Returns:
        Total number of notifications sent
    """
    if not is_push_configured():
        return 0

    from modules.base.core.models.user import User
    from modules.base.core.models.workspace_user import WorkspaceUser
    from modules.base.updates.models.channel_read_state import UpdateChannelReadState
    from modules.base.updates.models.dm import DMThread

    # Get all active users in current workspace except the sender
    all_users = WorkspaceUser.get_workspace_users()
    total_sent = 0

    sender = User.get_by_id(sender_id)
    sender_name = sender.first_name if sender else "Someone"

    from modules.base.updates.controllers.socketio_events import is_user_viewing_channel

    for user in all_users:
        if user.id == sender_id:
            continue

        # Skip if user is actively viewing this channel
        if is_user_viewing_channel(user.id, channel_name):
            continue

        # Compute total unread count across channels and DMs
        unread = (UpdateChannelReadState.get_total_unread_count(user.id)
                  + DMThread.get_total_unread_count(user.id))

        count = send_push(
            user_id=user.id,
            title=f"#{channel_name}",
            body=f"{sender_name}: {message_preview}" if message_preview else f"{sender_name} sent a message",
            url=f"/sync/chat?channel={channel_name}",
            badge_count=unread,
        )
        total_sent += count

    return total_sent


def send_push_dm(
    recipient_id: int,
    sender_id: int,
    message_preview: str,
    thread_id: Optional[int] = None,
) -> int:
    """Send push notification for a direct message.

    Args:
        recipient_id: The user to notify
        sender_id: The user who sent the message
        message_preview: Preview of the message content
        thread_id: The DM thread ID (to check if user is viewing it)

    Returns:
        Number of notifications sent
    """
    if not is_push_configured():
        return 0

    from modules.base.core.models.user import User
    from modules.base.updates.models.channel_read_state import UpdateChannelReadState
    from modules.base.updates.models.dm import DMThread

    recipient = User.get_by_id(recipient_id)
    if not recipient:
        return 0

    # Skip if user is actively viewing this DM thread
    if thread_id:
        from modules.base.updates.controllers.socketio_events import is_user_viewing_dm
        if is_user_viewing_dm(recipient_id, thread_id):
            return 0

    sender = User.get_by_id(sender_id)
    sender_name = sender.first_name if sender else "Someone"

    # Compute total unread count across channels and DMs
    unread = (UpdateChannelReadState.get_total_unread_count(recipient_id)
              + DMThread.get_total_unread_count(recipient_id))

    return send_push(
        user_id=recipient_id,
        title=f"Message from {sender_name}",
        body=message_preview or "Sent you a message",
        url=f"/sync/chat?dm={sender_id}",
        badge_count=unread,
    )
