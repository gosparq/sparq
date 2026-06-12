# -----------------------------------------------------------------------------
# sparQ - Error Handlers
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# Error Handlers
#
# Registers Flask error handlers for AppError, HTTPException, and generic exceptions.
# -----------------------------------------------------------------------------

import logging
import os
import traceback
import uuid
from datetime import datetime, timezone
from html import escape
from typing import Any

from flask import Flask, g, render_template, request
from flask_login import current_user
from werkzeug.exceptions import HTTPException

from system.exceptions import AppError

logger = logging.getLogger(__name__)


def _wants_json() -> bool:
    """Check if client prefers JSON response over HTML."""
    return request.accept_mimetypes["application/json"] >= request.accept_mimetypes["text/html"]


def _is_htmx_request() -> bool:
    """Check if the current request was made by HTMX."""
    return request.headers.get("HX-Request") == "true"


def _send_error_notification(error_id: str, exc: Exception) -> None:
    """Best-effort email to dev team when an unhandled 500 occurs.

    Gathers request/user/workspace/org context and sends via the email
    gateway (no workspace config required). Never raises — a failure here
    must not interfere with the error response.
    """
    recipients = os.environ.get("ERROR_NOTIFY_EMAIL", "")
    if not recipients:
        return

    try:
        from system.email.service import send_gateway_email

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        tb = escape(traceback.format_exc())

        url = "Unknown"
        method = "Unknown"
        user_agent = "Unknown"
        referer = "Unknown"
        request_id = "Unknown"
        try:
            url = escape(request.url)
            method = escape(request.method)
            user_agent = escape(request.headers.get("User-Agent", "Unknown"))
            referer = escape(request.headers.get("Referer", "None"))
            request_id = escape(str(getattr(g, "request_id", "Unknown")))
        except RuntimeError:
            pass

        user_email = "Anonymous"
        user_name = "Anonymous"
        user_id = "N/A"
        try:
            if current_user.is_authenticated:
                user_email = escape(current_user.email or "Unknown")
                first = current_user.first_name or ""
                last = current_user.last_name or ""
                user_name = escape(f"{first} {last}".strip() or user_email)
                user_id = escape(str(current_user.id))
        except Exception:
            pass

        workspace_name = "None"
        workspace_id = "None"
        try:
            ts_id = getattr(g, "workspace_id", None)
            if ts_id:
                workspace_id = escape(str(ts_id))
                ts = getattr(g, "workspace", None)
                if ts:
                    workspace_name = escape(str(getattr(ts, "name", "Unknown")))
        except Exception:
            pass

        org_name = "None"
        org_id = "None"
        try:
            o_id = getattr(g, "organization_id", None)
            if o_id:
                org_id = escape(str(o_id))
                from modules.base.core.models.organization import Organization
                org = Organization.query.get(o_id)
                if org:
                    org_name = escape(str(org.name))
        except Exception:
            pass

        exc_type_raw = type(exc).__name__
        exc_msg_raw = str(exc)
        exc_type = escape(exc_type_raw)
        exc_msg = escape(exc_msg_raw)

        html = (
            f'<div style="font-family:system-ui,sans-serif;max-width:700px;margin:0 auto;">'
            f'<div style="background:#dc3545;color:#fff;padding:16px 20px;border-radius:8px 8px 0 0;">'
            f'<h2 style="margin:0;font-size:18px;">500 Error Report</h2>'
            f'<p style="margin:4px 0 0;opacity:0.9;font-size:13px;">Error ID: {error_id}</p>'
            f'</div>'
            f'<div style="border:1px solid #e5e7eb;border-top:none;border-radius:0 0 8px 8px;padding:20px;">'
            f'<table style="width:100%;border-collapse:collapse;font-size:14px;">'
            f'<tr><td style="padding:6px 12px;color:#6b7280;width:130px;">Timestamp</td>'
            f'<td style="padding:6px 12px;">{timestamp}</td></tr>'
            f'<tr style="background:#f9fafb;"><td style="padding:6px 12px;color:#6b7280;">URL</td>'
            f'<td style="padding:6px 12px;">{method} {url}</td></tr>'
            f'<tr><td style="padding:6px 12px;color:#6b7280;">User</td>'
            f'<td style="padding:6px 12px;">{user_name} ({user_email})</td></tr>'
            f'<tr style="background:#f9fafb;"><td style="padding:6px 12px;color:#6b7280;">User ID</td>'
            f'<td style="padding:6px 12px;"><code>{user_id}</code></td></tr>'
            f'<tr><td style="padding:6px 12px;color:#6b7280;">Workspace</td>'
            f'<td style="padding:6px 12px;">{workspace_name} (<code>{workspace_id}</code>)</td></tr>'
            f'<tr style="background:#f9fafb;"><td style="padding:6px 12px;color:#6b7280;">Organization</td>'
            f'<td style="padding:6px 12px;">{org_name} (<code>{org_id}</code>)</td></tr>'
            f'<tr><td style="padding:6px 12px;color:#6b7280;">Request ID</td>'
            f'<td style="padding:6px 12px;"><code>{request_id}</code></td></tr>'
            f'<tr style="background:#f9fafb;"><td style="padding:6px 12px;color:#6b7280;">User Agent</td>'
            f'<td style="padding:6px 12px;font-size:12px;">{user_agent}</td></tr>'
            f'<tr><td style="padding:6px 12px;color:#6b7280;">Referer</td>'
            f'<td style="padding:6px 12px;font-size:12px;">{referer}</td></tr>'
            f'</table>'
            f'<h3 style="margin:20px 0 8px;font-size:15px;color:#dc3545;">'
            f'{exc_type}: {exc_msg}</h3>'
            f'<pre style="background:#1e1e1e;color:#d4d4d4;padding:16px;border-radius:6px;'
            f'font-size:12px;line-height:1.5;overflow-x:auto;white-space:pre-wrap;">{tb}</pre>'
            f'</div></div>'
        )

        short_id = error_id[:8]
        subject = f"[sparQ 500] {exc_type_raw}: {exc_msg_raw[:80]} ({short_id})"

        for addr in recipients.split(","):
            addr = addr.strip()
            if addr:
                try:
                    send_gateway_email(addr, subject, html)
                except Exception:
                    logger.warning("Failed to send error notification to %s", addr, exc_info=True)

    except Exception:
        logger.warning("Failed to send error notification for %s", error_id, exc_info=True)


