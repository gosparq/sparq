# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     PersonNote model for private notes on people profiles.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

"""Person note model for admin/HR private notes.

Notes are visible only to admins and HR users. People cannot see
notes written about them. Supports soft delete and audit tracking.

Example:
    Creating a note::

        note = PersonNote.create(
            member_id=42,
            content="Performance review scheduled for next week.",
            user_id=current_user.id,
        )

    Fetching notes for a person::

        notes = PersonNote.get_for_member(member_id=42)
"""

from datetime import datetime, timezone

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.mixins import AuditMixin, SoftDeleteMixin
from system.db.workspace import WorkspaceMixin
from system.db.raise_on_lazy import LAZY


@ModelRegistry.register
class PersonNote(db.Model, WorkspaceMixin, AuditMixin, SoftDeleteMixin):
    """Private note attached to a person's profile.

    Attributes:
        id: Primary key.
        member_id: FK to workspace_user being noted on.
        content: Plain-text note content.
        created_at: When the note was created.
        updated_at: When the note was last edited.
    """

    __tablename__ = "person_note"

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(
        db.Integer, db.ForeignKey("workspace_user.id"), nullable=False, index=True
    )
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    member = db.relationship("WorkspaceUser", backref=db.backref("notes", lazy="dynamic"), lazy=LAZY)

    @classmethod
    def create(cls, member_id: int, content: str, user_id: int) -> "PersonNote":
        """Create a new person note.

        Args:
            member_id: ID of the member this note is about.
            content: Plain-text note content.
            user_id: ID of the user creating the note.

        Returns:
            The newly created PersonNote instance.
        """
        note = cls(
            member_id=member_id,
            content=content,
            created_by_id=user_id,
            updated_by_id=user_id,
        )
        db.session.add(note)
        db.session.commit()
        return note

    @classmethod
    def get_for_member(cls, member_id: int) -> list["PersonNote"]:
        """Get all active notes for a member in reverse chronological order.

        Args:
            member_id: ID of the member.

        Returns:
            List of active PersonNote instances, newest first.
        """
        from sqlalchemy.orm import joinedload

        return (
            cls.active()
            .options(joinedload(cls.created_by))
            .filter_by(member_id=member_id)
            .order_by(cls.created_at.desc())
            .all()
        )

    def update_content(self, content: str, user_id: int) -> None:
        """Update the note content.

        Args:
            content: New plain-text content.
            user_id: ID of the user making the edit.
        """
        self.content = content
        self.updated_by_id = user_id
        db.session.commit()

    def __repr__(self) -> str:
        return f"<PersonNote {self.id} member={self.member_id}>"
