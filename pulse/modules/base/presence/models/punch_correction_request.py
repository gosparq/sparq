# -----------------------------------------------------------------------------
# sparQ - Punch Correction Request Model
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""Punch correction request model for member-initiated time corrections.

Allows members to request corrections to their clock punch times, which
go through an admin approval workflow. On approval, the existing
ClockPunch.update_time() flow applies the correction and records the audit trail.

Classes:
    PunchCorrectionRequestStatus: Enum for request workflow states.
    PunchCorrectionRequest: Model for punch time correction requests.

Example:
    Creating a correction request::

        from modules.base.presence.models.punch_correction_request import PunchCorrectionRequest

        req = PunchCorrectionRequest.create(
            clock_punch_id=punch.id,
            member_id=member.id,
            requested_time=new_time_utc,
            reason="Forgot to clock in on time"
        )

    Approving a request::

        req.approve(user_id=admin_user.id, notes="Looks good")
"""

from datetime import datetime
from enum import Enum
from typing import Any

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.mixins import AuditMixin
from system.db.raise_on_lazy import LAZY
from system.db.workspace import OrganizationMixin


class PunchCorrectionRequestStatus(Enum):
    """Status of a punch correction request."""

    PENDING = "Pending"
    APPROVED = "Approved"
    DENIED = "Denied"


@ModelRegistry.register
class PunchCorrectionRequest(db.Model, OrganizationMixin, AuditMixin):
    """Member request to correct a clock punch time.

    Members submit requests from the Time Clock page. Pending requests
    are displayed optimistically (showing requested time with a badge).
    Admins review via the Approve page, approving or denying.

    Attributes:
        clock_punch_id: FK to the punch being corrected.
        member_id: FK to the requesting member.
        original_time: Snapshot of punch_time at request creation (UTC).
        requested_time: The new time the member wants (UTC).
        reason: Member's reason for the correction.
        status: Workflow state (Pending, Approved, Denied).
        admin_notes: Admin feedback on the request.
        reviewed_by_id: FK to User who reviewed.
        reviewed_at: When the review happened.
        created_at: When the request was created.

    Relationships:
        clock_punch: The ClockPunch being corrected.
        member: The member who made the request.
        reviewed_by: The User who reviewed the request.
    """

    __tablename__ = "punch_change_request"

    id = db.Column(db.Integer, primary_key=True)
    clock_punch_id = db.Column(
        db.Integer,
        db.ForeignKey("clock_punch.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    member_id = db.Column(
        db.Integer,
        db.ForeignKey("organization_user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    original_time = db.Column(db.DateTime, nullable=False)
    requested_time = db.Column(db.DateTime, nullable=False)
    reason = db.Column(db.Text, nullable=True)
    status = db.Column(
        db.Enum(PunchCorrectionRequestStatus),
        default=PunchCorrectionRequestStatus.PENDING,
        nullable=False,
    )
    admin_notes = db.Column(db.Text, nullable=True)
    reviewed_by_id = db.Column(
        db.Integer, db.ForeignKey("organization_user.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    clock_punch = db.relationship(
        "ClockPunch",
        backref=db.backref("correction_requests", lazy="dynamic"),
        lazy=LAZY,
    )
    member = db.relationship(
        "OrganizationUser",
        foreign_keys=[member_id],
        backref=db.backref("punch_correction_requests", lazy="dynamic"),
        lazy=LAZY,
    )
    reviewed_by = db.relationship("OrganizationUser", foreign_keys=[reviewed_by_id], lazy=LAZY)

    __table_args__ = (
        db.Index("ix_punch_change_request_status", "status"),
    )

    # --- Properties ---

    @property
    def status_badge_class(self) -> str:
        """Return Bootstrap badge class based on status."""
        return {
            PunchCorrectionRequestStatus.PENDING: "bg-warning text-dark",
            PunchCorrectionRequestStatus.APPROVED: "bg-success",
            PunchCorrectionRequestStatus.DENIED: "bg-danger",
        }.get(self.status, "bg-secondary")

    @property
    def is_pending(self) -> bool:
        """Return True if the request is still pending."""
        return self.status == PunchCorrectionRequestStatus.PENDING

    # --- Class Methods ---

    @classmethod
    def create(
        cls,
        clock_punch_id: int,
        member_id: int,
        requested_time: datetime,
        reason: str | None = None,
    ) -> "PunchCorrectionRequest":
        """Create a new punch correction request.

        Validates that no existing PENDING request exists for this punch.

        Args:
            clock_punch_id: ID of the punch to correct.
            member_id: ID of the requesting member.
            requested_time: The new time requested (UTC).
            reason: Optional reason for the correction.

        Returns:
            The created PunchCorrectionRequest.

        Raises:
            ValueError: If a pending request already exists for this punch.
        """
        existing = cls.get_pending_for_punch(clock_punch_id)
        if existing:
            raise ValueError("A pending correction request already exists for this punch")

        from .clock_punch import ClockPunch

        punch = ClockPunch.scoped().filter_by(id=clock_punch_id).first()
        if not punch:
            raise ValueError("Clock punch not found")

        request = cls(
            clock_punch_id=clock_punch_id,
            member_id=member_id,
            original_time=punch.punch_time,
            requested_time=requested_time,
            reason=reason,
            status=PunchCorrectionRequestStatus.PENDING,
        )
        db.session.add(request)
        db.session.commit()

        from sqlalchemy.orm import joinedload
        from modules.base.core.models.organization_user import OrganizationUser
        request = cls.query.options(
            joinedload(cls.member).joinedload(OrganizationUser.user),
        ).get(request.id)

        from system.events import emit
        emit.created("PunchCorrectionRequest", request)

        return request

    @classmethod
    def pending_count(cls) -> int:
        """Count pending correction requests."""
        return cls.scoped().filter_by(status=PunchCorrectionRequestStatus.PENDING).count()

    @classmethod
    def get_pending_approval(cls) -> list["PunchCorrectionRequest"]:
        """Get all pending requests ordered by created_at desc.

        Returns:
            List of pending PunchCorrectionRequest records.
        """
        from sqlalchemy.orm import joinedload
        from modules.base.core.models.organization_user import OrganizationUser
        return (
            cls.scoped()
            .options(
                joinedload(cls.member).joinedload(OrganizationUser.user),
                joinedload(cls.clock_punch),
            )
            .filter_by(status=PunchCorrectionRequestStatus.PENDING)
            .order_by(cls.created_at.desc())
            .all()
        )

    @classmethod
    def get_pending_for_punch(cls, clock_punch_id: int) -> "PunchCorrectionRequest | None":
        """Get the pending request for a specific punch.

        Args:
            clock_punch_id: The punch ID to check.

        Returns:
            The pending PunchCorrectionRequest or None.
        """
        return cls.scoped().filter_by(
            clock_punch_id=clock_punch_id,
            status=PunchCorrectionRequestStatus.PENDING,
        ).first()

    @classmethod
    def get_pending_map_for_punches(
        cls, punch_ids: list[int],
    ) -> dict[int, "PunchCorrectionRequest"]:
        """Get a map of punch_id -> pending request for efficient lookups.

        Args:
            punch_ids: List of punch IDs to check.

        Returns:
            Dict mapping punch_id to its pending PunchCorrectionRequest.
        """
        if not punch_ids:
            return {}

        requests = cls.scoped().filter(
            cls.clock_punch_id.in_(punch_ids),
            cls.status == PunchCorrectionRequestStatus.PENDING,
        ).all()

        return {req.clock_punch_id: req for req in requests}

    @classmethod
    def get_pending_grouped_by_member(cls) -> dict[int, dict[str, Any]]:
        """Get pending requests grouped by member for the admin queue.

        Returns:
            Dict keyed by member_id with member and requests list.
        """
        pending_requests = cls.get_pending_approval()

        requests_by_member: dict[int, dict[str, Any]] = {}
        for req in pending_requests:
            if req.member_id not in requests_by_member:
                requests_by_member[req.member_id] = {
                    "member": req.member,
                    "requests": [],
                }
            requests_by_member[req.member_id]["requests"].append(req)

        return requests_by_member

    @classmethod
    def count_pending_for_member(cls, member_id: int) -> int:
        """Count pending requests for a member.

        Args:
            member_id: The member ID to check.

        Returns:
            Number of pending punch correction requests.
        """
        return cls.scoped().filter_by(
            member_id=member_id,
            status=PunchCorrectionRequestStatus.PENDING,
        ).count()

    @property
    def affected_time_entry(self) -> "TimeEntry | None":  # noqa: F821
        """Get the TimeEntry affected by this punch correction request.

        Handles both OUT punches (direct time_entry_id) and IN punches
        (via matching OUT punch).

        Returns:
            The affected TimeEntry, or None if not linked.
        """
        from .time_entry import TimeEntry

        punch = self.clock_punch
        if punch.time_entry_id:
            return TimeEntry.scoped().filter_by(id=punch.time_entry_id).first()

        # IN punch — find the matching OUT punch's entry
        from .clock_punch import PunchType

        if punch.punch_type == PunchType.IN:
            matching_out = punch.get_matching_out()
            if matching_out and matching_out.time_entry_id:
                return TimeEntry.scoped().filter_by(id=matching_out.time_entry_id).first()

        return None

    # --- Instance Methods ---

    def approve(self, user_id: int, notes: str | None = None) -> None:
        """Approve the correction request and apply the time change.

        Sets status to APPROVED, then delegates to ClockPunch.update_time()
        which handles the audit trail (ClockPunchAdjustment) and TimeEntry
        recalculation.

        Args:
            user_id: ID of the admin approving.
            notes: Optional admin notes.

        Raises:
            ValueError: If the request is not pending.
        """
        if self.status != PunchCorrectionRequestStatus.PENDING:
            raise ValueError("Only pending requests can be approved")

        from modules.base.core.models.user import User

        self.status = PunchCorrectionRequestStatus.APPROVED
        self.reviewed_by_id = user_id
        self.reviewed_at = datetime.utcnow()
        if notes:
            self.admin_notes = notes
        db.session.commit()

        # Apply the time correction via existing flow
        reviewer = User.get_by_id(user_id)
        self.clock_punch.update_time(
            self.requested_time,
            adjusted_by=reviewer,
            reason=self.reason,
        )

    def deny(self, user_id: int) -> None:
        """Deny the correction request.

        Args:
            user_id: ID of the admin denying.

        Raises:
            ValueError: If the request is not pending.
        """
        if self.status != PunchCorrectionRequestStatus.PENDING:
            raise ValueError("Only pending requests can be denied")

        self.status = PunchCorrectionRequestStatus.DENIED
        self.reviewed_by_id = user_id
        self.reviewed_at = datetime.utcnow()
        db.session.commit()

    def __repr__(self) -> str:
        return f"<PunchCorrectionRequest {self.id}: punch={self.clock_punch_id} status={self.status.value}>"
