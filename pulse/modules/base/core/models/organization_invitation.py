# -----------------------------------------------------------------------------
# sparQ - OrganizationInvitation Model
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""Organization-level invitation model.

Tracks invitations to join an organization. Checked during signup (rule 1 of the
domain routing spec): pending invitations always take precedence over domain-based
auto-join. Also used by the staff ownership-transfer tool to invite an external
user as owner.

"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.raise_on_lazy import LAZY


ORGANIZATION_INVITATION_ROLES = ("owner", "admin", "member")


@ModelRegistry.register
class OrganizationInvitation(db.Model):
    """Invitation to join an organization."""

    __tablename__ = "organization_invitation"
    __table_args__ = (
        db.Index("ix_org_invitation_email_accepted", "email", "accepted_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(
        db.UUID(as_uuid=True),
        db.ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email = db.Column(db.String(255), nullable=False)
    invited_by_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    )
    role = db.Column(db.String(20), nullable=False, default="member")
    token = db.Column(db.String(100), unique=True, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc),
    )
    accepted_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    organization = db.relationship(
        "Organization",
        foreign_keys=[organization_id],
        backref=db.backref("invitations", lazy="dynamic"),
        lazy=LAZY,
    )
    invited_by = db.relationship("User", foreign_keys=[invited_by_id], lazy=LAZY)

    def __repr__(self) -> str:
        return f"<OrganizationInvitation org={self.organization_id} email={self.email}>"

    # ------------------------------------------------------------------
    # Creation
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        organization_id,
        email: str,
        invited_by_id: int | None = None,
        role: str = "member",
        expires_days: int = 7,
    ) -> OrganizationInvitation:
        """Create a new organization invitation.

        Args:
            organization_id: Target organization UUID.
            email: Invitee email (will be normalized to lowercase).
            invited_by_id: User who sent the invitation.
            role: Role to grant on acceptance (owner/admin/member).
            expires_days: Days until invitation expires.

        Returns:
            The created OrganizationInvitation.
        """
        if role not in ORGANIZATION_INVITATION_ROLES:
            raise ValueError(
                f"Invalid role '{role}'; must be one of {ORGANIZATION_INVITATION_ROLES}"
            )
        invitation = cls(
            organization_id=organization_id,
            email=email.strip().lower(),
            invited_by_id=invited_by_id,
            role=role,
            token=secrets.token_urlsafe(32),
            expires_at=datetime.now(timezone.utc) + timedelta(days=expires_days),
        )
        db.session.add(invitation)
        db.session.commit()
        return invitation

    @classmethod
    def ensure_for_org(
        cls,
        email: str,
        organization_id: UUID,
        invited_by_id: int | None = None,
        role: str = "member",
    ) -> OrganizationInvitation | None:
        """Ensure a pending invitation exists for this email + org.

        Idempotent — returns None if one already exists, or creates and
        returns a new invitation.
        """
        existing = cls.get_pending_for_email(email)
        if any(inv.organization_id == organization_id for inv in existing):
            return None
        return cls.create(
            organization_id=organization_id,
            email=email,
            invited_by_id=invited_by_id,
            role=role,
        )

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    @classmethod
    def get_pending_for_email(cls, email: str) -> list[OrganizationInvitation]:
        """Get all pending (not accepted, not expired) invitations for an email.

        Ordered by created_at descending so the most recent invitation is first
        (used by rule 1 to determine the primary landing org).
        """
        now = datetime.now(timezone.utc)
        return (
            cls.query
            .filter_by(email=email.strip().lower())
            .filter(cls.accepted_at.is_(None))
            .filter(cls.expires_at > now)
            .order_by(cls.created_at.desc())
            .all()
        )

    @classmethod
    def get_by_token(cls, token: str) -> OrganizationInvitation | None:
        """Find an invitation by token with expiry and constant-time validation."""
        invitation = cls.query.filter_by(token=token).first()
        if invitation is None:
            return None

        now = datetime.now(timezone.utc)
        expires = invitation.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if now > expires:
            return None

        if not secrets.compare_digest(invitation.token, token):
            return None

        if invitation.accepted_at is not None:
            return None

        return invitation

    # ------------------------------------------------------------------
    # Acceptance
    # ------------------------------------------------------------------

    def accept(self, user_id: int):
        """Accept this invitation: mark accepted + create OrganizationUser.

        Args:
            user_id: The user accepting the invitation.

        Returns:
            The created OrganizationUser membership.
        """
        from modules.base.core.models.organization_user import OrganizationUser

        self.accepted_at = datetime.now(timezone.utc)

        membership = OrganizationUser(
            organization_id=self.organization_id,
            user_id=user_id,
            role=self.role,
            invited_by_id=self.invited_by_id,
            is_active=True,
        )
        db.session.add(membership)
        return membership
