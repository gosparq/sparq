# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Application model linking candidates to jobs (merged into Team module).
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

from datetime import datetime
from enum import Enum

from sqlalchemy.orm import joinedload, selectinload

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.mixins import AuditMixin
from system.db.workspace import WorkspaceMixin
from system.db.raise_on_lazy import LAZY


class ApplicationStatus(Enum):
    NEW = "New"
    SCREENING = "Screening"
    INTERVIEWING = "Interviewing"
    OFFER = "Offer"
    HIRED = "Hired"
    REJECTED = "Rejected"
    WITHDRAWN = "Withdrawn"


# Pipeline order for display
APPLICATION_STATUS_ORDER = [
    ApplicationStatus.NEW,
    ApplicationStatus.SCREENING,
    ApplicationStatus.INTERVIEWING,
    ApplicationStatus.OFFER,
    ApplicationStatus.HIRED,
    ApplicationStatus.REJECTED,
    ApplicationStatus.WITHDRAWN,
]


@ModelRegistry.register
class Application(db.Model, WorkspaceMixin, AuditMixin):
    """Application linking a candidate to a job"""

    __tablename__ = "application"

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Links
    job_posting_id = db.Column(db.Integer, db.ForeignKey("job_posting.id"), nullable=False)
    candidate_id = db.Column(db.Integer, db.ForeignKey("candidate.id"), nullable=False)

    # Status
    status = db.Column(db.Enum(ApplicationStatus), default=ApplicationStatus.NEW)

    # Application details
    applied_at = db.Column(db.DateTime, default=datetime.utcnow)
    cover_letter = db.Column(db.Text)

    # Tracking
    rejection_reason = db.Column(db.String(200))
    hired_at = db.Column(db.DateTime)

    # Rating (1-5 stars, optional)
    rating = db.Column(db.Integer)

    # Link to onboarding if hired
    onboarding_record_id = db.Column(
        db.Integer, db.ForeignKey("onboarding_record.id")
    )

    # Relationships
    job_posting = db.relationship("JobPosting", back_populates="applications", lazy=LAZY)
    candidate = db.relationship("Candidate", back_populates="applications", lazy=LAZY)
    interviews = db.relationship(
        "Interview", back_populates="application", cascade="all, delete-orphan", lazy=LAZY,
    )
    activities = db.relationship(
        "ApplicationActivity",
        back_populates="application",
        cascade="all, delete-orphan",
        order_by="desc(ApplicationActivity.created_at)",
        lazy=LAZY,
    )
    onboarding_record = db.relationship("OnboardingRecord", lazy=LAZY)

    __table_args__ = (
        db.UniqueConstraint("job_posting_id", "candidate_id", name="unique_application"),
    )

    @property
    def is_active(self):
        """Check if application is still active (not rejected/withdrawn/hired)"""
        return self.status not in [
            ApplicationStatus.REJECTED,
            ApplicationStatus.WITHDRAWN,
            ApplicationStatus.HIRED,
        ]

    @property
    def rating_display(self):
        """Return star rating display"""
        if not self.rating:
            return None
        return "★" * self.rating + "☆" * (5 - self.rating)

    def change_status(self, new_status, user_id=None, reason=None):
        """Change application status and log activity"""
        from .activity import ApplicationActivity, ActivityType

        old_status = self.status
        self.status = new_status

        if new_status == ApplicationStatus.REJECTED and reason:
            self.rejection_reason = reason
        elif new_status == ApplicationStatus.HIRED:
            self.hired_at = datetime.utcnow()

        # Log activity
        activity = ApplicationActivity(
            application_id=self.id,
            activity_type=ActivityType.STATUS_CHANGE,
            description=f"Status changed from {old_status.value} to {new_status.value}",
            old_value=old_status.value,
            new_value=new_status.value,
            created_by_id=user_id,
        )
        db.session.add(activity)
        db.session.commit()

    def set_rating(self, rating, user_id=None):
        """Set rating and log activity"""
        from .activity import ApplicationActivity, ActivityType

        old_rating = self.rating
        self.rating = rating

        # Log activity
        activity = ApplicationActivity(
            application_id=self.id,
            activity_type=ActivityType.RATING_CHANGED,
            description=f"Rating set to {rating} stars",
            old_value=str(old_rating) if old_rating else None,
            new_value=str(rating),
            created_by_id=user_id,
        )
        db.session.add(activity)
        db.session.commit()

    def add_note(self, note, user_id=None):
        """Add a note activity"""
        from .activity import ApplicationActivity, ActivityType

        activity = ApplicationActivity(
            application_id=self.id,
            activity_type=ActivityType.NOTE_ADDED,
            description=note,
            created_by_id=user_id,
        )
        db.session.add(activity)
        db.session.commit()

    @classmethod
    def get_by_id(cls, application_id):
        """Get application by ID"""
        return cls.scoped().options(
            joinedload(cls.candidate),
            joinedload(cls.job_posting),
            selectinload(cls.activities),
        ).filter_by(id=application_id).first()

    @classmethod
    def get_for_job(cls, job_posting_id):
        """Get all applications for a job"""
        return cls.scoped().options(
            joinedload(cls.candidate),
        ).filter_by(job_posting_id=job_posting_id).order_by(cls.applied_at.desc()).all()

    @classmethod
    def get_for_candidate(cls, candidate_id):
        """Get all applications for a candidate"""
        return cls.scoped().options(
            joinedload(cls.job_posting),
        ).filter_by(candidate_id=candidate_id).order_by(
            cls.applied_at.desc()
        ).all()

    @classmethod
    def get_pipeline_for_job(cls, job_posting_id):
        """Get applications grouped by status for pipeline view"""
        applications = cls.get_for_job(job_posting_id)
        pipeline = {status: [] for status in APPLICATION_STATUS_ORDER}
        for app in applications:
            pipeline[app.status].append(app)
        return pipeline

    def __repr__(self):
        return f"<Application {self.id}: {self.candidate.full_name} -> {self.job_posting.title}>"
