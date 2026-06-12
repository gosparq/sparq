# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     ApplicationActivity model for tracking activity timeline (merged into Team module).
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

from datetime import datetime
from enum import Enum

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.workspace import WorkspaceMixin
from system.db.raise_on_lazy import LAZY


class ActivityType(Enum):
    STATUS_CHANGE = "Status Change"
    NOTE_ADDED = "Note Added"
    INTERVIEW_SCHEDULED = "Interview Scheduled"
    INTERVIEW_COMPLETED = "Interview Completed"
    EMAIL_SENT = "Email Sent"
    RESUME_VIEWED = "Resume Viewed"
    RATING_CHANGED = "Rating Changed"
    CREATED = "Created"


@ModelRegistry.register
class ApplicationActivity(db.Model, WorkspaceMixin):
    """Activity log for application timeline"""

    __tablename__ = "application_activity"

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(
        db.Integer, db.ForeignKey("application.id"), nullable=False
    )

    activity_type = db.Column(db.Enum(ActivityType), nullable=False)
    description = db.Column(db.String(500))
    old_value = db.Column(db.String(200))
    new_value = db.Column(db.String(200))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))

    # Relationships
    application = db.relationship("Application", back_populates="activities", lazy=LAZY)
    created_by = db.relationship("User", lazy=LAZY)

    @property
    def type_icon(self):
        """Return icon class for activity type"""
        icons = {
            ActivityType.STATUS_CHANGE: "fa-exchange-alt",
            ActivityType.NOTE_ADDED: "fa-sticky-note",
            ActivityType.INTERVIEW_SCHEDULED: "fa-calendar-plus",
            ActivityType.INTERVIEW_COMPLETED: "fa-calendar-check",
            ActivityType.EMAIL_SENT: "fa-envelope",
            ActivityType.RESUME_VIEWED: "fa-file-alt",
            ActivityType.RATING_CHANGED: "fa-star",
            ActivityType.CREATED: "fa-plus-circle",
        }
        return icons.get(self.activity_type, "fa-circle")

    @property
    def type_color(self):
        """Return color class for activity type"""
        colors = {
            ActivityType.STATUS_CHANGE: "text-primary",
            ActivityType.NOTE_ADDED: "text-warning",
            ActivityType.INTERVIEW_SCHEDULED: "text-info",
            ActivityType.INTERVIEW_COMPLETED: "text-success",
            ActivityType.EMAIL_SENT: "text-secondary",
            ActivityType.RESUME_VIEWED: "text-muted",
            ActivityType.RATING_CHANGED: "text-warning",
            ActivityType.CREATED: "text-success",
        }
        return colors.get(self.activity_type, "text-muted")

    @classmethod
    def log(cls, application_id, activity_type, description, user_id=None, **kwargs):
        """Create an activity log entry"""
        activity = cls(
            application_id=application_id,
            activity_type=activity_type,
            description=description,
            created_by_id=user_id,
            **kwargs,
        )
        db.session.add(activity)
        db.session.commit()
        return activity

    @classmethod
    def get_for_application(cls, application_id, limit=50):
        """Get activities for an application"""
        return (
            cls.scoped().filter_by(application_id=application_id)
            .order_by(cls.created_at.desc())
            .limit(limit)
            .all()
        )

    @classmethod
    def get_recent(cls, limit=20):
        """Get recent activities across all applications"""
        return cls.scoped().order_by(cls.created_at.desc()).limit(limit).all()

    def __repr__(self):
        return f"<ApplicationActivity {self.id}: {self.activity_type.value}>"
