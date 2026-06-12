# -----------------------------------------------------------------------------
# sparQ - Activity Log Event Handler
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""Creates ActivityLog entries from model lifecycle events."""

from typing import Any

from system.module.hooks import hookimpl
from system.events import activities


class ActivityHandler:
    """Subscribes to record events and creates activity logs."""

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
        """Create activity log if configured for this model+event."""
        config = activities.get(model_type, event)
        if not config or not config.should_trigger(record):
            return

        from .models.activity_log import ActivityLog
        ActivityLog.log(
            action=config.action,
            model_type=model_type,
            record_id=record.id,
            title=config.title(record),
            description=config.description(record),
            icon=config.icon,
            color=config.color,
            url=config.url(record) if config.url else None,
        )


activity_handler = ActivityHandler()
