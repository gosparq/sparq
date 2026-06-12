# -----------------------------------------------------------------------------
# sparQ - Notification Event Handler
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""Creates SystemNotifications from model lifecycle events."""

from typing import Any

from system.module.hooks import hookimpl
from system.events import notifications


class NotificationHandler:
    """Subscribes to record events and creates notifications."""

    @hookimpl
    def record_created(self, model_type: str, record: Any, user_id: int | None) -> None:
        self._handle(model_type, "created", record)

    @hookimpl
    def record_updated(self, model_type: str, record: Any, user_id: int | None, changes: dict) -> None:
        self._handle(model_type, "updated", record)

    @hookimpl
    def record_custom(self, model_type: str, event: str, record: Any, user_id: int | None) -> None:
        self._handle(model_type, event, record)

    def _handle(self, model_type: str, event: str, record: Any) -> None:
        """Create notification if configured for this model+event."""
        config = notifications.get(model_type, event)
        if not config or not config.should_trigger(record):
            return

        target_role, target_user_id = config.resolve_target(record)

        from .models.notification import SystemNotification

        # Support list of user IDs for multi-target notifications
        if isinstance(target_user_id, list):
            for user_id in target_user_id:
                SystemNotification.create(
                    title=config.resolve_title(record),
                    message=config.resolve_message(record),
                    type=config.type,
                    target_role="user",  # Per-user notifications use "user" role
                    user_id=user_id,
                    icon=config.icon,
                    action_url=config.resolve_url(record),
                    category=config.category,
                )
        else:
            SystemNotification.create(
                title=config.resolve_title(record),
                message=config.resolve_message(record),
                type=config.type,
                target_role=target_role or "admin",  # Default to admin if not specified
                user_id=target_user_id,
                icon=config.icon,
                action_url=config.resolve_url(record),
                category=config.category,
            )


notification_handler = NotificationHandler()
