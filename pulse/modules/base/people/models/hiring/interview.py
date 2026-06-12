# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Interview model (merged into Team module).
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

from datetime import datetime
from enum import Enum

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.mixins import AuditMixin
from system.db.workspace import WorkspaceMixin
from system.db.raise_on_lazy import LAZY


class InterviewType(Enum):
    PHONE_SCREEN = "Phone Screen"
    VIDEO = "Video Call"
    ONSITE = "On-site"
    TECHNICAL = "Technical"
    PANEL = "Panel"


class InterviewStatus(Enum):
    SCHEDULED = "Scheduled"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"
    NO_SHOW = "No Show"


class InterviewRecommendation(Enum):
    STRONG_HIRE = "Strong Hire"
    HIRE = "Hire"
    MAYBE = "Maybe"
    NO_HIRE = "No Hire"
    STRONG_NO_HIRE = "Strong No Hire"


@ModelRegistry.register
class Interview(db.Model, WorkspaceMixin, AuditMixin):
    """Interview scheduled for an application"""

    __tablename__ = "interview"

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Link to application
    application_id = db.Column(
        db.Integer, db.ForeignKey("application.id"), nullable=False
    )

    # Interview details
    interview_type = db.Column(db.Enum(InterviewType), default=InterviewType.VIDEO)
    status = db.Column(db.Enum(InterviewStatus), default=InterviewStatus.SCHEDULED)

    # Scheduling
    scheduled_at = db.Column(db.DateTime, nullable=False)
    duration_minutes = db.Column(db.Integer, default=60)
    location = db.Column(db.String(500))  # Room name, video link, address

    # Interviewer
    interviewer_id = db.Column(db.Integer, db.ForeignKey("workspace_user.id"))

    # Feedback (filled after interview)
    feedback = db.Column(db.Text)
    recommendation = db.Column(db.Enum(InterviewRecommendation))
    completed_at = db.Column(db.DateTime)

    # Relationships
    application = db.relationship("Application", back_populates="interviews", lazy=LAZY)
    interviewer = db.relationship("WorkspaceUser", foreign_keys=[interviewer_id], lazy=LAZY)

    @property
    def is_upcoming(self):
        """Check if interview is upcoming"""
        return (
            self.status == InterviewStatus.SCHEDULED
            and self.scheduled_at > datetime.utcnow()
        )

    @property
    def is_past(self):
        """Check if interview is past"""
        return self.scheduled_at < datetime.utcnow()

    @property
    def end_time(self):
        """Calculate end time based on duration"""
        from datetime import timedelta

        return self.scheduled_at + timedelta(minutes=self.duration_minutes)

    @property
    def type_icon(self):
        """Return icon class for interview type"""
        icons = {
            InterviewType.PHONE_SCREEN: "fa-phone",
            InterviewType.VIDEO: "fa-video",
            InterviewType.ONSITE: "fa-building",
            InterviewType.TECHNICAL: "fa-laptop-code",
            InterviewType.PANEL: "fa-users",
        }
        return icons.get(self.interview_type, "fa-calendar")

    def complete(self, feedback=None, recommendation=None, user_id=None):
        """Mark interview as completed"""
        from .activity import ApplicationActivity, ActivityType

        self.status = InterviewStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        if feedback:
            self.feedback = feedback
        if recommendation:
            self.recommendation = recommendation

        # Log activity on the application
        activity = ApplicationActivity(
            application_id=self.application_id,
            activity_type=ActivityType.INTERVIEW_COMPLETED,
            description=f"{self.interview_type.value} completed"
            + (f" - {recommendation.value}" if recommendation else ""),
            created_by_id=user_id,
        )
        db.session.add(activity)
        db.session.commit()

    def cancel(self, user_id=None):
        """Cancel the interview"""
        self.status = InterviewStatus.CANCELLED
        db.session.commit()

    @classmethod
    def get_by_id(cls, interview_id):
        """Get interview by ID"""
        from sqlalchemy.orm import joinedload
        from modules.base.core.models.workspace_user import WorkspaceUser
        from modules.base.people.models.hiring.application import Application
        return cls.scoped().options(
            joinedload(cls.application).joinedload(Application.candidate),
            joinedload(cls.application).joinedload(Application.job_posting),
            joinedload(cls.interviewer).joinedload(WorkspaceUser.user),
        ).filter_by(id=interview_id).first()

    @classmethod
    def get_upcoming(cls, limit=10):
        """Get upcoming interviews"""
        from sqlalchemy.orm import joinedload
        from modules.base.core.models.workspace_user import WorkspaceUser
        from modules.base.people.models.hiring.application import Application
        return (
            cls.scoped().options(
                joinedload(cls.application).joinedload(Application.candidate),
                joinedload(cls.application).joinedload(Application.job_posting),
                joinedload(cls.interviewer).joinedload(WorkspaceUser.user),
            ).filter(
                cls.status == InterviewStatus.SCHEDULED,
                cls.scheduled_at > datetime.utcnow(),
            )
            .order_by(cls.scheduled_at.asc())
            .limit(limit)
            .all()
        )

    @classmethod
    def get_for_application(cls, application_id):
        """Get all interviews for an application"""
        return (
            cls.scoped().filter_by(application_id=application_id)
            .order_by(cls.scheduled_at.desc())
            .all()
        )

    def __repr__(self):
        return f"<Interview {self.id}: {self.interview_type.value} at {self.scheduled_at}>"
