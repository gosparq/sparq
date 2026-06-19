# -----------------------------------------------------------------------------
# sparQ - Email Service
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""Email sending service for SMTP and API-based delivery.

This module provides the core email sending functionality with support
for both traditional SMTP servers and API-based services like sparQ Mail.

Classes:
    EmailService: SMTP-based email service.
    SparqMailService: API-based email service for sparQ Mail.
    GatewayEmailService: Bootstrap transport via the sparQ email gateway.

Functions:
    send_email: Send an email synchronously (blocks until sent).
    send_email_async: Queue an email for background delivery.
    is_configured: Check if email settings are properly configured.
    test_connection: Test SMTP connection without sending.

Example:
    Simple email sending::

        from system.email import send_email, is_configured

        if is_configured():
            success = send_email(
                to="customer@example.com",
                subject="Order Confirmation",
                html_body="<h1>Thank you for your order!</h1>"
            )

    Async (fire-and-forget) sending::

        from system.email import send_email_async

        # Returns immediately, email sent in background
        send_email_async(
            to="customer@example.com",
            subject="Welcome!",
            html_body="<p>Thanks for signing up</p>"
        )
"""

import base64
import logging
import os
import smtplib
from typing import Any
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.encoders import encode_base64

from system.email.config import EmailConfig

logger = logging.getLogger(__name__)


class SparqMailService:
    """Email service using sparQ Mail API."""

    SPARQMAIL_API_URL = os.environ.get("SPARQMAIL_API_URL", "")

    def __init__(self, config: EmailConfig) -> None:
        self.config = config

    def send(
        self,
        to: str,
        subject: str,
        html_body: str,
        text_body: str | None = None,
        attachments: list[dict] | None = None,
    ) -> bool:
        """Send email via sparQ Mail API.

        Args:
            to: Recipient email address
            subject: Email subject
            html_body: HTML content
            text_body: Plain text content (optional)
            attachments: List of attachment dicts with keys:
                - filename: Name of the file
                - content: Base64-encoded file content
                - content_type: MIME type (e.g., "application/pdf")
        """
        import requests

        try:
            payload: dict[str, Any] = {
                "to": to,
                "subject": subject,
                "body": html_body,
                "site_id": self.config.site_id,
            }

            # Include from_name if available (company name for sender display)
            if self.config.from_name:
                payload["from_name"] = self.config.from_name

            # Include attachments if provided
            if attachments:
                payload["attachments"] = attachments

            response = requests.post(
                self.SPARQMAIL_API_URL,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.config.api_key}",
                },
                json=payload,
                timeout=30,
            )
            if response.status_code in (200, 202):
                logger.info(f"[SPARQMAIL] Email sent successfully to {to}")
                return True
            else:
                logger.error(f"[SPARQMAIL] API returned status {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"[SPARQMAIL] Request failed: {e}")
            return False


class EmailService:
    """Service for sending emails via SMTP."""

    def __init__(self, config: EmailConfig):
        self.config = config

    def send(
        self,
        to: str,
        subject: str,
        html_body: str,
        text_body: str | None = None,
        attachments: list[dict] | None = None,
    ) -> bool:
        """
        Send an email.

        Args:
            to: Recipient email address
            subject: Email subject
            html_body: HTML content
            text_body: Plain text content (optional, auto-generated if not provided)
            attachments: List of attachment dicts with keys:
                - filename: Name of the file
                - content: Base64-encoded file content
                - content_type: MIME type (e.g., "application/pdf")

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # Use mixed type when we have attachments, alternative for text-only
            if attachments:
                msg = MIMEMultipart("mixed")
                # Create alternative part for text/html
                alt_part = MIMEMultipart("alternative")
                if text_body:
                    alt_part.attach(MIMEText(text_body, "plain"))
                alt_part.attach(MIMEText(html_body, "html"))
                msg.attach(alt_part)
            else:
                msg = MIMEMultipart("alternative")
                if text_body:
                    msg.attach(MIMEText(text_body, "plain"))
                msg.attach(MIMEText(html_body, "html"))

            msg["Subject"] = subject
            msg["From"] = f"{self.config.from_name} <{self.config.from_email}>"
            msg["To"] = to

            # Add attachments
            if attachments:
                for attachment in attachments:
                    filename = attachment.get("filename", "attachment")
                    content = attachment.get("content", "")
                    content_type = attachment.get("content_type", "application/octet-stream")

                    # Decode base64 content
                    file_data = base64.b64decode(content)

                    # Create attachment part
                    maintype, subtype = content_type.split("/", 1)
                    part = MIMEBase(maintype, subtype)
                    part.set_payload(file_data)
                    encode_base64(part)
                    part.add_header(
                        "Content-Disposition",
                        "attachment",
                        filename=filename
                    )
                    msg.attach(part)

            # Connect and send
            with smtplib.SMTP(self.config.host, self.config.port, timeout=30) as server:
                if self.config.use_tls:
                    server.starttls()
                server.login(self.config.username, self.config.password)
                server.sendmail(self.config.from_email, to, msg.as_string())

            logger.info(f"Email sent successfully to {to}")
            return True

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed: {e}")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error: {e}")
            return False
        except Exception as e:
            logger.error(f"Email send failed: {e}")
            return False


