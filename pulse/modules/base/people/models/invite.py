# -----------------------------------------------------------------------------
# sparQ - WorkspaceInvite Model
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""WorkspaceInvite model — lightweight email invitations to join a workspace.

This model tracks invite tokens sent by admins to invite new users (or existing
users from other workspaces) into their workspace. It is separate from the
onboarding system, which handles tasks, documents, and approvals.

Classes:
    InviteStatus: Enum of invite states.
    WorkspaceInvite: Invite record with secure token.

Example:
    Creating and sending an invite::

        invite = WorkspaceInvite.create(
            email="jane@example.com",
            invited_by_id=current_user.workspace_membership.id,
        )
        url = url_for("people_bp.accept_invite", token=invite.token, _external=True)
"""

import secrets
import uuid as _uuid
from datetime import datetime, timedelta, timezone
from enum import Enum

from flask_login import current_user
from sqlalchemy.orm import validates

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.mixins import AuditMixin
from system.db.workspace import WorkspaceMixin


class InviteStatus(Enum):
    """Status of a workspace invite."""

    PENDING = "Pending"
    ACCEPTED = "Accepted"
    CANCELLED = "Cancelled"


TOKEN_EXPIRY_DAYS = 7


@ModelRegistry.register
class WorkspaceInvite(db.Model, WorkspaceMixin, AuditMixin):
    """A lightweight invite for a user to join a workspace.

    Attributes:
        email: The invitee's email address.
        invited_by_id: FK to WorkspaceUser who sent the invite.
        token: Unique, cryptographically secure token for the invite link.
        token_expires: When the token expires (default 7 days from creation).
        status: Current invite status (Pending, Accepted, Cancelled).
        accepted_at: Timestamp when the invite was accepted.
        created_at: Timestamp when the invite was created.
    """

    __tablename__ = "workspace_invite"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, index=True)
    invited_by_id = db.Column(
        db.Integer,
        db.ForeignKey("workspace_user.id", ondelete="SET NULL"),
        nullable=True,
    )
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    token_expires = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.Enum(InviteStatus), default=InviteStatus.PENDING, nullable=False)
    accepted_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, onupdate=db.func.current_timestamp())

    # Multi-workspace invite scope (Phase 3).
    # workspace_id (from WorkspaceMixin) remains the invite's "home workspace"
    # for backward compatibility with workspace-admin invite flow.
    # scoped_workspace_ids: list of workspace UUIDs the invitee should be added to
    #   - NULL with invite_all_workspaces=False → legacy single-workspace (uses workspace_id).
    #   - Empty array with invite_all_workspaces=False → org-only invite.
    #   - Populated → add WorkspaceUser in each listed workspace.
    #   - invite_all_workspaces=True → snapshot all current workspaces at accept.
    scoped_workspace_ids = db.Column(
        db.JSON,
        nullable=True,
    )
    invite_all_workspaces = db.Column(db.Boolean, nullable=False, default=False)

    @validates("scoped_workspace_ids")
    def _serialize_workspace_ids(self, _key, value):
        if value is None:
            return None
        return [str(v) for v in value]

    # Relationships
    invited_by = db.relationship(
        "WorkspaceUser",
        foreign_keys=[invited_by_id],
        lazy="joined",
    )

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------

    @property
    def is_expired(self) -> bool:
        """Check if the invite token has expired."""
        now = datetime.now(timezone.utc)
        expires = self.token_expires
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return now >= expires

    def time_ago(self) -> str:
        """Return human-readable time since invite was created."""
        now = datetime.now(timezone.utc)
        created = self.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        diff = now - created

        if diff.days > 0:
            if diff.days == 1:
                return "1 day ago"
            return f"{diff.days} days ago"
        elif diff.seconds >= 3600:
            hours = diff.seconds // 3600
            if hours == 1:
                return "1 hour ago"
            return f"{hours} hours ago"
        elif diff.seconds >= 60:
            minutes = diff.seconds // 60
            if minutes == 1:
                return "1 minute ago"
            return f"{minutes} minutes ago"
        return "just now"

    # -------------------------------------------------------------------------
    # Class Methods
    # -------------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        email: str,
        invited_by_id: int,
        scoped_workspace_ids: list | None = None,
        invite_all_workspaces: bool = False,
    ) -> "WorkspaceInvite":
        """Create a new invite with a secure token.

        Args:
            email: The invitee's email address.
            invited_by_id: ID of the WorkspaceUser sending the invite.
            scoped_workspace_ids: Optional list of workspace PKs (org-admin
                mode). When None/empty and invite_all_workspaces=False, the
                invite is org-only. Workspace-admin invite paths can pass
                None (the home workspace from g.workspace_id carries the
                single-workspace scope via the existing workspace_id column).
            invite_all_workspaces: When True, the invitee is added to every
                workspace that exists in the organization at accept time
                (snapshot semantics per Q7).

        Returns:
            The created WorkspaceInvite instance.
        """
        invite = cls(
            email=email.strip().lower(),
            invited_by_id=invited_by_id,
            token=secrets.token_urlsafe(32),
            token_expires=datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRY_DAYS),
            scoped_workspace_ids=(scoped_workspace_ids or None) if not invite_all_workspaces else None,
            invite_all_workspaces=bool(invite_all_workspaces),
        )
        if current_user and current_user.is_authenticated:
            invite.created_by_id = current_user.id
        db.session.add(invite)
        db.session.commit()
        return invite

    # -------------------------------------------------------------------------
    # Multi-workspace helpers
    # -------------------------------------------------------------------------

    @property
    def is_organization_only(self) -> bool:
        """True when the invite grants organization membership only (no workspace).

        Resolution:
          - invite_all_workspaces=True → NOT org-only (expands to every workspace).
          - scoped_workspace_ids is not None AND empty → org-only (explicit).
          - scoped_workspace_ids is not None AND populated → NOT org-only.
          - scoped_workspace_ids is None → legacy single-workspace (NOT org-only).
        """
        if self.invite_all_workspaces:
            return False
        if self.scoped_workspace_ids is not None:
            return len(self.scoped_workspace_ids) == 0
        return False

    def resolve_target_workspace_ids(self) -> list:
        """Return the list of workspace PKs the invitee should be added to.

        Modes:
          - invite_all_workspaces=True → snapshot of every workspace in the
            invite's organization, resolved via this invite's home workspace.
          - scoped_workspace_ids is not None → that list literally (empty = org-only).
          - scoped_workspace_ids is None (legacy / workspace-admin single-invite)
            → [workspace_id] so existing flows keep working.
        """
        if self.invite_all_workspaces:
            from modules.base.core.models.workspace import Workspace

            if self.workspace_id is None:
                return []
            home = Workspace.query.get(self.workspace_id)
            if home is None or home.organization_id is None:
                return []
            return [
                t.id
                for t in Workspace.query.filter_by(
                    organization_id=home.organization_id
                ).all()
            ]

        if self.scoped_workspace_ids is not None:
            return [_uuid.UUID(x) for x in self.scoped_workspace_ids]

        if self.workspace_id is not None:
            return [self.workspace_id]

        return []

    @classmethod
    def get_by_token(cls, token: str) -> "WorkspaceInvite | None":
        """Find a pending, non-expired invite by token.

        This queries globally (not scoped) because the accept route is public
        and has no g.workspace_id context.

        Args:
            token: The invite token from the URL.

        Returns:
            WorkspaceInvite if found, valid, and pending; None otherwise.
        """
        invite = cls.query.filter_by(
            token=token,
            status=InviteStatus.PENDING,
        ).first()
        if invite is None:
            return None
        if invite.is_expired:
            return None
        return invite

    @classmethod
    def get_pending_all(cls) -> list["WorkspaceInvite"]:
        """Get all pending, non-expired invites in the current workspace.

        Uses scoped query (requires g.workspace_id).

        Returns:
            List of pending WorkspaceInvite records, newest first.
        """
        invites = cls.scoped().filter_by(
            status=InviteStatus.PENDING,
        ).order_by(cls.created_at.desc()).all()
        return [i for i in invites if not i.is_expired]

    @classmethod
    def get_pending_for_email(cls, email: str) -> "WorkspaceInvite | None":
        """Find a pending invite for an email in the current workspace.

        Uses scoped query (requires g.workspace_id).

        Args:
            email: The email address to look up.

        Returns:
            WorkspaceInvite if a pending invite exists, None otherwise.
        """
        return cls.scoped().filter_by(
            email=email.strip().lower(),
            status=InviteStatus.PENDING,
        ).first()

    # -------------------------------------------------------------------------
    # Instance Methods
    # -------------------------------------------------------------------------

    def regenerate_token(self) -> str:
        """Regenerate the invite token and reset expiry.

        Returns:
            The new token.
        """
        self.token = secrets.token_urlsafe(32)
        self.token_expires = datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRY_DAYS)
        if current_user and current_user.is_authenticated:
            self.updated_by_id = current_user.id
        db.session.commit()
        return self.token

    def mark_accepted(self) -> None:
        """Mark the invite as accepted."""
        self.status = InviteStatus.ACCEPTED
        self.accepted_at = datetime.now(timezone.utc)
        db.session.commit()

    def cancel(self) -> None:
        """Cancel the invite."""
        self.status = InviteStatus.CANCELLED
        if current_user and current_user.is_authenticated:
            self.updated_by_id = current_user.id
        db.session.commit()
