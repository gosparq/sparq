# -----------------------------------------------------------------------------
# sparQ - MSA Routes
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

import os
import re
import secrets
import uuid
from functools import wraps
from typing import Any, Callable

from flask import (
    Blueprint,
    Response,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask.typing import ResponseReturnValue

from modules.base.msa.models.instance_settings import InstanceSettings  # noqa: F401 — import at module level so db.create_all() sees the table
from system.db.database import db
from system.i18n.translation import _
from system.middleware.ratelimit import rate_limit

blueprint = Blueprint(
    "msa_bp",
    __name__,
    template_folder="../views/templates",
    static_folder="../views/assets",
)

MSA_USER = os.environ.get("MSA_USER")
MSA_PASS = os.environ.get("MSA_PASS")
MSA_ENABLED = bool(MSA_USER and MSA_PASS)

_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{1,49}$")


def msa_required(f: Callable[..., Any]) -> Callable[..., Any]:
    """Require MSA admin session."""

    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> ResponseReturnValue:
        if not MSA_ENABLED:
            return _("MSA is disabled. Set MSA_USER and MSA_PASS to enable."), 404
        if not session.get("msa_authenticated"):
            return redirect(url_for("msa_bp.login"))
        return f(*args, **kwargs)

    return decorated


# ---------- Auth ----------


@blueprint.route("/login", methods=["GET", "POST"])
@rate_limit(limit=5, window=300)
def login() -> ResponseReturnValue:
    if not MSA_ENABLED:
        return _("MSA is disabled. Set MSA_USER and MSA_PASS to enable."), 404

    if session.get("msa_authenticated"):
        return redirect(url_for("msa_bp.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if secrets.compare_digest(username, MSA_USER) and secrets.compare_digest(password, MSA_PASS):
            session["msa_authenticated"] = True
            return redirect(url_for("msa_bp.dashboard"))
        flash(_("Invalid credentials."), "error")

    return render_template("msa/desktop/login.html")


@blueprint.route("/logout")
def logout() -> ResponseReturnValue:
    session.pop("msa_authenticated", None)
    return redirect(url_for("msa_bp.login"))


# ---------- Dashboard ----------


@blueprint.route("/")
@msa_required
def dashboard() -> ResponseReturnValue:
    from modules.base.core.models.organization import Organization
    from modules.base.core.models.workspace import Workspace
    from modules.base.core.models.user import User

    total_workspaces = Workspace.count()
    active_workspaces = Workspace.count_active()
    inactive_workspaces = total_workspaces - active_workspaces
    total_users = User.count()
    total_organizations = Organization.count()
    recent = Workspace.get_recent(5)

    return render_template(
        "msa/desktop/dashboard.html",
        total_organizations=total_organizations,
        total_workspaces=total_workspaces,
        active_workspaces=active_workspaces,
        inactive_workspaces=inactive_workspaces,
        total_users=total_users,
        recent_workspaces=recent,
    )


# ---------- Organizations ----------


@blueprint.route("/organizations")
@msa_required
def organization_list() -> ResponseReturnValue:
    from modules.base.core.models.organization import Organization
    from modules.base.core.models.organization_user import OrganizationUser
    from modules.base.core.models.workspace import Workspace

    organizations = Organization.get_all()
    member_counts = OrganizationUser.get_member_counts()
    workspace_counts = Workspace.get_counts_by_organization()

    return render_template(
        "msa/desktop/organizations.html",
        organizations=organizations,
        member_counts=member_counts,
        workspace_counts=workspace_counts,
    )


@blueprint.route("/organizations/<uuid:org_id>")
@msa_required
def organization_detail(org_id: uuid.UUID) -> ResponseReturnValue:
    from modules.base.core.models.organization import Organization
    from modules.base.core.models.organization_user import OrganizationUser
    from modules.base.core.models.workspace import Workspace
    from modules.base.core.models.workspace_user import WorkspaceUser

    org = Organization.get_by_id_or_404(org_id)
    members = OrganizationUser.get_members_for_organization(org_id)
    workspaces = Workspace.for_organization(org_id)
    ts_member_counts = WorkspaceUser.get_member_counts()

    return render_template(
        "msa/desktop/organization_detail.html",
        org=org,
        members=members,
        workspaces=workspaces,
        ts_member_counts=ts_member_counts,
    )


@blueprint.route("/organizations/create", methods=["POST"])
@msa_required
def organization_create() -> ResponseReturnValue:
    from modules.base.core.models.organization import Organization

    name = request.form.get("name", "").strip()
    slug = request.form.get("slug", "").strip().lower()
    plan = request.form.get("plan", "").strip() or "free"
    claimed_domain = request.form.get("claimed_domain", "").strip() or None

    if not name or not slug:
        flash(_("Name and slug are required."), "error")
        return redirect(url_for("msa_bp.organization_list"))

    try:
        org = Organization.create(
            name=name, slug=slug, plan=plan, claimed_domain=claimed_domain,
        )
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("msa_bp.organization_list"))

    flash(_("Organization '%(name)s' created.") % {"name": org.name}, "success")
    return redirect(url_for("msa_bp.organization_list"))


@blueprint.route("/organizations/<uuid:org_id>/edit", methods=["POST"])
@msa_required
def organization_edit(org_id: uuid.UUID) -> ResponseReturnValue:
    from modules.base.core.models.organization import Organization

    org = Organization.get_by_id_or_404(org_id)

    name = request.form.get("name", "").strip() or None
    slug = request.form.get("slug", "").strip().lower() or None
    plan = request.form.get("plan", "").strip() or None
    claimed_domain = request.form.get("claimed_domain", "").strip() or None

    try:
        org.update(name=name, slug=slug, plan=plan, claimed_domain=claimed_domain)
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("msa_bp.organization_detail", org_id=org.id))

    flash(_("Organization '%(name)s' updated.") % {"name": org.name}, "success")
    return redirect(url_for("msa_bp.organization_detail", org_id=org.id))


@blueprint.route("/organizations/<uuid:org_id>/deactivate", methods=["POST"])
@msa_required
def organization_deactivate(org_id: uuid.UUID) -> ResponseReturnValue:
    from modules.base.core.models.organization import Organization

    org = Organization.get_by_id_or_404(org_id)
    org.deactivate()
    flash(_("Organization '%(name)s' deactivated.") % {"name": org.name}, "success")
    return redirect(url_for("msa_bp.organization_detail", org_id=org.id))


@blueprint.route("/organizations/<uuid:org_id>/activate", methods=["POST"])
@msa_required
def organization_activate(org_id: uuid.UUID) -> ResponseReturnValue:
    from modules.base.core.models.organization import Organization

    org = Organization.get_by_id_or_404(org_id)
    org.activate()
    flash(_("Organization '%(name)s' activated.") % {"name": org.name}, "success")
    return redirect(url_for("msa_bp.organization_detail", org_id=org.id))


# ---------- Workspace CRUD ----------


@blueprint.route("/workspaces")
@msa_required
def workspace_list() -> ResponseReturnValue:
    from modules.base.core.models.organization import Organization
    from modules.base.core.models.workspace import Workspace
    from modules.base.core.models.workspace_user import WorkspaceUser

    workspaces = Workspace.get_all()

    # Member counts per workspace
    member_counts = WorkspaceUser.get_member_counts()

    # Admin (or highest-role user) per workspace
    admin_map = WorkspaceUser.get_admin_emails()

    # Organization map for parent org display
    org_ids = {ws.organization_id for ws in workspaces if ws.organization_id}
    org_map = Organization.get_by_ids(org_ids)

    # Build workspace data as JSON for Alpine.js client-side grouping
    import json
    workspace_data = json.dumps([
        {
            "id": str(ws.id),
            "name": ws.name,
            "slug": ws.slug,
            "plan": ws.plan or "free",
            "is_active": ws.is_active,
            "created_at": ws.created_at.strftime("%b %d, %Y") if ws.created_at else "—",
            "created_ts": ws.created_at.isoformat() if ws.created_at else "",
            "members": member_counts.get(ws.id, 0),
            "admin": admin_map.get(ws.id, "—"),
            "url": url_for("msa_bp.workspace_detail", workspace_id=ws.id),
            "org_name": org_map[ws.organization_id].name if ws.organization_id and ws.organization_id in org_map else "",
            "org_url": url_for("msa_bp.organization_detail", org_id=ws.organization_id) if ws.organization_id and ws.organization_id in org_map else "",
        }
        for ws in workspaces
    ])

    return render_template(
        "msa/desktop/workspaces.html",
        workspaces=workspaces,
        member_counts=member_counts,
        admin_map=admin_map,
        org_map=org_map,
        workspace_data=workspace_data,
    )


@blueprint.route("/workspaces/<uuid:workspace_id>")
@msa_required
def workspace_detail(workspace_id: uuid.UUID) -> ResponseReturnValue:
    from modules.base.core.models.workspace import Workspace
    from modules.base.core.models.workspace_user import WorkspaceUser
    from modules.base.core.models.user import User

    workspace = Workspace.query.get_or_404(workspace_id)
    users = (
        User.query
        .join(WorkspaceUser, WorkspaceUser.user_id == User.id)
        .filter(WorkspaceUser.workspace_id == workspace.id)
        .order_by(User.created_at.desc())
        .all()
    )

    return render_template("msa/desktop/workspace_detail.html", workspace=workspace, users=users)


@blueprint.route("/workspaces/<uuid:workspace_id>/edit", methods=["POST"])
@msa_required
def workspace_edit(workspace_id: uuid.UUID) -> ResponseReturnValue:
    from modules.base.core.models.workspace import Workspace

    workspace = Workspace.query.get_or_404(workspace_id)
    name = request.form.get("name", "").strip()
    slug = request.form.get("slug", "").strip().lower()
    plan = request.form.get("plan", "").strip()
    is_active = request.form.get("is_active") == "1"

    if name:
        workspace.name = name
    if slug and _SLUG_RE.match(slug):
        workspace.slug = slug
    if plan:
        workspace.plan = plan
    workspace.is_active = is_active
    db.session.commit()
    flash(_("Workspace '%(slug)s' updated.") % {"slug": workspace.slug}, "success")
    return redirect(url_for("msa_bp.workspace_detail", workspace_id=workspace.id))


# ---------- Email Configuration ----------

_PROVIDER_DISPLAY = {
    "gmail": ("Gmail", "fab fa-google"),
    "microsoft_365": ("Microsoft 365", "fab fa-microsoft"),
    "sendgrid": ("SendGrid", "fas fa-paper-plane"),
    "mailgun": ("Mailgun", "fas fa-envelope-open-text"),
    "aws_ses": ("AWS SES", "fab fa-aws"),
    "custom": ("Custom SMTP", "fas fa-server"),
}


@blueprint.route("/email")
@msa_required
def email_config() -> ResponseReturnValue:
    from system.email.config import EmailProvider, PROVIDER_PRESETS

    settings = InstanceSettings.get_instance()
    env_overrides = InstanceSettings.get_env_overrides()
    has_env_overrides = InstanceSettings.any_env_overrides()
    providers = [p for p in EmailProvider if p != EmailProvider.SPARQMAIL]
    active_provider = settings.email_provider or "gmail"
    preset = PROVIDER_PRESETS.get(EmailProvider(active_provider), {})

    return render_template(
        "msa/desktop/email.html",
        settings=settings,
        env_overrides=env_overrides,
        has_env_overrides=has_env_overrides,
        providers=providers,
        provider_presets=PROVIDER_PRESETS,
        provider_display=_PROVIDER_DISPLAY,
        active_provider=active_provider,
        provider=active_provider,
        preset=preset,
    )


@blueprint.route("/email/provider/<provider>")
@msa_required
def email_provider_form(provider: str) -> ResponseReturnValue:
    from system.email.config import EmailProvider, PROVIDER_PRESETS

    valid = [p.value for p in EmailProvider if p != EmailProvider.SPARQMAIL]
    if provider not in valid:
        return _("Invalid provider."), 400

    settings = InstanceSettings.get_instance()
    env_overrides = InstanceSettings.get_env_overrides()
    preset = PROVIDER_PRESETS.get(EmailProvider(provider), {})

    return render_template(
        "msa/desktop/partials/_email_provider_form.html",
        settings=settings,
        env_overrides=env_overrides,
        provider=provider,
        preset=preset,
        provider_display=_PROVIDER_DISPLAY,
    )


@blueprint.route("/email", methods=["POST"])
@msa_required
def email_config_save() -> ResponseReturnValue:
    from system.email.config import EmailProvider, PROVIDER_PRESETS

    settings = InstanceSettings.get_instance()

    provider = request.form.get("provider", "").strip()
    valid = [p.value for p in EmailProvider if p != EmailProvider.SPARQMAIL]
    if provider not in valid:
        flash(_("Invalid email provider."), "error")
        return redirect(url_for("msa_bp.email_config"))

    preset = PROVIDER_PRESETS.get(EmailProvider(provider), {})

    if provider == "custom":
        host = request.form.get("host", "").strip()
        port_str = request.form.get("port", "587").strip()
        use_tls = request.form.get("use_tls") == "1"
    else:
        host = preset.get("host", "")
        port_str = str(preset.get("port", 587))
        use_tls = preset.get("use_tls", True)

    try:
        port = int(port_str)
    except ValueError:
        port = 587

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    from_email = request.form.get("from_email", "").strip()

    update_kwargs = {
        "email_provider": provider,
        "email_host": host,
        "email_port": port,
        "email_username": username,
        "email_from": from_email,
        "email_use_tls": use_tls,
    }
    if password:
        update_kwargs["email_password"] = password

    settings.update(**update_kwargs)

    flash(_("Email configuration saved."), "success")
    return redirect(url_for("msa_bp.email_config"))


@blueprint.route("/email/test", methods=["POST"])
@msa_required
@rate_limit(limit=5, window=60)
def email_test_connection() -> ResponseReturnValue:
    from system.email.service import test_connection

    success, message = test_connection()

    if success:
        settings = InstanceSettings.get_instance()
        settings.update(email_verified=True)

    return render_template(
        "msa/desktop/partials/_email_test_result.html",
        success=success,
        message=message,
    )


@blueprint.route("/email/send-test", methods=["POST"])
@msa_required
@rate_limit(limit=3, window=60)
def email_send_test() -> ResponseReturnValue:
    from system.email.service import send_email

    recipient = request.form.get("test_email", "").strip()
    if not recipient or "@" not in recipient:
        return render_template(
            "msa/desktop/partials/_email_test_result.html",
            success=False,
            message=_("Please enter a valid email address."),
        )

    html = render_template("msa/desktop/partials/_email_test_body.html")
    success = send_email(to=recipient, subject=_("sparQ Test Email"), html_body=html)

    if success:
        from modules.base.msa.models.instance_settings import InstanceSettings

        settings = InstanceSettings.get_instance()
        settings.update(email_verified=True)

    return render_template(
        "msa/desktop/partials/_email_test_result.html",
        success=success,
        message=_("Test email sent successfully!") if success else _("Failed to send. Check your settings and password."),
    )


# ---------- Transparent Login ----------


@blueprint.route("/workspaces/<uuid:workspace_id>/transparent-enter", methods=["POST"])
@msa_required
def transparent_enter(workspace_id: uuid.UUID) -> Response:
    """Enter a workspace in read-only transparent mode.

    Sets session flags so the request_loader returns an MsaTransparentUser
    as current_user. No real user is logged in — the MSA browses as a
    synthetic observer with id=0, so no private data (DMs, settings) is visible.
    All mutating requests are blocked by enforce_msa_transparent_readonly
    in request_hooks.py.

    Args:
        workspace_id: UUID of the target workspace.

    Returns:
        Redirect to workspace dashboard.
    """
    from modules.base.core.models.workspace import Workspace

    workspace = Workspace.query.get_or_404(workspace_id)

    session["active_workspace_id"] = str(workspace.id)
    session["msa_transparent_mode"] = True
    session["msa_return_workspace_id"] = str(workspace.id)
    return redirect(url_for("dashboard_bp.index"))


def exit_transparent_mode() -> str | None:
    """Clear transparent-mode session state.

    Returns:
        The workspace ID to return to, or None.
    """
    return_id = session.pop("msa_return_workspace_id", None)
    session.pop("msa_transparent_mode", None)
    session.pop("active_workspace_id", None)
    # msa_authenticated remains intact
    return return_id


@blueprint.route("/transparent-exit", methods=["POST"])
@msa_required
def transparent_exit() -> Response:
    """Exit transparent mode and return to MSA console.

    Clears Flask-Login session and transparent mode flags while
    preserving the MSA authentication session.

    Returns:
        Redirect to MSA workspace detail or MSA dashboard.
    """
    if not session.get("msa_transparent_mode"):
        return redirect(url_for("msa_bp.dashboard"))

    return_id = exit_transparent_mode()

    if return_id:
        return redirect(url_for("msa_bp.workspace_detail", workspace_id=return_id))
    return redirect(url_for("msa_bp.dashboard"))
