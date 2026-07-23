# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Core module route handlers and view logic. Implements authentication,
#     user management, and system settings functionality.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

from typing import Any
import importlib
import logging
import os
import sys

logger = logging.getLogger(__name__)

from flask import Blueprint, Response
from flask.typing import ResponseReturnValue
from flask import abort
from flask import current_app
from flask import flash
from flask import g
from flask import jsonify
from flask import make_response
from flask import redirect
from flask import render_template
from flask import request
from flask import send_from_directory
from flask import session
from flask import url_for

from system.device import render_device_template
from flask_login import current_user
from flask_login import login_required
from flask_login import login_user
from flask_login import logout_user

from system.auth.decorators import admin_required
from system.auth.password_policy import validate_password, is_breached
from system.db.database import db
from system.middleware.form_timing import generate_form_timestamp, validate_form_timing
from system.middleware.ratelimit import rate_limit
from system.i18n.translation import _  # Use our existing translation module
from system.version import get_version

from ..models.workspace_settings import WorkspaceSettings
from ..models.notification import SystemNotification
from ..models.user import User
from ..models.user_setting import UserSetting

# Create blueprint
blueprint = Blueprint(
    "core_bp", __name__, template_folder="../views/templates", static_folder="../views/assets"
)


# SVG icons for OAuth buttons (inline, matching cloud service pattern)
_OAUTH_SVG_ICONS: dict[str, str] = {
    "google": '<svg width="18" height="18" viewBox="0 0 48 48"><path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/><path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/><path fill="#FBBC05" d="M10.53 28.59A14.5 14.5 0 0 1 9.5 24c0-1.59.28-3.14.76-4.59l-7.98-6.19A23.99 23.99 0 0 0 0 24c0 3.77.9 7.35 2.56 10.53l7.97-5.94z"/><path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 5.94C6.51 42.62 14.62 48 24 48z"/></svg>',
    "github": '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/></svg>',
    "microsoft": '<svg width="18" height="18" viewBox="0 0 21 21"><rect x="1" y="1" width="9" height="9" fill="#F25022"/><rect x="1" y="11" width="9" height="9" fill="#00A4EF"/><rect x="11" y="1" width="9" height="9" fill="#7FBA00"/><rect x="11" y="11" width="9" height="9" fill="#FFB900"/></svg>',
    "linkedin": '<svg width="18" height="18" viewBox="0 0 24 24" fill="#0A66C2"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 0 1-2.063-2.065 2.064 2.064 0 1 1 2.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>',
}


def _build_oauth_providers() -> list[dict[str, str]]:
    """Build list of enabled OAuth providers for template rendering."""
    from system.oauth.providers import PROVIDERS
    from system.oauth.service import is_provider_enabled

    providers = []
    for name, config in PROVIDERS.items():
        if is_provider_enabled(name):
            providers.append({
                "name": name,
                "display_name": config.display_name,
                "login_url": url_for("oauth_bp.login", provider=name),
                "svg_icon": _OAUTH_SVG_ICONS.get(name, ""),
            })
    return providers


# -----------------------------------------------------------------------------
# Theme Preview (standalone, no auth required)
# -----------------------------------------------------------------------------


@blueprint.route("/newlook")  # type: ignore[misc]
def newlook() -> str:
    return render_template("core/desktop/newlook.html")


# -----------------------------------------------------------------------------
# Health Check (for upgrade validation - no auth required)
# -----------------------------------------------------------------------------


@blueprint.route("/health")  # type: ignore[misc]
def health() -> tuple[dict[str, str], int]:
    """
    Health check endpoint for upgrade validation and load balancers.
    No authentication required.
    """
    from sqlalchemy import text

    try:
        # Verify database connectivity
        db.session.execute(text("SELECT 1"))
        return {"status": "ok"}, 200
    except Exception as e:
        return {"status": "unhealthy", "reason": str(e)}, 503


# -----------------------------------------------------------------------------
# PWA Support (Service Worker, Manifest, Offline Page)
# -----------------------------------------------------------------------------


@blueprint.route("/service-worker.js")  # type: ignore[misc]
def service_worker() -> Response:
    """Serve service worker from root scope for PWA functionality."""
    response = send_from_directory(
        blueprint.static_folder,
        "js/service-worker.js",
        mimetype="application/javascript",
    )
    # Allow service worker to control all pages
    response.headers["Service-Worker-Allowed"] = "/"
    return response  # type: ignore[no-any-return]


@blueprint.route("/manifest.json")  # type: ignore[misc]
def manifest() -> Response:
    """Serve PWA manifest from root."""
    return send_from_directory(
        blueprint.static_folder,
        "manifest.json",
        mimetype="application/manifest+json",
    )  # type: ignore[no-any-return]


@blueprint.route("/offline")  # type: ignore[misc]
def offline() -> str:
    """Offline fallback page for PWA."""
    return render_template("core/desktop/offline.html")  # type: ignore[no-any-return]


@blueprint.route("/")  # type: ignore[misc]
@login_required  # type: ignore[misc]
def index() -> Response | str:
    """Redirect root based on user role"""
    # All users go to Dashboard (admins see metrics, non-admins see employee portal)
    return redirect(url_for("dashboard_bp.index"))  # type: ignore[no-any-return]


@blueprint.route("/no-workspace")  # type: ignore[misc]
def no_workspace() -> str:
    """Show 'no workspace access' page for users removed from all workspaces."""
    if not current_user.is_authenticated:
        return redirect(url_for("core_bp.login"))
    return render_template("core/desktop/no_workspace.html")


@blueprint.route("/login", methods=["GET", "POST"])  # type: ignore[misc]
@rate_limit(limit=10, window=60)  # type: ignore[misc]
def login() -> Response | str:
    from modules.base.core.models.auth_settings import AuthSettings
    from system.email import send_email, is_configured as email_is_configured
    from system.email.templates import get_magic_link_email_html

    # Redirect if user is already logged in
    if current_user.is_authenticated:
        if getattr(g, "workspace_id", None) is None:
            if getattr(g, "organization_id", None):
                return redirect(url_for("core_bp.org_landing"))
            return redirect(url_for("core_bp.personal_shell"))
        return redirect(url_for("dashboard_bp.index"))  # type: ignore[no-any-return]

    has_workspace = getattr(g, "workspace_id", None) is not None

    # Workspace-aware settings (only available with workspace context)
    auth_settings = AuthSettings.get_instance() if has_workspace else None

    # Build OAuth providers list for template (env-var-based, not workspace-dependent)
    oauth_providers = _build_oauth_providers()

    # Redirect to magic link page in production when no OAuth providers are configured
    # (when OAuth IS configured, the unified login page handles everything)
    if has_workspace and not oauth_providers:
        settings = WorkspaceSettings.get_instance()
        if settings.onboarding_completed and not current_app.debug and auth_settings.magic_link_enabled and email_is_configured():
            return redirect(url_for("core_bp.magic_link_request"))  # type: ignore[no-any-return]

    account_locked = False

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password")
        remember = bool(request.form.get("remember"))

        # --- Password login ---
        # Without workspace context, always allow password login
        # With workspace context, check auth settings
        if password and (not has_workspace or auth_settings.should_use_password_login()):
            user = User.get_by_email(email)
            result = _password_login(user, password, remember)
            if isinstance(result, Response):
                return result
            account_locked = result

        # --- Default: magic link flow (only with workspace context) ---
        elif email and has_workspace:
            user = User.get_by_email(email)

            if user and user.is_active:
                token = user.generate_magic_link_token()
                magic_link_url = url_for("core_bp.magic_link_verify", token=token, _external=True)
                settings = WorkspaceSettings.get_instance()
                company_name = settings.company_name or "sparQ"

                if email_is_configured():
                    send_email(
                        to=user.email,
                        subject=f"Your login link for {company_name}",
                        html_body=get_magic_link_email_html(company_name, magic_link_url),
                    )

            # Anti-enumeration: always show same message
            flash(_("If an account exists with that email, we've sent you a login link."), "success")
            return redirect(url_for("core_bp.login"))  # type: ignore[no-any-return]

    if has_workspace:
        settings = WorkspaceSettings.get_instance()
        company_name = settings.company_name if settings.company_name else None
    else:
        company_name = None

    taglines = [
        "Business management, simplified.",
        "Your operations. Your way.",
        "Built for small business.",
    ]

    # Determine if password login should be shown
    if auth_settings:
        show_password = auth_settings.should_use_password_login()
    else:
        show_password = not email_is_configured()

    return render_device_template(
        "core/desktop/login.html",
        company_name=company_name,
        taglines=taglines,
        version=get_version(),
        account_locked=account_locked,
        auth_settings=auth_settings,
        oauth_providers=oauth_providers,
        show_password=show_password,
    )  # type: ignore[no-any-return]


@blueprint.route("/logout")  # type: ignore[misc]
@login_required  # type: ignore[misc]
def logout() -> Response | str:
    # MSA transparent mode: use shared cleanup, return to MSA console
    if session.get("msa_transparent_mode"):
        from modules.base.msa.controllers.routes import exit_transparent_mode

        return_id = exit_transparent_mode()
        if return_id:
            return redirect(url_for("msa_bp.workspace_detail", workspace_id=return_id))  # type: ignore[no-any-return]
        return redirect(url_for("msa_bp.dashboard"))  # type: ignore[no-any-return]
    logout_user()
    session.pop("active_workspace_id", None)
    return redirect(url_for("core_bp.login"))  # type: ignore[no-any-return]


# -----------------------------------------------------------------------------
# Workspace Picker & Switching
# -----------------------------------------------------------------------------


