# -----------------------------------------------------------------------------
# sparQ - AuditLog Model
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""AuditLog — organization-level audit trail.

Records actions taken by organization admins and system-level events that
need to be auditable by the organization owner.

Coverage (v1 per the Phase 6 plan):
    - workspace_audit_access — org admin viewed a workspace they're not a member of
    - workspace_archive / workspace_restore
    - workspace_create
    - organization_member_role_change
    - invite_accept

Not yet covered (deferred to later): workspace-admin role changes inside a
single workspace, org-settings edits. Easy to add once the use case appears.

Example:
    AuditLog.record(
        action="workspace_audit_access",
        target_type="workspace",
        target_id=str(workspace.id),
        workspace_id=workspace.id,
    )

"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.workspace import OrganizationMixin


@ModelRegistry.register
class AuditLog(db.Model, OrganizationMixin):
    """A single entry in the organization-level audit trail."""

    __tablename__ = "audit_log"

    id = db.Column(db.Integer, primary_key=True)
    actor_user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_organization_user_id = db.Column(
        db.Integer,
        db.ForeignKey("organization_user.id", ondelete="SET NULL"),
        nullable=True,
    )
    action = db.Column(db.String(100), nullable=False, index=True)
    target_type = db.Column(db.String(50), nullable=False)
    target_id = db.Column(db.String(100), nullable=True)
    workspace_id = db.Column(
        db.UUID(as_uuid=True),
        db.ForeignKey("workspace.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    metadata_json = db.Column(db.JSON, nullable=True)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    actor = db.relationship(
        "User",
        foreign_keys=[actor_user_id],
        lazy="joined",
    )
    actor_organization_user = db.relationship(
        "OrganizationUser",
        foreign_keys=[actor_organization_user_id],
        lazy="joined",
    )

    # ------------------------------------------------------------------
    # Record
    # ------------------------------------------------------------------

    @classmethod
    def record(
        cls,
        action: str,
        target_type: str,
        target_id: str | None = None,
        *,
        organization_id=None,
        actor_user_id: int | None = None,
        workspace_id=None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Write a new audit log entry.

        Args:
            action: Snake_case event name (e.g. "workspace_archive").
            target_type: Entity type the event is about (e.g. "workspace").
            target_id: Optional stable identifier for the target (stringified).
            organization_id: Owning organization. Defaults to g.organization_id.
            actor_user_id: Acting user. Defaults to current_user.id.
            workspace_id: Optional workspace context.
            metadata: Arbitrary JSON-serializable payload.

        Returns:
            The persisted AuditLog row.
        """
        from flask import g
        from flask_login import current_user
        from modules.base.core.models.organization_user import OrganizationUser

        org_id = organization_id or getattr(g, "organization_id", None)

        uid = actor_user_id
        if uid is None and current_user and current_user.is_authenticated:
            uid = current_user.id

        actor_org_user_id = None
        if uid is not None and org_id is not None:
            org_membership = OrganizationUser.get_for_user(uid, org_id)
            if org_membership is not None:
                actor_org_user_id = org_membership.id

        entry = cls(
            organization_id=org_id,
            actor_user_id=uid,
            actor_organization_user_id=actor_org_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            workspace_id=workspace_id,
            metadata_json=metadata or None,
        )
        db.session.add(entry)
        db.session.commit()
        return entry

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    @classmethod
    def list_for_organization(
        cls,
        organization_id,
        *,
        action: str | None = None,
        limit: int = 100,
    ) -> list[AuditLog]:
        """List audit entries for an organization, newest first."""
        q = cls.query.filter_by(organization_id=organization_id)
        if action:
            q = q.filter_by(action=action)
        return q.order_by(cls.created_at.desc()).limit(limit).all()
