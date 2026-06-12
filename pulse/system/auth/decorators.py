# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Authentication decorators for route protection.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

"""Authentication and authorization decorators.

This module contains all the decorators used to protect routes
with various access control requirements.

Web vs API Decorators:
    Web decorators (e.g., admin_required) redirect to login page on failure.
    API decorators (e.g., admin_required_api) return JSON error responses.

Decorator Order:
    Always apply @login_required (from Flask-Login) first for web routes::

        @bp.route("/protected")
        @login_required        # First: ensure user is logged in
        @admin_required        # Then: check admin status
        def protected():
            ...

Available Decorators:
    - admin_required: Require admin role (web)
    - admin_required_api: Require admin role (API)
    - permission_required: Require permission area (web)
    - requires_access: Require permission area access (web)
    - requires_access_api: Require permission area access (API)
    - login_required_api: Require authentication (API)
"""

from functools import wraps
from typing import Any, Callable, TypeVar

from flask import flash, redirect, request, url_for, jsonify
from flask_login import current_user

F = TypeVar("F", bound=Callable[..., Any])


def _is_htmx_request() -> bool:
    """Check if the current request was made by HTMX."""
    return request.headers.get("HX-Request") == "true"


def admin_required(f: F) -> F:
    """Decorator to require **workspace-admin** access for a route.

    Use after @login_required decorator. Phase 6 note: this means
    "admin of the current workspace". Accepts organization admins when
    they're a full member of the current workspace. When an organization
    admin is viewing a non-member workspace via audit access
    (g.workspace_access='audit'), this decorator returns 403 because
    audit access is read-only (§3.4, §12.2).

    `workspace_admin_required` is an alias for clarity in new code.

    Example:
        @blueprint.route("/admin")
        @login_required
        @admin_required
        def admin_panel():
            return render_template("admin.html")
    """

    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        from flask import g

        if not current_user.is_authenticated:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("core_bp.login"))

        # Audit access is read-only — block mutating workspace-admin endpoints.
        if getattr(g, "workspace_access", None) == "audit":
            if _is_htmx_request():
                return "Read-only access via organization audit.", 403
            flash("Read-only access via organization audit. Actions are disabled.", "error")
            return redirect(url_for("dashboard_bp.index"))

        if not current_user.is_admin:
            if _is_htmx_request():
                return "Admin access required.", 403
            flash("Admin access required.", "error")
            return redirect(url_for("core_bp.login"))
        return f(*args, **kwargs)

    return decorated_function  # type: ignore[return-value]


# Alias — clearer name for new code in the org-hierarchy era.
workspace_admin_required = admin_required


def organization_member_required(f: F) -> F:
    """Require an active OrganizationUser row for the current organization.

    Blocks routes under /settings/organization or /organization-scoped
    paths for users who aren't members of g.organization_id.
    """

    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        from flask import g
        from modules.base.core.models.organization_user import OrganizationUser

        if not current_user.is_authenticated:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("core_bp.login"))

        org_id = getattr(g, "organization_id", None)
        if org_id is None:
            flash("No active organization context.", "error")
            return redirect(url_for("dashboard_bp.index"))

        membership = OrganizationUser.get_for_user(current_user.id, org_id)
        if membership is None or not membership.is_active:
            if _is_htmx_request():
                return "Organization membership required.", 403
            flash("You don't have access to this organization.", "error")
            return redirect(url_for("dashboard_bp.index"))
        return f(*args, **kwargs)

    return decorated_function  # type: ignore[return-value]


def organization_admin_required(f: F) -> F:
    """Require OrganizationUser.role='admin' for the current organization.

    Use on /settings/organization/* routes, workspace archive/restore, and
    any other org-admin-only action per the Phase 6 spec.
    """

    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        from flask import g

        if not current_user.is_authenticated:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("core_bp.login"))

        if not getattr(g, "is_organization_admin", False):
            if _is_htmx_request():
                return "Organization admin required.", 403
            flash("Organization admin access required.", "error")
            return redirect(url_for("dashboard_bp.index"))
        return f(*args, **kwargs)

    return decorated_function  # type: ignore[return-value]


def permission_required(area: str) -> Callable[[F], F]:
    """Decorator to require a permission area.

    Use after @login_required decorator. Admins always pass.

    Args:
        area: Permission area name (hr, finance, operations)

    Example:
        @blueprint.route("/managers")
        @login_required
        @permission_required("hr")
        def hr_only():
            return render_template("hr.html")
    """

    def decorator(f: F) -> F:
        @wraps(f)
        def decorated_function(*args: Any, **kwargs: Any) -> Any:
            if not current_user.is_authenticated:
                flash("Please log in.", "warning")
                return redirect(url_for("core_bp.login"))
            if not current_user.has_access(area):
                msg = f"Access requires {area.upper()} permission."
                if _is_htmx_request():
                    return msg, 403
                flash(msg, "error")
                return redirect(url_for("core_bp.login"))
            return f(*args, **kwargs)

        return decorated_function  # type: ignore[return-value]

    return decorator


# Backward compat alias
group_required = permission_required


def requires_access(area: str) -> Callable[[F], F]:
    """Decorator to require access to a permission area.

    Grants access if user is admin OR has the specified permission group.
    Use after @login_required decorator.

    Args:
        area: Permission area (hr, finance, operations)

    Example:
        @blueprint.route("/hiring")
        @login_required
        @requires_access("hr")
        def hiring_index():
            return render_template("hiring/index.html")
    """

    def decorator(f: F) -> F:
        @wraps(f)
        def decorated_function(*args: Any, **kwargs: Any) -> Any:
            if not current_user.is_authenticated:
                flash("Please log in.", "warning")
                return redirect(url_for("core_bp.login"))
            if not current_user.has_access(area):
                msg = f"Access denied. {area.upper()} permission required."
                if _is_htmx_request():
                    return msg, 403
                flash(msg, "error")
                return redirect(url_for("dashboard_bp.index"))
            return f(*args, **kwargs)

        return decorated_function  # type: ignore[return-value]

    return decorator


def requires_access_api(area: str) -> Callable[[F], F]:
    """API version of requires_access that returns JSON instead of redirect.

    Args:
        area: Permission area (hr, finance, operations)

    Example:
        @blueprint.route("/api/hiring/candidates")
        @requires_access_api("hr")
        def api_candidates():
            return jsonify({"candidates": [...]})
    """

    def decorator(f: F) -> F:
        @wraps(f)
        def decorated_function(*args: Any, **kwargs: Any) -> Any:
            if not current_user.is_authenticated:
                return jsonify({"error": "Authentication required"}), 401
            if not current_user.has_access(area):
                return jsonify({"error": f"{area.upper()} access required"}), 403
            return f(*args, **kwargs)

        return decorated_function  # type: ignore[return-value]

    return decorator


def login_required_api(f: F) -> F:
    """Decorator for API routes that returns JSON instead of redirect.

    Example:
        @blueprint.route("/api/data")
        @login_required_api
        def api_data():
            return jsonify({"data": "..."})
    """

    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        if not current_user.is_authenticated:
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)

    return decorated_function  # type: ignore[return-value]


def admin_required_api(f: F) -> F:
    """Decorator for API routes that requires admin and returns JSON.

    Example:
        @blueprint.route("/api/admin/users")
        @admin_required_api
        def api_admin_users():
            return jsonify({"users": [...]})
    """

    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        if not current_user.is_authenticated:
            return jsonify({"error": "Authentication required"}), 401
        if not current_user.is_admin:
            return jsonify({"error": "Admin access required"}), 403
        return f(*args, **kwargs)

    return decorated_function  # type: ignore[return-value]


