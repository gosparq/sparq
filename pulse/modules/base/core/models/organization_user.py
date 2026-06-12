# -----------------------------------------------------------------------------
# sparQ - OrganizationUser Model
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""OrganizationUser model — organization-level membership.

Sits between User and WorkspaceUser. A user can have one OrganizationUser row
per Organization they belong to, and many WorkspaceUser rows under each
OrganizationUser (one per workspace they've joined in that organization).

Roles:
    admin    — organization administrator (§3.4). Can manage billing, SSO,
               workspaces (create/archive), and has read-only audit access
               to workspaces they're not a member of (§12.2).
    member   — regular organization member.
    external — limited member reserved for the external_project_invites spec
               (Phase 4). Ships in the CHECK constraint now to avoid a future
               schema change; not used by any logic until that spec lands.

"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.raise_on_lazy import LAZY


ORGANIZATION_USER_ROLES = ("admin", "member", "external")


@ModelRegistry.register
class OrganizationUser(db.Model):
    """Membership record linking a User to an Organization."""

    __tablename__ = "organization_user"
    __table_args__ = (
        db.UniqueConstraint("organization_id", "user_id", name="uq_organization_user"),
        db.UniqueConstraint("organization_id", "employee_id", name="uq_org_user_employee_id"),
        db.UniqueConstraint("organization_id", "clock_pin", name="uq_org_user_clock_pin"),
    )

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(
        db.UUID(as_uuid=True),
        db.ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = db.Column(db.String(20), nullable=False, default="member")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    joined_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    invited_by_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    auto_join_banner_dismissed = db.Column(db.Boolean, default=False, nullable=False)

    # Employment fields (org-level — migrated from workspace_user)
    employee_id = db.Column(db.String(20), nullable=True)
    clock_pin = db.Column(db.String(4), nullable=True)
    labor_cost_rate = db.Column(db.Numeric(10, 2), nullable=True)
    bill_rate = db.Column(db.Numeric(10, 2), nullable=True)
    employment_status = db.Column(db.String(20), nullable=True, default="ACTIVE")

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    organization = db.relationship(
        "Organization",
        foreign_keys=[organization_id],
        backref=db.backref("organization_users", lazy="dynamic"),
        lazy=LAZY,
    )
    user = db.relationship(
        "User",
        foreign_keys=[user_id],
        backref=db.backref("organization_memberships", lazy="dynamic"),
        lazy=LAZY,
    )
    invited_by = db.relationship("User", foreign_keys=[invited_by_id], lazy=LAZY)
    workspace_users = db.relationship(
        "WorkspaceUser",
        foreign_keys="WorkspaceUser.organization_user_id",
        backref=db.backref("organization_user", lazy="joined"),
        lazy="dynamic",
    )

    def __repr__(self) -> str:
        return f"<OrganizationUser org={self.organization_id} user={self.user_id} role={self.role}>"

    # ------------------------------------------------------------------
    # Employment properties
    # ------------------------------------------------------------------

    @property
    def formatted_labor_cost_rate(self) -> str | None:
        """Return formatted labor cost rate."""
        if self.labor_cost_rate:
            return f"${self.labor_cost_rate:,.2f}/hr"
        return None

    @property
    def formatted_bill_rate(self) -> str | None:
        """Return formatted bill rate."""
        if self.bill_rate:
            return f"${self.bill_rate:,.2f}/hr"
        return None

    @property
    def is_employment_active(self) -> bool:
        """Check if employment status is Active."""
        return self.employment_status == "ACTIVE"

    # ------------------------------------------------------------------
    # Role helpers
    # ------------------------------------------------------------------

    @property
    def is_organization_admin(self) -> bool:
        """Is this user an organization-level admin?"""
        return self.role == "admin" and self.is_active

    def set_role(self, role: str) -> None:
        """Change this membership's organization role.

        Args:
            role: One of 'admin', 'member', 'external'.
        """
        if role not in ORGANIZATION_USER_ROLES:
            raise ValueError(f"Invalid role '{role}'; must be one of {ORGANIZATION_USER_ROLES}")
        self.role = role
        db.session.commit()

    def deactivate(self) -> None:
        """Mark the organization membership inactive (reversible)."""
        self.is_active = False
        db.session.commit()

    def reactivate(self) -> None:
        """Mark the organization membership active again."""
        self.is_active = True
        db.session.commit()

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    @classmethod
    def get_by_id(cls, organization_user_id: int) -> OrganizationUser | None:
        """Get an organization_user row by primary key."""
        return cls.query.get(organization_user_id)

    @classmethod
    def get_for_user(
        cls, user_id: int, organization_id
    ) -> OrganizationUser | None:
        """Get the membership row for a (user, organization) pair."""
        return cls.query.filter_by(
            user_id=user_id, organization_id=organization_id
        ).first()

    @classmethod
    def list_for_user(cls, user_id: int, active_only: bool = True) -> list[OrganizationUser]:
        """All organization memberships for a user, active-only by default."""
        q = cls.query.filter_by(user_id=user_id)
        if active_only:
            q = q.filter_by(is_active=True)
        return q.order_by(cls.joined_at.asc()).all()

    @classmethod
    def list_for_organization(
        cls, organization_id, active_only: bool = True
    ) -> list[OrganizationUser]:
        """All memberships in a given organization."""
        q = cls.query.filter_by(organization_id=organization_id)
        if active_only:
            q = q.filter_by(is_active=True)
        return q.order_by(cls.joined_at.asc()).all()

    @classmethod
    def get_active_for_org(cls, organization_id) -> list[OrganizationUser]:
        """All active members with Active employment status in an organization."""
        return cls.query.filter_by(
            organization_id=organization_id, is_active=True, employment_status="ACTIVE"
        ).order_by(cls.joined_at.asc()).all()

    @classmethod
    def get_by_pin(cls, pin: str, organization_id) -> OrganizationUser | None:
        """Look up an org member by clock PIN within an organization."""
        if not pin:
            return None
        return cls.query.filter_by(
            organization_id=organization_id, clock_pin=pin, is_active=True
        ).first()

    @classmethod
    def get_landing_data(cls, user_id: int) -> list[dict]:
        """Build org-landing page data for all of a user's organizations."""
        from modules.base.core.models.workspace import Workspace
        from modules.base.core.models.workspace_user import WorkspaceUser

        memberships = cls.list_for_user(user_id)
        if not memberships:
            return []

        user_ts_ids = {
            tu.workspace_id for tu in WorkspaceUser.query.filter_by(user_id=user_id).filter(
                WorkspaceUser.deleted_at.is_(None),
            ).all()
        }

        result = []
        for om in memberships:
            org = om.organization
            ts_all = Workspace.query.filter_by(
                organization_id=org.id,
            ).filter(Workspace.deleted_at.is_(None)).all()

            workspaces = [
                {"id": ts.id, "name": ts.name, "is_member": ts.id in user_ts_ids}
                for ts in ts_all
            ]

            members = cls.list_for_organization(org.id)
            directory = [
                {"user": m.user, "role": m.role}
                for m in members
                if m.user and m.user.is_active
            ]
            directory.sort(key=lambda r: ((r["user"].first_name or ""), (r["user"].last_name or "")))

            result.append({
                "org": org,
                "org_user": om,
                "workspaces": workspaces,
                "directory": directory,
            })

        return result

    @classmethod
    def count_admins(cls, organization_id) -> int:
        """Count active organization admins for a given organization."""
        return cls.query.filter_by(
            organization_id=organization_id, role="admin", is_active=True
        ).count()

    @classmethod
    def get_member_counts(cls) -> dict[uuid.UUID, int]:
        """Get active member count per organization (cross-org, for MSA admin)."""
        from sqlalchemy import func

        rows = (
            db.session.query(cls.organization_id, func.count(cls.id))
            .filter(cls.is_active.is_(True))
            .group_by(cls.organization_id)
            .all()
        )
        return dict(rows)

    @classmethod
    def get_members_for_organization(cls, organization_id: uuid.UUID, active_only: bool = False) -> list[dict]:
        """Get structured member data for an organization (MSA admin view)."""
        memberships = cls.list_for_organization(organization_id, active_only=active_only)
        return [
            {"user": m.user, "role": m.role, "is_active": m.is_active, "joined_at": m.joined_at}
            for m in memberships
        ]

    # ------------------------------------------------------------------
    # Creation
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        organization_id,
        user_id: int,
        role: str = "member",
        invited_by_id: int | None = None,
    ) -> OrganizationUser:
        """Create a new organization membership.

        Raises:
            ValueError: if role is invalid.
        """
        if role not in ORGANIZATION_USER_ROLES:
            raise ValueError(f"Invalid role '{role}'; must be one of {ORGANIZATION_USER_ROLES}")
        membership = cls(
            organization_id=organization_id,
            user_id=user_id,
            role=role,
            invited_by_id=invited_by_id,
            is_active=True,
        )
        db.session.add(membership)
        db.session.commit()
        return membership

    @classmethod
    def get_or_create(
        cls,
        organization_id,
        user_id: int,
        role: str = "member",
        invited_by_id: int | None = None,
    ) -> OrganizationUser:
        """Return the existing organization_user row or create it.

        If the row exists but is deactivated, it is reactivated (but the role
        is NOT changed — callers that need to upgrade the role should call
        `set_role` explicitly after).
        """
        existing = cls.get_for_user(user_id, organization_id)
        if existing:
            if not existing.is_active:
                existing.reactivate()
            return existing
        return cls.create(
            organization_id=organization_id,
            user_id=user_id,
            role=role,
            invited_by_id=invited_by_id,
        )

    # ------------------------------------------------------------------
    # Auto-join banner
    # ------------------------------------------------------------------

    def dismiss_auto_join_banner(self) -> None:
        """Mark the rule-3 auto-join confirmation banner as dismissed."""
        self.auto_join_banner_dismissed = True
        db.session.commit()

    # ------------------------------------------------------------------
    # Leave-org guard
    # ------------------------------------------------------------------

    @classmethod
    def can_leave(cls, user_id: int, organization_id) -> tuple[bool, str]:
        """Check whether a user can leave an organization.

        Returns:
            (True, "") if allowed, or (False, reason) if blocked.
        """
        from modules.base.core.models.organization import Organization

        org = Organization.query.get(organization_id)
        if org is None:
            return False, "Organization not found."
        if org.owner_id == user_id:
            return False, "You are the owner of this organization. Transfer ownership before leaving."
        return True, ""
