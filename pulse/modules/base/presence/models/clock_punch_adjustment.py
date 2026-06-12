# -----------------------------------------------------------------------------
# sparQ - Clock Punch Adjustment Model (Audit Trail)
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""Clock punch adjustment model for audit trail of admin edits.

This module tracks administrative changes to clock punch times for compliance
and audit purposes.

Classes:
    ClockPunchAdjustment: Records changes made by admins to clock punches.

Example:
    Recording an adjustment::

        from modules.base.presence.models.clock_punch_adjustment import ClockPunchAdjustment

        adjustment = ClockPunchAdjustment.record(
            clock_punch_id=punch.id,
            adjusted_by_id=admin_user.id,
            original_punch_time=punch.punch_time,
            new_punch_time=new_time,
            reason="Member reported wrong clock-in time"
        )
"""

from datetime import datetime

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.raise_on_lazy import LAZY
from system.db.workspace import OrganizationMixin


@ModelRegistry.register
class ClockPunchAdjustment(db.Model, OrganizationMixin):
    """Audit trail for administrative edits to clock punches.

    Records every change made by an administrator to a clock punch time,
    preserving the original value, new value, reason, and who made the change.

    Attributes:
        clock_punch_id: Foreign key to the modified ClockPunch.
        adjusted_by_id: Foreign key to User who made the change.
        original_punch_time: The punch time before adjustment.
        new_punch_time: The punch time after adjustment.
        reason: Optional reason for the adjustment.
        created_at: When the adjustment was made.

    Relationships:
        clock_punch: The ClockPunch that was modified.
        adjusted_by: The User who made the adjustment.
    """

    __tablename__ = "clock_punch_adjustment"

    id = db.Column(db.Integer, primary_key=True)
    clock_punch_id = db.Column(
        db.Integer,
        db.ForeignKey("clock_punch.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    adjusted_by_id = db.Column(
        db.Integer,
        db.ForeignKey("organization_user.id"),
        nullable=False,
        index=True,
    )
    original_punch_time = db.Column(db.DateTime, nullable=False)
    new_punch_time = db.Column(db.DateTime, nullable=False)
    reason = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    clock_punch = db.relationship(
        "ClockPunch",
        backref=db.backref("adjustments", lazy="dynamic", cascade="all, delete-orphan"),
        lazy=LAZY,
    )
    adjusted_by = db.relationship(
        "OrganizationUser",
        backref=db.backref("clock_punch_adjustments", lazy="dynamic"),
        lazy=LAZY,
    )

    @classmethod
    def record(
        cls,
        clock_punch_id: int,
        adjusted_by_id: int,
        original_punch_time: datetime,
        new_punch_time: datetime,
        reason: str | None = None,
    ) -> "ClockPunchAdjustment":
        """Record a clock punch adjustment.

        Args:
            clock_punch_id: ID of the clock punch being adjusted.
            adjusted_by_id: ID of the admin user making the adjustment.
            original_punch_time: The original punch time before change.
            new_punch_time: The new punch time after change.
            reason: Optional reason for the adjustment.

        Returns:
            The created ClockPunchAdjustment record.
        """
        adjustment = cls(
            clock_punch_id=clock_punch_id,
            adjusted_by_id=adjusted_by_id,
            original_punch_time=original_punch_time,
            new_punch_time=new_punch_time,
            reason=reason,
        )
        db.session.add(adjustment)
        db.session.commit()
        return adjustment

    def __repr__(self):
        return f"<ClockPunchAdjustment {self.id}: punch={self.clock_punch_id}>"