class GatewayEmailService:
    """Email service using the sparQ email gateway (bypass-token auth).

    The gateway is a bootstrap transport used when no SMTP / sparQ Mail
    provider is configured yet — for example on fresh installs, signup
    confirmation, admin/error notices, and passwordless login links. It posts
    to ``{gateway_url}/send`` and authenticates with the bypass token rather
    than per-workspace credentials.

    Configure via environment variables:
        SPARQ_GATEWAY_URL: Base URL of the gateway (e.g. https://mail.example.com).
        SPARQ_GATEWAY_BYPASS_TOKEN: Bearer token matching the gateway's AUTH_BYPASS.
        SPARQ_GATEWAY_SITE_ID: Optional site identifier (defaults to "sparq").
        SPARQ_GATEWAY_FROM_NAME: Optional sender display name (defaults to "sparQ").
    """

    def __init__(self, gateway_url: str, bypass_token: str) -> None:
        self.gateway_url = gateway_url.rstrip("/")
        self.bypass_token = bypass_token
        self.site_id = os.environ.get("SPARQ_GATEWAY_SITE_ID", "sparq")
        self.from_name = os.environ.get("SPARQ_GATEWAY_FROM_NAME", "sparQ")

    def send(
        self,
        to: str,
        subject: str,
        html_body: str,
        text_body: str | None = None,
        attachments: list[dict] | None = None,
    ) -> bool:
        """Send an email through the gateway.

        Args:
            to: Recipient email address.
            subject: Email subject.
            html_body: HTML content.
            text_body: Plain text content (optional, sent alongside HTML).
            attachments: List of attachment dicts with keys filename, content
                (base64), and content_type.

        Returns:
            True if the gateway accepted the message, False otherwise.
        """
        import requests

        payload: dict[str, Any] = {
            "to": to,
            "subject": subject,
            "body": html_body,
            "from_name": self.from_name,
            "site_id": self.site_id,
        }
        if text_body:
            payload["text_body"] = text_body
        if attachments:
            payload["attachments"] = attachments

        try:
            response = requests.post(
                f"{self.gateway_url}/send",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.bypass_token}",
                },
                json=payload,
                timeout=30,
            )
            if response.status_code in (200, 202):
                logger.info(f"[GATEWAY] Email sent successfully to {to}")
                return True
            logger.error(f"[GATEWAY] API returned status {response.status_code}: {response.text[:500]}")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"[GATEWAY] Request failed: {e}")
            return False


def _gateway_config() -> tuple[str, str] | None:
    """Return ``(gateway_url, bypass_token)`` if the email gateway is configured.

    The gateway acts as a fallback transport when no SMTP / sparQ Mail provider
    is configured. Both the URL and bypass token must be present.

    Returns:
        A ``(url, token)`` tuple when configured, otherwise None.
    """
    url = os.environ.get("SPARQ_GATEWAY_URL", "").strip()
    token = os.environ.get("SPARQ_GATEWAY_BYPASS_TOKEN", "").strip()
    if url and token:
        return url, token
    return None