def register_error_handlers(app: Flask) -> None:
    """Register global error handlers for the Flask application."""

    @app.errorhandler(AppError)
    def handle_app_error(e: AppError) -> tuple[str, int] | tuple[dict[str, Any], int]:
        """Handle custom application errors."""
        app.logger.error(
            "Application error [%s]: %s - %s", e.error_id, e.__class__.__name__, str(e)
        )

        # Map exception types to HTTP status codes
        status_code = 500
        from system.exceptions import (
            ValidationError,
            NotFoundError,
            ConflictError,
            AuthenticationError,
            AuthorizationError,
        )

        if isinstance(e, ValidationError):
            status_code = 400
        elif isinstance(e, NotFoundError):
            status_code = 404
        elif isinstance(e, ConflictError):
            status_code = 409
        elif isinstance(e, AuthenticationError):
            status_code = 401
        elif isinstance(e, AuthorizationError):
            status_code = 403

        if _wants_json():
            response = {
                "error": {
                    "id": e.error_id,
                    "code": status_code,
                    "title": e.__class__.__name__,
                    "message": e.message,
                }
            }
            if hasattr(e, "field") and e.field:
                response["error"]["field"] = e.field  # type: ignore[index]
            return response, status_code

        # HTMX requests get plain text so the JS toast handler can display it
        if _is_htmx_request() and status_code == 403:
            return e.message, 403

        return (
            render_template(
                "core/desktop/errors/error.html",
                error_code=status_code,
                error_title=e.__class__.__name__.replace("Error", " Error"),
                error_message=e.message,
                error_id=e.error_id,
            ),
            status_code,
        )

    @app.errorhandler(HTTPException)
    def handle_http_exception(e: HTTPException) -> tuple[str, int] | tuple[dict[str, Any], int]:
        """Handle HTTP exceptions (404, 403, etc.)."""
        error_id = str(uuid.uuid4())[:8]  # Short ID for console
        # Use short message for common errors
        short_desc = {
            403: "Access denied",
            404: "Not found",
            405: "Method not allowed",
        }.get(e.code or 0, e.name)
        app.logger.warning("HTTP %s [%s]: %s", e.code, error_id, short_desc)

        if _wants_json():
            response = {
                "error": {
                    "id": error_id,
                    "code": e.code or 500,
                    "title": e.name,
                    "message": e.description or "An error occurred",
                }
            }
            return response, e.code or 500

        # HTMX requests get plain text so the JS toast handler can display it
        if _is_htmx_request() and e.code == 403:
            return short_desc, 403

        return (
            render_template(
                "core/desktop/errors/error.html",
                error_code=e.code,
                error_title=e.name,
                error_message=e.description,
                error_id=error_id,
                module_home="core_bp.index",  # Default for error pages
            ),
            e.code or 500,
        )

    @app.errorhandler(Exception)
    def handle_unexpected_exception(e: Exception) -> tuple[str, int] | tuple[dict[str, Any], int]:
        """Handle all unexpected exceptions."""
        error_id = str(uuid.uuid4())
        app.logger.exception("Unhandled exception [%s]: %s", error_id, str(e))

        # Roll back any failed DB transaction so template rendering doesn't cascade
        try:
            from system.db.database import db
            db.session.rollback()
        except Exception:
            pass

        _send_error_notification(error_id, e)

        friendly_message = "Something unexpected happened. Please try again shortly."

        if _wants_json():
            response = {
                "error": {
                    "id": error_id,
                    "code": 500,
                    "title": "Internal Server Error",
                    "message": friendly_message,
                }
            }
            return response, 500

        try:
            return (
                render_template(
                    "core/desktop/errors/error.html",
                    error_code=500,
                    error_title="Internal Server Error",
                    error_message=friendly_message,
                    error_id=error_id,
                    module_home="core_bp.index",
                ),
                500,
            )
        except Exception:
            # Fallback if template rendering itself fails (e.g. DB-dependent context processors)
            return (
                f'<!DOCTYPE html><html><head><title>500</title></head>'
                f'<body style="font-family:system-ui;display:flex;align-items:center;'
                f'justify-content:center;min-height:100vh;margin:0;background:#f9fafb;">'
                f'<div style="text-align:center;">'
                f'<h1 style="font-size:3rem;color:#d1d5db;margin:0;">500</h1>'
                f'<p style="color:#6b7280;margin:0.5rem 0;">{friendly_message}</p>'
                f'<p style="font-size:0.75rem;color:#9ca3af;">ID: {error_id[:8]}</p>'
                f'<a href="/" style="color:#6366f1;font-size:0.875rem;">Go home</a>'
                f'</div></body></html>',
                500,
            )
