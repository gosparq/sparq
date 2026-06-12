# -----------------------------------------------------------------------------
# sparQ - Event System
#
# Provides model lifecycle events using pluggy hooks.
# Models emit events, handlers subscribe via @hookimpl.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""Event system for model lifecycle notifications.

Example:
    # In model's create() method
    from system.events import emit

    @classmethod
    def create(cls, ...) -> "ServiceRequest":
        request = cls(...)
        db.session.commit()
        emit.created("ServiceRequest", request)
        return request

    # In module's __init__.py to register notification config
    from system.events import notifications

    notifications.register(
        "ServiceRequest", "created",
        title="New Service Request",
        message=lambda r: f"{r.contact.display_name} submitted a request",
        target="admin",
        condition=lambda r: r.source.value in ("Portal", "Website"),
    )
"""

from dataclasses import dataclass
from typing import Callable, Any

from flask import current_app
from flask_login import current_user


# =============================================================================
# Event Emitter
# =============================================================================

class EventEmitter:
    """Emit model lifecycle events to pluggy hooks.

    Safe to call in any context - no-op if module_loader unavailable.
    """

    @staticmethod
    def _get_user_id() -> int | None:
        """Extract current user ID safely."""
        if current_user and hasattr(current_user, "id") and current_user.is_authenticated:
            return current_user.id
        return None

    @staticmethod
    def _get_hook() -> Any:
        """Get pluggy hook caller, or None if unavailable."""
        if hasattr(current_app, "module_loader"):
            return current_app.module_loader.pm.hook
        return None

    def created(self, model_type: str, record: Any) -> None:
        """Emit record_created event."""
        hook = self._get_hook()
        if hook:
            hook.record_created(
                model_type=model_type,
                record=record,
                user_id=self._get_user_id(),
            )

    def updated(self, model_type: str, record: Any, changes: dict) -> None:
        """Emit record_updated event."""
        hook = self._get_hook()
        if hook:
            hook.record_updated(
                model_type=model_type,
                record=record,
                user_id=self._get_user_id(),
                changes=changes,
            )

    def deleted(self, model_type: str, record_id: int, soft: bool = False) -> None:
        """Emit record_deleted event."""
        hook = self._get_hook()
        if hook:
            hook.record_deleted(
                model_type=model_type,
                record_id=record_id,
                user_id=self._get_user_id(),
                soft=soft,
            )

    def custom(self, model_type: str, event: str, record: Any) -> None:
        """Emit custom event for status transitions and other domain events."""
        hook = self._get_hook()
        if hook:
            hook.record_custom(
                model_type=model_type,
                event=event,
                record=record,
                user_id=self._get_user_id(),
            )


# Singleton
emit = EventEmitter()


# =============================================================================
# Notification Configuration
# =============================================================================

@dataclass
class NotificationConfig:
    """Configuration for auto-generating notifications."""
    title: str | Callable[[Any], str]
    message: str | Callable[[Any], str]
    type: str = "info"
    target: str | Callable[[Any], int | None] = "admin"
    icon: str = "fa-bell"
    url: str | Callable[[Any], str] | None = None
    condition: Callable[[Any], bool] | None = None
    category: str = "system"

    def resolve_title(self, record) -> str:
        return self.title(record) if callable(self.title) else self.title

    def resolve_message(self, record) -> str:
        return self.message(record) if callable(self.message) else self.message

    def resolve_url(self, record) -> str | None:
        if self.url is None:
            return None
        return self.url(record) if callable(self.url) else self.url

    def resolve_target(self, record) -> tuple[str | None, int | list[int] | None]:
        """Returns (target_role, user_id_or_list) tuple.

        When target is a callable that returns a list of user IDs, returns
        (None, [user_id, ...]) for multi-target notifications.
        """
        if callable(self.target):
            result = self.target(record)
            # Support both single user ID and list of user IDs
            return (None, result)
        elif self.target in ("admin", "all"):
            return (self.target, None)
        return ("admin", None)

    def should_trigger(self, record) -> bool:
        return self.condition(record) if self.condition else True


class NotificationRegistry:
    """Registry for notification configurations."""

    def __init__(self):
        self._configs: dict[str, dict[str, NotificationConfig]] = {}

    def register(
        self,
        model_type: str,
        event: str,
        title: str | Callable[[Any], str],
        message: str | Callable[[Any], str],
        type: str = "info",
        target: str | Callable[[Any], int | None] = "admin",
        icon: str = "fa-bell",
        url: str | Callable[[Any], str] | None = None,
        condition: Callable[[Any], bool] | None = None,
        category: str = "system",
    ) -> None:
        """Register notification config for model+event."""
        if model_type not in self._configs:
            self._configs[model_type] = {}
        self._configs[model_type][event] = NotificationConfig(
            title=title, message=message, type=type, target=target,
            icon=icon, url=url, condition=condition, category=category,
        )

    def get(self, model_type: str, event: str) -> NotificationConfig | None:
        """Get config or None if not registered."""
        return self._configs.get(model_type, {}).get(event)


# Singleton
notifications = NotificationRegistry()


# =============================================================================
# Activity Log Configuration
# =============================================================================

@dataclass
class ActivityConfig:
    """Configuration for auto-generating activity logs."""
    action: str
    title: Callable[[Any], str]
    description: Callable[[Any], str]
    icon: str = "fa-circle"
    color: str = "secondary"
    url: Callable[[Any], str] | None = None
    condition: Callable[[Any], bool] | None = None

    def should_trigger(self, record) -> bool:
        return self.condition(record) if self.condition else True


class ActivityRegistry:
    """Registry for activity log configurations."""

    def __init__(self):
        self._configs: dict[str, dict[str, ActivityConfig]] = {}

    def register(
        self,
        model_type: str,
        event: str,
        action: str,
        title: Callable[[Any], str],
        description: Callable[[Any], str],
        icon: str = "fa-circle",
        color: str = "secondary",
        url: Callable[[Any], str] | None = None,
        condition: Callable[[Any], bool] | None = None,
    ) -> None:
        """Register activity config for model+event."""
        if model_type not in self._configs:
            self._configs[model_type] = {}
        self._configs[model_type][event] = ActivityConfig(
            action=action, title=title, description=description,
            icon=icon, color=color, url=url, condition=condition,
        )

    def get(self, model_type: str, event: str) -> ActivityConfig | None:
        """Get config or None if not registered."""
        return self._configs.get(model_type, {}).get(event)


# Singleton
activities = ActivityRegistry()
