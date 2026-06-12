# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

"""TaskLog model — audit trail for Task lifecycle events.

Classes:
    TaskLog: Immutable log entry for action item events.
"""

from datetime import datetime

from sqlalchemy.orm import joinedload

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.raise_on_lazy import LAZY


@ModelRegistry.register
class TaskLog(db.Model):
    """Immutable audit log entry for an Task event.

    Attributes:
        task_id: FK to the task record.
        event_type: Type of event (created, nudge_sent, snoozed, resolved, etc.).
        actor_id: FK to workspace_user who performed the action (null = system).
        detail: Optional short description of the event.
        created_at: When the event occurred.
    """

    __tablename__ = "task_log"
    __table_args__ = (
        db.Index("ix_task_log_item", "task_id", "created_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(
        db.Integer, db.ForeignKey("task.id", ondelete="CASCADE"), nullable=False
    )
    event_type = db.Column(db.String(30), nullable=False)
    actor_id = db.Column(
        db.Integer, db.ForeignKey("workspace_user.id"), nullable=True
    )
    detail = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    task = db.relationship("Task", backref=db.backref("logs", lazy="dynamic"), lazy=LAZY)
    actor = db.relationship("WorkspaceUser", foreign_keys=[actor_id], lazy=LAZY)

    @classmethod
    def log(cls, task_id, event_type, actor_id=None, detail=None):
        """Record an event in the Task audit log.

        Args:
            task_id: Task.id this event relates to.
            event_type: One of: created, nudge_sent, snoozed, resolved,
                        dismissed, reopened, canceled, auto_resolved, escalation_sent.
            actor_id: WorkspaceUser.id who performed the action (None for system).
            detail: Optional short description.

        Returns:
            Created TaskLog instance.
        """
        entry = cls(
            task_id=task_id,
            event_type=event_type,
            actor_id=actor_id,
            detail=detail[:500] if detail else None,
        )
        db.session.add(entry)
        db.session.commit()
        return entry

    @classmethod
    def get_for_item(cls, task_id):
        """Get all log entries for an Task, newest first.

        Args:
            task_id: Task.id to look up.

        Returns:
            List of TaskLog instances.
        """
        from modules.base.core.models.workspace_user import WorkspaceUser
        return (
            cls.query
            .options(joinedload(cls.actor).joinedload(WorkspaceUser.user))
            .filter_by(task_id=task_id)
            .order_by(cls.created_at.desc())
            .all()
        )
