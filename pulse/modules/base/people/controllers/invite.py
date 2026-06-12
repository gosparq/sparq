# -----------------------------------------------------------------------------
# sparQ - Workspace Invite Controller
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""Workspace invite routes — send and accept invites.

Routes:
    POST /people/invite          — Admin sends an invite email.
    GET+POST /people/invite/accept/<token> — Recipient accepts the invite.
"""

import logging
import re

from flask import flash, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user, login_required, login_user

from system.db.database import db
from system.device.template import render_device_template
from system.i18n.translation import translate as _

from modules.base.core.models.user import User
from modules.base.core.models.workspace_user import WorkspaceUser
from ..decorators import admin_required
from ..models.invite import WorkspaceInvite

from . import blueprint

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# -----------------------------------------------------------------------------
# Admin: Send Invite
# -----------------------------------------------------------------------------

@blueprint.route("/people/invite", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def send_invite() -> ResponseReturnValue:
    """Send a workspace invite email to the given address.

    Accepts four scopes (Phase 3):
      - `current` (default) — workspace-admin mode, just the active workspace.
      - `select` — org-admin picks specific workspaces via checkboxes.
      - `all` — org-admin invites to every workspace in the organization.
      - `org_only` — org-admin invites without any workspace assignment.

    Only organization admins can use non-`current` scopes.
    """
    from modules.base.core.models.organization_user import OrganizationUser
    from modules.base.core.models.workspace import Workspace
    from flask import g as flask_g

    email = (request.form.get("email") or "").strip().lower()
    scope = (request.form.get("scope") or "current").strip()

    if not email or not EMAIL_RE.match(email):
        flash(_("Please enter a valid email address."), "error")
        return redirect(url_for("people_bp.people"))

    # Verify org-admin status when using non-default scopes.
    is_org_admin = False
    if flask_g.organization_id and current_user.is_authenticated:
        org_membership = OrganizationUser.get_for_user(
            current_user.id, flask_g.organization_id
        )
        is_org_admin = bool(org_membership and org_membership.is_organization_admin)

    if scope != "current" and not is_org_admin:
        flash(_("Only organization admins can invite beyond the current workspace."), "error")
        return redirect(url_for("people_bp.people"))

    # Resolve the scope into invite payload.
    scoped_workspace_ids: list | None = None
    invite_all_workspaces = False

    if scope == "current":
        # Legacy single-workspace behaviour — already covered by workspace_id.
        if WorkspaceUser.get_by_email(email):
            flash(_("This person is already a member of your team."), "warning")
            return redirect(url_for("people_bp.people"))
    elif scope == "select":
        import uuid as _uuid
        raw_ids = request.form.getlist("workspace_ids")
        parsed_ids: list = []
        for x in raw_ids:
            if not x:
                continue
            try:
                parsed_ids.append(_uuid.UUID(x))
            except (TypeError, ValueError):
                # Skip malformed tokens silently — validation below catches empty case.
                continue
        if not parsed_ids:
            flash(_("Select at least one workspace."), "error")
            return redirect(url_for("people_bp.people"))
        # Verify every chosen workspace is in the current organization.
        valid_ids = {
            t.id
            for t in Workspace.query.filter_by(organization_id=flask_g.organization_id).all()
        }
        scoped_workspace_ids = [tid for tid in parsed_ids if tid in valid_ids]
        if not scoped_workspace_ids:
            flash(_("Selected workspaces are not in this organization."), "error")
            return redirect(url_for("people_bp.people"))
    elif scope == "all":
        invite_all_workspaces = True
    elif scope == "org_only":
        scoped_workspace_ids = []  # explicit empty array = org-only
    else:
        flash(_("Unknown invite scope."), "error")
        return redirect(url_for("people_bp.people"))

    # Pending invite exists? Regenerate token and resend (keep the scope fields).
    invite = WorkspaceInvite.get_pending_for_email(email)
    if invite:
        invite.regenerate_token()
        invite.scoped_workspace_ids = scoped_workspace_ids
        invite.invite_all_workspaces = invite_all_workspaces
        db.session.commit()
    else:
        invite = WorkspaceInvite.create(
            email=email,
            invited_by_id=current_user.workspace_membership.id,
            scoped_workspace_ids=scoped_workspace_ids,
            invite_all_workspaces=invite_all_workspaces,
        )

    from modules.base.core.models.organization_invitation import OrganizationInvitation

    OrganizationInvitation.ensure_for_org(
        email=email,
        organization_id=flask_g.organization_id,
        invited_by_id=current_user.id,
    )

    # Build invite URL and send email
    invite_url = url_for("people_bp.accept_invite", token=invite.token, _external=True)
    _send_invite_email(invite, invite_url)

    flash(_("Invite sent to") + f" {email}.", "success")
    return redirect(url_for("people_bp.people"))


def _send_invite_email(invite: WorkspaceInvite, invite_url: str) -> bool:
    """Send the invite email via the configured provider.

    Uses send_email_async which auto-selects the configured email provider.

    Args:
        invite: The WorkspaceInvite record.
        invite_url: The fully-qualified accept URL.

    Returns:
        True if email was queued, False otherwise.
    """
    from system.email.service import send_email_async, is_configured
    from system.email.templates import (
        get_workspace_invite_email_html,
        get_workspace_invite_email_text,
    )

    if not is_configured():
        logger.warning("[INVITE] Email not configured — cannot send invite to %s", invite.email)
        return False

    from modules.base.core.models.workspace_settings import WorkspaceSettings

    company = WorkspaceSettings.get_instance()
    company_name = company.company_name or "Your Company"

    invited_text = _("You're Invited!")
    join_text = _("Join")
    on_sparq_text = _("on sparQ")
    subject = f"{invited_text} — {join_text} {company_name} {on_sparq_text}"
    html_body = get_workspace_invite_email_html(company_name, invite_url)
    text_body = get_workspace_invite_email_text(company_name, invite_url)

    send_email_async(invite.email, subject, html_body, text_body)
    return True


# -----------------------------------------------------------------------------
# Admin: Resend / Cancel Invite
# -----------------------------------------------------------------------------

@blueprint.route("/people/invite/<int:invite_id>/resend", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def resend_invite(invite_id: int) -> ResponseReturnValue:
    """Resend a pending invite — regenerate token and send email."""
    invite = WorkspaceInvite.scoped().get_or_404(invite_id)
    invite.regenerate_token()

    invite_url = url_for("people_bp.accept_invite", token=invite.token, _external=True)
    _send_invite_email(invite, invite_url)

    return _render_pending_partial()


@blueprint.route("/people/invite/<int:invite_id>/cancel", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def cancel_invite(invite_id: int) -> ResponseReturnValue:
    """Cancel a pending invite."""
    invite = WorkspaceInvite.scoped().get_or_404(invite_id)
    invite.cancel()

    return _render_pending_partial()


def _render_pending_partial() -> str:
    """Render the pending invites partial for HTMX swap."""
    pending_invites = WorkspaceInvite.get_pending_all()
    return render_template(
        "people/desktop/people/_invite_pending.html",
        pending_invites=pending_invites,
    )


# -----------------------------------------------------------------------------
# Public: Accept Invite
# -----------------------------------------------------------------------------

@blueprint.route("/people/invite/accept/<token>", methods=["GET", "POST"])  # type: ignore[misc]
def accept_invite(token: str) -> ResponseReturnValue:
    """Accept a workspace invite — create account or join workspace."""
    invite = WorkspaceInvite.get_by_token(token)
    if invite is None:
        flash(_("This invite link is invalid or has expired."), "error")
        return redirect(url_for("core_bp.login"))

    existing_user = User.get_by_email(invite.email)

    # Resolve which workspace(s) this invite grants access to.
    target_workspace_ids = invite.resolve_target_workspace_ids()

    # If the user already belongs to every target workspace (or the invite is
    # org-only and they're already an org member), skip straight to login.
    if existing_user:
        from modules.base.core.models.organization_user import OrganizationUser
        from modules.base.core.models.workspace import Workspace

        # Determine organization_id this invite targets.
        home_workspace = Workspace.query.get(invite.workspace_id) if invite.workspace_id else None
        organization_id = home_workspace.organization_id if home_workspace else None

        if target_workspace_ids:
            all_members = all(
                WorkspaceUser.is_member(existing_user.id, ts_id)
                for ts_id in target_workspace_ids
            )
            if all_members:
                flash(_("You are already a member of this team."), "info")
                invite.mark_accepted()
                return redirect(url_for("core_bp.login"))
        elif invite.is_organization_only and organization_id:
            org_membership = OrganizationUser.get_for_user(existing_user.id, organization_id)
            if org_membership and org_membership.is_active:
                flash(_("You are already a member of this organization."), "info")
                invite.mark_accepted()
                return redirect(url_for("core_bp.login"))

    if request.method == "GET":
        return render_device_template(
            "people/desktop/invite/accept.html",
            token=token,
            invite=invite,
            new_user=existing_user is None,
            target_workspace_ids=target_workspace_ids,
        )

    # POST — process the form
    if existing_user is None:
        return _accept_new_user(invite, target_workspace_ids)
    else:
        return _accept_existing_user(invite, existing_user, target_workspace_ids)


def _accept_new_user(
    invite: WorkspaceInvite, target_workspace_ids: list
) -> ResponseReturnValue:
    """Create a new user account from an invite and wire the org + workspace memberships.

    Args:
        invite: The WorkspaceInvite being accepted.
        target_workspace_ids: Resolved list of workspace PKs to join. Empty
            for org-only invites.
    """
    from system.auth.password_policy import validate_password

    first_name = (request.form.get("first_name") or "").strip()
    last_name = (request.form.get("last_name") or "").strip()
    password = request.form.get("password") or ""
    confirm_password = request.form.get("confirm_password") or ""

    # Validate required fields
    if not first_name or not last_name:
        flash(_("First name and last name are required."), "error")
        return render_device_template(
            "people/desktop/invite/accept.html",
            token=invite.token,
            invite=invite,
            new_user=True,
            target_workspace_ids=target_workspace_ids,
        )

    if password != confirm_password:
        flash(_("Passwords do not match."), "error")
        return render_device_template(
            "people/desktop/invite/accept.html",
            token=invite.token,
            invite=invite,
            new_user=True,
            target_workspace_ids=target_workspace_ids,
        )

    # Validate password strength
    violations = validate_password(password)
    if violations:
        flash(violations[0], "error")
        return render_device_template(
            "people/desktop/invite/accept.html",
            token=invite.token,
            invite=invite,
            new_user=True,
            target_workspace_ids=target_workspace_ids,
        )

    try:
        user = _provision_invitee(
            invite,
            target_workspace_ids,
            first_name=first_name,
            last_name=last_name,
            password=password,
        )
        invite.mark_accepted()
        login_user(user)
        logger.info(
            "[INVITE] New user %s accepted invite — workspaces=%s, org_only=%s",
            invite.email, target_workspace_ids, invite.is_organization_only,
        )
        flash(_("Welcome! Your account has been created."), "success")
        return redirect(url_for("dashboard_bp.index"))

    except Exception as e:
        logger.error("[INVITE] Failed to provision invitee: %s", e)
        flash(_("Something went wrong. Please try again."), "error")
        return render_device_template(
            "people/desktop/invite/accept.html",
            token=invite.token,
            invite=invite,
            new_user=True,
            target_workspace_ids=target_workspace_ids,
        )


def _accept_existing_user(
    invite: WorkspaceInvite, user: User, target_workspace_ids: list
) -> ResponseReturnValue:
    """Add an existing user to the org + the invite's target workspaces.

    Args:
        invite: The WorkspaceInvite being accepted.
        user: The existing User account.
        target_workspace_ids: Resolved list of workspace PKs to join. Empty
            for org-only invites.
    """
    try:
        _provision_invitee(invite, target_workspace_ids, existing_user=user)
        invite.mark_accepted()
        login_user(user)
        logger.info(
            "[INVITE] Existing user %s accepted invite — workspaces=%s, org_only=%s",
            user.email, target_workspace_ids, invite.is_organization_only,
        )
        if target_workspace_ids:
            flash(_("You've joined the team!"), "success")
        else:
            flash(_("You've joined the organization!"), "success")
        return redirect(url_for("dashboard_bp.index"))

    except Exception as e:
        logger.error("[INVITE] Failed to add existing user to workspace: %s", e)
        flash(_("Something went wrong. Please try again."), "error")
        return redirect(url_for("core_bp.login"))


def _provision_invitee(
    invite: WorkspaceInvite,
    target_workspace_ids: list,
    *,
    existing_user: User | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    password: str | None = None,
) -> User:
    """Create/attach the invitee's User, OrganizationUser, and N WorkspaceUsers.

    Handles the full matrix:
      - org-only invite → OrganizationUser only, no WorkspaceUser rows.
      - single-workspace invite → OrganizationUser + one WorkspaceUser.
      - multi-workspace / all-workspaces → OrganizationUser + N WorkspaceUsers.

    Args:
        invite: The invite being accepted.
        target_workspace_ids: List of workspace PKs to add the invitee to.
            Empty for org-only invites.
        existing_user: If set, attach memberships to this existing User.
        first_name, last_name, password: Required when creating a brand-new user.

    Returns:
        The User account that now holds the memberships.

    Raises:
        ValueError: If creating a new user without first_name/last_name/password.
    """
    from flask import g as flask_g
    from modules.base.core.models.organization_user import OrganizationUser
    from modules.base.core.models.workspace import Workspace
    from modules.base.core.models.workspace_user import (
        EmployeeStatus,
        WorkspaceUser,
    )
    from system.db.database import db

    # Resolve the organization_id from the invite's home workspace.
    organization_id = None
    if invite.workspace_id:
        home = Workspace.query.get(invite.workspace_id)
        if home:
            organization_id = home.organization_id

    # 1. User — create if new, reuse if existing.
    if existing_user is not None:
        user = existing_user
    else:
        if not first_name or not last_name or not password:
            raise ValueError(
                "first_name, last_name, and password are required for new users"
            )
        user = User(email=invite.email, first_name=first_name, last_name=last_name)
        user.password = password
        db.session.add(user)
        db.session.flush()

    # 2. OrganizationUser — always created (every invite grants org membership).
    org_membership_id = None
    if organization_id is not None:
        org_membership = OrganizationUser.get_or_create(
            organization_id=organization_id,
            user_id=user.id,
            role="member",
            invited_by_id=invite.created_by_id,
        )
        org_membership_id = org_membership.id

    # 3. WorkspaceUser rows — one per target workspace. Idempotent via is_member.
    prev_workspace_id = getattr(flask_g, "workspace_id", None)
    prev_organization_id = getattr(flask_g, "organization_id", None)
    try:
        for ts_id in target_workspace_ids:
            if WorkspaceUser.is_member(user.id, ts_id):
                continue
            flask_g.workspace_id = ts_id
            flask_g.organization_id = organization_id
            db.session.add(
                WorkspaceUser(
                    user_id=user.id,
                    workspace_id=ts_id,
                    organization_id=organization_id,
                    organization_user_id=org_membership_id,
                    role="member",
                    member_type="full",
                    status=EmployeeStatus.ACTIVE,
                )
            )
    finally:
        flask_g.workspace_id = prev_workspace_id
        flask_g.organization_id = prev_organization_id

    db.session.commit()
    return user
