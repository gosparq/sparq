# -----------------------------------------------------------------------------
# sparQ - AI Pending Action Model
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""
Model for tracking AI-proposed actions pending user confirmation.
"""

from datetime import datetime
from typing import Any

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.workspace import WorkspaceMixin
from system.db.raise_on_lazy import LAZY


class ActionStatus:
    """Status constants for pending actions."""

    PROPOSED = "proposed"
    NEEDS_CLARIFICATION = "needs_clarification"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    EXECUTED = "executed"
    FAILED = "failed"


@ModelRegistry.register
class AIPendingAction(db.Model, WorkspaceMixin):
    """
    Tracks AI-proposed actions pending user confirmation.

    When a user sends a message to sparQy, the AI may propose an action
    (e.g., create_contact). This model stores the proposed action until
    the user confirms, cancels, or edits it.
    """

    __tablename__ = "ai_pending_action"

    id = db.Column(db.Integer, primary_key=True)

    # References
    channel_id = db.Column(db.Integer, db.ForeignKey("update_channel.id", ondelete="SET NULL"), nullable=True)
    trigger_chat_id = db.Column(db.Integer, nullable=True)  # Legacy: was FK to sync_message
    proposal_chat_id = db.Column(db.Integer, nullable=True)  # Legacy: was FK to sync_message
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    # Action details
    tool_name = db.Column(db.String(100), nullable=False)
    args_json = db.Column(db.JSON, nullable=False)
    status = db.Column(db.String(20), nullable=False, default=ActionStatus.PROPOSED)

    # Clarification data (for ambiguous references)
    clarification_json = db.Column(db.JSON, nullable=True)

    # Result data
    result_json = db.Column(db.JSON, nullable=True)
    error = db.Column(db.Text, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    channel = db.relationship("UpdateChannel", backref=db.backref("pending_actions", lazy="dynamic"), lazy=LAZY)
    created_by = db.relationship("User", backref=db.backref("ai_pending_actions", lazy="dynamic"), lazy=LAZY)

    @classmethod
    def create(
        cls,
        channel_id: int | None,
        trigger_chat_id: int | None,
        created_by_id: int,
        tool_name: str,
        args_json: dict[str, Any],
        status: str = ActionStatus.PROPOSED,
        clarification_json: dict[str, Any] | None = None,
    ) -> "AIPendingAction":
        """Create a new pending action."""
        action = cls(
            channel_id=channel_id,
            trigger_chat_id=trigger_chat_id,
            created_by_id=created_by_id,
            tool_name=tool_name,
            args_json=args_json,
            status=status,
            clarification_json=clarification_json,
        )
        db.session.add(action)
        db.session.commit()
        return action

    def confirm(self) -> None:
        """Mark action as confirmed."""
        self.status = ActionStatus.CONFIRMED
        self.updated_at = datetime.utcnow()
        db.session.commit()

    def cancel(self) -> None:
        """Mark action as cancelled."""
        self.status = ActionStatus.CANCELLED
        self.updated_at = datetime.utcnow()
        db.session.commit()

    def mark_executed(self, result: dict[str, Any] | None = None) -> None:
        """Mark action as executed with optional result."""
        self.status = ActionStatus.EXECUTED
        self.result_json = result
        self.updated_at = datetime.utcnow()
        db.session.commit()

    def mark_failed(self, error: str) -> None:
        """Mark action as failed with error message."""
        self.status = ActionStatus.FAILED
        self.error = error
        self.updated_at = datetime.utcnow()
        db.session.commit()

    def update_args(self, new_args: dict[str, Any]) -> None:
        """Update the action arguments (for edit flow)."""
        self.args_json = new_args
        self.updated_at = datetime.utcnow()
        db.session.commit()

    def set_proposal_chat(self, chat_id: int) -> None:
        """Link the proposal chat message."""
        self.proposal_chat_id = chat_id
        db.session.commit()

    @classmethod
    def get_by_id(cls, action_id: int) -> "AIPendingAction | None":
        """Get pending action by ID."""
        return cls.scoped().filter_by(id=action_id).first()

    @classmethod
    def get_pending_for_user(cls, user_id: int) -> list["AIPendingAction"]:
        """Get all pending actions for a user."""
        return cls.scoped().filter_by(
            created_by_id=user_id,
            status=ActionStatus.PROPOSED,
        ).order_by(cls.created_at.desc()).all()
