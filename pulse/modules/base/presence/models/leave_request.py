# -----------------------------------------------------------------------------
# sparQ - LeaveRequest Model
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from sqlalchemy.orm import joinedload

from system.api.serialization import SerializableMixin
from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.mixins import AuditMixin
from system.db.workspace import OrganizationMixin
from system.db.raise_on_lazy import LAZY


class LeaveType(Enum):
    """Types of leave requests"""

    VACATION = "Vacation"
    SICK = "Sick Leave"
    PERSONAL = "Personal"
    BEREAVEMENT = "Bereavement"
    JURY_DUTY = "Jury Duty"
    OTHER = "Other"


class LeaveRequestStatus(Enum):
    """Status of leave request"""

    DRAFT = "Draft"
    PENDING = "Pending"
    APPROVED = "Approved"
    DENIED = "Denied"
    CANCELLED = "Cancelled"


@ModelRegistry.register
class LeaveRequest(db.Model, OrganizationMixin, AuditMixin, SerializableMixin):
    """Leave request model for tracking member time off"""

    __tablename__ = "leave_request"

    id = db.Column(db.Integer, primary_key=True)

    # --- Core fields ---
    member_id = db.Column(
        db.Integer, db.ForeignKey("organization_user.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Request details
    leave_type = db.Column(db.Enum(LeaveType), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    employee_notes = db.Column(db.Text)  # "Why I need this time off"

    # --- Workflow ---
    status = db.Column(db.Enum(LeaveRequestStatus), default=LeaveRequestStatus.DRAFT, nullable=False)
    submitted_at = db.Column(db.DateTime, nullable=True)

    # --- Admin response ---
    admin_notes = db.Column(db.Text)  # Feedback to member
    reviewed_by_id = db.Column(
        db.Integer, db.ForeignKey("organization_user.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at = db.Column(db.DateTime, nullable=True)

    # --- Timestamps ---
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # --- Relationships ---
    member = db.relationship("OrganizationUser", backref=db.backref("leave_requests", lazy=LAZY), foreign_keys=[member_id], lazy=LAZY)
    reviewed_by = db.relationship("OrganizationUser", foreign_keys=[reviewed_by_id], lazy=LAZY)

    # --- Indexes ---
    __table_args__ = (
        db.Index("ix_leave_request_member_dates", "member_id", "start_date", "end_date"),
        db.Index("ix_leave_request_status", "status"),
    )

    # --- Properties ---
    @property
    def total_days(self):
        """Calculate total days of leave"""
        return (self.end_date - self.start_date).days + 1

    @property
    def is_editable_by_member(self):
        """Check if member can still edit this request"""
        return self.status in [LeaveRequestStatus.DRAFT, LeaveRequestStatus.PENDING]

    @property
    def can_cancel(self):
        """Check if request can be cancelled"""
        return self.status in [LeaveRequestStatus.DRAFT, LeaveRequestStatus.PENDING]

    @property
    def status_badge_class(self):
        """Return Bootstrap badge class based on status"""
        return {
            LeaveRequestStatus.DRAFT: "bg-secondary",
            LeaveRequestStatus.PENDING: "bg-warning text-dark",
            LeaveRequestStatus.APPROVED: "bg-success",
            LeaveRequestStatus.DENIED: "bg-danger",
            LeaveRequestStatus.CANCELLED: "bg-secondary",
        }.get(self.status, "bg-secondary")

    # --- Class Methods (CRUD) ---
    @classmethod
    def create(cls, member_id, leave_type, start_date, end_date, employee_notes=None):
        """Create a new leave request"""
        request = cls(
            member_id=member_id,
            leave_type=leave_type,
            start_date=start_date,
            end_date=end_date,
            employee_notes=employee_notes,
            status=LeaveRequestStatus.DRAFT,
        )
        db.session.add(request)
        db.session.commit()
        return request

    @classmethod
    def get_by_member(cls, member_id, status=None):
        """Get leave requests for a member, optionally filtered by status"""
        from modules.base.core.models.organization_user import OrganizationUser
        query = cls.scoped().options(
            joinedload(cls.member).joinedload(OrganizationUser.user),
            joinedload(cls.reviewed_by).joinedload(OrganizationUser.user),
        ).filter_by(member_id=member_id)
        if status:
            query = query.filter_by(status=status)
        return query.order_by(cls.start_date.desc()).all()

    @classmethod
    def get_pending_approval(cls):
        """Get all leave requests awaiting approval"""
        from modules.base.core.models.organization_user import OrganizationUser
        return (
            cls.scoped()
            .options(joinedload(cls.member).joinedload(OrganizationUser.user))
            .filter_by(status=LeaveRequestStatus.PENDING)
            .order_by(cls.submitted_at.desc())
            .all()
        )

    @classmethod
    def pending_count(cls) -> int:
        """Count leave requests awaiting approval."""
        return cls.scoped().filter_by(status=LeaveRequestStatus.PENDING).count()

    @classmethod
    def get_approved_in_range(cls, start_date, end_date):
        """Get approved leave requests that overlap with a date range"""
        from modules.base.core.models.organization_user import OrganizationUser
        return (
            cls.scoped()
            .options(joinedload(cls.member).joinedload(OrganizationUser.user))
            .filter(
                cls.status == LeaveRequestStatus.APPROVED,
                cls.start_date <= end_date,
                cls.end_date >= start_date,
            )
            .all()
        )

    @classmethod
    def find_overlapping(
        cls,
        member_id: int,
        start_date: date,
        end_date: date,
        statuses: list[LeaveRequestStatus] | None = None,
        exclude_id: int | None = None,
    ) -> list[LeaveRequest]:
        """Find leave requests for a member that overlap a date range.

        Args:
            member_id: The member to check.
            start_date: Range start (inclusive).
            end_date: Range end (inclusive).
            statuses: Statuses to match (defaults to PENDING + APPROVED).
            exclude_id: Request ID to exclude (for edit scenarios).

        Returns:
            List of overlapping LeaveRequest objects.
        """
        if statuses is None:
            statuses = [LeaveRequestStatus.PENDING, LeaveRequestStatus.APPROVED]

        query = cls.scoped().filter(
            cls.member_id == member_id,
            cls.status.in_(statuses),
            cls.start_date <= end_date,
            cls.end_date >= start_date,
        )
        if exclude_id is not None:
            query = query.filter(cls.id != exclude_id)
        return query.all()

    @classmethod
    def get_upcoming_approved(cls) -> list[LeaveRequest]:
        """Get approved leave requests where end_date >= today."""
        from modules.base.core.models.organization_user import OrganizationUser
        return (
            cls.scoped()
            .options(
                joinedload(cls.member).joinedload(OrganizationUser.user),
                joinedload(cls.reviewed_by).joinedload(OrganizationUser.user),
            )
            .filter(
                cls.status == LeaveRequestStatus.APPROVED,
                cls.end_date >= date.today(),
            )
            .order_by(cls.start_date.asc())
            .all()
        )

    @classmethod
    def get_upcoming_approved_count(cls) -> int:
        """Count approved leave requests where end_date >= today."""
        return cls.scoped().filter(
            cls.status == LeaveRequestStatus.APPROVED,
            cls.end_date >= date.today(),
        ).count()

    @classmethod
    def get_past_approved(cls, limit: int = 5, offset: int = 0) -> tuple[list[LeaveRequest], bool]:
        """Get past approved leave requests with pagination.

        Returns (requests, has_more) tuple.
        """
        from modules.base.core.models.organization_user import OrganizationUser
        query = (
            cls.scoped()
            .options(
                joinedload(cls.member).joinedload(OrganizationUser.user),
                joinedload(cls.reviewed_by).joinedload(OrganizationUser.user),
            )
            .filter(
                cls.status == LeaveRequestStatus.APPROVED,
                cls.end_date < date.today(),
            )
            .order_by(cls.start_date.desc())
        )
        total = query.count()
        requests = query.offset(offset).limit(limit).all()
        has_more = offset + limit < total
        return requests, has_more

    # --- Instance Methods ---
    def submit(self):
        """Submit leave request for approval"""
        if self.status != LeaveRequestStatus.DRAFT:
            raise ValueError("Only draft requests can be submitted")

        self.status = LeaveRequestStatus.PENDING
        self.submitted_at = datetime.utcnow()
        db.session.commit()

        from system.events import emit
        emit.custom("LeaveRequest", "submitted", self)

    def approve(self, user_id, notes=None):
        """Approve leave request"""
        if self.status != LeaveRequestStatus.PENDING:
            raise ValueError("Only pending requests can be approved")

        self.status = LeaveRequestStatus.APPROVED
        self.reviewed_by_id = user_id
        self.reviewed_at = datetime.utcnow()
        if notes:
            self.admin_notes = notes
        db.session.commit()

    def deny(self, user_id, notes):
        """Deny leave request with reason"""
        if self.status != LeaveRequestStatus.PENDING:
            raise ValueError("Only pending requests can be denied")

        self.status = LeaveRequestStatus.DENIED
        self.reviewed_by_id = user_id
        self.reviewed_at = datetime.utcnow()
        self.admin_notes = notes
        db.session.commit()

    def request_changes(self, user_id, notes):
        """Send feedback to member without changing status"""
        if self.status != LeaveRequestStatus.PENDING:
            raise ValueError("Only pending requests can have changes requested")

        self.reviewed_by_id = user_id
        self.reviewed_at = datetime.utcnow()
        self.admin_notes = notes
        db.session.commit()

    def cancel(self):
        """Cancel leave request"""
        if not self.can_cancel:
            raise ValueError("This request cannot be cancelled")

        self.status = LeaveRequestStatus.CANCELLED
        db.session.commit()

    def unapprove(self, user_id):
        """Revert approved request back to pending"""
        if self.status != LeaveRequestStatus.APPROVED:
            raise ValueError("Only approved requests can be unapproved")
        if self.end_date < date.today():
            raise ValueError("Cannot unapprove leave that has already passed")

        self.status = LeaveRequestStatus.PENDING
        self.reviewed_by_id = user_id
        self.reviewed_at = datetime.utcnow()
        self.admin_notes = (self.admin_notes or "") + "\n[Reverted to pending]"
        db.session.commit()

    def update(self, leave_type=None, start_date=None, end_date=None, employee_notes=None):
        """Update leave request details (only if editable)"""
        if not self.is_editable_by_member:
            raise ValueError("This request cannot be edited")

        if leave_type:
            self.leave_type = leave_type
        if start_date:
            self.start_date = start_date
        if end_date:
            self.end_date = end_date
        if employee_notes is not None:
            self.employee_notes = employee_notes

        db.session.commit()

    def admin_update(
        self,
        leave_type: LeaveType | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        employee_notes: str | None = None,
        status: LeaveRequestStatus | None = None,
    ) -> None:
        """Admin update — bypasses member-editability checks.

        Args:
            leave_type: New leave type.
            start_date: New start date.
            end_date: New end date.
            employee_notes: Updated employee notes.
            status: New status (admin can set any status).
        """
        if leave_type is not None:
            self.leave_type = leave_type
        if start_date is not None:
            self.start_date = start_date
        if end_date is not None:
            self.end_date = end_date
        if employee_notes is not None:
            self.employee_notes = employee_notes
        if status is not None:
            self.status = status

        db.session.commit()
