# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

"""CannedTask model — reusable action item templates.

Pre-defined action titles that can be quickly selected when creating
Tasks. Limited to 10 per workspace. Can be created by admins
in settings or on-the-fly by any team member.

Classes:
    CannedTask: Reusable action item template.
"""

from datetime import datetime

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.workspace import WorkspaceMixin
from system.db.raise_on_lazy import LAZY

MAX_CANNED_TASKS = 10


@ModelRegistry.register
class CannedTask(db.Model, WorkspaceMixin):
    """Reusable action item template with optional default tier.

    Attributes:
        title: The template text (max 200 chars).
        default_tier: Optional default urgency tier (1-3, nullable).
        sort_order: Display order.
        created_by_id: FK to workspace_user who created this.
    """

    __tablename__ = "canned_task"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    default_tier = db.Column(db.Integer, nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_by_id = db.Column(
        db.Integer, db.ForeignKey("workspace_user.id"), nullable=True
    )

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    created_by = db.relationship("WorkspaceUser", foreign_keys=[created_by_id], lazy=LAZY)

    @classmethod
    def get_all(cls):
        """Get all canned actions for the current workspace, ordered by sort_order."""
        return cls.scoped().order_by(cls.sort_order.asc(), cls.created_at.asc()).all()

    @classmethod
    def count(cls):
        """Get count of canned actions for the current workspace."""
        return cls.scoped().count()

    @classmethod
    def create(cls, title, default_tier=None, created_by_id=None):
        """Create a new canned action if under the limit.

        Args:
            title: Template text (max 200 chars).
            default_tier: Optional default urgency tier (1-3).
            created_by_id: WorkspaceUser.id of the creator.

        Returns:
            Created CannedTask or None if at limit.
        """
        if cls.count() >= MAX_CANNED_TASKS:
            return None

        # Deduplicate: don't create if same title exists
        existing = cls.scoped().filter(
            db.func.lower(cls.title) == title.strip().lower()
        ).first()
        if existing:
            return existing

        action = cls(
            title=title.strip()[:200],
            default_tier=max(1, min(3, default_tier)) if default_tier else None,
            sort_order=cls.count(),
            created_by_id=created_by_id,
        )
        db.session.add(action)
        db.session.commit()
        return action

    @classmethod
    def update(cls, action_id, title=None, default_tier=None):
        """Update a canned action.

        Args:
            action_id: CannedTask.id to update.
            title: New title (optional).
            default_tier: New default tier (optional, 0 to clear).

        Returns:
            Updated CannedTask or None.
        """
        action = cls.scoped().filter_by(id=action_id).first()
        if not action:
            return None

        if title is not None:
            action.title = title.strip()[:200]
        if default_tier is not None:
            action.default_tier = max(1, min(3, default_tier)) if default_tier else None
        db.session.commit()
        return action

    @classmethod
    def delete(cls, action_id):
        """Delete a canned action.

        Args:
            action_id: CannedTask.id to delete.

        Returns:
            True if deleted, False if not found.
        """
        action = cls.scoped().filter_by(id=action_id).first()
        if not action:
            return False
        db.session.delete(action)
        db.session.commit()
        return True
