# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Pending signup model for email confirmation during workspace creation.
#     Stores signup data temporarily until the user confirms their email
#     address, at which point a real User + Workspace are provisioned.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

from __future__ import annotations

import logging
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from urllib.parse import quote
from uuid import UUID

from flask import g
from werkzeug.security import generate_password_hash

if TYPE_CHECKING:
    from modules.base.core.models.user import User

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.utils.email_domain import extract_domain, is_free_email


@dataclass
class SignupResult:
    """Result of signup domain routing — tells the controller where to land the user."""

    user: User
    rule: int
    primary_organization_id: UUID | None
    has_workspace: bool
    workspace: object | None = None
    ts_user: object | None = None

logger = logging.getLogger(__name__)

TOKEN_EXPIRY_MINUTES = 30


def _slugify_with_uniqueness(name: str, taken) -> str:
    """Turn a name into a URL-safe slug, suffixing -2/-3/... if taken.

    Per Q1 (resolved 2026-04-21): duplicate organization/workspace names are
    allowed in the UI; the backend silently generates unique slugs.

    Args:
        name: Raw display name (e.g. "Acme Corp").
        taken: Callable[[str], bool] — returns True if the slug is already in use.
    """
    base = re.sub(r"[^a-z0-9-]", "", name.lower().replace(" ", "-"))[:50].strip("-") or "org"
    slug = base
    counter = 2
    while taken(slug):
        slug = f"{base}-{counter}"
        counter += 1
    return slug


def _provision_org_and_workspace(user, name: str, claimed_domain: str | None = None):
    """Create Organization → Workspace → OrganizationUser → WorkspaceUser → settings.

    Reusable by rule-2 signup and the "Create Organization" controller action.
    Does NOT commit — caller manages the transaction.

    Returns:
        (organization, workspace, org_user, ts_user)
    """
    from modules.base.core.models.auth_settings import AuthSettings
    from modules.base.core.models.organization import Organization
    from modules.base.core.models.organization_user import OrganizationUser
    from modules.base.core.models.workspace import RESERVED_SLUGS, Workspace
    from modules.base.core.models.workspace_settings import WorkspaceSettings
    from modules.base.core.models.workspace_user import EmployeeStatus, WorkspaceUser
    from modules.base.updates.models.channel import UpdateChannel

    slug = _slugify_with_uniqueness(name, taken=lambda s: (
        Organization.query.filter_by(slug=s).first() is not None
        or Workspace.query.filter_by(slug=s).first() is not None
        or s in RESERVED_SLUGS
    ))

    organization = Organization(name=name, slug=slug, claimed_domain=claimed_domain)
    db.session.add(organization)
    db.session.flush()

    g.organization_id = organization.id

    workspace_slug = slug if not Workspace.query.filter_by(slug=slug).first() else _slugify_with_uniqueness(
        name, taken=lambda s: Workspace.query.filter_by(slug=s).first() is not None or s in RESERVED_SLUGS,
    )
    workspace = Workspace(slug=workspace_slug, name="Main", organization_id=organization.id)
    db.session.add(workspace)
    db.session.flush()

    g.workspace_id = workspace.id

    org_user = OrganizationUser(
        organization_id=organization.id,
        user_id=user.id,
        role="admin",
        is_active=True,
    )
    db.session.add(org_user)
    db.session.flush()

    ts_user = WorkspaceUser(
        user_id=user.id,
        organization_user_id=org_user.id,
        role="admin",
        member_type="full",
        status=EmployeeStatus.ACTIVE,
        position="Owner",
    )
    db.session.add(ts_user)

    organization.owner_id = user.id

    settings = WorkspaceSettings.get_instance()
    settings.company_name = name
    settings.onboarding_completed = True

    auth = AuthSettings.get_instance()
    auth.local_auth_enabled = True

    UpdateChannel.create_default_channels()

    return organization, workspace, org_user, ts_user


def _seed_after_commit(workspace, user, ts_user):
    """Seed sample data after the provisioning transaction has committed."""
    try:
        from system.db.seed_sample import seed_sample_data
        seed_sample_data(workspace.id, user.id, ts_user.id)
    except Exception:
        logger.exception("Failed to seed sample data for %s", workspace.slug)


