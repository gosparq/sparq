# -----------------------------------------------------------------------------
# sparQ - Instance Setup
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""First-time instance setup: bootstrap the first user, organization, and workspace.

Called once on a fresh install when no users exist. Repurposes the default
Organization and Workspace created by init_database() so that module-seeded
data is preserved.
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

from flask import g
from werkzeug.security import generate_password_hash

from system.db.database import db
from system.utils.email_domain import extract_domain, is_free_email

if TYPE_CHECKING:
    from modules.base.core.models.user import User
    from modules.base.core.models.workspace import Workspace

logger = logging.getLogger(__name__)

DEFAULT_ORGANIZATION_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DEFAULT_WORKSPACE_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def is_fresh_install() -> bool:
    """Return True when the instance has no user accounts yet."""
    from modules.base.core.models.user import User

    return db.session.query(User.id).first() is None


def provision_instance(
    first_name: str,
    last_name: str,
    email: str,
    password: str,
    company_name: str,
    color: str,
    timezone: str,
    language: str,
) -> tuple[User, Workspace]:
    """Bootstrap the instance with the first user, organization, and workspace.

    Repurposes the default Organization/Workspace created by init_database()
    and creates the admin user plus all required membership and settings rows.

    Args:
        first_name: Admin user's first name.
        last_name: Admin user's last name.
        email: Admin user's email address.
        password: Plaintext password (will be hashed).
        company_name: Organization/workspace display name.
        color: Workspace color key (must be in WORKSPACE_COLORS).
        timezone: IANA timezone string.
        language: Language code (e.g. "en").

    Returns:
        (user, workspace) tuple.
    """
    from modules.base.core.models.auth_settings import AuthSettings
    from modules.base.core.models.organization import Organization
    from modules.base.core.models.organization_user import OrganizationUser
    from modules.base.core.models.pending_signup import (
        _seed_after_commit,
        _slugify_with_uniqueness,
    )
    from modules.base.core.models.user import User
    from modules.base.core.models.workspace import RESERVED_SLUGS, Workspace
    from modules.base.core.models.workspace_settings import WorkspaceSettings
    from modules.base.core.models.workspace_user import EmployeeStatus, WorkspaceUser
    from modules.base.updates.models.channel import UpdateChannel

    # 1. Create admin user
    user = User(
        email=email,
        first_name=first_name,
        last_name=last_name,
        password_hash=generate_password_hash(password),
        is_active=True,
    )
    db.session.add(user)
    db.session.flush()

    # 2. Update default organization
    organization = Organization.query.get(DEFAULT_ORGANIZATION_ID)
    if not organization:
        organization = Organization(id=DEFAULT_ORGANIZATION_ID, name=company_name, slug="default")
        db.session.add(organization)
        db.session.flush()

    slug = _slugify_with_uniqueness(
        company_name,
        taken=lambda s: (
            (Organization.query.filter(Organization.id != DEFAULT_ORGANIZATION_ID).filter_by(slug=s).first() is not None)
            or (Workspace.query.filter(Workspace.id != DEFAULT_WORKSPACE_ID).filter_by(slug=s).first() is not None)
            or s in RESERVED_SLUGS
        ),
    )

    organization.name = company_name
    organization.slug = slug
    organization.owner_id = user.id
    if not is_free_email(email):
        organization.claimed_domain = extract_domain(email)

    # 3. Update default workspace
    workspace = Workspace.query.get(DEFAULT_WORKSPACE_ID)
    if not workspace:
        workspace = Workspace(id=DEFAULT_WORKSPACE_ID, name=company_name, slug=slug)
        db.session.add(workspace)
        db.session.flush()

    workspace.name = company_name
    workspace.slug = slug
    workspace.color = color
    workspace.organization_id = organization.id

    # Set g context for WorkspaceMixin auto-stamping and scoped singletons
    g.organization_id = organization.id
    g.workspace_id = workspace.id

    # 4. Create organization membership (admin)
    org_user = OrganizationUser(
        organization_id=organization.id,
        user_id=user.id,
        role="admin",
        is_active=True,
    )
    db.session.add(org_user)
    db.session.flush()

    # 5. Create workspace membership (admin)
    ws_user = WorkspaceUser(
        user_id=user.id,
        organization_user_id=org_user.id,
        role="admin",
        member_type="full",
        status=EmployeeStatus.ACTIVE,
        position="Owner",
    )
    db.session.add(ws_user)

    # 6. Configure workspace settings
    settings = WorkspaceSettings.get_instance()
    settings.company_name = company_name
    settings.timezone = timezone
    settings.default_language = language
    settings.onboarding_completed = True

    # 7. Enable local auth
    auth = AuthSettings.get_instance()
    auth.local_auth_enabled = True

    # 8. Seed default channels
    UpdateChannel.create_default_channels()

    # 9. Commit
    db.session.commit()

    # 10. Seed sample data (post-commit, separate transaction)
    _seed_after_commit(workspace, user, ws_user)

    logger.info(
        "Instance setup complete: user=%s org=%s workspace=%s",
        email, organization.slug, workspace.slug,
    )

    return user, workspace
