# -----------------------------------------------------------------------------
# sparQ - Activity Log Model
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""Activity log for dashboard stream and team energy tracking.

No circular buffer — activity history is kept for rolling averages
(Team Energy widget uses 14-day baseline).
"""

from datetime import datetime

from flask import g

from system.api.serialization import SerializableMixin
from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.workspace import WorkspaceMixin
from system.db.raise_on_lazy import LAZY


@ModelRegistry.register
class ActivityLog(db.Model, WorkspaceMixin, SerializableMixin):
    """Activity log entry for the dashboard stream."""

    __tablename__ = "activity_log"
    __table_args__ = (
        db.Index("ix_activity_log_org_ws_date", "organization_id", "workspace_id", "created_at"),
    )

    id = db.Column(db.Integer, primary_key=True)

    # Who triggered the activity (member_id → workspace_user.id)
    member_id = db.Column(
        db.Integer, db.ForeignKey("workspace_user.id", ondelete="SET NULL"), nullable=True
    )

    # Activity details
    action = db.Column(db.String(50), nullable=False)
    model_type = db.Column(db.String(50), nullable=False)
    record_id = db.Column(db.Integer, nullable=True)

    # Display fields
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    icon = db.Column(db.String(50), default="fa-circle")
    color = db.Column(db.String(20), default="secondary")
    url = db.Column(db.String(255), nullable=True)

    # Timestamp
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    member = db.relationship("WorkspaceUser", backref=db.backref("activities", lazy="dynamic"), lazy=LAZY)

    # --- Class Methods ---

    @classmethod
    def log(
        cls,
        action: str,
        model_type: str,
        title: str,
        description: str,
        record_id: int | None = None,
        member_id: int | None = None,
        user_id: int | None = None,
        icon: str = "fa-circle",
        color: str = "secondary",
        url: str | None = None,
    ) -> "ActivityLog":
        """Log an activity.

        Args:
            action: Action type (e.g., 'connect.message_posted').
            model_type: Model name (e.g., 'ConnectMessage').
            title: Display title.
            description: Display description.
            record_id: Related record ID.
            member_id: WorkspaceUser.id who triggered the action.
            user_id: Deprecated — ignored. Use member_id.
            icon: FontAwesome icon class.
            color: Bootstrap color name.
            url: Link to related record.
        """
        activity = cls(
            action=action,
            model_type=model_type,
            record_id=record_id,
            member_id=member_id,
            title=title,
            description=description,
            icon=icon,
            color=color,
            url=url,
        )
        db.session.add(activity)
        db.session.commit()
        return activity

    @classmethod
    def get_recent(cls, limit: int = 10) -> list["ActivityLog"]:
        """Get most recent activities for dashboard feed.

        Joins to Task to exclude system-raised entries (raised_by_id IS NULL).
        Non-action-item activities pass through unfiltered.
        """
        from modules.base.tasks.models.task import Task

        return (
            cls.scoped()
            .outerjoin(
                Task,
                db.and_(cls.model_type == "Task", cls.record_id == Task.id),
            )
            .filter(
                db.or_(
                    cls.model_type != "Task",
                    Task.raised_by_id.isnot(None),
                )
            )
            .order_by(cls.created_at.desc())
            .limit(limit)
            .all()
        )

    @classmethod
    def get_today_count(cls) -> int:
        """Get activity count for today (for Team Energy widget)."""
        from datetime import date

        return cls.scoped().filter(
            db.func.date(cls.created_at) == date.today()
        ).count()

    @classmethod
    def get_14day_average(cls) -> float:
        """Get average daily activity count over past 14 days."""
        from datetime import date, timedelta

        start = date.today() - timedelta(days=14)
        rows = (
            db.session.query(
                db.func.date(cls.created_at).label("day"),
                db.func.count(cls.id).label("cnt"),
            )
            .filter(
                cls.workspace_id == g.workspace_id,
                db.func.date(cls.created_at) >= start,
                db.func.date(cls.created_at) < date.today(),
            )
            .group_by(db.func.date(cls.created_at))
            .all()
        )
        if not rows:
            return 0.0
        return sum(r.cnt for r in rows) / len(rows)

    # --- Properties ---

    @property
    def time_ago(self) -> str:
        """Human-readable time ago string."""
        delta = datetime.utcnow() - self.created_at

        if delta.days > 0:
            return f"{delta.days}d ago"
        elif delta.seconds >= 3600:
            return f"{delta.seconds // 3600}h ago"
        elif delta.seconds >= 60:
            return f"{delta.seconds // 60}m ago"
        else:
            return "just now"