def route_new_signup(user) -> SignupResult:
    """Route a new user through the 5-rule domain lookup.

    Reusable by PendingSignup.confirm() and OAuth signup. Accepts an
    already-created, flushed User. Does NOT commit — caller manages
    the transaction.

    Args:
        user: A User instance that has been added to the session and flushed.

    Returns:
        SignupResult describing which rule matched and where to land the user.
    """
    from modules.base.core.models.organization import Organization
    from modules.base.core.models.organization_invitation import OrganizationInvitation
    from modules.base.core.models.organization_user import OrganizationUser
    from modules.base.core.models.workspace_user import WorkspaceUser

    domain = extract_domain(user.email)

    # ---- Rule 1: Pending invitations ----
    pending_invitations = OrganizationInvitation.get_pending_for_email(user.email)
    if pending_invitations:
        for inv in pending_invitations:
            inv.accept(user.id)
        primary_org_id = pending_invitations[0].organization_id
        has_ts = WorkspaceUser.query.filter_by(user_id=user.id).filter(
            WorkspaceUser.deleted_at.is_(None),
        ).first() is not None
        logger.info("Signup rule 1 (invitation) for %s — %d invitations accepted",
                     user.email, len(pending_invitations))
        return SignupResult(user=user, rule=1, primary_organization_id=primary_org_id,
                            has_workspace=has_ts)

    # ---- Rule 5: Free email → personal shell ----
    if is_free_email(user.email):
        logger.info("Signup rule 5 (free email) for %s — personal shell", user.email)
        return SignupResult(user=user, rule=5, primary_organization_id=None,
                            has_workspace=False)

    # ---- Rules 2-4: Custom domain ----
    orgs_on_domain = Organization.find_by_domain(domain)
    count = len(orgs_on_domain)

    # Rule 2: Unclaimed domain → create org + workspace
    if count == 0:
        org, workspace, _org_user, ts_user = _provision_org_and_workspace(
            user=user,
            name=domain.split(".")[0].capitalize(),
            claimed_domain=domain,
        )
        logger.info("Signup rule 2 (new org) for %s — org %r", user.email, org.name)
        return SignupResult(user=user, rule=2, primary_organization_id=org.id,
                            has_workspace=True, workspace=workspace, ts_user=ts_user)

    # Rule 3: Single claimer → auto-join as member
    if count == 1:
        org = orgs_on_domain[0]
        membership = OrganizationUser(
            organization_id=org.id,
            user_id=user.id,
            role="member",
            is_active=True,
        )
        db.session.add(membership)
        _notify_admins_auto_join(org, user)
        logger.info("Signup rule 3 (auto-join) for %s — org %r", user.email, org.name)
        return SignupResult(user=user, rule=3, primary_organization_id=org.id,
                            has_workspace=False)

    # Rule 4: Multiple claimers → personal shell
    _notify_admins_pending_signup(orgs_on_domain, user)
    logger.info("Signup rule 4 (multi-claimer) for %s — %d orgs on domain", user.email, count)
    return SignupResult(user=user, rule=4, primary_organization_id=None,
                        has_workspace=False)


def _notify_admins_auto_join(org, user):
    """Rule-3: notify org admins that a user auto-joined via domain match.

    Creates SystemNotification per admin and sends an email via the gateway.
    Does NOT commit — caller manages the transaction.
    """
    from modules.base.core.models.notification import SystemNotification
    from modules.base.core.models.organization_user import OrganizationUser
    from modules.base.core.models.workspace_user import WorkspaceUser

    from sqlalchemy.orm import joinedload

    admins = OrganizationUser.query.filter_by(
        organization_id=org.id, role="admin", is_active=True,
    ).options(joinedload(OrganizationUser.user)).all()

    display = user.first_name or user.email

    for admin_ou in admins:
        ts_member = (
            WorkspaceUser.query
            .filter_by(organization_user_id=admin_ou.id)
            .filter(WorkspaceUser.deleted_at.is_(None))
            .first()
        )
        notification = SystemNotification(
            title=f"{display} joined your organization",
            message=f"{user.email} auto-joined {org.name} via domain match.",
            type="info",
            target_role="admin",
            user_id=admin_ou.user_id,
            action_url="/settings/organization/?tab=members",
            organization_id=org.id,
            workspace_id=ts_member.workspace_id if ts_member else None,
        )
        db.session.add(notification)

    _send_admin_email_notifications(
        admins,
        subject=f"New member joined {org.name}",
        body=f"{display} ({user.email}) auto-joined {org.name} because their email domain matched.",
    )


