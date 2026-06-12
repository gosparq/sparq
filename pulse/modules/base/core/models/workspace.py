# -----------------------------------------------------------------------------
# sparQ - Workspace Model
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

import random
import re
import uuid
from datetime import datetime, timezone

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.mixins import SoftDeleteMixin


RESERVED_SLUGS = {
    "www", "api", "admin", "app", "mail", "smtp", "sms", "cloud",
    "default", "demo", "staging", "dev", "test", "status", "help",
    "support", "billing",
}

WORKSPACE_COLORS = {
    "orange": "#E8431A",
    "violet": "#7C3AED",
    "indigo": "#4F46E5",
    "fuchsia": "#C026D3",
    "rose": "#E11D48",
    "amber": "#D97706",
    "emerald": "#059669",
    "teal": "#0D9488",
    "sky": "#0284C7",
    "slate": "#475569",
}

DEFAULT_WORKSPACE_COLOR = "orange"


@ModelRegistry.register
class Workspace(db.Model, SoftDeleteMixin):
    """Workspace model for multi-tenancy support.

    Each workspace represents an isolated team sharing the same database.
    All workspace-scoped models reference this table via workspace_id FK.

    Phase 6: workspaces are soft-deletable ("archive") by organization admins
    per §12.5. Archived workspaces stay in place with their contents preserved;
    org admins can restore. Workspace owners do NOT get a delete action.
    """

    __tablename__ = "workspace"

    @classmethod
    def get_by_id(cls, workspace_id: int) -> "Workspace | None":
        """Get a workspace by its primary key."""
        return cls.query.get(workspace_id)

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    plan = db.Column(db.String(50), default="free")
    organization_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey("organization.id"), nullable=True)
    color = db.Column(db.String(10), nullable=False, default=DEFAULT_WORKSPACE_COLOR)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self):
        return f"<Workspace {self.slug}>"

    @property
    def color_hex(self) -> str:
        """Return the hex value for this workspace's color."""
        return WORKSPACE_COLORS.get(self.color, WORKSPACE_COLORS[DEFAULT_WORKSPACE_COLOR])

    @classmethod
    def create(
        cls,
        name: str,
        organization_id,
        creator_user_id: int,
        color: str | None = None,
    ) -> "Workspace":
        """Create a new workspace inside an organization.

        Centralized bootstrap: validates that the caller is an organization
        admin, creates the workspace, links the creator as the workspace admin
        (via their OrganizationUser), seeds default update channels,
        WorkspaceSettings, and AuthSettings.

        Args:
            name: Workspace display name (required, non-empty).
            organization_id: UUID of the parent Organization.
            creator_user_id: User.id of the user creating the workspace —
                must have an active OrganizationUser row with role='admin'
                for the target organization.
            color: Optional workspace color; defaults to DEFAULT_WORKSPACE_COLOR.

        Returns:
            The newly created Workspace (already flushed + committed).

        Raises:
            ValueError: If name is empty, color invalid, or caller is not
                an organization admin of the target organization.
        """
        from flask import g
        from modules.base.core.models.auth_settings import AuthSettings
        from modules.base.core.models.organization_user import OrganizationUser
        from modules.base.core.models.workspace_settings import WorkspaceSettings
        from modules.base.core.models.workspace_user import (
            EmployeeStatus,
            WorkspaceUser,
        )
        from modules.base.updates.models.channel import UpdateChannel

        name = (name or "").strip()
        if not name:
            raise ValueError("Workspace name is required.")

        color = color if color in WORKSPACE_COLORS else DEFAULT_WORKSPACE_COLOR

        # Caller must be an active organization admin of the target org.
        org_membership = OrganizationUser.get_for_user(creator_user_id, organization_id)
        if org_membership is None or not org_membership.is_organization_admin:
            raise ValueError(
                "Only organization admins can create a workspace in this organization."
            )

        # Generate a unique slug silently (Q1 — allow duplicate names).
        slug = cls._generate_unique_slug(name)

        workspace = cls(
            slug=slug,
            name=name,
            color=color,
            organization_id=organization_id,
        )
        db.session.add(workspace)
        db.session.flush()

        # Seed scoped rows inside the new workspace context.
        prev_workspace_id = getattr(g, "workspace_id", None)
        prev_organization_id = getattr(g, "organization_id", None)
        g.workspace_id = workspace.id
        g.organization_id = organization_id
        try:
            # Creator becomes workspace admin, linked to their OrganizationUser.
            member = WorkspaceUser(
                user_id=creator_user_id,
                workspace_id=workspace.id,
                organization_user_id=org_membership.id,
                role="admin",
                member_type="full",
                status=EmployeeStatus.ACTIVE,
                position="Owner",
            )
            db.session.add(member)

            settings = WorkspaceSettings.get_instance()
            settings.company_name = name

            auth = AuthSettings.get_instance()
            auth.local_auth_enabled = True

            UpdateChannel.create_default_channels()

            try:
                from modules.base.projects.models.project_status import ProjectStatus
                ProjectStatus.seed_defaults()
                from modules.base.tasks.models.task_status import TaskStatus
                TaskStatus.seed_defaults()
            except Exception:
                pass

            db.session.commit()
        finally:
            g.workspace_id = prev_workspace_id
            g.organization_id = prev_organization_id

        return workspace

    @classmethod
    def _generate_unique_slug(cls, name: str) -> str:
        """Slugify a name and suffix -2/-3/... until it's unique.

        Q1 resolution: duplicate names are accepted; the backend silently
        disambiguates slugs. Reserved slugs are skipped and a numeric suffix
        is appended until collision-free.
        """
        base = re.sub(r"[^a-z0-9-]", "", name.lower().replace(" ", "-"))
        base = re.sub(r"-+", "-", base).strip("-")[:46] or "workspace"

        candidate = base
        if candidate in RESERVED_SLUGS:
            candidate = f"{base}-{random.randint(100, 999)}"

        counter = 2
        while cls.query.filter_by(slug=candidate).first() is not None:
            candidate = f"{base}-{counter}"
            counter += 1
        return candidate

    # ------------------------------------------------------------------
    # Archive / Restore (Phase 6 §12.5)
    # ------------------------------------------------------------------

    def archive(self, actor_user_id: int) -> None:
        """Soft-delete this workspace and record an audit log entry.

        Only organization admins should call this — enforce at the route
        layer. Archive preserves all scoped content; no cascade.

        Args:
            actor_user_id: User.id of the organization admin performing the
                archive. Stamped on deleted_by_id and the audit log entry.

        Raises:
            ValueError: If this is the last active workspace in the org.
                The sole remaining workspace is treated as a default and
                cannot be archived until a second workspace exists.
        """
        if Workspace.active_count_for_organization(self.organization_id) <= 1:
            raise ValueError(
                "Cannot archive the last workspace in the organization. "
                "Create a second workspace first."
            )
        self.soft_delete(user_id=actor_user_id)
        self._record_audit("workspace_archive", actor_user_id)

    def restore_archived(self, actor_user_id: int) -> None:
        """Restore a previously archived workspace.

        Uses a distinct name from the mixin's `restore()` to keep the audit
        log step bundled. Clears deleted_at / deleted_by_id and logs.

        Args:
            actor_user_id: User.id of the organization admin restoring.
        """
        self.restore()
        self._record_audit("workspace_restore", actor_user_id)

    def _record_audit(self, action: str, actor_user_id: int) -> None:
        """Thin wrapper so archive()/restore_archived() share the logging path."""
        try:
            from modules.base.core.models.audit_log import AuditLog
        except ImportError:
            return
        AuditLog.record(
            action=action,
            target_type="workspace",
            target_id=str(self.id),
            organization_id=self.organization_id,
            actor_user_id=actor_user_id,
            workspace_id=self.id,
            metadata={"name": self.name, "slug": self.slug},
        )

    @classmethod
    def active_in_organization(cls, organization_id) -> list["Workspace"]:
        """Return non-archived workspaces in an organization, ordered by name."""
        return (
            cls.query.filter_by(organization_id=organization_id)
            .filter(cls.deleted_at.is_(None))
            .order_by(cls.name)
            .all()
        )

    @classmethod
    def active_count_for_organization(cls, organization_id) -> int:
        """Count non-archived workspaces in an organization."""
        return (
            cls.query.filter_by(organization_id=organization_id)
            .filter(cls.deleted_at.is_(None))
            .count()
        )

    @classmethod
    def count(cls) -> int:
        """Count all workspaces."""
        return cls.query.count()

    @classmethod
    def count_active(cls) -> int:
        """Count active (non-deleted) workspaces."""
        return cls.query.filter(cls.is_active.is_(True)).count()

    @classmethod
    def get_all(cls) -> list["Workspace"]:
        """Get all workspaces ordered by creation date (newest first)."""
        return cls.query.order_by(cls.created_at.desc()).all()

    @classmethod
    def get_recent(cls, limit: int = 5) -> list["Workspace"]:
        """Get most recently created workspaces."""
        return cls.query.order_by(cls.created_at.desc()).limit(limit).all()

    @classmethod
    def get_counts_by_organization(cls) -> dict[uuid.UUID, int]:
        """Get workspace count per organization (cross-org, for MSA admin)."""
        from sqlalchemy import func

        rows = (
            db.session.query(cls.organization_id, func.count(cls.id))
            .filter(cls.organization_id.isnot(None))
            .group_by(cls.organization_id)
            .all()
        )
        return dict(rows)

    @classmethod
    def for_organization(cls, organization_id: uuid.UUID) -> list["Workspace"]:
        """Get all workspaces for an organization, newest first."""
        return cls.query.filter_by(organization_id=organization_id).order_by(cls.created_at.desc()).all()

    @classmethod
    def archived_in_organization(cls, organization_id) -> list["Workspace"]:
        """Return archived workspaces in an organization, ordered by most recent."""
        return (
            cls.query.filter_by(organization_id=organization_id)
            .filter(cls.deleted_at.isnot(None))
            .order_by(cls.deleted_at.desc())
            .all()
        )

    @classmethod
    def delete_with_cascade(cls, workspace_id) -> None:
        """Delete a workspace using raw SQL to trigger ON DELETE CASCADE.

        The ORM delete tries to nullify FKs first, which violates NOT NULL
        constraints on dependent tables. Raw DELETE lets the database handle
        cascading deletes correctly.

        Args:
            workspace_id: UUID of the workspace to delete.
        """
        from sqlalchemy import text

        db.session.execute(text("DELETE FROM workspace WHERE id = :id"), {"id": workspace_id})
        db.session.commit()
