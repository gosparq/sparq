# -----------------------------------------------------------------------------
# CSRF Protection Middleware
#
# Prevents cross-site request forgery by requiring a per-session token
# on all state-changing requests (POST, PUT, DELETE, PATCH).
#
# Token can be submitted as:
#   - Form field: <input name="csrf_token" value="{{ csrf_token }}">
#   - HTTP header: X-CSRF-Token (used by HTMX and fetch())
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

import secrets

from flask import Flask, abort, current_app, request, session


def generate_csrf_token() -> str:
    """Generate a CSRF token and store it in the session.

    Returns the existing token if one is already present, ensuring
    the same token is used across all forms in a single session.

    Returns:
        URL-safe CSRF token string.
    """
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_urlsafe(32)
    return session["_csrf_token"]


def validate_csrf_token() -> bool:
    """Validate the submitted CSRF token against the session token.

    Checks both the form field ``csrf_token`` and the ``X-CSRF-Token``
    header. Uses ``secrets.compare_digest`` for timing-attack-safe
    comparison.

    Returns:
        True if the token is valid, False otherwise.
    """
    token = session.get("_csrf_token")
    if not token:
        return False

    submitted = request.form.get("csrf_token") or request.headers.get(
        "X-CSRF-Token"
    )

    if not submitted:
        return False

    return secrets.compare_digest(token, submitted)


def init_csrf(app: Flask) -> None:
    """Initialize CSRF protection on the Flask application.

    Registers a context processor to make ``csrf_token`` available in
    all templates, and a ``before_request`` hook that validates the
    token on all state-changing requests.

    Exempt paths:
        - ``/health`` — health check endpoint
        - ``/api/webhooks/`` — webhook API (uses token auth)
        - ``/auth/`` — OAuth callbacks (use state parameter)

    Args:
        app: Flask application instance.
    """

    @app.context_processor
    def csrf_context():
        return {"csrf_token": generate_csrf_token()}

    @app.before_request
    def check_csrf():
        if not current_app.config.get("WTF_CSRF_ENABLED", True):
            return

        if request.method in ("GET", "HEAD", "OPTIONS"):
            return

        # Exempt paths
        exempt = (
            "/health",
            "/api/v1/",  # Mobile API uses JWT auth
            "/api/webhooks/",  # Webhook API uses token auth
            "/auth/",  # OAuth callbacks use state parameter
            "/integrations/webhooks/",  # GitHub App webhooks use HMAC-SHA256 signature
        )
        if any(request.path.startswith(p) for p in exempt):
            return

        if not validate_csrf_token():
            abort(403, "CSRF token missing or invalid")
