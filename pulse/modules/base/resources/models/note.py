# -----------------------------------------------------------------------------
# sparQ - Note Model
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""Note model — personal and team notes in Resources.

Org-scoped (organization_id NOT NULL). `workspace_id` is a nullable filter:
set = note belongs to a workspace, NULL = org-wide. Pinned notes sort first,
then by updated_at descending.
"""

from datetime import datetime

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.workspace import WorkspaceMixin
from system.db.raise_on_lazy import LAZY


@ModelRegistry.register
class Note(db.Model, WorkspaceMixin):
    """Personal or team note.

    Attributes:
        member_id: Author (FK to WorkspaceUser).
        title: Derived from first line of content.
        content: Freeform text/markdown.
        visibility: 'personal' or 'team'.
        is_pinned: Whether note is pinned to top.
    """

    __tablename__ = "note"
    __table_args__ = (
        db.Index("ix_note_member_visibility", "workspace_id", "member_id", "visibility"),
    )

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(
        db.Integer, db.ForeignKey("workspace_user.id"), nullable=False
    )

    title = db.Column(db.String(255), nullable=True)
    content = db.Column(db.Text, nullable=True)
    visibility = db.Column(db.String(20), nullable=False, default="personal")
    is_pinned = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    member = db.relationship("WorkspaceUser", foreign_keys=[member_id], lazy=LAZY)

    @classmethod
    def create(cls, member_id, content="", visibility="personal"):
        """Create a new note in the active scope.

        Args:
            member_id: Author's workspace_user.id.
            content: Note content.
            visibility: 'personal' or 'team'.

        Returns:
            Created Note instance.
        """
        title = cls._extract_title(content)
        note = cls(
            member_id=member_id,
            title=title,
            content=content,
            visibility=visibility,
        )
        db.session.add(note)
        db.session.commit()
        return note

    @classmethod
    def get_for_member(cls, member_id, visibility=None):
        """Get notes for a member, with optional visibility filter.

        Args:
            member_id: WorkspaceUser.id.
            visibility: Optional 'personal' or 'team' filter; None returns
                personal notes by this member plus all team notes.

        Returns:
            List of Note instances, pinned first then newest updated_at.
        """
        from sqlalchemy.orm import joinedload
        from modules.base.core.models.workspace_user import WorkspaceUser

        query = cls.scoped().options(joinedload(cls.member).joinedload(WorkspaceUser.user))

        if visibility == "personal":
            query = query.filter(cls.member_id == member_id, cls.visibility == "personal")
        elif visibility == "team":
            query = query.filter(cls.visibility == "team")
        else:
            query = query.filter(
                db.or_(
                    db.and_(cls.member_id == member_id, cls.visibility == "personal"),
                    cls.visibility == "team",
                )
            )

        return query.order_by(cls.is_pinned.desc(), cls.updated_at.desc()).all()

    @classmethod
    def get_by_id(cls, note_id):
        """Get a note by ID within the active scope."""
        return cls.scoped().filter(cls.id == note_id).first()

    def update_content(self, content):
        """Update note content and re-derive the title from the first line."""
        self.content = content
        self.title = self._extract_title(content)
        db.session.commit()

    @staticmethod
    def _extract_title(content):
        """Extract the title from the first line of content (strips markdown)."""
        if not content:
            return "Untitled"
        first_line = content.strip().split("\n")[0][:255]
        if first_line.startswith("#"):
            first_line = first_line.lstrip("#").strip()
        return first_line or "Untitled"