def send_email(
    to: str,
    subject: str,
    html_body: str,
    text_body: str | None = None,
    attachments: list[dict] | None = None,
) -> bool:
    """
    Convenience function for sending email.

    Args:
        to: Recipient email address
        subject: Email subject
        html_body: HTML content
        text_body: Plain text content (optional)
        attachments: List of attachment dicts with keys:
            - filename: Name of the file
            - content: Base64-encoded file content
            - content_type: MIME type (e.g., "application/pdf")

    Returns:
        True if sent, False if failed or not configured.
    """
    logger.info(f"[EMAIL] Preparing to send email to: {to}, subject: {subject[:50]}...")

    service: SparqMailService | EmailService | GatewayEmailService
    config = EmailConfig.from_env_and_settings()
    if config:
        # A real provider is configured — prefer it over the gateway.
        if config.provider == "sparqmail":
            logger.info(f"[EMAIL] Using sparQ Mail API, from: {config.from_email}")
            service = SparqMailService(config)
        else:
            logger.info(f"[EMAIL] Config loaded - host: {config.host}, from: {config.from_email}")
            service = EmailService(config)
    else:
        # No provider configured — fall back to the email gateway if available.
        gateway = _gateway_config()
        if not gateway:
            logger.warning("[EMAIL] Email not configured - skipping send")
            return False
        logger.info("[EMAIL] No provider configured - using email gateway")
        service = GatewayEmailService(*gateway)

    result = service.send(to, subject, html_body, text_body, attachments)

    if result:
        logger.info(f"[EMAIL] Successfully sent email to {to}")
    else:
        logger.error(f"[EMAIL] Failed to send email to {to}")

    return result


def is_configured() -> bool:
    """Check if email can be sent.

    True when either a real provider (SMTP / sparQ Mail) is configured or the
    email gateway is available as a fallback.
    """
    if EmailConfig.from_env_and_settings() is not None:
        return True
    return _gateway_config() is not None


def send_email_async(
    to: str,
    subject: str,
    html_body: str,
    text_body: str | None = None,
    attachments: list[dict] | None = None,
) -> None:
    """
    Send an email asynchronously (fire-and-forget).

    The email is queued for background delivery and the function returns
    immediately. Any failures are logged but not raised.

    Args:
        to: Recipient email address
        subject: Email subject
        html_body: HTML content
        text_body: Plain text content (optional)
        attachments: List of attachment dicts with keys:
            - filename: Name of the file
            - content: Base64-encoded file content
            - content_type: MIME type (e.g., "application/pdf")
    """
    from system.background import submit_task

    submit_task(send_email, to, subject, html_body, text_body, attachments)


def send_gateway_email(to: str, subject: str, html_body: str) -> bool:
    """Send a bootstrap email (signup confirmation, admin/error notices).

    Retained for existing call sites. Delegates to send_email(), which prefers
    a configured provider (SMTP / sparQ Mail) and transparently falls back to
    the email gateway when none is configured — so these emails still send on a
    fresh install that only has the gateway available.

    Args:
        to: Recipient email address.
        subject: Email subject.
        html_body: HTML content.

    Returns:
        True if sent successfully, False otherwise.
    """
    return send_email(to, subject, html_body)


def test_connection() -> tuple[bool, str]:
    """
    Test the SMTP connection without sending an email.

    Returns:
        Tuple of (success: bool, message: str)
    """
    config = EmailConfig.from_env_and_settings()
    if not config:
        return False, "Email not configured. Please complete the email settings."

    # sparQ Mail - verify config exists (API key and site_id)
    if config.provider == "sparqmail":
        if config.api_key and config.site_id:
            return True, "sparQ Mail is configured"
        return False, "sparQ Mail API key or site ID missing"

    # SMTP providers - test actual connection
    try:
        with smtplib.SMTP(config.host, config.port, timeout=10) as server:
            if config.use_tls:
                server.starttls()
            server.login(config.username, config.password)
            return True, "Connection successful!"
    except smtplib.SMTPAuthenticationError:
        return False, "Authentication failed. Check username and password."
    except smtplib.SMTPConnectError:
        return False, f"Could not connect to {config.host}:{config.port}"
    except TimeoutError:
        return False, f"Connection to {config.host}:{config.port} timed out"
    except Exception as e:
        return False, f"Connection failed: {str(e)}"
