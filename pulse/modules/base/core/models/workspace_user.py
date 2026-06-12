# -----------------------------------------------------------------------------
# sparQ - WorkspaceUser Model
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""WorkspaceUser model — per-workspace membership and employment data.

This model replaces the old Employee model. Each row represents a user's
membership in a workspace, including their role, department, position,
salary, and other employment-specific data.

A user can belong to multiple workspaces, each with different roles and
employment data. This is the many-to-many join between User and Workspace.

Classes:
    EmployeeStatus: Enum of employment states.
    EmployeeType: Enum of employment types.
    SalaryType: Salary payment type.
    TerminationReason: Reason for termination.
    WorkspaceUser: Workspace membership model.

Example:
    Creating a workspace membership::

        membership = WorkspaceUser.create(
            email="john@company.com",
            first_name="John",
            last_name="Doe",
            department="Engineering",
            position="Developer",
            type=EmployeeType.FULL_TIME
        )

    Querying memberships::

        active = WorkspaceUser.scoped().filter_by(status=EmployeeStatus.ACTIVE).all()
"""

import random
from datetime import datetime
from enum import Enum

from flask import g

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.mixins import SoftDeleteMixin
from system.db.workspace import WorkspaceMixin
from system.db.raise_on_lazy import LAZY


class TerminationReason(str, Enum):
    """Reason for employee termination."""

    RESIGNATION = "Resignation"
    LAYOFF = "Layoff"
    TERMINATION_FOR_CAUSE = "Termination for Cause"
    RETIREMENT = "Retirement"
    CONTRACT_END = "Contract End"
    MUTUAL_AGREEMENT = "Mutual Agreement"
    OTHER = "Other"


class EmployeeStatus(Enum):
    """Employee employment status."""

    ACTIVE = "Active"
    ON_LEAVE = "On Leave"
    TERMINATED = "Terminated"
    CONTRACTOR = "Contractor"
    INACTIVE = "Inactive"


class EmployeeType(Enum):
    """Employee employment type classification."""

    FULL_TIME = "Full Time"
    PART_TIME = "Part Time"
    CONTRACTOR = "Contractor"
    INTERN = "Intern"


class Gender(Enum):
    """Gender options."""

    MALE = "Male"
    FEMALE = "Female"
    OTHER = "Other"
    PREFER_NOT_TO_SAY = "Prefer not to say"


class SalaryType(Enum):
    """Salary payment type classification."""

    HOURLY = "Hourly"
    YEARLY = "Yearly"


def _generate_employee_id():
    """Generate unique employee ID."""
    return f"EMP{random.randint(10000, 99999)}"


@ModelRegistry.register
class WorkspaceUser(db.Model, WorkspaceMixin, SoftDeleteMixin):
    """Workspace membership — links User to Workspace with employment data.

    This replaces the old Employee model. Each row is one user's membership
    in one workspace. A user can have multiple memberships (one per workspace).

    Attributes:
        user_id: Foreign key to User account.
        role: Workspace role (admin, member, viewer).
        department: Department name.
        position: Job title/position.
        employee_id: Auto-generated identifier (e.g., EMP12345).
        status: EmployeeStatus (Active, On Leave, etc.).
        type: EmployeeType (Full Time, Part Time, etc.).
        start_date: Employment start date.
        salary: Salary amount.
        salary_type: Hourly or Yearly.
        labor_cost_rate: Hourly cost rate for time tracking.
        bill_rate: Hourly billing rate for customer invoicing.
        clock_pin: 4-digit PIN for time clock kiosk.
        manager_id: FK to manager WorkspaceUser.
        termination_date: Date of termination.
        termination_reason: Reason for termination.

    Relationships:
        user: Associated User account.
        manager: Manager WorkspaceUser.
        reports: WorkspaceUsers who report to this member.
    """

    __tablename__ = "workspace_user"
    __table_args__ = (
        db.UniqueConstraint("user_id", "workspace_id", name="uq_workspace_user"),
        db.UniqueConstraint("employee_id", "workspace_id", name="uq_workspace_user_employee_id"),
        db.Index("ix_workspace_user_org_ws_active", "organization_id", "workspace_id", "deleted_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False)

    # Organization-level membership parent (added Phase 2 — may be NULL briefly
    # during the backfill window for legacy workspaces without an organization).
    organization_user_id = db.Column(
        db.Integer,
        db.ForeignKey("organization_user.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Workspace role
    role = db.Column(db.String(20), default="member", nullable=False)  # admin, member, viewer

    # Member type at the workspace level: 'full' counts toward the 8/12 cap and
    # has full access; 'limited' is reserved for external_project_invites (Phase 4).
    # Ships dormant at 'full' — no logic references 'limited' until that spec lands.
    member_type = db.Column(db.String(20), default="full", nullable=False)

    # Permission areas (comma-separated: "hr,finance,operations")
    permissions = db.Column(db.Text, default="", nullable=False)

    # Employment fields
    employee_id = db.Column(db.String(20), default=_generate_employee_id)
    department = db.Column(db.String(100))
    position = db.Column(db.String(100))
    status = db.Column(db.Enum(EmployeeStatus), default=EmployeeStatus.ACTIVE)
    type = db.Column(db.Enum(EmployeeType), default=EmployeeType.FULL_TIME)
    start_date = db.Column(db.Date)

    # Compensation
    salary = db.Column(db.Numeric(10, 2))
    salary_type = db.Column(db.Enum(SalaryType), default=SalaryType.YEARLY)
    labor_cost_rate = db.Column(db.Numeric(10, 2))
    bill_rate = db.Column(db.Numeric(10, 2))

    # Work contact phone (workspace-level, distinct from User.personal_phone)
    phone = db.Column(db.String(20))

    # Time clock PIN (4-digit for kiosk mode)
    clock_pin = db.Column(db.String(4), nullable=True)

    # Termination
    termination_date = db.Column(db.Date, nullable=True)
    termination_reason = db.Column(db.Enum(TerminationReason), nullable=True)

    # Profile (v2 team sync)
    bio = db.Column(db.Text, nullable=True)
    working_style = db.Column(db.Text, nullable=True)
    intro_posted = db.Column(db.Boolean, default=False)
    pulse_exempt = db.Column(db.Boolean, default=False, nullable=False)

    # Open Door signal
    open_door_until = db.Column(db.DateTime, nullable=True)

    # Organizational hierarchy
    manager_id = db.Column(db.Integer, db.ForeignKey("workspace_user.id"), nullable=True)
    reports = db.relationship(
        "WorkspaceUser", backref=db.backref("manager", remote_side="WorkspaceUser.id", lazy=LAZY),
        lazy=LAZY,
    )

    # Relationship to User (one-to-many: user has many workspace memberships)
    # foreign_keys needed because SoftDeleteMixin adds a second FK to user (deleted_by_id)
    user = db.relationship(
        "User",
        foreign_keys=[user_id],
        backref=db.backref("workspace_memberships", lazy="dynamic"),
        lazy=LAZY,
    )

    # Relationship to Workspace (for workspace picker and display)
    workspace = db.relationship(
        "Workspace",
        foreign_keys="WorkspaceUser.workspace_id",
        backref=db.backref("members", lazy="dynamic"),
        lazy=LAZY,
    )

    # -------------------------------------------------------------------------
    # Scoped query override (auto-excludes soft-deleted members)
    # -------------------------------------------------------------------------

    @classmethod
    def scoped(cls) -> "_ScopedQuery":  # noqa: F821
        """Workspace-scoped membership query (always filters by g.workspace_id).

        WorkspaceUser is the membership join — it is always keyed to a single
        workspace and never "org-wide", so this override sidesteps the
        org-first mixin branching and preserves the historical workspace-only
        filter. Also excludes soft-deleted members.
        """
        from system.db.workspace import _ScopedQuery

        workspace_id = getattr(g, "workspace_id", None)
        if workspace_id is None:
            raise RuntimeError(
                f"{cls.__name__}.scoped() called without workspace context. "
                "Use .for_workspace(id) or WorkspaceUser.for_organization(id) "
                "for cross-workspace access."
            )
        q = cls.query.filter_by(workspace_id=workspace_id).filter(
            cls.deleted_at.is_(None)
        )
        return _ScopedQuery(q, cls)

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------

    @property
    def permission_set(self) -> set[str]:
        """Return permissions as a set of lowercase area names."""
        if not self.permissions:
            return set()
        return {p.strip().lower() for p in self.permissions.split(",") if p.strip()}

    def has_permission(self, area: str) -> bool:
        """Check if member has access to a permission area.

        Admins always have all permissions.

        Args:
            area: Permission area name (hr, finance, operations).
        """
        if self.role == "admin":
            return True
        return area.lower() in self.permission_set

    def set_permissions(self, areas: list[str]) -> None:
        """Set permission areas.

        Args:
            areas: List of permission area names.
        """
        self.permissions = ",".join(a.strip().lower() for a in areas if a.strip())

    @property
    def has_active_onboarding(self) -> bool:
        """Check if member has an active (non-completed/cancelled) onboarding record."""
        from modules.base.people.models.onboarding import OnboardingStatus

        record = self.onboarding_record
        return record is not None and record.status not in (
            OnboardingStatus.COMPLETED,
            OnboardingStatus.CANCELLED,
        )

    @property
    def formatted_salary(self):
        """Return formatted salary with currency and type."""
        if self.salary:
            suffix = "/hr" if self.salary_type == SalaryType.HOURLY else "/yr"
            return f"${self.salary:,.2f}{suffix}"
        return None

    @property
    def formatted_labor_cost_rate(self):
        """Return formatted labor cost rate."""
        if self.labor_cost_rate:
            return f"${self.labor_cost_rate:,.2f}/hr"
        return None

    @property
    def formatted_bill_rate(self):
        """Return formatted bill rate."""
        if self.bill_rate:
            return f"${self.bill_rate:,.2f}/hr"
        return None

    @property
    def is_contactable(self):
        """Check if member should receive system emails."""
        return self.status == EmployeeStatus.ACTIVE

    @property
    def door_is_open(self):
        """Check if this member's door is currently open."""
        return self.open_door_until is not None and self.open_door_until > datetime.utcnow()

    @property
    def door_minutes_remaining(self):
        """Minutes remaining on open door signal."""
        if not self.door_is_open:
            return 0
        delta = self.open_door_until - datetime.utcnow()
        return max(0, int(delta.total_seconds() / 60))

    # -------------------------------------------------------------------------
    # Class Methods
    # -------------------------------------------------------------------------

    @classmethod
    def get_workspace_users(cls) -> list["User"]:  # noqa: F821
        """Get all active User accounts in the current workspace.

        Excludes soft-deleted (removed) members.
        """
        from modules.base.core.models.user import User
        return (
            User.query
            .join(cls, cls.user_id == User.id)
            .filter(cls.workspace_id == g.workspace_id)
            .filter(cls.deleted_at.is_(None))
            .filter(User.is_active.is_(True))
            .order_by(User.first_name, User.last_name)
            .all()
        )

    @classmethod
    def create(
        cls, email, password=None, first_name=None, last_name=None, is_admin=False, **kwargs
    ):
        """Create new workspace membership, creating user if needed.

        Args:
            email: User email.
            password: User password. Random if not provided.
            first_name: User first name.
            last_name: User last name.
            is_admin: Whether user is admin in this workspace.
            **kwargs: Additional employment fields.

        Returns:
            Created WorkspaceUser instance.
        """
        from modules.base.core.models.organization_user import OrganizationUser
        from modules.base.core.models.workspace import Workspace
        from modules.base.core.models.user import User

        try:
            user = User.get_by_email(email)

            if not user:
                user = User.create(
                    email=email,
                    password=password or User.generate_random_password(),
                    first_name=first_name,
                    last_name=last_name,
                )

            # Determine role
            role = "admin" if is_admin else "member"

            # Resolve the OrganizationUser parent for this (org, user) pair.
            # Required whenever the target workspace has an organization.
            organization_user_id = None
            workspace = Workspace.query.get(g.workspace_id)
            if workspace and workspace.organization_id:
                org_user = OrganizationUser.get_or_create(
                    organization_id=workspace.organization_id,
                    user_id=user.id,
                    role="admin" if is_admin else "member",
                )
                organization_user_id = org_user.id

            membership = cls(
                user=user,
                role=role,
                organization_user_id=organization_user_id,
                department=kwargs.get("department", ""),
                position=kwargs.get("position", ""),
                type=EmployeeType[kwargs.get("type", "FULL_TIME")],
                status=kwargs.get("status", EmployeeStatus.ACTIVE),
                start_date=kwargs.get("start_date", datetime.utcnow().date()),
                phone=kwargs.get("phone", ""),
                salary=kwargs.get("salary"),
                salary_type=kwargs.get("salary_type", SalaryType.YEARLY),
                labor_cost_rate=kwargs.get("labor_cost_rate"),
                bill_rate=kwargs.get("bill_rate"),
            )

            # Set personal fields on user if provided
            for field in ("birthday", "gender", "emergency_contact_name",
                          "emergency_contact_phone", "emergency_contact_relationship",
                          "social_media"):
                if field in kwargs and kwargs[field]:
                    setattr(user, field, kwargs[field])

            # Map address fields to user
            for field in ("address", "address_2", "city", "state", "zip_code", "country"):
                if field in kwargs and kwargs[field]:
                    setattr(user, field, kwargs[field])

            # Map phone to personal_phone on user if not already set
            if kwargs.get("phone") and not user.personal_phone:
                user.personal_phone = kwargs["phone"]

            db.session.add(membership)
            db.session.commit()

            # Auto-follow status templates for new member
            try:
                from modules.base.updates.models.follow import UpdateFollow
                UpdateFollow.auto_follow_member(membership.id)
            except Exception:
                pass  # Non-critical — member is still created

            return membership

        except Exception as e:
            db.session.rollback()
            raise e

    @classmethod
    def get_by_email(cls, email):
        """Get workspace member by email."""
        from modules.base.core.models.user import User
        return cls.scoped().join(User, cls.user_id == User.id).filter(User.email == email).first()

    @classmethod
    def get_by_user_id(cls, user_id: int) -> "WorkspaceUser | None":
        """Get workspace member by user ID."""
        cache_key = ("by_user_id", user_id, getattr(g, "workspace_id", None))
        try:
            cache = getattr(g, "_tsu_cache", None)
            if cache is None:
                cache = {}
                g._tsu_cache = cache
            if cache_key in cache:
                return cache[cache_key]
        except Exception:
            cache = None
        result = cls.scoped().filter_by(user_id=user_id).first()
        if cache is not None:
            cache[cache_key] = result
        return result

    @classmethod
    def create_for_onboarding(cls, user, **kwargs) -> "WorkspaceUser":
        """Create an INACTIVE membership for onboarding.

        Args:
            user: The User account to link.
            **kwargs: Employment fields.

        Returns:
            The created WorkspaceUser instance.
        """
        from modules.base.core.models.organization_user import OrganizationUser
        from modules.base.core.models.workspace import Workspace

        organization_user_id = None
        workspace = Workspace.query.get(g.workspace_id)
        if workspace and workspace.organization_id:
            org_user = OrganizationUser.get_or_create(
                organization_id=workspace.organization_id,
                user_id=user.id,
                role="member",
            )
            organization_user_id = org_user.id

        membership = cls(
            user_id=user.id,
            organization_user_id=organization_user_id,
            status=EmployeeStatus.INACTIVE,
            role="member",
            **kwargs,
        )
        db.session.add(membership)
        db.session.flush()
        return membership

    @classmethod
    def get_member_counts(cls) -> dict:
        """Get member count per workspace (cross-workspace, for MSA admin).

        Returns:
            Dict mapping workspace_id (UUID) to member count (int).
        """
        from sqlalchemy import func

        rows = (
            db.session.query(cls.workspace_id, func.count(cls.id))
            .group_by(cls.workspace_id)
            .all()
        )
        return dict(rows)

    @classmethod
    def get_admin_emails(cls) -> dict:
        """Get the highest-role user's email per workspace (cross-workspace, for MSA admin).

        Returns admin > manager > member, picking the first by ID on ties.

        Returns:
            Dict mapping workspace_id (UUID) to email (str).
        """
        from modules.base.core.models.user import User

        rows = (
            db.session.query(cls.workspace_id, User.email, cls.role)
            .join(User, User.id == cls.user_id)
            .order_by(
                db.case(
                    (cls.role == "admin", 0),
                    (cls.role == "manager", 1),
                    (cls.role == "member", 2),
                    else_=3,
                ),
                cls.id.asc(),
            )
            .all()
        )
        admin_map = {}
        for ws_id, email, role in rows:
            if ws_id not in admin_map:
                admin_map[ws_id] = email
        return admin_map

    # -------------------------------------------------------------------------
    # Instance Methods
    # -------------------------------------------------------------------------

    def terminate(self, reason: TerminationReason, termination_date=None):
        """Terminate membership and deactivate the user account.

        Args:
            reason: TerminationReason enum value.
            termination_date: Date of termination (defaults to today).

        Returns:
            Self for chaining.
        """
        from datetime import date

        self.status = EmployeeStatus.TERMINATED
        self.termination_date = termination_date or date.today()
        self.termination_reason = reason
        self.user.is_active = False
        db.session.commit()
        return self

    def rehire(self):
        """Rehire a terminated member and reactivate their user account.

        Returns:
            Self for chaining.
        """
        self.status = EmployeeStatus.ACTIVE
        self.termination_date = None
        self.termination_reason = None
        self.user.is_active = True
        db.session.commit()
        return self

    def remove_from_workspace(self):
        """Remove this member from the workspace via soft delete.

        Soft-deletes the membership row (sets deleted_at) while leaving the
        User account intact. The member loses access to this workspace but
        can still log in to other workspaces or be re-invited later.

        Raises:
            ValueError: If trying to remove self or the last admin.
        """
        from flask_login import current_user

        # Guard: cannot remove yourself
        if current_user.workspace_membership and current_user.workspace_membership.id == self.id:
            raise ValueError("Cannot remove yourself from the workspace")

        # Guard: cannot remove the last admin
        if self.role == "admin":
            admin_count = (
                WorkspaceUser.query
                .filter_by(workspace_id=self.workspace_id, role="admin")
                .filter(WorkspaceUser.deleted_at.is_(None))
                .count()
            )
            if admin_count <= 1:
                raise ValueError("Cannot remove the only administrator")

        if self.user.is_sample:
            from system.db.seed_sample import remove_sample_data
            remove_sample_data(self.workspace_id)
            return

        self.soft_delete()

    def reactivate_for_onboarding(self, **kwargs) -> "WorkspaceUser":
        """Reactivate an inactive member for re-onboarding.

        Args:
            **kwargs: Employment fields to update.

        Returns:
            Self for chaining.
        """
        self.status = EmployeeStatus.INACTIVE
        self.user.is_active = True

        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

        db.session.commit()
        return self

    def activate(self) -> None:
        """Promote member from INACTIVE to ACTIVE."""
        self.status = EmployeeStatus.ACTIVE
        db.session.commit()

    # -------------------------------------------------------------------------
    # Invite Helpers
    # -------------------------------------------------------------------------

    @classmethod
    def is_member(cls, user_id: int, workspace_id) -> bool:
        """Check if a user is already a member of a specific workspace.

        Args:
            user_id: The User ID to check.
            workspace_id: The workspace UUID to check.

        Returns:
            True if a membership exists, False otherwise.
        """
        return cls.query.filter_by(
            user_id=user_id, workspace_id=workspace_id
        ).first() is not None

    @classmethod
    def create_from_invite(
        cls,
        email: str,
        workspace_id,
        first_name: str | None = None,
        last_name: str | None = None,
        password: str | None = None,
    ) -> "WorkspaceUser":
        """Create a User + WorkspaceUser membership from an invite.

        If the user already exists (by email), only the membership is created.
        The user is always assigned role='member' at the workspace level.

        An OrganizationUser row is created (or reused) for the invitee on the
        workspace's parent organization first, then the WorkspaceUser is linked
        back to it via organization_user_id. This preserves the invariant that
        every workspace membership has an organization membership parent.

        Args:
            email: Invitee email address.
            workspace_id: The workspace to join.
            first_name: First name (required for new users).
            last_name: Last name (required for new users).
            password: Password (required for new users).

        Returns:
            The created WorkspaceUser membership.

        Raises:
            ValueError: If creating a new user but name/password are missing.
        """
        from modules.base.core.models.organization_user import OrganizationUser
        from modules.base.core.models.workspace import Workspace
        from modules.base.core.models.user import User

        user = User.get_by_email(email)

        if not user:
            if not first_name or not last_name or not password:
                raise ValueError("first_name, last_name, and password are required for new users")
            user = User(
                email=email,
                first_name=first_name,
                last_name=last_name,
            )
            user.password = password
            db.session.add(user)
            db.session.flush()

        # Resolve the OrganizationUser parent.
        organization_user_id = None
        workspace = Workspace.query.get(workspace_id)
        if workspace and workspace.organization_id:
            org_user = OrganizationUser.get_or_create(
                organization_id=workspace.organization_id,
                user_id=user.id,
                role="member",
            )
            organization_user_id = org_user.id

        membership = cls(
            user_id=user.id,
            workspace_id=workspace_id,
            organization_user_id=organization_user_id,
            role="member",
        )
        db.session.add(membership)
        db.session.commit()
        return membership
