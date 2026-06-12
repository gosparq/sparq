# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

"""Area model — permanent domain categorization for posts, blockers, and action items.

Areas are ongoing/permanent tags representing domains of work (e.g., "Infrastructure",
"Sales", "Product"). They are scoped to a workspace and managed by admins.

Classes:
    UpdateArea: Domain categorization model.
"""

from datetime import datetime

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.workspace import WorkspaceMixin

MAX_AREAS_PER_WORKSPACE = 10


@ModelRegistry.register
class UpdateArea(db.Model, WorkspaceMixin):
    """Permanent domain categorization tag.

    Attributes:
        name: Display name (e.g., "Infrastructure").
        color: Hex color code for badges/dots.
        emoji: Optional emoji icon.
        sort_order: Display order (lower = first).
        is_active: Soft-delete flag.
    """

    __tablename__ = "update_area"
    __table_args__ = (
        db.Index("ix_update_area_workspace_active", "workspace_id", "is_active"),
        db.UniqueConstraint("workspace_id", "name", name="uq_update_area_name"),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    color = db.Column(db.String(7), nullable=False, default="#6b7280")
    emoji = db.Column(db.String(10), nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    @classmethod
    def get_all(cls):
        """Get all active areas for the current workspace, ordered by sort_order.

        Returns:
            List of active Area instances.
        """
        return (
            cls.scoped()
            .filter(cls.is_active == True)  # noqa: E712
            .order_by(cls.sort_order.asc(), cls.name.asc())
            .all()
        )

    @classmethod
    def get_by_id(cls, area_id):
        """Get a single area by ID within current workspace.

        Args:
            area_id: The area ID.

        Returns:
            Area instance or None.
        """
        return cls.scoped().filter_by(id=area_id).first()

    @classmethod
    def create(cls, name, color="#6b7280", emoji=None):
        """Create a new area. Enforces max limit per workspace.

        Args:
            name: Display name.
            color: Hex color code.
            emoji: Optional emoji.

        Returns:
            Created Area instance.

        Raises:
            ValueError: If max areas limit reached or name already exists.
        """
        count = cls.scoped().filter(cls.is_active == True).count()  # noqa: E712
        if count >= MAX_AREAS_PER_WORKSPACE:
            raise ValueError(f"Maximum of {MAX_AREAS_PER_WORKSPACE} areas allowed.")

        # Get next sort_order
        max_order = (
            db.session.query(db.func.max(cls.sort_order))
            .filter(cls.workspace_id == cls._current_workspace_id())
            .scalar()
        ) or 0

        area = cls(
            name=name.strip(),
            color=color,
            emoji=emoji.strip() if emoji else None,
            sort_order=max_order + 1,
        )
        db.session.add(area)
        db.session.commit()
        return area

    @classmethod
    def _current_workspace_id(cls):
        """Get current workspace ID from Flask g context."""
        from flask import g
        return getattr(g, "workspace_id", None)

    def update(self, name=None, color=None, emoji=None):
        """Update area attributes.

        Args:
            name: New display name (optional).
            color: New hex color (optional).
            emoji: New emoji (optional, pass empty string to clear).
        """
        if name is not None:
            self.name = name.strip()
        if color is not None:
            self.color = color
        if emoji is not None:
            self.emoji = emoji.strip() if emoji else None
        db.session.commit()

    def delete(self):
        """Soft-delete this area by marking inactive."""
        self.is_active = False
        db.session.commit()

    @classmethod
    def reorder(cls, area_ids):
        """Reorder areas by a list of IDs.

        Args:
            area_ids: List of area IDs in desired order.
        """
        for idx, area_id in enumerate(area_ids):
            area = cls.scoped().filter_by(id=area_id).first()
            if area:
                area.sort_order = idx
        db.session.commit()
