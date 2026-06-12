# -----------------------------------------------------------------------------
# sparQ - Email System
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""
Email sending system for sparQ.

Usage:
    from system.email import send_email, is_configured

    # Check if email is configured
    if is_configured():
        send_email(
            to="user@example.com",
            subject="Hello",
            html_body="<p>Hello World</p>"
        )

Configuration:
    Configure via Settings > Email in the admin UI
    (Password can also be set via SMTP_PASSWORD env var as fallback)
"""

from system.email.service import send_email, send_email_async, is_configured, test_connection

__all__ = ["send_email", "send_email_async", "is_configured", "test_connection"]