def _notify_admins_pending_signup(orgs, user):
    """Rule-4: notify admins of all domain-claiming orgs about a new signup.

    Does NOT commit — caller manages the transaction.
    """
    from modules.base.core.models.notification import SystemNotification
    from modules.base.core.models.organization_user import OrganizationUser
    from modules.base.core.models.workspace_user import WorkspaceUser

    display = user.first_name or user.email

    from sqlalchemy.orm import joinedload

    for org in orgs:
        admins = OrganizationUser.query.filter_by(
            organization_id=org.id, role="admin", is_active=True,
        ).options(joinedload(OrganizationUser.user)).all()

        for admin_ou in admins:
            ts_member = (
                WorkspaceUser.query
                .filter_by(organization_user_id=admin_ou.id)
                .filter(WorkspaceUser.deleted_at.is_(None))
                .first()
            )
            notification = SystemNotification(
                title=f"{display} signed up and is waiting",
                message=f"{user.email} signed up with a domain claimed by {org.name}.",
                type="info",
                target_role="admin",
                user_id=admin_ou.user_id,
                action_url=f"/people/people?invite_email={quote(user.email)}",
                organization_id=org.id,
                workspace_id=ts_member.workspace_id if ts_member else None,
            )
            db.session.add(notification)

        _send_admin_email_notifications(
            admins,
            subject=f"{display} is waiting to join {org.name}",
            body=f"{user.email} signed up with a domain claimed by {org.name}. "
                 f"You can invite them from your organization settings.",
        )


def _send_admin_email_notifications(admin_org_users, subject: str, body: str):
    """Best-effort email delivery to a list of org-admin OrganizationUser rows."""
    try:
        from system.email.service import send_gateway_email
    except Exception:
        logger.debug("Email gateway not available, skipping admin email notification")
        return

    for admin_ou in admin_org_users:
        admin_user = admin_ou.user
        if admin_user and admin_user.email:
            try:
                send_gateway_email(admin_user.email, subject, f"<p>{body}</p>")
            except Exception:
                logger.debug("Failed to send admin notification email to %s", admin_user.email)


@ModelRegistry.register
class PendingSignup(db.Model):
    """Staging table for unconfirmed signups.

    A row is created when a user submits the signup form.
    Once they click the confirmation link in their email, a real
    User, Workspace, and WorkspaceUser are provisioned and the
    pending row is deleted.
    """

    __tablename__ = "pending_signup"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(200), nullable=True)
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    organization_name = db.Column(db.String(255), nullable=True)
    token = db.Column(db.String(100), unique=True, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.now())

    @classmethod
    def create_or_update(
        cls,
        email: str,
        password: str = "",
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> PendingSignup:
        """Create a pending signup or refresh an existing one.

        If a pending row already exists for this email, the token and
        expiration are refreshed and the password is re-hashed.

        Args:
            email: Email address.
            password: Plaintext password (will be hashed). Optional for SSO/magic link users.
            first_name: First name.
            last_name: Last name.

        Returns:
            PendingSignup instance.
        """
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRY_MINUTES)
        password_hash = generate_password_hash(password) if password else None

        existing = cls.query.filter_by(email=email).first()
        if existing:
            existing.password_hash = password_hash
            existing.first_name = first_name
            existing.last_name = last_name
            existing.token = token
            existing.expires_at = expires_at
            db.session.commit()
            return existing

        pending = cls(
            email=email,
            password_hash=password_hash,
            first_name=first_name,
            last_name=last_name,
            token=token,
            expires_at=expires_at,
        )
        db.session.add(pending)
        db.session.commit()
        return pending

    @classmethod
    def get_by_token(cls, token: str) -> PendingSignup | None:
        """Find a pending signup by token.

        Returns None if the token does not exist or has expired.

        Args:
            token: The confirmation token from the URL.

        Returns:
            PendingSignup instance or None.
        """
        pending = cls.query.filter_by(token=token).first()
        if pending is None:
            return None

        # Check expiration
        now = datetime.now(timezone.utc)
        expires = pending.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if now > expires:
            return None

        # Constant-time comparison
        if not secrets.compare_digest(pending.token, token):
            return None

        return pending

    def confirm(self) -> SignupResult | None:
        """Confirm email and route the user through the 5-rule domain lookup.

        Creates a real User, delegates to route_new_signup() for domain
        routing, deletes this pending row, and commits.

        Returns:
            SignupResult describing where to land the user, or None if the email
            is already taken (race condition guard).
        """
        from modules.base.core.models.user import User

        # Guard against race conditions
        if User.get_by_email(self.email):
            db.session.delete(self)
            db.session.commit()
            logger.warning("User already exists for %s, deleting pending row", self.email)
            return None

        user = User(
            email=self.email,
            first_name=self.first_name,
            last_name=self.last_name,
            password_hash=self.password_hash,
        )
        db.session.add(user)
        db.session.flush()

        result = route_new_signup(user)

        db.session.delete(self)
        db.session.commit()

        if result.rule == 2 and result.workspace and result.ts_user:
            _seed_after_commit(result.workspace, user, result.ts_user)

        return result

    @classmethod
    def cleanup_expired(cls) -> None:
        """Delete all expired pending signups."""
        now = datetime.now(timezone.utc)
        count = cls.query.filter(cls.expires_at < now).delete()
        if count:
            db.session.commit()
            logger.info("Cleaned up %d expired pending signups", count)
