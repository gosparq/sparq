# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Authentication module exports for decorators and utilities.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

"""Authentication decorators and utilities for route protection.

This module provides decorators to protect Flask routes with various
authentication and authorization requirements, plus password policy
enforcement.

Decorators:
    login_required_api: Require login, return JSON on failure.
    admin_required: Require admin role, redirect on failure.
    admin_required_api: Require admin role, return JSON on failure.
    permission_required: Require a permission area.
Password Policy:
    validate_password: Check password meets complexity requirements.
    is_breached: Check if password appears in known data breaches.

Example:
    Protecting a route with admin access::

        from flask import Blueprint
        from flask_login import login_required
        from system.auth import admin_required

        bp = Blueprint("admin", __name__)

        @bp.route("/dashboard")
        @login_required
        @admin_required
        def admin_dashboard():
            return render_template("admin/dashboard.html")

    Protecting an API route::

        from system.auth import login_required_api

        @bp.route("/api/users")
        @login_required_api
        def api_users():
            return jsonify({"users": [...]})

Note:
    For web routes, use Flask-Login's @login_required first,
    then add @admin_required or other decorators.
    For API routes, use @login_required_api instead.
"""

# Authentication utilities
from .decorators import (
    admin_required,
    admin_required_api,
    group_required,
    login_required_api,
    permission_required,
)

# Password policy
from .password_policy import is_breached, validate_password

__all__ = [
    "admin_required",
    "admin_required_api",
    "group_required",
    "login_required_api",
    "permission_required",
    "is_breached",
    "validate_password",
]
