# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

"""ProjectStatus model — per-workspace configurable project status definitions.

Classes:
    ProjectStatus: Admin-configurable status row for a workspace.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.workspace import WorkspaceMixin

MAX_PROJECT_STATUSES = 5

_DEFAULT_STATUSES = [
    {"code": "upcoming",  "label": "To Do",       "color": "#6b7280", "sort_order": 1, "is_archived": False, "is_default": False},
    {"code": "current",   "label": "In Progress",  "color": "#2563eb", "sort_order": 2, "is_archived": False, "is_default": True},
    {"code": "on_hold",   "label": "On Hold",      "color": "#f59e0b", "sort_order": 3, "is_archived": False, "is_default": False},
    {"code": "archived",  "label": "Completed",    "color": "#16a34a", "sort_order": 4, "is_archived": True,  "is_default": False},
]


@ModelRegistry.register
class ProjectStatus(db.Model, WorkspaceMixin):
    """Admin-configurable project status for a workspace.

    Attributes:
        code: Stable string key stored on project.status (e.g. 'current').
        label: Display label shown in UI (e.g. 'In Progress').
        color: Hex color code for pills and board column headers.
        sort_order: Admin-controlled display order (ascending).
        is_archived: When True, moving a project here triggers archive behavior.
        is_default: When True, new projects are created with this status.
    """

    __tablename__ = "project_status"

    __table_args__ = (
        db.UniqueConstraint("workspace_id", "code", name="uq_project_status_ws_code"),
        db.Index("ix_project_status_ws_sort", "organization_id", "workspace_id", "sort_order"),
    )

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), nullable=False)
    label = db.Column(db.String(100), nullable=False)
    color = db.Column(db.String(10), nullable=False, default="#6b7280")
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_archived = db.Column(db.Boolean, nullable=False, default=False)
    is_default = db.Column(db.Boolean, nullable=False, default=False)

    # ── Classmethods ──────────────────────────────────────────────────────────

    @classmethod
    def get_for_workspace(cls) -> list["ProjectStatus"]:
        """Return all statuses for the current workspace ordered by sort_order.

        Result is cached on g for the request lifetime.

        Returns:
            List of ProjectStatus instances ordered by sort_order ascending.
        """
        from flask import g

        cache_key = "_project_status_list_cache"
        workspace_id = getattr(g, "workspace_id", None)
        try:
            cache = getattr(g, cache_key, None)
            if cache is not None and cache.get("ws") == workspace_id:
                return cache["rows"]
        except Exception:
            pass

        rows = cls.scoped().order_by(cls.sort_order).all()

        try:
            setattr(g, cache_key, {"ws": workspace_id, "rows": rows})
        except Exception:
            pass

        return rows

    @classmethod
    def get_default(cls) -> "ProjectStatus | None":
        """Return the status marked is_default=True, or the first status.

        Returns:
            ProjectStatus instance, or None if no statuses exist.
        """
        rows = cls.get_for_workspace()
        for s in rows:
            if s.is_default:
                return s
        return rows[0] if rows else None

    @classmethod
    def get_archived_status(cls) -> "ProjectStatus | None":
        """Return the status marked is_archived=True, or None.

        Returns:
            ProjectStatus instance where is_archived=True, or None.
        """
        rows = cls.get_for_workspace()
        for s in rows:
            if s.is_archived:
                return s
        return None

    @classmethod
    def get_codes(cls) -> list[str]:
        """Return ordered list of valid status codes for the current workspace.

        Returns:
            List of code strings.
        """
        return [s.code for s in cls.get_for_workspace()]

    @classmethod
    def add(
        cls,
        *,
        label: str,
        code: str,
        color: str = "#6b7280",
        is_default: bool = False,
    ) -> tuple["ProjectStatus | None", str | None]:
        """Create a new status for the current workspace.

        Args:
            label: Display label (max 100 chars).
            code: Stable slug — lowercase letters, digits, underscores (max 50).
            color: 6-digit hex color string (e.g. '#6b7280').
            is_default: If True, clears is_default on all other statuses.

        Returns:
            (ProjectStatus, None) on success, (None, error_message) on failure.
        """
        import re
        from flask import g

        if not label:
            return None, "Label is required."
        if not re.match(r'^[a-z0-9_]{1,50}$', code):
            return None, "Code must be lowercase letters, numbers, or underscores (max 50 chars)."
        if not re.match(r'^#[0-9a-fA-F]{6}$', color):
            color = "#6b7280"

        if cls.scoped().count() >= MAX_PROJECT_STATUSES:
            return None, f"Maximum of {MAX_PROJECT_STATUSES} project statuses reached."

        if cls.scoped().filter_by(code=code).first():
            return None, "A status with that code already exists."

        max_order = db.session.execute(
            db.select(db.func.max(cls.sort_order)).where(
                cls.workspace_id == g.workspace_id
            )
        ).scalar() or 0

        if is_default:
            cls.scoped().filter_by(is_default=True).update({"is_default": False})

        ps = cls(
            workspace_id=g.workspace_id,
            organization_id=g.organization_id,
            code=code,
            label=label[:100],
            color=color,
            sort_order=max_order + 1,
            is_archived=False,
            is_default=is_default,
        )
        db.session.add(ps)
        db.session.commit()
        return ps, None

    @classmethod
    def update(
        cls,
        status_id: int,
        *,
        label: str,
        color: str,
        is_archived: bool,
        is_default: bool,
    ) -> tuple[bool, str | None]:
        """Update label, color, and flag fields for a status.

        Enforces exactly-one is_archived and exactly-one is_default invariants.

        Args:
            status_id: Primary key of the status to update.
            label: New display label.
            color: New hex color string.
            is_archived: Desired is_archived value.
            is_default: Desired is_default value.

        Returns:
            (True, None) on success, (False, error_message) on failure.
        """
        import re

        ps = cls.scoped().filter_by(id=status_id).first()
        if not ps:
            return False, "Status not found."

        if label:
            ps.label = label[:100]
        if re.match(r'^#[0-9a-fA-F]{6}$', color):
            ps.color = color

        if is_archived and not ps.is_archived:
            cls.scoped().filter(cls.id != status_id).update({"is_archived": False})
            ps.is_archived = True
        elif not is_archived and ps.is_archived:
            other = cls.scoped().filter(cls.id != status_id, cls.is_archived == True).first()  # noqa: E712
            if not other:
                return False, "Cannot remove archive flag — at least one status must handle archiving."
            ps.is_archived = False

        if is_default and not ps.is_default:
            cls.scoped().filter(cls.id != status_id).update({"is_default": False})
            ps.is_default = True
        elif not is_default and ps.is_default:
            other = cls.scoped().filter(cls.id != status_id, cls.is_default == True).first()  # noqa: E712
            if not other:
                return False, "Cannot remove default — at least one status must be the default."
            ps.is_default = False

        db.session.commit()
        return True, None

    @classmethod
    def delete(cls, status_id: int) -> tuple[bool, str | None]:
        """Delete a status after running guard checks.

        Guards: not in use by any project, not the last status, not the only
        archived status. If deleting the default, promotes the next status.

        Args:
            status_id: Primary key of the status to delete.

        Returns:
            (True, None) on success, (False, error_message) on failure.
        """
        from modules.base.projects.models.project import Project

        ps = cls.scoped().filter_by(id=status_id).first()
        if not ps:
            return False, "Status not found."

        in_use = Project.scoped().filter_by(status=ps.code).count()
        if in_use:
            return False, f"Cannot delete — {in_use} project(s) are using this status."

        if cls.scoped().count() <= 1:
            return False, "Cannot delete the last project status."

        if ps.is_archived:
            other = cls.scoped().filter(cls.id != status_id, cls.is_archived == True).first()  # noqa: E712
            if not other:
                return False, "Cannot delete the only archive status — designate another first."

        if ps.is_default:
            next_status = cls.scoped().filter(cls.id != status_id).order_by(cls.sort_order).first()
            if next_status:
                next_status.is_default = True

        db.session.delete(ps)
        db.session.commit()
        return True, None

    @classmethod
    def set_default(cls, status_id: int) -> tuple[bool, str | None]:
        """Mark a status as the default for new projects.

        Clears is_default on all other statuses for this workspace.

        Args:
            status_id: Primary key of the status to make default.

        Returns:
            (True, None) on success, (False, error_message) on failure.
        """
        ps = cls.scoped().filter_by(id=status_id).first()
        if not ps:
            return False, "Status not found."

        cls.scoped().update({"is_default": False})
        ps.is_default = True
        db.session.commit()
        return True, None

    @classmethod
    def bulk_reorder(cls, items: list[dict]) -> None:
        """Bulk-update sort_order for multiple statuses.

        Args:
            items: List of dicts with 'id' and 'sort_order' keys.
        """
        for item in items:
            try:
                sid = int(item["id"])
                order = int(item["sort_order"])
            except (KeyError, TypeError, ValueError):
                continue
            ps = cls.scoped().filter_by(id=sid).first()
            if ps:
                ps.sort_order = order
        db.session.commit()

    @classmethod
    def seed_defaults(cls) -> None:
        """Insert the four default statuses if none exist for this workspace.

        Idempotent — safe to call on existing workspaces. Uses ON CONFLICT DO
        NOTHING semantics by checking existence first rather than relying on
        raw SQL, so it works in both dev (SQLite) and production (PostgreSQL).
        """
        from flask import g

        workspace_id = getattr(g, "workspace_id", None)
        organization_id = getattr(g, "organization_id", None)

        if workspace_id is None or organization_id is None:
            return

        existing = cls.scoped().count()
        if existing > 0:
            return

        for row in _DEFAULT_STATUSES:
            db.session.add(cls(
                workspace_id=workspace_id,
                organization_id=organization_id,
                code=row["code"],
                label=row["label"],
                color=row["color"],
                sort_order=row["sort_order"],
                is_archived=row["is_archived"],
                is_default=row["is_default"],
            ))
        db.session.flush()
