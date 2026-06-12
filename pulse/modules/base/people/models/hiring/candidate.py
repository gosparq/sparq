# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Candidate model (merged into Team module).
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


class CandidateSource(Enum):
    WEBSITE = "Website"
    LINKEDIN = "LinkedIn"
    INDEED = "Indeed"
    REFERRAL = "Referral"
    AGENCY = "Agency"
    OTHER = "Other"


@ModelRegistry.register
class Candidate(db.Model, WorkspaceMixin, AuditMixin):
    """Candidate in the hiring pipeline"""

    __tablename__ = "candidate"
    __table_args__ = (
        db.UniqueConstraint("email", "workspace_id", name="uq_candidate_email_workspace"),
    )

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Basic info
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(50))

    # Location
    city = db.Column(db.String(100))
    state = db.Column(db.String(100))
    country = db.Column(db.String(100))

    # Professional
    current_company = db.Column(db.String(200))
    current_title = db.Column(db.String(200))
    linkedin_url = db.Column(db.String(500))

    # Resume - uses existing Attachment model from Resources
    resume_id = db.Column(db.Integer, db.ForeignKey("attachment.id"))

    # Source tracking
    source = db.Column(db.Enum(CandidateSource), default=CandidateSource.OTHER)
    source_detail = db.Column(db.String(200))  # e.g., referrer name

    # Tags for filtering (comma-separated)
    tags = db.Column(db.String(500))

    # Notes
    notes = db.Column(db.Text)

    # Relationships
    resume = db.relationship("Attachment", foreign_keys=[resume_id], lazy=LAZY)
    applications = db.relationship(
        "Application", back_populates="candidate", cascade="all, delete-orphan", lazy=LAZY,
    )

    @property
    def full_name(self):
        """Return full name"""
        return f"{self.first_name} {self.last_name}"

    @property
    def location_display(self):
        """Return formatted location"""
        parts = [p for p in [self.city, self.state, self.country] if p]
        return ", ".join(parts) if parts else None

    @property
    def tag_list(self):
        """Return tags as a list"""
        if not self.tags:
            return []
        return [t.strip() for t in self.tags.split(",") if t.strip()]

    def add_tag(self, tag):
        """Add a tag"""
        current_tags = self.tag_list
        if tag not in current_tags:
            current_tags.append(tag)
            self.tags = ", ".join(current_tags)
            db.session.commit()

    def remove_tag(self, tag):
        """Remove a tag"""
        current_tags = self.tag_list
        if tag in current_tags:
            current_tags.remove(tag)
            self.tags = ", ".join(current_tags) if current_tags else None
            db.session.commit()

    @classmethod
    def get_by_id(cls, candidate_id):
        """Get candidate by ID"""
        from sqlalchemy.orm import joinedload, selectinload

        from modules.base.people.models.hiring.application import Application

        return cls.scoped().options(
            selectinload(cls.applications).joinedload(Application.job_posting),
            joinedload(cls.resume),
        ).filter_by(id=candidate_id).first()

    @classmethod
    def get_by_email(cls, email):
        """Get candidate by email"""
        return cls.scoped().filter_by(email=email).first()

    @classmethod
    def get_all(cls):
        """Get all candidates ordered by created date"""
        return cls.scoped().order_by(cls.created_at.desc()).all()

    @classmethod
    def search(cls, query):
        """Search candidates by name or email"""
        search_term = f"%{query}%"
        return cls.scoped().filter(
            db.or_(
                cls.first_name.ilike(search_term),
                cls.last_name.ilike(search_term),
                cls.email.ilike(search_term),
            )
        ).order_by(cls.created_at.desc()).all()

    def __repr__(self):
        return f"<Candidate {self.id}: {self.full_name}>"