@blueprint.route("/workspaces", methods=["GET"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
def workspace_picker() -> Response | str:
    """Show workspace picker for multi-workspace users."""
    from modules.base.core.models.workspace_user import WorkspaceUser
    from modules.base.core.models.workspace import Workspace

    memberships = (
        WorkspaceUser.query
        .filter_by(user_id=current_user.id)
        .join(Workspace)
        .order_by(Workspace.name)
        .all()
    )

    # Auto-select first workspace and go to dashboard (skip picker)
    if memberships:
        session["active_workspace_id"] = str(memberships[0].workspace_id)
    return redirect(url_for("dashboard_bp.index"))  # type: ignore[no-any-return]


@blueprint.route("/workspaces/switch/<uuid:workspace_id>", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
def switch_workspace(workspace_id) -> Response | str:
    """Switch active workspace within the current organization.

    The target workspace must (a) belong to the current organization and
    (b) have an active WorkspaceUser row for the current user. Cross-org
    switches go through /organizations/switch/<uuid> instead.
    """
    from modules.base.core.models.workspace import Workspace
    from modules.base.core.models.workspace_user import WorkspaceUser

    target = Workspace.query.get(workspace_id)
    if target is None:
        flash(_("That workspace no longer exists."), "error")
        return redirect(url_for("dashboard_bp.index"))  # type: ignore[no-any-return]

    # Archived workspaces are read-only placeholders — no switching into them.
    # Restore them first via Org Settings → Workspaces.
    if target.deleted_at is not None:
        flash(_("That workspace is archived. Restore it first from Organization Settings."), "error")
        return redirect(url_for("dashboard_bp.index"))  # type: ignore[no-any-return]

    # Same-organization guard — switching across orgs must go through the
    # organization switcher so g.organization_id flips atomically.
    current_org_id = getattr(g, "organization_id", None)
    if current_org_id and target.organization_id != current_org_id:
        return redirect(
            url_for("core_bp.switch_organization", organization_id=target.organization_id)
        )  # type: ignore[no-any-return]

    # Verify user belongs to this workspace
    membership = (
        WorkspaceUser.query
        .filter_by(user_id=current_user.id, workspace_id=workspace_id)
        .filter(WorkspaceUser.deleted_at.is_(None))
        .first()
    )

    if not membership:
        flash(_("You don't have access to that workspace."), "error")
        return redirect(url_for("core_bp.workspace_picker"))  # type: ignore[no-any-return]

    session["active_workspace_id"] = str(workspace_id)
    return redirect(url_for("dashboard_bp.index"))  # type: ignore[no-any-return]


@blueprint.route("/organizations/switch/<uuid:organization_id>", methods=["POST", "GET"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
def switch_organization(organization_id) -> Response | str:
    """Switch active organization.

    The user must have an active OrganizationUser row for the target. The
    session's active_workspace_id is replaced with the user's first active
    WorkspaceUser in the new organization (or cleared if they have none,
    per §3.5 — org-only member lands on the Organization scope tab).
    """
    from modules.base.core.models.organization_user import OrganizationUser
    from modules.base.core.models.workspace_user import WorkspaceUser

    from modules.base.core.models.organization import Organization

    org_membership = OrganizationUser.get_for_user(current_user.id, organization_id)
    org = Organization.query.get(organization_id) if org_membership else None
    if org_membership is None or not org_membership.is_active or org is None or not org.is_active:
        flash(_("You don't have access to that organization."), "error")
        return redirect(url_for("dashboard_bp.index"))  # type: ignore[no-any-return]

    # Find the user's first active (non-archived) workspace in the target org.
    # skip_tenant_filter: this is a cross-org query by design — g.organization_id
    # still points to the OLD org at this point in the request.
    from modules.base.core.models.workspace import Workspace
    new_membership = (
        WorkspaceUser.query
        .execution_options(skip_tenant_filter=True)
        .filter_by(organization_user_id=org_membership.id)
        .filter(WorkspaceUser.deleted_at.is_(None))
        .join(Workspace, Workspace.id == WorkspaceUser.workspace_id)
        .filter(Workspace.deleted_at.is_(None))
        .order_by(WorkspaceUser.id.asc())
        .first()
    )

    if new_membership:
        session["active_workspace_id"] = str(new_membership.workspace_id)
    else:
        # Org-only member — clear the stale workspace session so the request
        # hook can reset context on the next request.
        session.pop("active_workspace_id", None)

    return redirect(url_for("dashboard_bp.index"))  # type: ignore[no-any-return]


@blueprint.route("/organizations/create", methods=["GET", "POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
def create_organization() -> Response | str:
    """Create a new organization from the personal shell or org switcher."""
    from modules.base.core.models.pending_signup import _provision_org_and_workspace, _seed_after_commit
    from system.utils.email_domain import extract_domain, is_free_email

    if request.method == "POST":
        organization_name = request.form.get("organization_name", "").strip()
        if not organization_name:
            flash(_("Organization name is required."), "error")
            return render_template("core/desktop/create_organization.html")  # type: ignore[no-any-return]

        claimed_domain = None if is_free_email(current_user.email) else extract_domain(current_user.email)

        try:
            org, workspace, _org_user, ts_user = _provision_org_and_workspace(
                user=current_user,
                name=organization_name,
                claimed_domain=claimed_domain,
            )
            db.session.commit()
            _seed_after_commit(workspace, current_user, ts_user)

            session["active_workspace_id"] = str(workspace.id)
            return redirect(url_for("dashboard_bp.index"))  # type: ignore[no-any-return]
        except Exception:
            logger.exception("Organization creation failed")
            db.session.rollback()
            flash(_("Something went wrong. Please try again."), "error")
            return render_template(
                "core/desktop/create_organization.html",
                organization_name=organization_name,
            )  # type: ignore[no-any-return]

    return render_template("core/desktop/create_organization.html")  # type: ignore[no-any-return]


@blueprint.route("/workspaces/create", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
def create_workspace() -> Response | str:
    """Create a new workspace inside the active organization.

    Requires the caller to be an organization admin — enforced inside
    Workspace.create(). Only org admins can grow an organization's workspace
    count per spec §9.2.
    """
    from modules.base.core.models.workspace import Workspace

    name = request.form.get("name", "").strip()
    color = request.form.get("color", "") or None

    if not name:
        flash(_("Workspace name is required."), "error")
        return redirect(url_for("dashboard_bp.index"))  # type: ignore[no-any-return]

    organization_id = getattr(g, "organization_id", None)
    if organization_id is None:
        flash(_("No active organization context."), "error")
        return redirect(url_for("dashboard_bp.index"))  # type: ignore[no-any-return]

    try:
        workspace = Workspace.create(
            name=name,
            organization_id=organization_id,
            creator_user_id=current_user.id,
            color=color,
        )
        # Switch to the new workspace
        session["active_workspace_id"] = str(workspace.id)
        flash(_("Workspace created!"), "success")
    except ValueError as e:
        flash(str(e), "error")
    except Exception:
        db.session.rollback()
        flash(_("Something went wrong creating your workspace. Please try again."), "error")

    return redirect(url_for("dashboard_bp.index"))  # type: ignore[no-any-return]



# -----------------------------------------------------------------------------
# Workspace Signup (bare domain — no workspace context)
# -----------------------------------------------------------------------------

from modules.base.core.models.workspace import RESERVED_SLUGS

import re

_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{1,49}$")


@blueprint.route("/signup", methods=["GET", "POST"])  # type: ignore[misc]
@rate_limit(limit=5, window=60)  # type: ignore[misc]
def signup() -> Response | str:
    """Collect signup info and send an email confirmation link.

    Workspace provisioning is deferred until the user confirms their email
    via the /signup/confirm/<token> route.
    """
    from modules.base.core.models.pending_signup import PendingSignup

    oauth_providers = _build_oauth_providers()

    try:
        from system.email.service import is_configured as _email_check
        email_configured = _email_check()
    except RuntimeError:
        email_configured = False

    if request.method == "POST":
        if not validate_form_timing(min_seconds=2):
            flash(_("Something went wrong. Please try again."), "error")
            return render_template(
                "core/desktop/signup.html",
                oauth_providers=oauth_providers,
                email_configured=email_configured,
                form_ts=generate_form_timestamp(),
            )  # type: ignore[no-any-return]

        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")  # Optional — SSO/magic link users won't set one

        # --- Validation ---
        errors = []
        if not first_name:
            errors.append(_("First name is required."))
        if not last_name:
            errors.append(_("Last name is required."))
        if not email:
            errors.append(_("Email is required."))
        # Email uniqueness check (unscoped — across all workspaces)
        if email and not errors:
            if User.query.filter_by(email=email).first():
                errors.append(_("An account with that email already exists."))

        # Validate password complexity (only if provided)
        if password and not errors:
            pw_errors = validate_password(password)
            if pw_errors:
                errors.extend(pw_errors)

        if password and not errors:
            if is_breached(password):
                errors.append(_("This password has appeared in a data breach. Please choose a different password."))

        if errors:
            flash(" ".join(errors), "error")
            return render_template(
                "core/desktop/signup.html",
                first_name=first_name, last_name=last_name, email=email,
                oauth_providers=oauth_providers,
                email_configured=email_configured,
                form_ts=generate_form_timestamp(),
            )  # type: ignore[no-any-return]

        # --- Create user account ---
        try:
            if email_configured:
                # Email available: create pending signup → send confirmation link
                PendingSignup.cleanup_expired()

                pending = PendingSignup.create_or_update(
                    email=email, password=password,
                    first_name=first_name, last_name=last_name,
                )

                confirm_url = url_for(
                    "core_bp.confirm_signup", token=pending.token, _external=True,
                )

                from system.email.service import send_gateway_email
                from system.email.templates import get_email_confirmation_html

                html_body = get_email_confirmation_html(confirm_url)
                send_gateway_email(email, _("Confirm your sparQ account"), html_body)

                dev_confirm_url = confirm_url if current_app.debug else None

                return render_template(
                    "core/desktop/signup_check_email.html",
                    confirm_url=dev_confirm_url,
                )  # type: ignore[no-any-return]
            else:
                # No email configured: provision immediately with password
                from modules.base.core.models.pending_signup import route_new_signup, _seed_after_commit

                if not password:
                    flash(_("Password is required."), "error")
                    return render_template(
                        "core/desktop/signup.html",
                        first_name=first_name, last_name=last_name, email=email,
                        oauth_providers=oauth_providers,
                        email_configured=email_configured,
                        form_ts=generate_form_timestamp(),
                    )  # type: ignore[no-any-return]

                from werkzeug.security import generate_password_hash

                user = User(
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    password_hash=generate_password_hash(password),
                )
                db.session.add(user)
                db.session.flush()

                result = route_new_signup(user)
                db.session.commit()

                if result.rule == 2 and result.workspace and result.ts_user:
                    _seed_after_commit(result.workspace, user, result.ts_user)

                from flask_login import login_user
                login_user(user, remember=True)

                if result.has_workspace:
                    session["active_workspace_id"] = str(result.workspace.id) if result.workspace else None
                    return redirect(url_for("dashboard_bp.index"))  # type: ignore[no-any-return]
                elif result.primary_organization_id:
                    return redirect("/org-landing")  # type: ignore[no-any-return]
                else:
                    return redirect("/personal-shell")  # type: ignore[no-any-return]

        except Exception:
            logger.exception("Signup failed")
            db.session.rollback()
            flash(_("Something went wrong. Please try again."), "error")
            return render_template(
                "core/desktop/signup.html",
                first_name=first_name, last_name=last_name, email=email,
                oauth_providers=oauth_providers,
                email_configured=email_configured,
                form_ts=generate_form_timestamp(),
            )  # type: ignore[no-any-return]

    # GET
    return render_template("core/desktop/signup.html", oauth_providers=oauth_providers, email_configured=email_configured, form_ts=generate_form_timestamp())  # type: ignore[no-any-return]


@blueprint.route("/signup/confirm/<token>")  # type: ignore[misc]
@rate_limit(limit=10, window=60)  # type: ignore[misc]
def confirm_signup(token: str) -> Response | str:
    """Confirm email and route the user based on the 5-rule domain lookup.

    Called when the user clicks the confirmation link in their email.
    """
    from modules.base.core.models.pending_signup import PendingSignup

    pending = PendingSignup.get_by_token(token)
    if not pending:
        flash(_("Invalid or expired confirmation link. Please sign up again."), "error")
        return redirect(url_for("core_bp.signup"))  # type: ignore[no-any-return]

    try:
        result = pending.confirm()
        if result is None:
            flash(_("An account with that email already exists. Please log in."), "info")
            return redirect(url_for("core_bp.login"))  # type: ignore[no-any-return]

        user = result.user
        login_user(user, remember=True)

        if result.has_workspace:
            from modules.base.core.models.workspace_user import WorkspaceUser
            membership = WorkspaceUser.query.filter_by(user_id=user.id).filter(
                WorkspaceUser.deleted_at.is_(None),
            ).first()
            if membership:
                g.workspace_id = membership.workspace_id
                session["active_workspace_id"] = str(membership.workspace_id)

        if result.rule == 1:
            return redirect(url_for("dashboard_bp.index"))  # type: ignore[no-any-return]
        if result.rule == 2:
            return redirect(url_for("core_bp.onboarding"))  # type: ignore[no-any-return]
        if result.rule == 3:
            return redirect(url_for("core_bp.org_landing"))  # type: ignore[no-any-return]
        # Rules 4 and 5: personal shell
        return redirect(url_for("core_bp.personal_shell"))  # type: ignore[no-any-return]

    except Exception:
        logger.exception("Signup confirmation failed")
        db.session.rollback()
        flash(_("Something went wrong during confirmation. Please try again."), "error")
        return redirect(url_for("core_bp.signup"))  # type: ignore[no-any-return]


@blueprint.route("/personal-shell")  # type: ignore[misc]
@login_required  # type: ignore[misc]
def personal_shell() -> str:
    """Personal shell for users without an organization."""
    from modules.base.core.models.organization_invitation import OrganizationInvitation

    pending_invitations = OrganizationInvitation.get_pending_for_email(current_user.email)
    return render_template(
        "core/desktop/personal_shell.html",
        pending_invitations=pending_invitations,
    )  # type: ignore[no-any-return]


@blueprint.route("/invitations/<int:invitation_id>/accept", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
def accept_invitation(invitation_id: int) -> Response | str:
    """Accept an organization invitation."""
    from modules.base.core.models.organization_invitation import OrganizationInvitation
    from modules.base.core.models.workspace_user import WorkspaceUser

    invitation = OrganizationInvitation.query.get(invitation_id)
    if not invitation or invitation.email != current_user.email.strip().lower():
        return "", 404

    invitation.accept(current_user.id)
    db.session.commit()

    membership = WorkspaceUser.query.filter_by(user_id=current_user.id).filter(
        WorkspaceUser.deleted_at.is_(None),
    ).first()
    if membership:
        session["active_workspace_id"] = str(membership.workspace_id)

    return redirect(url_for("dashboard_bp.index"))  # type: ignore[no-any-return]


@blueprint.route("/invitations/<int:invitation_id>/decline", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
def decline_invitation(invitation_id: int) -> str:
    """Decline an organization invitation."""
    from modules.base.core.models.organization_invitation import OrganizationInvitation

    invitation = OrganizationInvitation.query.get(invitation_id)
    if not invitation or invitation.email != current_user.email.strip().lower():
        return "", 404

    db.session.delete(invitation)
    db.session.commit()
    return ""


@blueprint.route("/org-landing")  # type: ignore[misc]
@login_required  # type: ignore[misc]
def org_landing() -> str:
    """Org landing page for users with org membership but no workspace."""
    from modules.base.core.models.organization_user import OrganizationUser

    organizations = OrganizationUser.get_landing_data(current_user.id)
    if not organizations:
        return redirect(url_for("core_bp.personal_shell"))  # type: ignore[no-any-return]

    return render_template(
        "core/desktop/org_landing.html",
        organizations=organizations,
        organization=organizations[0]["org"],
        org_user=organizations[0]["org_user"],
    )  # type: ignore[no-any-return]


@blueprint.route("/organizations/<uuid:org_id>/dismiss-banner", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
def dismiss_auto_join_banner(org_id) -> str:
    """Dismiss the rule-3 auto-join confirmation banner."""
    from modules.base.core.models.organization_user import OrganizationUser

    org_user = OrganizationUser.get_for_user(current_user.id, org_id)
    if org_user:
        org_user.dismiss_auto_join_banner()
    return ""


@blueprint.route("/organizations/<uuid:org_id>/leave", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
def leave_organization(org_id) -> Response | str:
    """Leave an organization. Blocked if the user is the sole owner."""
    from modules.base.core.models.organization_user import OrganizationUser
    from modules.base.core.models.workspace_user import WorkspaceUser

    allowed, reason = OrganizationUser.can_leave(current_user.id, org_id)
    if not allowed:
        flash(_(reason), "error")
        return redirect(url_for("core_bp.org_landing"))  # type: ignore[no-any-return]

    org_user = OrganizationUser.get_for_user(current_user.id, org_id)
    if org_user:
        for tu in org_user.workspace_users.filter(WorkspaceUser.deleted_at.is_(None)).all():
            tu.soft_delete()
        org_user.deactivate()
        db.session.commit()

    session.pop("active_workspace_id", None)
    return redirect(url_for("core_bp.personal_shell"))  # type: ignore[no-any-return]


@blueprint.route("/workspaces/<uuid:ts_id>/request-join", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
def request_join_workspace(ts_id) -> str:
    """Request to join a workspace — notifies workspace admins."""
    from urllib.parse import quote

    from modules.base.core.models.organization_user import OrganizationUser
    from modules.base.core.models.workspace import Workspace
    from modules.base.core.models.workspace_user import WorkspaceUser

    workspace = Workspace.query.get(ts_id)
    if not workspace:
        return _("Workspace not found."), 404

    org_user = OrganizationUser.get_for_user(current_user.id, workspace.organization_id)
    if not org_user or not org_user.is_active:
        return _("You must be an organization member to request access."), 403

    ts_admins = WorkspaceUser.query.filter_by(
        workspace_id=ts_id, role="admin",
    ).filter(WorkspaceUser.deleted_at.is_(None)).all()

    display = current_user.first_name or current_user.email
    for admin_tu in ts_admins:
        notification = SystemNotification(
            title=f"{display} wants to join {workspace.name}",
            message=f"{current_user.email} requested to join {workspace.name}.",
            type="info",
            target_role="admin",
            user_id=admin_tu.user_id,
            action_url=f"/people/people?invite_email={quote(current_user.email)}",
            organization_id=workspace.organization_id,
            workspace_id=ts_id,
        )
        db.session.add(notification)
    db.session.commit()

    return f'<span class="badge bg-secondary">{_("Request Sent")}</span>'


@blueprint.route("/signup/check-slug")  # type: ignore[misc]
def check_slug() -> Response:
    """AJAX endpoint to check subdomain availability."""
    from modules.base.core.models.workspace import Workspace

    slug = request.args.get("slug", "").strip().lower()
    if not slug or not _SLUG_RE.match(slug) or slug in RESERVED_SLUGS:
        return jsonify({"available": False})  # type: ignore[no-any-return]
    taken = Workspace.query.filter_by(slug=slug).first() is not None
    return jsonify({"available": not taken})  # type: ignore[no-any-return]


def _get_supported_languages() -> dict[str, str]:
    """Get supported languages from installed language packs."""
    from system.lang_packs import get_available_languages

    return {lang["code"]: lang["name"] for lang in get_available_languages()}


@blueprint.route("/settings/language", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
def update_language() -> str:
    lang = request.form.get("language")
    supported = _get_supported_languages()
    if lang in supported:
        session["lang"] = lang
        if current_user.is_authenticated:
            UserSetting.set(current_user.id, "language", lang)
        return jsonify({"success": True})  # type: ignore[no-any-return]
    return jsonify({"error": "Invalid language"})  # type: ignore[no-any-return]


@blueprint.route("/settings/timezone", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
def update_timezone() -> str:
    """Update user's personal timezone setting."""
    from zoneinfo import available_timezones

    tz = request.form.get("timezone", "").strip()
    if tz and tz in available_timezones():
        UserSetting.set(current_user.id, "timezone", tz)
        return jsonify({"success": True})  # type: ignore[no-any-return]
    return jsonify({"error": "Invalid timezone"})  # type: ignore[no-any-return]


@blueprint.route("/settings/start-time", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
def update_start_time() -> str:
    """Update user's approximate work start time.

    Deprecated: prefer POST /settings/schedule. This route writes to both
    UserSetting and MemberSchedule during the transition period.
    """
    from datetime import time as dt_time

    from modules.base.presence.models.member_schedule import MemberSchedule
    from system.auth.current_member import current_member

    time_str = request.form.get("start_time", "").strip()
    if not re.match(r"^\d{2}:\d{2}$", time_str):
        return jsonify({"error": "Invalid time format"}), 422  # type: ignore[return-value]
    hours, mins = map(int, time_str.split(":"))
    if not (0 <= hours < 24 and 0 <= mins < 60):
        return jsonify({"error": "Invalid time"}), 422  # type: ignore[return-value]
    UserSetting.set(current_user.id, "start_time", time_str)

    member = current_member()
    if member:
        start = dt_time(hours, mins)
        end_h = min(hours + 8, 23)
        end_m = mins if hours + 8 < 24 else 59
        end = dt_time(end_h, end_m)
        schedule_data = [
            {"day": d, "start": start, "end": end} for d in range(5)
        ]
        MemberSchedule.set_weekly_schedule(member.id, schedule_data)

    return jsonify({"success": True})  # type: ignore[no-any-return]


@blueprint.route("/settings/schedule", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
def update_schedule() -> str:
    """Save weekly work schedule for the current member."""
    from datetime import time as dt_time

    from modules.base.presence.models.member_schedule import MemberSchedule
    from system.auth.current_member import current_member

    member = current_member()
    if not member:
        return jsonify({"error": "No workspace membership"}), 400  # type: ignore[return-value]

    DAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    schedule_data: list[dict] = []

    for day_idx, day_name in enumerate(DAY_NAMES):
        active = request.form.get(f"{day_name}_active")
        if not active:
            continue
        start_str = request.form.get(f"{day_name}_start", "09:00")
        end_str = request.form.get(f"{day_name}_end", "17:00")
        if not re.match(r"^\d{2}:\d{2}$", start_str) or not re.match(r"^\d{2}:\d{2}$", end_str):
            continue
        status_str = request.form.get(f"{day_name}_status", "in")
        if status_str not in ("in", "remote"):
            status_str = "in"
        sh, sm = map(int, start_str.split(":"))
        eh, em = map(int, end_str.split(":"))
        schedule_data.append({
            "day": day_idx,
            "start": dt_time(sh, sm),
            "end": dt_time(eh, em),
            "default_status": status_str,
        })

    MemberSchedule.set_weekly_schedule(member.id, schedule_data)

    # Keep UserSetting in sync during transition (use Monday start or first active day)
    if schedule_data:
        first_start = schedule_data[0]["start"]
        UserSetting.set(current_user.id, "start_time", first_start.strftime("%H:%M"))

    return jsonify({"success": True})  # type: ignore[no-any-return]


@blueprint.route("/settings")  # type: ignore[misc]
@blueprint.route("/settings/")  # type: ignore[misc]
@login_required  # type: ignore[misc]
def settings() -> Response | str:
    """Settings hub page - redirects to appropriate sub-page"""
    from system.device import is_mobile

    # On desktop, redirect to general settings (admin) or preferences (non-admin)
    if not is_mobile():
        if current_user.is_admin:
            return redirect(url_for("core_bp.settings_company"))
        else:
            return redirect(url_for("core_bp.settings_preferences"))

    # On mobile, render settings index
    return render_template(  # type: ignore[no-any-return]
        "core/mobile/settings/index.html",
        module_name="Settings",
        module_icon="fa-solid fa-cog",
        module_home="dashboard_bp.index",
    )


@blueprint.route("/settings/company", methods=["GET", "POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def settings_company() -> Response | str:
    """General settings — workspace, regional, and organization info combined."""
    from modules.base.core.models.organization import Organization
    from modules.base.core.models.workspace import Workspace, WORKSPACE_COLORS
    from zoneinfo import available_timezones

    workspace = Workspace.query.get(g.workspace_id)
    settings = WorkspaceSettings.get_instance()
    organization = Organization.query.get(workspace.organization_id) if workspace and workspace.organization_id else None

    # If no organization linked yet, create one and link it
    if not organization:
        import uuid

        organization = Organization(
            name=workspace.name or "My Organization",
            slug=workspace.slug or str(uuid.uuid4())[:8],
        )
        db.session.add(organization)
        db.session.flush()
        workspace.organization_id = organization.id
        db.session.commit()

    if request.method == "POST":
        section = request.form.get("_section", "")

        if section == "workspace":
            new_name = request.form.get("company_name", "").strip()
            if new_name:
                workspace.name = new_name
                settings.company_name = new_name
            new_color = request.form.get("color", "")
            if new_color and new_color in WORKSPACE_COLORS:
                workspace.color = new_color
            db.session.commit()
            flash(_("Workspace settings saved"), "success")

        elif section == "regional":
            from modules.base.core.models.workspace_settings import Industry

            first_day = request.form.get("first_day_of_week", "0")
            try:
                first_day_int = int(first_day)
            except ValueError:
                first_day_int = 0

            industry_value = request.form.get("industry", "workforce")
            try:
                industry = Industry(industry_value)
            except ValueError:
                industry = Industry.WORKFORCE

            settings.update(
                timezone=request.form.get("timezone"),
                date_format=request.form.get("date_format"),
                time_format=request.form.get("time_format"),
                currency=request.form.get("currency"),
                first_day_of_week=first_day_int,
                industry=industry,
            )
            flash(_("Regional settings saved"), "success")

        elif section == "work":
            try:
                stale_val = int(request.form.get("stale_days", "3"))
            except ValueError:
                stale_val = 3
            stale_val = max(1, min(30, stale_val))
            settings.update(stale_days=stale_val)
            flash(_("Work settings saved"), "success")

        elif section == "organization":
            organization.name = request.form.get("name", "").strip() or organization.name
            organization.phone = request.form.get("phone", "").strip() or None
            organization.email = request.form.get("email", "").strip() or None
            organization.website = request.form.get("website", "").strip() or None
            organization.tax_id = request.form.get("tax_id", "").strip() or None
            organization.address = request.form.get("address", "").strip() or None
            organization.address_2 = request.form.get("address_2", "").strip() or None
            organization.city = request.form.get("city", "").strip() or None
            organization.state = request.form.get("state", "").strip() or None
            organization.zip_code = request.form.get("zip_code", "").strip() or None
            organization.country = request.form.get("country", "").strip() or None
            db.session.commit()
            flash(_("Organization info saved"), "success")

        return redirect(url_for("core_bp.settings_company"))  # type: ignore[no-any-return]

    # Common timezones (filter to show cleaner list)
    all_timezones = sorted(available_timezones())
    common_timezones = [tz for tz in all_timezones if "/" in tz and not tz.startswith(("Etc/", "posix/", "right/", "SystemV/"))]

    return render_device_template(  # type: ignore[no-any-return]
        "core/desktop/settings/company.html",
        workspace=workspace,
        settings=settings,
        organization=organization,
        timezones=common_timezones,
        module_name="Settings",
        module_icon="fa-solid fa-cog",
        module_home="dashboard_bp.index",
    )


@blueprint.route("/settings/regional")  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def settings_regional() -> Response | str:
    """Regional settings — mobile renders dedicated page; desktop redirects to General."""
    from system.device import is_mobile
    from zoneinfo import available_timezones

    if is_mobile():
        settings = WorkspaceSettings.get_instance()
        all_timezones = sorted(available_timezones())
        common_timezones = [
            tz for tz in all_timezones
            if "/" in tz and not tz.startswith(("Etc/", "posix/", "right/", "SystemV/"))
        ]
        return render_template(  # type: ignore[no-any-return]
            "core/mobile/settings/regional.html",
            settings=settings,
            timezones=common_timezones,
            module_name="Settings",
            module_icon="fa-solid fa-cog",
            module_home="dashboard_bp.index",
        )
    return redirect(url_for("core_bp.settings_company"))  # type: ignore[no-any-return]


@blueprint.route("/settings/organization")  # type: ignore[misc]
@blueprint.route("/settings/organization/")  # type: ignore[misc]
@login_required  # type: ignore[misc]
def settings_organization() -> Response | str:
    """Organization Settings — dedicated org-admin page (Phase 6).

    Accessed only from the top-right account dropdown. Tabbed sections:
    General / Workspaces / Members / Channels / Audit Log.

    Requires organization admin. Non-org-admins get a 403 via the inner
    decorator call instead of silently redirecting.
    """
    from modules.base.core.models.audit_log import AuditLog
    from modules.base.core.models.organization import Organization
    from modules.base.updates.models.channel import UpdateChannel
    from modules.base.core.models.organization_user import OrganizationUser
    from modules.base.core.models.workspace import Workspace
    from modules.base.core.models.user import User

    if not getattr(g, "is_organization_admin", False):
        flash(_("Organization admin access required."), "error")
        return redirect(url_for("dashboard_bp.index"))  # type: ignore[no-any-return]

    organization = Organization.query.get(g.organization_id)
    can_delete_org = Organization.can_delete(g.organization_id, current_user.id)
    tab = (request.args.get("tab") or "general").strip().lower()

    workspaces_active = Workspace.active_in_organization(g.organization_id)
    workspaces_archived = Workspace.archived_in_organization(g.organization_id)

    org_members = []
    if tab == "members":
        rows = OrganizationUser.list_for_organization(g.organization_id, active_only=False)
        for ou in rows:
            user = User.query.get(ou.user_id)
            if user is None:
                continue
            workspace_memberships = ou.workspace_users.filter_by().all()
            ts_names = []
            for tu in workspace_memberships:
                ts = Workspace.query.get(tu.workspace_id)
                if ts and ts.deleted_at is None:
                    ts_names.append(ts.name)
            org_members.append({
                "organization_user": ou,
                "user": user,
                "workspace_names": ts_names,
            })

    channels = []
    if tab == "channels":
        channels = UpdateChannel.list_org_wide()

    audit_entries = []
    if tab == "audit-log":
        audit_entries = AuditLog.list_for_organization(g.organization_id, limit=100)

    org_admin_count = OrganizationUser.count_admins(g.organization_id) if tab == "members" else 0

    return render_device_template(  # type: ignore[no-any-return]
        "core/desktop/settings/organization.html",
        active_tab=tab,
        organization=organization,
        can_delete_org=can_delete_org,
        workspaces_active=workspaces_active,
        workspaces_archived=workspaces_archived,
        org_members=org_members,
        org_admin_count=org_admin_count,
        channels=channels,
        audit_entries=audit_entries,
        module_name="Settings",
        module_icon="fa-solid fa-cog",
        module_home="dashboard_bp.index",
    )


@blueprint.route("/settings/business")  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def settings_business() -> Response:
    """Legacy alias — kept so existing bookmarks continue to work."""
    return redirect(url_for("core_bp.settings_organization"))  # type: ignore[no-any-return]


@blueprint.route("/settings/organization/delete", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
def delete_organization() -> Response:
    """Delete (deactivate) the current organization. Owner-only."""
    from modules.base.core.models.organization import Organization

    if not Organization.can_delete(g.organization_id, current_user.id):
        flash(_("You cannot delete this organization."), "error")
        return redirect(url_for("core_bp.settings_organization"))  # type: ignore[no-any-return]

    org = Organization.query.get(g.organization_id)
    org.deactivate()
    session.pop("active_workspace_id", None)
    flash(_("Organization deleted."), "success")
    return redirect(url_for("dashboard_bp.index"))  # type: ignore[no-any-return]


# -----------------------------------------------------------------------------
# Organization-admin actions (Phase 6 §12.5, §5 Channels)
# -----------------------------------------------------------------------------

@blueprint.route("/settings/organization/workspaces/<uuid:workspace_id>/archive",
                 methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
def archive_workspace(workspace_id) -> Response:
    """Archive a workspace (org-admin only).

    Soft-deletes the workspace and writes an AuditLog entry via
    Workspace.archive(). Contents are preserved and restorable.
    """
    from modules.base.core.models.workspace import Workspace

    if not getattr(g, "is_organization_admin", False):
        flash(_("Organization admin access required."), "error")
        return redirect(url_for("dashboard_bp.index"))  # type: ignore[no-any-return]

    ts = Workspace.query.get(workspace_id)
    if ts is None or ts.organization_id != g.organization_id:
        flash(_("Workspace not found."), "error")
        return redirect(url_for("core_bp.settings_organization", tab="workspaces"))  # type: ignore[no-any-return]

    if ts.deleted_at is not None:
        flash(_("That workspace is already archived."), "info")
        return redirect(url_for("core_bp.settings_organization", tab="workspaces"))  # type: ignore[no-any-return]

    try:
        ts.archive(actor_user_id=current_user.id)
    except ValueError as e:
        flash(_(str(e)), "error")
        return redirect(url_for("core_bp.settings_organization", tab="workspaces"))  # type: ignore[no-any-return]

    # If the archived workspace was the user's active one, clear the session
    # pointer so the next request resolves a fresh active workspace.
    if session.get("active_workspace_id") == str(workspace_id):
        session.pop("active_workspace_id", None)

    flash(_("Workspace archived."), "success")
    return redirect(url_for("core_bp.settings_organization", tab="workspaces"))  # type: ignore[no-any-return]


@blueprint.route("/settings/organization/workspaces/<uuid:workspace_id>/restore",
                 methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
def restore_workspace(workspace_id) -> Response:
    """Restore an archived workspace (org-admin only)."""
    from modules.base.core.models.workspace import Workspace

    if not getattr(g, "is_organization_admin", False):
        flash(_("Organization admin access required."), "error")
        return redirect(url_for("dashboard_bp.index"))  # type: ignore[no-any-return]

    ts = Workspace.query.get(workspace_id)
    if ts is None or ts.organization_id != g.organization_id:
        flash(_("Workspace not found."), "error")
        return redirect(url_for("core_bp.settings_organization", tab="workspaces"))  # type: ignore[no-any-return]

    if ts.deleted_at is None:
        flash(_("That workspace is already active."), "info")
        return redirect(url_for("core_bp.settings_organization", tab="workspaces"))  # type: ignore[no-any-return]

    ts.restore_archived(actor_user_id=current_user.id)
    flash(_("Workspace restored."), "success")
    return redirect(url_for("core_bp.settings_organization", tab="workspaces"))  # type: ignore[no-any-return]


@blueprint.route("/settings/organization/channels", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
def create_organization_channel() -> Response:
    """Org-admin: create a new organization-level channel."""
    from modules.base.updates.models.channel import UpdateChannel

    if not getattr(g, "is_organization_admin", False):
        flash(_("Organization admin access required."), "error")
        return redirect(url_for("dashboard_bp.index"))  # type: ignore[no-any-return]

    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip() or None
    is_default = bool(request.form.get("is_default"))

    try:
        UpdateChannel.create_org_wide(
            name=name,
            description=description,
            is_default=is_default,
        )
        flash(_("Channel created."), "success")
    except ValueError as e:
        flash(str(e), "error")
    except Exception:
        db.session.rollback()
        flash(_("Something went wrong creating the channel."), "error")

    return redirect(url_for("core_bp.settings_organization", tab="channels"))  # type: ignore[no-any-return]


@blueprint.route("/settings/organization/channels/<int:channel_id>/delete",
                 methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
def delete_organization_channel(channel_id: int) -> Response:
    """Org-admin: hard-delete an organization channel."""
    from modules.base.updates.models.channel import UpdateChannel

    if not getattr(g, "is_organization_admin", False):
        flash(_("Organization admin access required."), "error")
        return redirect(url_for("dashboard_bp.index"))  # type: ignore[no-any-return]

    ch = UpdateChannel.query.get(channel_id)
    if (
        ch is None
        or ch.organization_id != g.organization_id
        or ch.workspace_id is not None
    ):
        flash(_("Channel not found."), "error")
        return redirect(url_for("core_bp.settings_organization", tab="channels"))  # type: ignore[no-any-return]

    ch.hard_delete()
    flash(_("Channel deleted."), "success")
    return redirect(url_for("core_bp.settings_organization", tab="channels"))  # type: ignore[no-any-return]


@blueprint.route("/settings/organization/save", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
def save_organization_info() -> Response:
    """Org-admin: save organization info (name, contact, address)."""
    from modules.base.core.models.organization import Organization

    if not getattr(g, "is_organization_admin", False):
        flash(_("Organization admin access required."), "error")
        return redirect(url_for("dashboard_bp.index"))  # type: ignore[no-any-return]

    organization = Organization.query.get(g.organization_id)
    if organization is None:
        flash(_("Organization not found."), "error")
        return redirect(url_for("dashboard_bp.index"))  # type: ignore[no-any-return]

    form = request.form
    organization.update_info(
        name=form.get("name", ""),
        phone=form.get("phone", ""), email=form.get("email", ""),
        website=form.get("website", ""), tax_id=form.get("tax_id", ""),
        address=form.get("address", ""), address_2=form.get("address_2", ""),
        city=form.get("city", ""), state=form.get("state", ""),
        zip_code=form.get("zip_code", ""), country=form.get("country", ""),
    )
    flash(_("Organization info saved."), "success")
    return redirect(url_for("core_bp.settings_organization", tab="general"))  # type: ignore[no-any-return]


@blueprint.route("/settings/organization/members/<int:org_user_id>/role",
                 methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
def update_org_member_role(org_user_id: int) -> Response:
    """Org-admin: promote/demote an organization member's role."""
    from modules.base.core.models.organization_user import OrganizationUser

    members_url = url_for("core_bp.settings_organization", tab="members")

    if not getattr(g, "is_organization_admin", False):
        flash(_("Organization admin access required."), "error")
        return redirect(url_for("dashboard_bp.index"))  # type: ignore[no-any-return]

    target = OrganizationUser.query.get(org_user_id)
    if target is None or target.organization_id != g.organization_id:
        flash(_("Member not found."), "error")
        return _org_members_redirect(members_url)

    new_role = request.form.get("role", "").strip()
    if new_role not in ("admin", "member"):
        flash(_("Invalid role."), "error")
        return _org_members_redirect(members_url)

    if target.role == "admin" and new_role != "admin":
        if OrganizationUser.count_admins(g.organization_id) <= 1:
            flash(_("Cannot remove the only organization administrator."), "error")
            return _org_members_redirect(members_url)

    target.set_role(new_role)
    flash(_("Role updated."), "success")
    return _org_members_redirect(members_url)


def _org_members_redirect(url: str) -> Response:
    """Return HX-Redirect for HTMX requests, normal redirect otherwise."""
    if request.headers.get("HX-Request") == "true":
        response = make_response()
        response.headers["HX-Redirect"] = url
        return response  # type: ignore[return-value]
    return redirect(url)  # type: ignore[return-value]


@blueprint.route("/settings/projects")  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def settings_projects() -> Response | str:
    """Project status settings — workspace admin manages status list."""
    from modules.base.projects.models.project_status import MAX_PROJECT_STATUSES, ProjectStatus

    statuses = ProjectStatus.get_for_workspace()
    if not statuses:
        ProjectStatus.seed_defaults()
        db.session.commit()
        statuses = ProjectStatus.get_for_workspace()
    return render_device_template(
        "core/desktop/settings/projects.html",
        statuses=statuses,
        max_project_statuses=MAX_PROJECT_STATUSES,
        module_name=_("Settings"),
        module_icon="fa-solid fa-cog",
        module_home="dashboard_bp.index",
        active_page="projects_settings",
    )


@blueprint.route("/settings/projects/add", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def settings_projects_add() -> Response:
    """Add a new project status for this workspace."""
    from modules.base.projects.models.project_status import ProjectStatus

    ps, err = ProjectStatus.add(
        label=request.form.get("label", "").strip(),
        code=request.form.get("code", "").strip().lower().replace(" ", "_"),
        color=request.form.get("color", "#6b7280").strip(),
        is_default=request.form.get("is_default") == "on",
    )
    if err:
        flash(_(err), "error")
    else:
        flash(_("Status added."), "success")
    return redirect(url_for("core_bp.settings_projects"))  # type: ignore[return-value]


@blueprint.route("/settings/projects/<int:status_id>/update", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def settings_projects_update(status_id: int) -> Response:
    """Update label, color, is_archived, or is_default for a project status."""
    from modules.base.projects.models.project_status import ProjectStatus

    ps = ProjectStatus.scoped().filter_by(id=status_id).first()
    ok, err = ProjectStatus.update(
        status_id,
        label=request.form.get("label", "").strip(),
        color=request.form.get("color", ps.color if ps else "#6b7280").strip(),
        is_archived=request.form.get("is_archived") == "on",
        is_default=request.form.get("is_default") == "on",
    )
    if err:
        flash(_(err), "error")
    else:
        flash(_("Status updated."), "success")
    return redirect(url_for("core_bp.settings_projects"))  # type: ignore[return-value]


@blueprint.route("/settings/projects/<int:status_id>/delete", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def settings_projects_delete(status_id: int) -> Response:
    """Delete a project status (blocked if projects use it or it's the only archived status)."""
    from modules.base.projects.models.project_status import ProjectStatus

    ok, err = ProjectStatus.delete(status_id)
    if err:
        flash(_(err), "error")
    else:
        flash(_("Status deleted."), "success")
    return redirect(url_for("core_bp.settings_projects"))  # type: ignore[return-value]


@blueprint.route("/settings/projects/<int:status_id>/set-default", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def settings_projects_set_default(status_id: int) -> Response:
    """Mark a status as the default for new projects."""
    from modules.base.projects.models.project_status import ProjectStatus

    ok, err = ProjectStatus.set_default(status_id)
    if err:
        flash(_(err), "error")
    else:
        flash(_("Default status updated."), "success")
    return redirect(url_for("core_bp.settings_projects"))  # type: ignore[return-value]


@blueprint.route("/settings/projects/reorder", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def settings_projects_reorder() -> Response:
    """Bulk-update sort_order for project statuses. Accepts JSON [{id, sort_order}, ...]."""
    from modules.base.projects.models.project_status import ProjectStatus

    ProjectStatus.bulk_reorder(request.get_json(silent=True) or [])
    return jsonify({"ok": True})


@blueprint.route("/settings/preferences")  # type: ignore[misc]
@login_required  # type: ignore[misc]
def settings_preferences() -> str:
    """User preferences settings"""
    from modules.base.core.models.workspace_settings import WorkspaceSettings

    ts_settings = WorkspaceSettings.get_instance()
    current_timezone = UserSetting.get(current_user.id, "timezone") or ts_settings.timezone or "America/Chicago"

    timezones = [
        ("America/New_York", "America / New York (Eastern)"),
        ("America/Chicago", "America / Chicago (Central)"),
        ("America/Denver", "America / Denver (Mountain)"),
        ("America/Los_Angeles", "America / Los Angeles (Pacific)"),
        ("America/Anchorage", "America / Anchorage (Alaska)"),
        ("America/Phoenix", "America / Phoenix (Arizona)"),
        ("America/Toronto", "America / Toronto"),
        ("America/Vancouver", "America / Vancouver"),
        ("America/Sao_Paulo", "America / Sao Paulo"),
        ("America/Mexico_City", "America / Mexico City"),
        ("America/Bogota", "America / Bogota"),
        ("America/Argentina/Buenos_Aires", "America / Buenos Aires"),
        ("Europe/London", "Europe / London (GMT)"),
        ("Europe/Paris", "Europe / Paris (CET)"),
        ("Europe/Berlin", "Europe / Berlin (CET)"),
        ("Europe/Madrid", "Europe / Madrid (CET)"),
        ("Europe/Rome", "Europe / Rome (CET)"),
        ("Europe/Amsterdam", "Europe / Amsterdam (CET)"),
        ("Europe/Zurich", "Europe / Zurich (CET)"),
        ("Europe/Stockholm", "Europe / Stockholm (CET)"),
        ("Europe/Warsaw", "Europe / Warsaw (CET)"),
        ("Europe/Athens", "Europe / Athens (EET)"),
        ("Europe/Istanbul", "Europe / Istanbul"),
        ("Europe/Moscow", "Europe / Moscow"),
        ("Asia/Dubai", "Asia / Dubai (GST)"),
        ("Asia/Kolkata", "Asia / Kolkata (IST)"),
        ("Asia/Shanghai", "Asia / Shanghai (CST)"),
        ("Asia/Tokyo", "Asia / Tokyo (JST)"),
        ("Asia/Seoul", "Asia / Seoul (KST)"),
        ("Asia/Singapore", "Asia / Singapore (SGT)"),
        ("Asia/Hong_Kong", "Asia / Hong Kong"),
        ("Asia/Bangkok", "Asia / Bangkok (ICT)"),
        ("Asia/Jakarta", "Asia / Jakarta (WIB)"),
        ("Asia/Karachi", "Asia / Karachi (PKT)"),
        ("Asia/Riyadh", "Asia / Riyadh (AST)"),
        ("Pacific/Auckland", "Pacific / Auckland (NZST)"),
        ("Pacific/Fiji", "Pacific / Fiji"),
        ("Pacific/Honolulu", "Pacific / Honolulu (HST)"),
        ("Australia/Sydney", "Australia / Sydney (AEST)"),
        ("Australia/Melbourne", "Australia / Melbourne (AEST)"),
        ("Australia/Perth", "Australia / Perth (AWST)"),
        ("Africa/Cairo", "Africa / Cairo (EET)"),
        ("Africa/Lagos", "Africa / Lagos (WAT)"),
        ("Africa/Johannesburg", "Africa / Johannesburg (SAST)"),
        ("Africa/Nairobi", "Africa / Nairobi (EAT)"),
    ]

    current_start_time = UserSetting.get(current_user.id, "start_time") or "09:00"

    from modules.base.presence.models.member_schedule import MemberSchedule
    from system.auth.current_member import current_member

    member = current_member()
    weekly_schedule: dict[int, dict] = {}
    if member:
        sched = MemberSchedule.get_weekly_schedule(member.id)
        for day_num, row in sched.items():
            weekly_schedule[day_num] = {
                "start": row.start_time.strftime("%H:%M"),
                "end": row.end_time.strftime("%H:%M"),
                "default_status": row.default_status or "in",
            }

    return render_device_template(  # type: ignore[no-any-return]
        "core/desktop/settings/preferences.html",
        languages=_get_supported_languages(),
        current_language=session.get("lang", "en"),
        current_timezone=current_timezone,
        timezones=timezones,
        current_start_time=current_start_time,
        weekly_schedule=weekly_schedule,
        module_name="Settings",
        module_icon="fa-solid fa-cog",
        module_home="dashboard_bp.index",
    )


@blueprint.route("/about")  # type: ignore[misc]
@login_required  # type: ignore[misc]
def about() -> str:
    """About page with version info and copyright."""
    return render_device_template(  # type: ignore[no-any-return]
        "core/desktop/about.html",
        module_name="About",
        module_icon="fa-solid fa-info-circle",
        module_home="dashboard_bp.index",
        active_page="about",
    )


@blueprint.route("/settings/updates")  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def settings_updates() -> str:
    """Settings → Updates: update-service status and disclosure."""
    from system import update_check

    return render_device_template(  # type: ignore[no-any-return]
        "core/desktop/settings/updates.html",
        status=update_check.read_status(),
        current_version=get_version(),
        checks_enabled=update_check.is_enabled(),
        payload=update_check.build_payload(),
        active_page="updates",
        module_name="Settings",
        module_icon="fa-solid fa-cog",
        module_home="dashboard_bp.index",
    )


@blueprint.route("/settings/updates/check", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def settings_updates_check() -> Response:
    """Manually run an update check (respects the SPARQ_UPDATE_CHECK opt-out)."""
    from system import update_check

    if not update_check.is_enabled():
        flash(
            _(
                "Automatic update checks are disabled. sparQ may not receive "
                "security or compatibility update notices."
            ),
            "warning",
        )
        return redirect(url_for("core_bp.settings_updates"))  # type: ignore[no-any-return]

    status = update_check.run_check(force=True)
    if status is None:
        flash(_("Could not reach the update service. Please try again later."), "error")
    elif status.get("update_available"):
        flash(
            _("A newer version of sparQ is available:") + f" {status.get('latest_version') or ''}",
            "info",
        )
    else:
        flash(_("sparQ is up to date."), "success")
    return redirect(url_for("core_bp.settings_updates"))  # type: ignore[no-any-return]


@blueprint.route("/settings/install-app")  # type: ignore[misc]
@login_required  # type: ignore[misc]
def install_app() -> str:
    """PWA installation page with browser-specific instructions."""
    return render_device_template(  # type: ignore[no-any-return]
        "core/desktop/settings/install_app.html",
        module_name="Settings",
        module_icon="fa-solid fa-cog",
        module_home="dashboard_bp.index",
    )


@blueprint.route("/settings/apps")  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def manage_apps() -> str:
    """Apps management page - shows core modules, plugins, and standalone apps"""
    core_modules = []
    plugin_modules = []
    app_modules = []

    # Scan base, plugins, and apps folders
    for folder in ["base", "plugins", "apps"]:
        folder_path = os.path.join("modules", folder)
        if not os.path.isdir(folder_path):
            continue

        for module_name in os.listdir(folder_path):
            module_path = os.path.join(folder_path, module_name)

            if os.path.isdir(module_path) and not module_name.startswith("_"):
                try:
                    # Load the manifest
                    manifest = importlib.import_module(
                        f"modules.{folder}.{module_name}.__manifest__"
                    ).manifest.copy()

                    # Check if module is disabled
                    disabled_file = os.path.join(module_path, "__DISABLED__")
                    manifest["enabled"] = not os.path.exists(disabled_file)
                    manifest["_folder"] = folder  # Track which folder it's in

                    # Categorize by folder
                    if folder == "base":
                        core_modules.append(manifest)
                    elif folder == "plugins":
                        plugin_modules.append(manifest)
                    else:  # apps
                        app_modules.append(manifest)
                except Exception as e:
                    print(f"Error loading manifest for {folder}/{module_name}: {e}")

    # Custom sort order for core modules
    core_order = ["Core", "Dashboard", "Team", "Sales", "Service", "Billing", "Finance", "Marketing", "Chat"]
    def core_sort_key(mod: dict) -> int:
        try:
            return core_order.index(mod["name"])
        except ValueError:
            return len(core_order)  # Unknown modules go at the end

    return render_template(
        "core/desktop/settings/apps.html",
        core_modules=sorted(core_modules, key=core_sort_key),
        plugin_modules=sorted(plugin_modules, key=lambda x: x["name"]),
        app_modules=sorted(app_modules, key=lambda x: x["name"]),
        module_name="Settings",
        module_icon="fa-solid fa-cog",
        module_home="dashboard_bp.index",
        installed_modules=g.installed_modules,
    )


@blueprint.route("/api/modules/toggle", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def toggle_module() -> Response | tuple[Any, int]:
    """Toggle module enabled/disabled state"""
    data = request.get_json()
    module_name = data.get("module")
    folder = data.get("folder", "plugins")  # Default to plugins for safety
    enabled = data.get("enabled")

    if not module_name:
        return jsonify({"error": "Module name required"})  # type: ignore[no-any-return]

    known = {(m.get("folder"), m.get("name")) for m in (g.installed_modules or [])}
    if (folder, module_name) not in known:
        return jsonify({"error": "Unknown module"}), 400  # type: ignore[return-value]

    module_path = os.path.join("modules", folder, module_name)
    disabled_file = os.path.join(module_path, "__DISABLED__")

    try:
        if enabled and os.path.exists(disabled_file):
            os.remove(disabled_file)
        elif not enabled and not os.path.exists(disabled_file):
            open(disabled_file, "a").close()

        # After toggling, trigger a restart
        if current_app.debug:
            main_app_file = os.path.abspath(sys.modules["__main__"].__file__)
            print(f"Debug mode: Triggering reload by touching {main_app_file}")
            os.utime(main_app_file, None)

        return jsonify(  # type: ignore[no-any-return]
            {
                "success": True,
                "message": f"Module {module_name} {'enabled' if enabled else 'disabled'}. Restarting application...",
            }
        )  # type: ignore[no-any-return]
    except Exception as e:
        print(f"Error toggling module: {e}")
        print(f"Error type: {type(e)}")
        return jsonify({"error": str(e)}), 500  # type: ignore[no-any-return]


@blueprint.route("/exception")  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def test_exception() -> str:
    """Test route to trigger a 500 error page"""
    # Deliberately raise an exception
    raise Exception("This is a test exception to verify the 500 error page functionality")


@blueprint.app_errorhandler(500)
def handle_500_error(e):
    """Handle internal server errors"""
    # Set up error context
    g.current_module = {
        "name": "Error",
        "color": "#dc3545",  # Bootstrap danger color
        "icon_class": "fas fa-exclamation-triangle",
    }
    g.installed_modules = []

    return render_template(
        "core/desktop/errors/500.html",
        error=str(e),
        module_name="Error",
        module_icon="fas fa-exclamation-triangle",
        module_home="dashboard_bp.index",
    ), 500


@blueprint.app_errorhandler(404)
def handle_404_error(e):
    """Handle 404 errors"""
    # If not logged in, redirect to login
    if not current_user.is_authenticated:
        return redirect(url_for("core_bp.login"))

    # Set up error context for logged-in users
    g.current_module = {
        "name": "Error",
        "color": "#dc3545",
        "icon_class": "fas fa-exclamation-triangle",
    }
    g.installed_modules = []

    return render_template(
        "core/desktop/errors/404.html",
        error=str(e),
        module_name="Error",
        module_icon="fas fa-exclamation-triangle",
        module_home="dashboard_bp.index",
    ), 404



@blueprint.route("/settings/permissions")  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def manage_permissions() -> str:
    """Permission management page — manage user roles and permission areas."""
    from modules.base.core.models.workspace_user import WorkspaceUser
    from sqlalchemy.orm import joinedload

    members = WorkspaceUser.scoped().options(joinedload(WorkspaceUser.user)).all()
    return render_device_template(  # type: ignore[no-any-return]
        "core/desktop/settings/permissions.html",
        members=members,
        permission_areas=["hr", "finance", "operations"],
        module_name="Settings",
        module_icon="fa-solid fa-cog",
        module_home="dashboard_bp.index",
    )  # type: ignore[no-any-return]


@blueprint.route("/settings/permissions/users/<int:user_id>", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def update_user_permissions(user_id: int) -> str:
    """Update user's role (admin/member) from the permissions page."""
    from sqlalchemy.orm import joinedload
    from modules.base.core.models.workspace_user import WorkspaceUser
    try:
        member = (
            WorkspaceUser.scoped()
            .options(joinedload(WorkspaceUser.user))
            .filter_by(user_id=user_id)
            .first_or_404()
        )
        user = member.user

        # Determine target role from form (whitelist-validated)
        target_role = request.form.get("role", member.role)
        if target_role not in ("admin", "member"):
            flash(_("Invalid role"), "error")
            if request.headers.get("HX-Request") == "true":
                response = make_response()
                response.headers["HX-Redirect"] = url_for("core_bp.manage_permissions")
                return response
            return redirect(url_for("core_bp.manage_permissions"))

        # Sole-admin protection: cannot demote the last admin
        if member.role == "admin" and target_role != "admin":
            if user.is_sole_admin:
                flash(_("Cannot remove admin status from the only administrator"), "error")
                if request.headers.get("HX-Request") == "true":
                    response = make_response()
                    response.headers["HX-Redirect"] = url_for("core_bp.manage_permissions")
                    return response
                return redirect(url_for("core_bp.manage_permissions"))

        member.role = target_role

        # Admins have implicit all-access; clear explicit permissions
        if target_role == "admin":
            member.permissions = ""

        db.session.commit()

        if request.headers.get("HX-Request") == "true":
            response = make_response()
            response.headers["HX-Redirect"] = url_for("core_bp.manage_permissions")
            return response
        return redirect(url_for("core_bp.manage_permissions"))

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)})  # type: ignore[no-any-return]


@blueprint.route("/settings/permissions/clear-modal")  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def clear_modal() -> str:
    return ""


@blueprint.route("/settings/templates")  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def settings_templates() -> str:
    """Admin template management — list and manage UpdateTemplates."""
    from modules.base.updates.models.template import UpdateTemplate

    templates = UpdateTemplate.query.filter(
        db.or_(
            UpdateTemplate.workspace_id == g.workspace_id,
            UpdateTemplate.workspace_id.is_(None),
        )
    ).order_by(UpdateTemplate.post_type, UpdateTemplate.sort_order).all()

    grouped = {}
    for t in templates:
        grouped.setdefault(t.post_type, []).append(t)

    return render_device_template(
        "core/desktop/settings/templates.html",
        active_page="settings",
        module_home="core_bp.settings",
        templates=templates,
        grouped_templates=grouped,
    )


@blueprint.route("/settings/templates/create", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def settings_templates_create() -> Response:
    """Create a new UpdateTemplate."""
    from modules.base.updates.models.template import UpdateTemplate

    name = request.form.get("name", "").strip()
    post_type = request.form.get("post_type", "update")
    description = request.form.get("description", "").strip()
    anonymous = request.form.get("anonymous") == "on"
    nudge_enabled = request.form.get("nudge_enabled") == "on"
    nudge_time = request.form.get("nudge_time", "17:00")

    # Build nudge scope from form
    scope_start = request.form.get("nudge_scope_start", "08:00")
    scope_end = request.form.get("nudge_scope_end", "18:00")
    scope_days = [int(d) for d in request.form.getlist("nudge_scope_days") if d.isdigit()]
    nudge_scope = {"start": scope_start, "end": scope_end, "days": scope_days} if scope_days else None

    # Build fields from form
    fields = []
    field_keys = request.form.getlist("field_key[]")
    field_labels = request.form.getlist("field_label[]")
    field_types = request.form.getlist("field_type[]")
    field_required = request.form.getlist("field_required[]")
    field_placeholders = request.form.getlist("field_placeholder[]")
    field_placeholder_modes = request.form.getlist("field_placeholder_mode[]")
    field_options_list = request.form.getlist("field_options[]")

    for i in range(len(field_keys)):
        if field_keys[i].strip():
            field = {
                "key": field_keys[i].strip(),
                "label": field_labels[i].strip() if i < len(field_labels) else "",
                "type": field_types[i] if i < len(field_types) else "text",
                "required": str(i) in field_required,
                "placeholder": field_placeholders[i].strip() if i < len(field_placeholders) else "",
                "placeholder_mode": field_placeholder_modes[i] if i < len(field_placeholder_modes) else "hint",
            }
            raw_opts = field_options_list[i].strip() if i < len(field_options_list) else ""
            if raw_opts and field["type"] == "choice":
                field["options"] = [o.strip() for o in raw_opts.split(",") if o.strip()]
            fields.append(field)

    if not name:
        flash(_("Template name is required."), "error")
        return redirect(url_for("core_bp.settings_templates"))

    # Get max sort_order for this post_type
    max_order = db.session.query(db.func.max(UpdateTemplate.sort_order)).filter(
        UpdateTemplate.post_type == post_type
    ).scalar() or 0

    schedule_type = request.form.get("schedule_type") or None
    interval_minutes = request.form.get("interval_minutes", type=int) or None
    grace_minutes = request.form.get("grace_minutes", type=int) or 30

    # Periodic schedules use active window start, not nudge_time
    if schedule_type == "periodic":
        nudge_time = None

    template = UpdateTemplate(
        workspace_id=g.workspace_id,
        name=name,
        post_type=post_type,
        description=description,
        fields=fields,
        anonymous=anonymous,
        nudge_enabled=nudge_enabled,
        nudge_time=nudge_time,
        nudge_scope=nudge_scope,
        schedule_type=schedule_type,
        interval_minutes=interval_minutes,
        grace_minutes=grace_minutes,
        sort_order=max_order + 1,
    )
    db.session.add(template)
    db.session.commit()

    flash(_("Template created."), "success")
    next_url = request.form.get("next")
    if next_url and next_url.startswith("/"):
        return redirect(next_url)
    return redirect(url_for("core_bp.settings_templates"))


@blueprint.route("/settings/templates/<int:template_id>/edit", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def settings_templates_edit(template_id: int) -> Response:
    """Edit an existing UpdateTemplate."""
    from modules.base.updates.models.template import UpdateTemplate

    template = UpdateTemplate.query.filter(
        UpdateTemplate.id == template_id,
        db.or_(UpdateTemplate.workspace_id == g.workspace_id, UpdateTemplate.workspace_id.is_(None)),
    ).first()
    if not template:
        abort(404)

    template.name = request.form.get("name", "").strip() or template.name
    template.description = request.form.get("description", "").strip() or None
    template.anonymous = request.form.get("anonymous") == "on"
    template.nudge_enabled = request.form.get("nudge_enabled") == "on"
    template.schedule_type = request.form.get("schedule_type") or None
    # Periodic schedules use active window start, not nudge_time
    template.nudge_time = None if template.schedule_type == "periodic" else request.form.get("nudge_time", "17:00")
    scope_start = request.form.get("nudge_scope_start", "08:00")
    scope_end = request.form.get("nudge_scope_end", "18:00")
    scope_days = [int(d) for d in request.form.getlist("nudge_scope_days") if d.isdigit()]
    template.nudge_scope = {"start": scope_start, "end": scope_end, "days": scope_days} if scope_days else None
    template.interval_minutes = request.form.get("interval_minutes", type=int) or None
    template.grace_minutes = request.form.get("grace_minutes", type=int) or 30

    # Rebuild fields from form
    fields = []
    field_keys = request.form.getlist("field_key[]")
    field_labels = request.form.getlist("field_label[]")
    field_types = request.form.getlist("field_type[]")
    field_required = request.form.getlist("field_required[]")
    field_placeholders = request.form.getlist("field_placeholder[]")
    field_placeholder_modes = request.form.getlist("field_placeholder_mode[]")
    field_options_list = request.form.getlist("field_options[]")

    for i in range(len(field_keys)):
        if field_keys[i].strip():
            field = {
                "key": field_keys[i].strip(),
                "label": field_labels[i].strip() if i < len(field_labels) else "",
                "type": field_types[i] if i < len(field_types) else "text",
                "required": str(i) in field_required,
                "placeholder": field_placeholders[i].strip() if i < len(field_placeholders) else "",
                "placeholder_mode": field_placeholder_modes[i] if i < len(field_placeholder_modes) else "hint",
            }
            raw_opts = field_options_list[i].strip() if i < len(field_options_list) else ""
            if raw_opts and field["type"] == "choice":
                field["options"] = [o.strip() for o in raw_opts.split(",") if o.strip()]
            fields.append(field)

    template.fields = fields
    db.session.commit()

    flash(_("Template updated."), "success")
    return redirect(url_for("core_bp.settings_templates"))


@blueprint.route("/settings/templates/<int:template_id>/toggle", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def settings_templates_toggle(template_id: int) -> Response:
    """Toggle a template's is_active status."""
    from modules.base.updates.models.template import UpdateTemplate

    template = UpdateTemplate.query.filter(
        UpdateTemplate.id == template_id,
        db.or_(UpdateTemplate.workspace_id == g.workspace_id, UpdateTemplate.workspace_id.is_(None)),
    ).first()
    if not template:
        abort(404)
    template.is_active = not template.is_active
    db.session.commit()

    status = _("activated") if template.is_active else _("deactivated")
    flash(f"{template.name} {status}.", "success")
    return redirect(url_for("core_bp.settings_templates"))


@blueprint.route("/settings/templates/<int:template_id>/delete", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def settings_templates_delete(template_id: int) -> Response:
    """Delete a custom template (built-in templates cannot be deleted)."""
    from modules.base.updates.models.template import UpdateTemplate

    template = UpdateTemplate.query.filter(
        UpdateTemplate.id == template_id,
        db.or_(UpdateTemplate.workspace_id == g.workspace_id, UpdateTemplate.workspace_id.is_(None)),
    ).first()
    if not template:
        abort(404)
    if template.workspace_id is None:
        flash(_("Built-in templates cannot be deleted."), "error")
        return redirect(url_for("core_bp.settings_templates"))

    db.session.delete(template)
    db.session.commit()

    flash(_("Template deleted."), "success")
    return redirect(url_for("core_bp.settings_templates"))




# -----------------------------------------------------------------------------
# Onboarding
# -----------------------------------------------------------------------------


@blueprint.route("/onboarding", methods=["GET"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
def onboarding() -> Response | str:
    """Organization admin onboarding wizard."""
    # Check if onboarding already completed
    settings = WorkspaceSettings.get_instance()
    if settings.onboarding_completed:
        return redirect(url_for("dashboard_bp.index"))  # type: ignore[no-any-return]

    from system.lang_packs import get_available_languages

    return render_template(  # type: ignore[no-any-return]
        "core/desktop/onboarding/wizard.html",
        settings=settings,
        available_languages=get_available_languages(),
        module_home="dashboard_bp.index",
    )


@blueprint.route("/onboarding", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
def onboarding_submit() -> Response:
    """Process onboarding wizard submission."""
    from modules.base.core.models.workspace import Workspace, WORKSPACE_COLORS

    settings = WorkspaceSettings.get_instance()

    # Get form data
    company_name = request.form.get("company_name", "").strip()
    color = request.form.get("color", "").strip()
    timezone = request.form.get("timezone", "America/Chicago")
    default_language = request.form.get("default_language", "en")

    # Update workspace color
    if color and color in WORKSPACE_COLORS:
        workspace = Workspace.query.get(g.workspace_id)
        if workspace:
            workspace.color = color
            db.session.commit()

    # Update settings
    settings.update(
        company_name=company_name or settings.company_name,
        timezone=timezone,
        default_language=default_language,
        onboarding_completed=True,
    )

    flash(_("Welcome! Your account is set up and ready to use."), "success")
    return redirect(url_for("dashboard_bp.index"))  # type: ignore[no-any-return]


@blueprint.route("/onboarding/skip", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
def onboarding_skip() -> Response:
    """Skip onboarding and use defaults."""
    settings = WorkspaceSettings.get_instance()
    settings.update(onboarding_completed=True)

    flash(_("Onboarding skipped. You can configure settings later."), "info")
    return redirect(url_for("dashboard_bp.index"))  # type: ignore[no-any-return]


# -----------------------------------------------------------------------------
# Instance Setup (first-time only)
# -----------------------------------------------------------------------------


@blueprint.route("/setup", methods=["GET"])  # type: ignore[misc]
@rate_limit(limit=10, window=60)
def instance_setup() -> Response | str:
    """First-time instance setup wizard. Only accessible when no users exist."""
    from modules.base.core.utils.instance_setup import is_fresh_install

    if not is_fresh_install():
        from flask import abort

        abort(404)

    from modules.base.core.models.workspace import WORKSPACE_COLORS
    from system.lang_packs import get_available_languages

    return render_template(  # type: ignore[no-any-return]
        "core/desktop/setup/wizard.html",
        available_languages=get_available_languages(),
        workspace_colors=WORKSPACE_COLORS,
        form_ts=generate_form_timestamp(),
    )


@blueprint.route("/setup", methods=["POST"])  # type: ignore[misc]
@rate_limit(limit=5, window=60)
def instance_setup_submit() -> Response:
    """Process instance setup wizard submission."""
    from modules.base.core.models.workspace import WORKSPACE_COLORS
    from modules.base.core.utils.instance_setup import is_fresh_install, provision_instance

    if not is_fresh_install():
        from flask import abort

        abort(404)

    if not validate_form_timing(min_seconds=2):
        flash(_("Something went wrong. Please try again."), "error")
        return redirect(url_for("core_bp.instance_setup"))  # type: ignore[no-any-return]

    first_name = request.form.get("first_name", "").strip()
    last_name = request.form.get("last_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    company_name = request.form.get("company_name", "").strip()
    color = request.form.get("color", "orange").strip()
    timezone = request.form.get("timezone", "America/Chicago")
    language = request.form.get("default_language", "en")

    errors: list[str] = []
    if not first_name:
        errors.append(_("First name is required."))
    if not last_name:
        errors.append(_("Last name is required."))
    if not email or "@" not in email:
        errors.append(_("A valid email address is required."))
    if not password:
        errors.append(_("Password is required."))
    if not company_name:
        errors.append(_("Organization name is required."))

    if password and not errors:
        pw_errors = validate_password(password)
        if pw_errors:
            errors.extend(pw_errors)

    if password and not errors:
        if is_breached(password):
            errors.append(_("This password has appeared in a data breach. Please choose a different one."))

    if color not in WORKSPACE_COLORS:
        color = "orange"

    if errors:
        for error in errors:
            flash(error, "error")
        return redirect(url_for("core_bp.instance_setup"))  # type: ignore[no-any-return]

    try:
        user, workspace = provision_instance(
            first_name=first_name,
            last_name=last_name,
            email=email,
            password=password,
            company_name=company_name,
            color=color,
            timezone=timezone,
            language=language,
        )

        login_user(user, remember=True)
        session["active_workspace_id"] = str(workspace.id)

        flash(_("Welcome to sparQ! Your instance is ready."), "success")
        return redirect(url_for("dashboard_bp.index"))  # type: ignore[no-any-return]

    except Exception:
        logger.exception("Instance setup failed")
        db.session.rollback()
        flash(_("Something went wrong during setup. Please try again."), "error")
        return redirect(url_for("core_bp.instance_setup"))  # type: ignore[no-any-return]


# -----------------------------------------------------------------------------
# User Security Settings
# -----------------------------------------------------------------------------


@blueprint.route("/settings/security")  # type: ignore[misc]
@login_required  # type: ignore[misc]
def settings_security() -> str:
    """User security settings - manage connected accounts and password."""
    from modules.base.core.models.auth_settings import AuthSettings
    from modules.base.core.models.oauth_connection import OAuthConnection
    from system.oauth.providers import PROVIDERS

    from system.oauth.service import is_provider_enabled

    auth_settings = AuthSettings.get_instance()
    user_connections = OAuthConnection.get_user_connections(current_user.id)

    # Build a dict of provider -> connection for easy lookup
    connections_by_provider = {c.provider: c for c in user_connections}

    # Get list of available providers (enabled via env vars or DB)
    available_providers = []
    for name, config in PROVIDERS.items():
        if is_provider_enabled(name):
            available_providers.append({
                "name": name,
                "config": config,
                "connected": name in connections_by_provider,
                "connection": connections_by_provider.get(name),
            })

    return render_device_template(  # type: ignore[no-any-return]
        "core/desktop/settings/security.html",
        user_connections=user_connections,
        connections_by_provider=connections_by_provider,
        available_providers=available_providers,
        auth_settings=auth_settings,
        has_password=current_user.has_password(),
        active_page="security",
        module_name="Settings",
        module_icon="fa-solid fa-cog",
        module_home="dashboard_bp.index",
    )


@blueprint.route("/settings/security/password", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
def settings_security_password() -> Response:
    """Change or set password."""
    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")

    # Validate new password
    if not new_password:
        flash(_("New password is required."), "error")
        return redirect(url_for("core_bp.settings_security"))  # type: ignore[no-any-return]

    # Validate password complexity
    errors = validate_password(new_password)
    if errors:
        flash(" ".join(errors), "error")
        return redirect(url_for("core_bp.settings_security"))  # type: ignore[no-any-return]

    if new_password != confirm_password:
        flash(_("Passwords do not match."), "error")
        return redirect(url_for("core_bp.settings_security"))  # type: ignore[no-any-return]

    if is_breached(new_password):
        flash(_("This password has appeared in a data breach. Please choose a different password."), "error")
        return redirect(url_for("core_bp.settings_security"))  # type: ignore[no-any-return]

    # If user has a password, verify current password
    if current_user.has_password():
        if not current_user.check_password(current_password):
            flash(_("Current password is incorrect."), "error")
            return redirect(url_for("core_bp.settings_security"))  # type: ignore[no-any-return]

    # Update password
    current_user.password = new_password
    db.session.commit()

    flash(_("Password updated successfully."), "success")
    return redirect(url_for("core_bp.settings_security"))  # type: ignore[no-any-return]


@blueprint.route("/settings/security/phone", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
def settings_security_phone() -> Response:
    """Add or update phone number for SMS login."""
    from system.sms import send_sms, is_configured as sms_is_configured

    phone = request.form.get("phone", "").strip()

    if not phone:
        flash(_("Phone number is required."), "error")
        return redirect(url_for("core_bp.settings_security"))  # type: ignore[no-any-return]

    # Check if phone is already used by another user
    existing = User.get_by_phone(phone)
    if existing and existing.id != current_user.id:
        flash(_("This phone number is already registered to another account."), "error")
        return redirect(url_for("core_bp.settings_security"))  # type: ignore[no-any-return]

    # Update phone number
    current_user.phone_number = phone
    current_user.phone_verified = False
    db.session.commit()

    # Send verification code if SMS is configured
    if sms_is_configured():
        otp = current_user.generate_sms_otp()
        settings = WorkspaceSettings.get_instance()
        company_name = settings.company_name or "sparQ"
        send_sms(phone, f"Your {company_name} verification code is: {otp}. Expires in 5 minutes.")
        flash(_("Phone number saved. A verification code has been sent."), "success")
        return redirect(url_for("core_bp.settings_verify_phone"))  # type: ignore[no-any-return]
    else:
        # Auto-verify if SMS not configured (for development)
        current_user.phone_verified = True
        db.session.commit()
        flash(_("Phone number saved and verified."), "success")

    return redirect(url_for("core_bp.settings_security"))  # type: ignore[no-any-return]


@blueprint.route("/settings/security/phone/verify", methods=["GET", "POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
def settings_verify_phone() -> Response | str:
    """Verify phone number with OTP."""
    if not current_user.phone_number:
        return redirect(url_for("core_bp.settings_security"))  # type: ignore[no-any-return]

    if current_user.phone_verified:
        flash(_("Phone number already verified."), "info")
        return redirect(url_for("core_bp.settings_security"))  # type: ignore[no-any-return]

    if request.method == "POST":
        otp = request.form.get("otp", "").strip()

        if current_user.is_sms_otp_valid(otp):
            current_user.phone_verified = True
            current_user.clear_sms_otp()
            flash(_("Phone number verified successfully."), "success")
            return redirect(url_for("core_bp.settings_security"))  # type: ignore[no-any-return]

        flash(_("Invalid or expired code. Please try again."), "error")

    return render_template("core/desktop/settings/verify_phone.html")  # type: ignore[no-any-return]


# -----------------------------------------------------------------------------
# Password Reset
# -----------------------------------------------------------------------------


@blueprint.route("/auth/forgot-password", methods=["GET", "POST"])  # type: ignore[misc]
@rate_limit(limit=5, window=300)  # type: ignore[misc]
def forgot_password() -> Response | str:
    """Request password reset email."""
    from system.email import send_email, is_configured as email_is_configured
    from system.email.templates import get_password_reset_email_html

    if current_user.is_authenticated:
        return redirect(url_for("core_bp.index"))  # type: ignore[no-any-return]

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()

        if not email:
            flash(_("Please enter your email address."), "error")
            return render_template("core/desktop/auth/forgot_password.html", version=get_version())  # type: ignore[no-any-return]

        user = User.get_by_email(email)

        # Always show success to prevent email enumeration
        if user and user.has_password():
            # Generate reset token
            token = user.generate_password_reset_token()

            if email_is_configured():
                reset_url = url_for("core_bp.reset_password", token=token, _external=True)
                settings = WorkspaceSettings.get_instance()
                company_name = settings.company_name or "sparQ"

                send_email(
                    to=user.email,
                    subject=f"Reset your {company_name} password",
                    html_body=get_password_reset_email_html(company_name, reset_url),
                )

        flash(_("If an account exists with that email, we've sent password reset instructions."), "success")
        return redirect(url_for("core_bp.login"))  # type: ignore[no-any-return]

    return render_template("core/desktop/auth/forgot_password.html", version=get_version())  # type: ignore[no-any-return]


@blueprint.route("/auth/reset-password/<token>", methods=["GET", "POST"])  # type: ignore[misc]
def reset_password(token: str) -> Response | str:
    """Reset password using token."""
    if current_user.is_authenticated:
        return redirect(url_for("core_bp.index"))  # type: ignore[no-any-return]

    user = User.get_by_reset_token(token)

    if not user:
        flash(_("Invalid or expired reset link. Please request a new one."), "error")
        return redirect(url_for("core_bp.forgot_password"))  # type: ignore[no-any-return]

    if request.method == "POST":
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not new_password:
            flash(_("Password is required."), "error")
            return render_template("core/desktop/auth/reset_password.html", token=token, version=get_version())  # type: ignore[no-any-return]

        # Validate password complexity
        errors = validate_password(new_password)
        if errors:
            flash(" ".join(errors), "error")
            return render_template("core/desktop/auth/reset_password.html", token=token, version=get_version())  # type: ignore[no-any-return]

        if new_password != confirm_password:
            flash(_("Passwords do not match."), "error")
            return render_template("core/desktop/auth/reset_password.html", token=token, version=get_version())  # type: ignore[no-any-return]

        if is_breached(new_password):
            flash(_("This password has appeared in a data breach. Please choose a different password."), "error")
            return render_template("core/desktop/auth/reset_password.html", token=token, version=get_version())  # type: ignore[no-any-return]

        # Update password and clear token
        user.password = new_password
        user.clear_password_reset_token()

        flash(_("Your password has been reset. You can now log in."), "success")
        return redirect(url_for("core_bp.login"))  # type: ignore[no-any-return]

    return render_template("core/desktop/auth/reset_password.html", token=token, version=get_version())  # type: ignore[no-any-return]


# -----------------------------------------------------------------------------
# Magic Link Authentication
# -----------------------------------------------------------------------------


def _redirect_after_login(user: User) -> Response:
    """Helper to redirect user after successful login.

    Three cases:
      - 1+ non-archived workspace memberships → auto-select first, go to dashboard.
      - 0 workspace memberships but has an active OrganizationUser → Phase 6 §3.5:
        org-only members land on the People → Organization directory.
      - 0 of either → /no-workspace page.
    """
    from modules.base.core.models.organization_user import OrganizationUser
    from modules.base.core.models.workspace import Workspace
    from modules.base.core.models.workspace_user import WorkspaceUser

    # Resolve workspace memberships in non-archived workspaces only.
    memberships = (
        WorkspaceUser.query
        .filter_by(user_id=user.id)
        .filter(WorkspaceUser.deleted_at.is_(None))
        .join(Workspace, Workspace.id == WorkspaceUser.workspace_id)
        .filter(Workspace.deleted_at.is_(None))
        .all()
    )

    if len(memberships) >= 1:
        # Prefer last-used workspace if still accessible
        target = memberships[0]
        if user.last_workspace_id:
            for m in memberships:
                if m.workspace_id == user.last_workspace_id:
                    target = m
                    break
        session["active_workspace_id"] = str(target.workspace_id)
        g.workspace_id = target.workspace_id
        ts = Workspace.query.get(target.workspace_id)
        if ts:
            g.organization_id = ts.organization_id
    else:
        # Clear any stale session pointer — this user has no workspace.
        session.pop("active_workspace_id", None)
        g.workspace_id = None

        # Org-only member? Land on the org landing page.
        org_memberships = OrganizationUser.list_for_user(user.id, active_only=True)
        if org_memberships:
            g.organization_id = org_memberships[0].organization_id
            next_page = request.args.get("next")
            if not next_page or not next_page.startswith("/"):
                next_page = url_for("core_bp.org_landing")
            return redirect(next_page)  # type: ignore[no-any-return]

        # Neither workspace nor organization membership — personal shell.
        return redirect(url_for("core_bp.personal_shell"))  # type: ignore[no-any-return]

    next_page = request.args.get("next")

    if not next_page or not next_page.startswith("/"):
        settings = WorkspaceSettings.get_instance()
        if user.is_admin and not settings.onboarding_completed:
            next_page = url_for("core_bp.onboarding")
        else:
            next_page = url_for("dashboard_bp.index")

    return redirect(next_page)  # type: ignore[no-any-return]


def _password_login(user: User | None, password: str, remember: bool) -> Response | bool:
    """Attempt a password-based login.

    Returns:
        A redirect Response on success, or True/False (account_locked) on failure.
    """
    if user and user.is_locked:
        flash(_("Invalid email or password"), "error")
        return True

    if user and user.check_password(password):
        if not user.is_active:
            flash(_("Your account has been deactivated."), "error")
            return redirect(url_for("core_bp.login"))  # type: ignore[no-any-return]
        user.reset_failed_logins()
        session.clear()
        login_user(user, remember=remember)
        return _redirect_after_login(user)

    return _handle_failed_login(user)


def _handle_failed_login(user: User | None) -> bool:
    """Record a failed login and flash a message.

    Returns:
        True if the account is now locked, False otherwise.
    """
    if user:
        count = user.record_failed_login()
        if count >= User.MAX_FAILED_ATTEMPTS:
            flash(_("Invalid email or password"), "error")
            return True
        elif count > User.LOCKOUT_WARNING_THRESHOLD:
            remaining = user.remaining_login_attempts
            flash(
                _("Invalid email or password")
                + f" {remaining} "
                + _("attempt(s) remaining."),
                "warning",
            )
        else:
            flash(_("Invalid email or password"), "error")
    else:
        flash(_("Invalid email or password"), "error")
    return False


@blueprint.route("/auth/magic-link", methods=["GET", "POST"])  # type: ignore[misc]
@rate_limit(limit=5, window=300)  # type: ignore[misc]
def magic_link_request() -> Response | str:
    """Request magic link email for passwordless login."""
    from modules.base.core.models.auth_settings import AuthSettings
    from system.email import send_email, is_configured as email_is_configured
    from system.email.templates import get_magic_link_email_html

    if current_user.is_authenticated:
        return redirect(url_for("core_bp.index"))  # type: ignore[no-any-return]

    has_workspace = getattr(g, "workspace_id", None) is not None

    # AuthSettings requires workspace context; fall back to defaults without one
    if has_workspace:
        auth_settings = AuthSettings.get_instance()
        if not auth_settings.magic_link_enabled:
            flash(_("Magic link login is not available."), "error")
            return redirect(url_for("core_bp.login"))  # type: ignore[no-any-return]
    else:
        auth_settings = None

    oauth_providers = _build_oauth_providers()

    account_locked = False

    def _render_magic_link(**kwargs: Any) -> str:
        return render_device_template(
            "core/desktop/auth/magic_link_request.html",
            auth_settings=auth_settings,
            account_locked=account_locked,
            version=get_version(),
            oauth_providers=oauth_providers,
            **kwargs,
        )

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()

        if not email:
            flash(_("Please enter your email address."), "error")
            return _render_magic_link()  # type: ignore[no-any-return]

        # --- Email format validation ---
        from system.utils.validation import validate_email as check_email_format
        from system.exceptions import ValidationError
        try:
            check_email_format(email)
        except ValidationError:
            flash(_("Please enter a valid email address."), "error")
            return _render_magic_link()  # type: ignore[no-any-return]

        # Find user globally (no workspace context before login)
        user = User.query.filter_by(email=email).first()

        # Always show success to prevent email enumeration
        if user and user.is_active:
            # Set workspace context from user's membership for downstream queries
            from modules.base.core.models.workspace_user import WorkspaceUser
            membership = WorkspaceUser.query.filter_by(user_id=user.id).filter(WorkspaceUser.deleted_at.is_(None)).first()
            if membership:
                g.workspace_id = membership.workspace_id
                session["active_workspace_id"] = str(membership.workspace_id)

            token = user.generate_magic_link_token()
            magic_link_url = url_for("core_bp.magic_link_verify", token=token, _external=True)

            # Get company name (now with workspace context)
            if getattr(g, "workspace_id", None):
                settings = WorkspaceSettings.get_instance()
                company_name = settings.company_name or "sparQ"
            else:
                company_name = "sparQ"

            # Debug mode: show magic link directly instead of sending email
            if current_app.debug:
                return _render_magic_link(  # type: ignore[no-any-return]
                    debug_mode=True,
                    magic_link_url=magic_link_url,
                    demo_email=email,
                )

            if email_is_configured():
                send_email(
                    to=user.email,
                    subject=f"Your login link for {company_name}",
                    html_body=get_magic_link_email_html(company_name, magic_link_url),
                )

        flash(_("If an account exists with that email, we've sent you a login link."), "success")
        return redirect(url_for("core_bp.login"))  # type: ignore[no-any-return]

    return _render_magic_link()  # type: ignore[no-any-return]


@blueprint.route("/auth/magic-link/verify/<token>")  # type: ignore[misc]
def magic_link_verify(token: str) -> Response:
    """Verify magic link and log in user."""
    if current_user.is_authenticated:
        return redirect(url_for("core_bp.index"))  # type: ignore[no-any-return]

    user = User.get_by_magic_link_token(token)

    if not user:
        flash(_("Invalid or expired login link. Please request a new one."), "error")
        return redirect(url_for("core_bp.login"))  # type: ignore[no-any-return]

    # Clear the token (single use)
    user.clear_magic_link_token()

    # Check if user is active
    if not user.is_active:
        flash(_("Your account has been deactivated."), "error")
        return redirect(url_for("core_bp.login"))  # type: ignore[no-any-return]

    # Set workspace context from user's membership (skip deactivated orgs)
    from modules.base.core.models.organization import Organization
    from modules.base.core.models.workspace import Workspace
    from modules.base.core.models.workspace_user import WorkspaceUser

    membership = (
        WorkspaceUser.query
        .filter_by(user_id=user.id)
        .filter(WorkspaceUser.deleted_at.is_(None))
        .join(Workspace, Workspace.id == WorkspaceUser.workspace_id)
        .join(Organization, Organization.id == Workspace.organization_id)
        .filter(Organization.is_active.is_(True))
        .first()
    )
    if membership:
        g.workspace_id = membership.workspace_id
        session["active_workspace_id"] = str(membership.workspace_id)

    # Log in the user
    login_user(user, remember=True)

    return _redirect_after_login(user)


# -----------------------------------------------------------------------------
# SMS OTP Authentication
# -----------------------------------------------------------------------------


@blueprint.route("/auth/sms", methods=["GET", "POST"])  # type: ignore[misc]
@rate_limit(limit=3, window=300)  # type: ignore[misc]
def sms_request() -> Response | str:
    """Request SMS OTP code for passwordless login."""
    from modules.base.core.models.auth_settings import AuthSettings
    from system.sms import send_sms, is_configured as sms_is_configured

    if current_user.is_authenticated:
        return redirect(url_for("core_bp.index"))  # type: ignore[no-any-return]

    auth_settings = AuthSettings.get_instance()
    if not auth_settings.sms_enabled:
        flash(_("SMS login is not available."), "error")
        return redirect(url_for("core_bp.login"))  # type: ignore[no-any-return]

    if request.method == "POST":
        phone = request.form.get("phone", "").strip()

        if not phone:
            flash(_("Please enter your phone number."), "error")
            return render_template("core/desktop/auth/sms_request.html", version=get_version())  # type: ignore[no-any-return]

        user = User.get_by_phone(phone)

        # Always show success to prevent phone enumeration
        if user and user.is_active and user.phone_verified:
            otp = user.generate_sms_otp()

            if sms_is_configured():
                settings = WorkspaceSettings.get_instance()
                company_name = settings.company_name or "sparQ"

                send_sms(
                    to=user.phone_number,
                    body=f"Your {company_name} login code is: {otp}. Expires in 5 minutes.",
                )

        # Store phone in session for verification step
        session["sms_login_phone"] = phone
        flash(_("If a verified account exists with that phone, we've sent you a code."), "success")
        return redirect(url_for("core_bp.sms_verify"))  # type: ignore[no-any-return]

    return render_template("core/desktop/auth/sms_request.html", version=get_version())  # type: ignore[no-any-return]


@blueprint.route("/auth/sms/verify", methods=["GET", "POST"])  # type: ignore[misc]
@rate_limit(limit=5, window=300)  # type: ignore[misc]
def sms_verify() -> Response | str:
    """Verify SMS OTP code and log in."""
    if current_user.is_authenticated:
        return redirect(url_for("core_bp.index"))  # type: ignore[no-any-return]

    phone = session.get("sms_login_phone")
    if not phone:
        return redirect(url_for("core_bp.sms_request"))  # type: ignore[no-any-return]

    if request.method == "POST":
        otp = request.form.get("otp", "").strip()

        if not otp:
            flash(_("Please enter your verification code."), "error")
            return render_template("core/desktop/auth/sms_verify.html", version=get_version())  # type: ignore[no-any-return]

        user = User.get_by_phone(phone)

        if user and user.is_sms_otp_valid(otp):
            # Clear the OTP (single use)
            user.clear_sms_otp()
            session.pop("sms_login_phone", None)

            # Check if user is active
            if not user.is_active:
                flash(_("Your account has been deactivated."), "error")
                return redirect(url_for("core_bp.login"))  # type: ignore[no-any-return]

            # Log in the user
            login_user(user, remember=True)

            return _redirect_after_login(user)

        flash(_("Invalid or expired code. Please try again."), "error")
        return render_template("core/desktop/auth/sms_verify.html", version=get_version())  # type: ignore[no-any-return]

    return render_template("core/desktop/auth/sms_verify.html", version=get_version())  # type: ignore[no-any-return]


# -----------------------------------------------------------------------------
# Notifications
# -----------------------------------------------------------------------------


def _render_inbox_list_partial(source: str) -> str:
    """Render the inbox list partial for the appropriate device."""
    from datetime import date, timedelta

    _today = date.today()
    items = SystemNotification.get_inbox_items(current_user, limit=100)
    partial = "core/mobile/core/_inbox_list.html" if source == "mobile-inbox" else "core/desktop/core/_inbox_list.html"
    return render_template(
        partial,
        items=items,
        category_labels=SystemNotification.CATEGORY_LABELS,
        today=_today,
        yesterday=_today - timedelta(days=1),
    )


def _render_notification_partial(notifications: list, system_alerts: list | None = None) -> str:
    """Render the appropriate notification partial for the current device."""
    from system.device import is_mobile

    if system_alerts is None:
        system_alerts = []
    template = "core/mobile/_notification_sheet.html" if is_mobile() else "core/desktop/core/_notification_dropdown.html"
    html = render_template(template, notifications=notifications, system_alerts=system_alerts)
    g.pop("_notification_cache", None)
    count = SystemNotification.get_unread_count(current_user)
    if current_user.is_admin:
        count += SystemNotification.get_system_alerts_count()
    badge_oob = render_template(
        "core/desktop/partials/_notification_badge.html",
        notification_count=count,
        oob=True,
    )
    return html + badge_oob


@blueprint.route("/notifications")  # type: ignore[misc]
@login_required  # type: ignore[misc]
def notifications_dropdown() -> str:
    """HTMX: Get notification dropdown content."""
    notifications = SystemNotification.get_for_user(current_user, limit=10)
    system_alerts = SystemNotification.get_system_alerts() if current_user.is_admin else []
    return _render_notification_partial(notifications, system_alerts)


@blueprint.route("/notifications/inbox")  # type: ignore[misc]
@login_required  # type: ignore[misc]
def notifications_inbox() -> str:
    """Notification center — unified inbox with category filter tabs."""
    from datetime import date, timedelta

    from system.device import is_mobile
    from system.device.template import render_device_template

    filter_key = request.args.get("filter", "all")
    filter_groups = SystemNotification.FILTER_GROUPS
    categories = filter_groups.get(filter_key)

    items = SystemNotification.get_inbox_items(current_user, category=categories, limit=100)
    tab_counts = SystemNotification.get_unread_counts_by_group(current_user)
    category_labels = SystemNotification.CATEGORY_LABELS
    today = date.today()
    yesterday = today - timedelta(days=1)

    if request.headers.get("HX-Request") == "true":
        partial = "core/mobile/core/_inbox_list.html" if is_mobile() else "core/desktop/core/_inbox_list.html"
        return render_template(
            partial,
            items=items,
            active_filter=filter_key,
            category_labels=category_labels,
            today=today,
            yesterday=yesterday,
        )  # type: ignore[no-any-return]

    return render_device_template(
        "core/desktop/core/inbox.html",
        items=items,
        active_filter=filter_key,
        filter_groups=filter_groups,
        tab_counts=tab_counts,
        category_labels=category_labels,
        today=today,
        yesterday=yesterday,
        module_name=_("Inbox"),
        module_icon="fa-solid fa-inbox",
        module_home="dashboard_bp.index",
    )  # type: ignore[no-any-return]


@blueprint.route("/notifications/all")  # type: ignore[misc]
@login_required  # type: ignore[misc]
def notifications_all() -> ResponseReturnValue:
    """Redirect old notifications page to inbox."""
    return redirect(url_for("core_bp.notifications_inbox"))


@blueprint.route("/notifications/<int:notification_id>/read", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
def notification_mark_read(notification_id: int) -> ResponseReturnValue:
    """Mark notification as read. Returns inbox list, dropdown HTML, or redirects."""
    notification = SystemNotification.scoped().get_or_404(notification_id)
    notification.mark_read()

    source = request.form.get("source", "")
    if source in ("inbox", "mobile-inbox"):
        return _render_inbox_list_partial(source)

    if request.form.get("redirect") == "page":
        return redirect(url_for("core_bp.notifications_inbox"))

    notifications = SystemNotification.get_for_user(current_user, limit=10)
    return _render_notification_partial(notifications)


@blueprint.route("/notifications/read-all", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
def notifications_mark_all_read() -> ResponseReturnValue:
    """Mark all notifications as read. Returns inbox list, dropdown HTML, or redirects."""
    SystemNotification.mark_all_read(current_user)

    source = request.form.get("source", "")
    if source in ("inbox", "mobile-inbox"):
        return _render_inbox_list_partial(source)

    if request.form.get("redirect") == "page":
        return redirect(url_for("core_bp.notifications_inbox"))

    notifications = SystemNotification.get_for_user(current_user, limit=10)
    return _render_notification_partial(notifications)


@blueprint.route("/notifications/<int:notification_id>/dismiss", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
def notification_dismiss(notification_id: int) -> ResponseReturnValue:
    """Dismiss a notification. Returns inbox list, dropdown HTML, or redirects."""
    notification = SystemNotification.scoped().get_or_404(notification_id)
    notification.dismiss()

    source = request.form.get("source", "")
    if source in ("inbox", "mobile-inbox"):
        return _render_inbox_list_partial(source)

    if request.form.get("redirect") == "page":
        return redirect(url_for("core_bp.notifications_inbox"))

    notifications = SystemNotification.get_for_user(current_user, limit=10)
    return _render_notification_partial(notifications)


@blueprint.route("/notifications/dismiss-all", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
def notifications_dismiss_all() -> ResponseReturnValue:
    """Dismiss all notifications. Returns inbox list, dropdown HTML, or redirects."""
    SystemNotification.dismiss_all(current_user)

    source = request.form.get("source", "")
    if source in ("inbox", "mobile-inbox"):
        return _render_inbox_list_partial(source)

    if request.form.get("redirect") == "page":
        return redirect(url_for("core_bp.notifications_inbox"))

    notifications = SystemNotification.get_for_user(current_user, limit=10)
    return _render_notification_partial(notifications)


@blueprint.route("/notifications/count")  # type: ignore[misc]
@login_required  # type: ignore[misc]
def notifications_count() -> Response:
    """JSON: Get unread notification count for polling"""
    count = SystemNotification.get_unread_count(current_user)
    return jsonify({"count": count})  # type: ignore[no-any-return]


@blueprint.route("/dismiss-sample-modal", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
def dismiss_sample_modal() -> ResponseReturnValue:
    """Dismiss the sample data info modal (one-time, per user)."""
    from modules.base.core.models.user_setting import UserSetting

    UserSetting.set(current_user.id, "sample_data_modal_dismissed", "true")
    return "", 204
