# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Job model for job postings (merged into Team module).
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

"""Job posting model for recruitment and hiring.

This module provides models for creating and managing job postings,
tracking application status, and managing the hiring pipeline.

Classes:
    JobStatus: Enum for job posting workflow states.
    JobType: Enum for employment type classification.
    JobPosting: Main job posting model.

Example:
    Creating a job posting::

        job = JobPosting(
            title="Software Engineer",
            department="Engineering",
            location="Remote",
            job_type=JobType.FULL_TIME,
            description="Join our team..."
        )
        db.session.add(job)
        db.session.commit()
        job.publish()

    Getting open positions::

        open_jobs = JobPosting.get_open_jobs()
"""

from datetime import datetime
from enum import Enum

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.mixins import AuditMixin
from system.db.workspace import WorkspaceMixin
from system.db.raise_on_lazy import LAZY


class JobStatus(Enum):
    """Job posting workflow status states.

    Attributes:
        DRAFT: Job is being drafted, not yet published.
        OPEN: Job is published and accepting applications.
        ON_HOLD: Hiring temporarily paused.
        CLOSED: Job is no longer accepting applications.
    """

    DRAFT = "Draft"
    OPEN = "Open"
    ON_HOLD = "On Hold"
    CLOSED = "Closed"


class JobType(Enum):
    """Employment type classification.

    Attributes:
        FULL_TIME: Full-time permanent position.
        PART_TIME: Part-time position.
        CONTRACT: Fixed-term contract position.
        INTERNSHIP: Internship or trainee position.
    """

    FULL_TIME = "Full-time"
    PART_TIME = "Part-time"
    CONTRACT = "Contract"
    INTERNSHIP = "Internship"


@ModelRegistry.register
class JobPosting(db.Model, WorkspaceMixin, AuditMixin):
    """Job posting for hiring.

    Attributes:
        id: Primary key.
        title: Job title.
        department: Department or team name.
        location: Work location (Remote, office, etc.).
        job_type: JobType enum value.
        salary_min: Minimum salary (optional).
        salary_max: Maximum salary (optional).
        description: Full job description.
        requirements: Required qualifications.
        status: JobStatus workflow state.
        published_at: Timestamp when job was published.
        closed_at: Timestamp when job was closed.
        hiring_manager_id: FK to Employee who owns this posting.

    Relationships:
        hiring_manager: The Employee managing this position.
        applications: Collection of Application records.

    Properties:
        candidate_count: Number of candidates who have applied.
        is_open: Whether job is accepting applications.
        salary_range: Formatted salary range string.
    """

    __tablename__ = "job_posting"

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    title = db.Column(db.String(200), nullable=False)
    department = db.Column(db.String(100))
    location = db.Column(db.String(200))  # "Remote", "NYC Office", etc.
    job_type = db.Column(db.Enum(JobType), default=JobType.FULL_TIME)

    # Compensation (optional)
    salary_min = db.Column(db.Numeric(10, 2))
    salary_max = db.Column(db.Numeric(10, 2))

    # Description
    description = db.Column(db.Text)
    requirements = db.Column(db.Text)

    # Status & workflow
    status = db.Column(db.Enum(JobStatus), default=JobStatus.DRAFT)
    published_at = db.Column(db.DateTime)
    closed_at = db.Column(db.DateTime)

    # Hiring manager
    hiring_manager_id = db.Column(db.Integer, db.ForeignKey("workspace_user.id"))

    # Relationships
    hiring_manager = db.relationship("WorkspaceUser", foreign_keys=[hiring_manager_id], lazy=LAZY)
    applications = db.relationship(
        "Application", back_populates="job_posting", cascade="all, delete-orphan", lazy=LAZY,
    )

    @property
    def candidate_count(self):
        """Return number of candidates for this job"""
        return len(self.applications)

    @property
    def is_open(self):
        """Check if job is open for applications"""
        return self.status == JobStatus.OPEN

    @property
    def salary_range(self):
        """Return formatted salary range"""
        if self.salary_min and self.salary_max:
            return f"${self.salary_min:,.0f} - ${self.salary_max:,.0f}"
        elif self.salary_min:
            return f"${self.salary_min:,.0f}+"
        elif self.salary_max:
            return f"Up to ${self.salary_max:,.0f}"
        return None

    def publish(self):
        """Publish the job"""
        self.status = JobStatus.OPEN
        self.published_at = datetime.utcnow()
        db.session.commit()

    def close(self):
        """Close the job"""
        self.status = JobStatus.CLOSED
        self.closed_at = datetime.utcnow()
        db.session.commit()

    def hold(self):
        """Put job on hold"""
        self.status = JobStatus.ON_HOLD
        db.session.commit()

    @classmethod
    def get_by_id(cls, job_id):
        """Get job by ID"""
        from sqlalchemy.orm import joinedload, selectinload
        from modules.base.core.models.workspace_user import WorkspaceUser
        from modules.base.people.models.hiring.application import Application
        return cls.scoped().options(
            joinedload(cls.hiring_manager).joinedload(WorkspaceUser.user),
            selectinload(cls.applications).joinedload(Application.candidate),
        ).filter_by(id=job_id).first()

    @classmethod
    def get_open_jobs(cls):
        """Get all open jobs"""
        return cls.scoped().filter_by(status=JobStatus.OPEN).order_by(
            cls.published_at.desc()
        ).all()

    @classmethod
    def get_all(cls):
        """Get all jobs ordered by created date"""
        return cls.scoped().order_by(cls.created_at.desc()).all()

    def __repr__(self):
        return f"<JobPosting {self.id}: {self.title}>"
