# -----------------------------------------------------------------------------
# sparQ - Request Hooks
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# Request Hooks
#
# Registers Flask before_request and other request lifecycle hooks.
# -----------------------------------------------------------------------------

import logging
import secrets
import time
import traceback
import uuid

from flask import Flask, Response, abort, current_app, g, redirect, request, session
from flask_login import current_user
from sqlalchemy import event

request_logger = logging.getLogger("sparq.requests")


def register_request_hooks(app: Flask) -> None:
    """Register request lifecycle hooks for the Flask application."""

    # --- Dev-only curl bypass (auto-login for CLI testing) ---
    if app.config.get("_DEBUG_MODE") or app.debug:

        @app.before_request
        def curl_dev_bypass() -> None:
            """Auto-authenticate curl requests as demo admin in debug mode."""
            ua = request.headers.get("User-Agent", "")
            if "curl/" not in ua:
                return
            if current_user.is_authenticated:
                return
            # Skip for static assets
            if request.path.startswith(("/static/", "/assets/")):
                return

            from flask_login import login_user

            from modules.base.core.models.workspace import Workspace
            from modules.base.core.models.workspace_user import WorkspaceUser

            from sqlalchemy.orm import joinedload


            # Pick an admin membership that still has a valid OrganizationUser parent.
            membership = (
                WorkspaceUser.query
                .options(joinedload(WorkspaceUser.user))
                .filter_by(role="admin")
                .filter(WorkspaceUser.deleted_at.is_(None))
                .filter(WorkspaceUser.organization_user_id.isnot(None))
                .first()
            )
            if membership:
                login_user(membership.user)
                g.workspace_id = membership.workspace_id
                session["active_workspace_id"] = str(membership.workspace_id)
                # Prime g.organization_id too so the rest of the request works.
                ts = Workspace.query.get(membership.workspace_id)
                if ts:
                    g.organization_id = ts.organization_id

    # --- Request profiling (System Info modal) ---

    _debug = app.config.get("_DEBUG_MODE", False)

    @app.before_request
    def start_request_profiling() -> None:
        """Capture request start time, ID, and initialize DB counters."""
        g.request_start_time = time.monotonic()
        g.request_id = str(uuid.uuid4())
        g.db_query_count = 0
        g.db_query_time = 0.0
        if _debug:
            g.db_query_log = []

    # SQLAlchemy query profiling via engine events
    from sqlalchemy.engine import Engine

    @event.listens_for(Engine, "before_cursor_execute")
    def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        conn.info.setdefault("query_start_time", []).append(time.monotonic())

    def _classify_query_origin() -> tuple[str, str]:
        """Walk the call stack to determine which app layer triggered a query."""
        for frame in reversed(traceback.extract_stack()):
            fn = frame.filename
            name = frame.name
            if fn.endswith("startup/templates.py") and name.startswith("inject_"):
                return ("Context Processor", name)
            if "/controllers/" in fn:
                return ("Controller", name)
            if fn.endswith("startup/request_hooks.py") and name not in (
                "_after_cursor_execute", "_before_cursor_execute",
                "_classify_query_origin", "register_request_hooks",
                "start_request_profiling",
            ):
                return ("Request Hook", name)
            if "/system/" in fn and "/startup/" not in fn:
                return ("System", name)
        return ("Other", "unknown")

    @event.listens_for(Engine, "after_cursor_execute")
    def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        total = time.monotonic() - conn.info["query_start_time"].pop(-1)
        try:
            g.db_query_count = getattr(g, "db_query_count", 0) + 1
            g.db_query_time = getattr(g, "db_query_time", 0.0) + total
            if _debug and hasattr(g, "db_query_log"):
                category, source = _classify_query_origin()
                g.db_query_log.append({"category": category, "source": source, "time": total})
        except RuntimeError:
            pass  # Outside request context (migrations, CLI commands)

    # --- Instance setup guard (fresh install redirect) ---

    @app.before_request
    def instance_setup_guard() -> Response | None:
        """Redirect all requests to /setup on fresh installs (no users yet)."""
        if getattr(app, "_instance_setup_done", False):
            return None
        # TESTING is set after create_app(), so check at request time.
        if app.config.get("TESTING") and not getattr(app, "_test_setup_guard", False):
            return None
        if request.path.startswith(("/setup", "/static/", "/assets/", "/health")):
            return None
        from modules.base.core.utils.instance_setup import is_fresh_install
        if is_fresh_install():
            return redirect("/setup")
        app._instance_setup_done = True
        return None

    # Workspace slug → UUID cache (populated on first lookup)
    _workspace_cache: dict[str, "uuid.UUID"] = {}

    @app.before_request
    def set_workspace_context() -> None:
        """Set g.workspace_id and g.organization_id from session or membership.

        Resolution order:
        1. Session active_workspace_id (set after login / workspace picker)
        2. Authenticated user — walk OrganizationUser → WorkspaceUser.
        3. None (bare domain — no workspace context).

        g.organization_id is always derived from the resolved workspace's
        organization_id, so it's consistent with g.workspace_id.
        """
        import uuid

        from modules.base.core.models.organization import Organization
        from modules.base.core.models.organization_user import OrganizationUser
        from modules.base.core.models.workspace import Workspace
        from modules.base.core.models.workspace_user import WorkspaceUser

        # Default unset — will be populated if a workspace is resolved.
        g.organization_id = None

        # 1. Session-based workspace (primary path after login)
        #    Single joined query fetches WorkspaceUser + Workspace +
        #    Organization + OrganizationUser + workspace count (§5.2).
        active_ws = session.get("active_workspace_id")
        if active_ws and current_user.is_authenticated:
            if isinstance(active_ws, str):
                try:
                    active_ws = uuid.UUID(active_ws)
                except ValueError:
                    active_ws = None
            if active_ws:
                from sqlalchemy import func, select

                from system.db.database import db as _db

                org_id_sq = select(Workspace.organization_id).where(Workspace.id == active_ws).correlate(None).scalar_subquery()
                ts_count_sq = (
                    select(func.count())
                    .select_from(WorkspaceUser)
                    .join(Workspace, Workspace.id == WorkspaceUser.workspace_id)
                    .where(
                        WorkspaceUser.user_id == current_user.id,
                        WorkspaceUser.deleted_at.is_(None),
                        Workspace.organization_id == org_id_sq,
                        Workspace.deleted_at.is_(None),
                    )
                    .correlate(None)
                    .scalar_subquery()
                )

                row = (
                    _db.session.query(
                        WorkspaceUser, Workspace, Organization, OrganizationUser,
                        ts_count_sq.label("ts_count"),
                    )
                    .join(Workspace, WorkspaceUser.workspace_id == Workspace.id)
                    .outerjoin(Organization, Workspace.organization_id == Organization.id)
                    .outerjoin(OrganizationUser, WorkspaceUser.organization_user_id == OrganizationUser.id)
                    .filter(
                        WorkspaceUser.user_id == current_user.id,
                        WorkspaceUser.workspace_id == active_ws,
                        WorkspaceUser.deleted_at.is_(None),
                    )
                    .first()
                )
                if row:
                    membership, ts, org, org_user, ts_count = row
                    if org is None or org.is_active:
                        g.workspace_id = active_ws
                        g._workspace_membership = membership
                        g._current_member_cache = membership
                        g.organization_id = ts.organization_id
                        g.workspace = ts
                        g._organization_user = org_user
                        g._workspace_count_cache = ts_count or 0
                        if hasattr(current_user, "save_last_workspace"):
                            current_user.save_last_workspace(active_ws)
                        return
                session.pop("active_workspace_id", None)

        # 2. Authenticated user — resolve via OrganizationUser → WorkspaceUser.
        #    Pick the oldest active organization membership, then the oldest
        #    active workspace membership within it. The caller can always
        #    switch explicitly via the workspace/organization switcher.
        if current_user.is_authenticated:
            from modules.base.core.models.organization_user import OrganizationUser

            # Prefer last-used workspace before falling back to org-iteration.
            last_ts_id = getattr(current_user, "last_workspace_id", None)
            if last_ts_id:
                from sqlalchemy import func, select

                from system.db.database import db as _db

                org_id_sq = (
                    select(Workspace.organization_id)
                    .where(Workspace.id == last_ts_id)
                    .correlate(None)
                    .scalar_subquery()
                )
                ts_count_sq = (
                    select(func.count())
                    .select_from(WorkspaceUser)
                    .join(Workspace, Workspace.id == WorkspaceUser.workspace_id)
                    .where(
                        WorkspaceUser.user_id == current_user.id,
                        WorkspaceUser.deleted_at.is_(None),
                        Workspace.organization_id == org_id_sq,
                        Workspace.deleted_at.is_(None),
                    )
                    .correlate(None)
                    .scalar_subquery()
                )

                last_row = (
                    _db.session.query(
                        WorkspaceUser, Workspace, Organization, OrganizationUser,
                        ts_count_sq.label("ts_count"),
                    )
                    .execution_options(skip_tenant_filter=True)
                    .join(Workspace, WorkspaceUser.workspace_id == Workspace.id)
                    .outerjoin(Organization, Workspace.organization_id == Organization.id)
                    .outerjoin(OrganizationUser, WorkspaceUser.organization_user_id == OrganizationUser.id)
                    .filter(
                        WorkspaceUser.user_id == current_user.id,
                        WorkspaceUser.workspace_id == last_ts_id,
                        WorkspaceUser.deleted_at.is_(None),
                        Workspace.deleted_at.is_(None),
                    )
                    .first()
                )
                if last_row:
                    membership, ts, org, org_user, ts_count = last_row
                    if org is None or org.is_active:
                        g.workspace_id = last_ts_id
                        g.organization_id = ts.organization_id
                        g._workspace_membership = membership
                        g._current_member_cache = membership
                        g._organization_user = org_user
                        g._workspace_count_cache = ts_count or 0
                        session["active_workspace_id"] = str(last_ts_id)
                        if hasattr(current_user, "save_last_workspace"):
                            current_user.save_last_workspace(last_ts_id)
                        return

            org_memberships = OrganizationUser.list_for_user(current_user.id, active_only=True)
            for org_membership in org_memberships:
                org = Organization.query.get(org_membership.organization_id)
                if not org or not org.is_active:
                    continue
                # skip_tenant_filter: g.organization_id is not yet established;
                # this loop walks across orgs to find the right one.
                membership = (
                    WorkspaceUser.query
                    .execution_options(skip_tenant_filter=True)
                    .filter_by(organization_user_id=org_membership.id)
                    .filter(WorkspaceUser.deleted_at.is_(None))
                    .order_by(WorkspaceUser.id.asc())
                    .first()
                )
                if membership:
                    g.workspace_id = membership.workspace_id
                    g.organization_id = org_membership.organization_id
                    g._workspace_membership = membership
                    g._current_member_cache = membership
                    session["active_workspace_id"] = str(membership.workspace_id)
                    if hasattr(current_user, "save_last_workspace"):
                        current_user.save_last_workspace(membership.workspace_id)
                    return
                g.organization_id = org_membership.organization_id

            # Ultimate fallback for legacy rows that still have a workspace_user
            # without an organization_user parent (pre-050 data).
            legacy = (
                WorkspaceUser.query
                .execution_options(skip_tenant_filter=True)
                .filter_by(user_id=current_user.id)
                .filter(WorkspaceUser.deleted_at.is_(None))
                .first()
            )
            if legacy:
                ts = Workspace.query.get(legacy.workspace_id)
                if ts:
                    org = Organization.query.get(ts.organization_id) if ts.organization_id else None
                    if org is not None and not org.is_active:
                        ts = None
                if ts:
                    g.workspace_id = legacy.workspace_id
                    g._workspace_membership = legacy
                    g._current_member_cache = legacy
                    g.organization_id = ts.organization_id
                    g.workspace = ts
                    session["active_workspace_id"] = str(legacy.workspace_id)
                    if hasattr(current_user, "save_last_workspace"):
                        current_user.save_last_workspace(legacy.workspace_id)
                    return

        # 3. No workspace resolved
        g.workspace_id = None
        g._workspace_membership = None
        g._current_member_cache = None

    @app.before_request
    def enforce_audit_access_readonly() -> Response | None:
        """Read-only + audit-log enforcement for organization-admin audit access.

        Per spec §12.2 and §3.4: when an organization admin visits a workspace
        they're not a member of, access is automatic but read-only and logged.

        This hook runs AFTER set_scope_context (which sets g.workspace_access)
        and AFTER set_workspace_context (which sets g.organization_id). It:

          1. Writes an AuditLog entry once per session-per-workspace on first
             audit access (dedupe via session['audited_workspaces']).
          2. Blocks non-GET/HEAD/OPTIONS requests with 403.
        """
        if getattr(g, "workspace_access", None) != "audit":
            return None

        workspace_id = getattr(g, "workspace_id", None)
        if workspace_id is None:
            return None

        # Log first-access per session (best-effort; swallow errors to avoid
        # making the audit trail block the UI).
        audited = session.get("audited_workspaces") or []
        workspace_key = str(workspace_id)
        if workspace_key not in audited:
            try:
                from modules.base.core.models.audit_log import AuditLog

                AuditLog.record(
                    action="workspace_audit_access",
                    target_type="workspace",
                    target_id=workspace_key,
                    workspace_id=workspace_id,
                )
                audited.append(workspace_key)
                session["audited_workspaces"] = audited
            except Exception:
                app.logger.exception("Failed to record workspace_audit_access")

        if request.method in ("GET", "HEAD", "OPTIONS"):
            return None
        # Allow static assets even in audit mode (they're read-only by nature).
        if request.path.startswith(("/static/", "/assets/")):
            return None
        abort(403)

    @app.before_request
    def enforce_msa_transparent_readonly() -> Response | None:
        """Block all mutating requests when MSA transparent mode is active.

        Allows only GET/HEAD/OPTIONS and the transparent-exit endpoint.
        Returns 403 for all other state-changing requests.
        """
        if not session.get("msa_transparent_mode"):
            return None

        if request.method in ("GET", "HEAD", "OPTIONS"):
            return None

        # Allow only the transparent-exit endpoint
        if request.endpoint == "msa_bp.transparent_exit":
            return None

        # Allow static assets
        if request.path.startswith(("/static/", "/assets/")):
            return None

        abort(403)

    @app.before_request
    def log_request() -> None:
        """Log incoming requests in debug mode."""
        if app.config.get("_DEBUG_MODE") and not request.path.startswith("/assets/"):
            request_logger.info(f"{request.method} {request.path}")

    @app.before_request
    def generate_csp_nonce() -> None:
        """Generate a unique CSP nonce for each request."""
        g.csp_nonce = secrets.token_urlsafe(16)

    @app.before_request
    def bare_domain_guard() -> Response | None:
        """Route requests when no workspace context is resolved.

        Allows login/signup/msa and other public routes through.
        Redirects authenticated users without a workspace to their landing page.
        """
        if getattr(g, "workspace_id", None) is not None:
            return None

        # Org-only members — allow organization-scoped + settings routes.
        if getattr(g, "organization_id", None) is not None and current_user.is_authenticated:
            org_only_allowed = (
                "/static/", "/assets/", "/health", "/api/", "/auth/", "/logout",
                "/settings/organization",
                "/organizations/",
                "/org-landing",
                "/personal-shell",
                "/workspaces/",
            )
            if request.path.startswith(org_only_allowed):
                return None
            if "/organization" in request.path:
                return None

        allowed_prefixes = ("/login", "/signup", "/msa", "/static/", "/assets/", "/health", "/api/", "/auth/", "/people/people/invite/accept/", "/logout", "/no-workspace", "/org-landing", "/personal-shell", "/organizations/create", "/invitations/", "/confirm-signup", "/integrations/webhooks/", "/setup")
        if request.path.startswith(allowed_prefixes):
            return None
        if current_user.is_authenticated:
            if getattr(g, "organization_id", None) is not None:
                return redirect("/org-landing")
            return redirect("/personal-shell")
        return redirect("/login")

    @app.before_request
    def before_request() -> None:
        """Global request setup and initialization."""
        from modules.base.core.models.workspace_settings import WorkspaceSettings
        from modules.base.core.models.user_setting import UserSetting

        # Skip full request setup when no workspace context (bare domain → signup only)
        if getattr(g, "workspace_id", None) is None:
            g.company_settings = None
            g.installed_modules = []
            g.current_module = {}
            g.lang = app.config.get("DEFAULT_LANGUAGE", "en")
            g.device_type = "desktop"
            g.is_mobile = False
            g.workspace_color = "#E8431A"  # brand orange default
            return

        # 0. Verify workspace exists (stale session may reference deleted workspace)
        from modules.base.core.models.workspace import DEFAULT_WORKSPACE_COLOR, Workspace, WORKSPACE_COLORS

        ts = getattr(g, "workspace", None) or Workspace.query.get(g.workspace_id)
        if not ts:
            session.pop("active_workspace_id", None)
            g.workspace_id = None
            g.organization_id = None
            g.workspace_color = WORKSPACE_COLORS[DEFAULT_WORKSPACE_COLOR]
            g.company_settings = None
            g.installed_modules = []
            g.current_module = {}
            g.lang = app.config.get("DEFAULT_LANGUAGE", "en")
            g.device_type = "desktop"
            g.is_mobile = False
            return

        # 0.1 Company Settings (for terminology, etc.)
        g.company_settings = WorkspaceSettings.get_instance()

        # 0.2 Workspace color (for top bar and avatar)
        g.workspace_color = ts.color_hex
        g.workspace = ts

        # 1.6 Onboarding Jail - redirect users in active onboarding to wizard
        # Skip for MSA transparent mode (MSA may be proxied as a non-admin user)
        if current_user.is_authenticated and not current_user.is_admin and not session.get("msa_transparent_mode"):
            from flask import redirect, url_for
            from modules.base.people.models.onboarding import OnboardingRecord, OnboardingStatus

            member = getattr(g, "_workspace_membership", None)
            if member:
                onboarding = OnboardingRecord.get_by_member_id(member.id)
                if onboarding and onboarding.status in (
                    OnboardingStatus.SENT,
                    OnboardingStatus.IN_PROGRESS,
                    OnboardingStatus.PENDING_REVIEW,
                ):
                    # Allow only onboarding-related routes
                    allowed_paths = [
                        "/people/onboarding/my",
                        "/people/onboarding/my/save",
                        "/people/onboarding/my/submit",
                        "/people/onboarding/my/skip/",
                        "/people/onboarding/start/",
                        "/people/onboarding/set-password",
                        "/sign/",  # Allow e-signing
                        "/static/",
                        "/assets/",  # Allow static assets
                        "/logout",
                    ]
                    path = request.path
                    if not any(path.startswith(allowed) for allowed in allowed_paths):
                        return redirect(url_for("people_bp.onboarding_wizard"))

        # 2. Module Context Setup
        g.installed_modules = current_app.config.get("INSTALLED_MODULES", {}).values()
        path_parts = request.path.split("/")

        # Handle /m/{mappid}/... routes for marketplace apps
        if len(path_parts) >= 3 and path_parts[1] == "m":
            mappid = path_parts[2]
            current_module = next(
                (m for m in g.installed_modules if m.get("mappid") == mappid),
                None,
            )
        else:
            # Standard route matching by main_route
            path = path_parts[1] if len(path_parts) > 1 else "core"
            current_module = next(
                (
                    m
                    for m in g.installed_modules
                    if m.get("main_route", "").strip("/").lower() == path.lower()
                ),
                next(
                    (m for m in g.installed_modules if m.get("name", "").lower() == "core"),
                    None,  # If neither path nor core module found, will be None
                ),
            )

        if current_module is None:
            # Log warning that module wasn't found
            app.logger.warning(f"Module not found for path: {request.path}")
            # Let the route handler deal with 404 if needed

        g.current_module = current_module

        # 3. Language Handling
        g.lang = (
            request.args.get("lang")
            or session.get("lang")
            or (
                UserSetting.get(current_user.id, "language")
                if current_user.is_authenticated
                else None
            )
            or app.config.get("DEFAULT_LANGUAGE", "en")
        )

        # Store language in session if changed
        if "lang" not in session or session["lang"] != g.lang:
            session["lang"] = g.lang

        # 4. Device Detection
        from system.device import get_device_type

        g.device_type = get_device_type()
        g.is_mobile = g.device_type == "mobile"

    @app.before_request
    def set_page_context() -> None:
        """Pre-populate g._page_context for full HTML page renders.

        Single SQL with scalar subqueries replaces ~15 individual context
        processor queries. Skips HTMX partials, API endpoints, and static
        assets (DB Access Standards §5.2, §7.2).
        """
        if not current_user.is_authenticated:
            return
        if getattr(g, "workspace_id", None) is None:
            return
        if getattr(g, "organization_id", None) is None:
            return

        path = request.path
        if path.startswith(("/static/", "/assets/", "/api/", "/health")):
            return
        if request.headers.get("HX-Request"):
            return

        member = getattr(g, "_current_member_cache", None)
        member_id = member.id if member else None
        org_user = getattr(g, "_organization_user", None)
        org_member_id = org_user.id if org_user else None

        from modules.base.dashboard.queries.page_context import get_dashboard_page_context

        g._page_context = get_dashboard_page_context(
            organization_id=g.organization_id,
            workspace_id=g.workspace_id,
            user_id=current_user.id,
            member_id=member_id,
            is_admin=current_user.is_admin,
            org_member_id=org_member_id,
        )

    @app.after_request
    def add_security_headers(response: Response) -> Response:
        """Add security headers to all responses."""
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(self), geolocation=(self)"
        )

        # HSTS — production only (behind HTTPS via Traefik)
        if not app.config.get("_DEBUG_MODE"):
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        # CSP — unsafe-inline required for Alpine.js (unsafe-eval) and inline
        # event handlers (onclick, etc.). Nonce removed because it causes
        # browsers to ignore unsafe-inline for event handlers.
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' "
            "https://unpkg.com https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' "
            "https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
            "font-src 'self' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net https://fonts.gstatic.com; "
            "img-src 'self' data: https:; "
            "media-src 'self' blob:; "
            "connect-src 'self' wss: ws: https://cdn.jsdelivr.net; "
            "frame-src 'self' https://maps.google.com https://www.google.com; "
            "frame-ancestors 'self';"
        )

        return response

    @app.after_request
    def log_query_stats(response: Response) -> Response:
        """Log per-request DB query count and time (§7.1). WARN on budget violations (§7.2)."""
        query_count = getattr(g, "db_query_count", 0)
        if query_count == 0:
            return response
        query_time_ms = round(getattr(g, "db_query_time", 0.0) * 1000, 1)
        request_logger.info(
            "request_db_stats",
            extra={
                "path": request.path,
                "method": request.method,
                "query_count": query_count,
                "query_time_ms": query_time_ms,
                "status": response.status_code,
            },
        )
        if query_count > 20:
            request_logger.warning(
                "query_budget_exceeded path=%s count=%d time=%.1fms",
                request.path,
                query_count,
                query_time_ms,
            )
        return response

    if _debug:

        @app.after_request
        def log_debug_query_breakdown(response: Response) -> Response:
            """Print per-origin DB query breakdown to console in debug mode."""
            content_type = response.content_type or ""
            if "text/html" not in content_type:
                return response
            if request.headers.get("HX-Request"):
                return response
            if request.path.startswith(("/static/", "/assets/", "/api/")):
                return response

            query_log = getattr(g, "db_query_log", None)
            if not query_log:
                return response

            agg: dict[tuple[str, str], list] = {}
            for entry in query_log:
                key = (entry["category"], entry["source"])
                if key not in agg:
                    agg[key] = [0, 0.0]
                agg[key][0] += 1
                agg[key][1] += entry["time"]

            rows = sorted(agg.items(), key=lambda r: (-r[1][0], -r[1][1]))

            total_count = sum(v[0] for _, v in rows)
            total_time = sum(v[1] for _, v in rows)

            w_cat = max(len(k[0]) for k, _ in rows)
            w_src = max(len(k[1]) for k, _ in rows)
            w_cat = max(w_cat, 8)
            w_src = max(w_src, 6)
            line_w = w_cat + w_src + 24

            lines = [
                "",
                "\033[90m" + "─" * line_w + "\033[0m",
                f" \033[93m{request.method} {request.path}\033[0m"
                f" — \033[1m{total_count}\033[0m queries, "
                f"\033[1m{round(total_time * 1000, 1)}\033[0m ms",
                "\033[90m" + "─" * line_w + "\033[0m",
                f" \033[90m{'Category':<{w_cat}}  {'Source':<{w_src}}  {'Qry':>5}  {'Time':>8}\033[0m",
            ]

            for (cat, src), (count, t) in rows:
                time_ms = f"{round(t * 1000, 1)}ms"
                count_color = "\033[93m" if count > 10 else ""
                time_color = "\033[91m" if t * 1000 > 10 else ""
                reset = "\033[0m"
                lines.append(
                    f" {cat:<{w_cat}}  {src:<{w_src}}"
                    f"  {count_color}{count:>5}{reset}"
                    f"  {time_color}{time_ms:>8}{reset}"
                )

            lines.append("\033[90m" + "─" * line_w + "\033[0m")
            print("\n".join(lines), flush=True)

            return response
