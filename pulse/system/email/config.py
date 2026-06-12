# -----------------------------------------------------------------------------
# sparQ - Email Configuration
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""Email configuration and provider presets.

This module provides email provider configuration with presets for
common email services like Gmail, Microsoft 365, SendGrid, and AWS SES.

Classes:
    EmailProvider: Enum of supported email providers.
    EmailConfig: Configuration dataclass for email settings.

Attributes:
    PROVIDER_PRESETS: Dictionary mapping providers to their SMTP settings.

Example:
    Load configuration from environment and database settings::

        from system.email.config import EmailConfig

        config = EmailConfig.from_env_and_settings()
        if config:
            print(f"Using {config.provider} via {config.host}")

    Check available presets::

        from system.email.config import PROVIDER_PRESETS, EmailProvider

        gmail_preset = PROVIDER_PRESETS[EmailProvider.GMAIL]
        print(f"Gmail SMTP: {gmail_preset['host']}:{gmail_preset['port']}")
"""

from dataclasses import dataclass
from enum import Enum
import os


class EmailProvider(str, Enum):
    """Supported email providers."""

    SPARQMAIL = "sparqmail"
    GMAIL = "gmail"
    MICROSOFT_365 = "microsoft_365"
    SENDGRID = "sendgrid"
    MAILGUN = "mailgun"
    AWS_SES = "aws_ses"
    CUSTOM = "custom"


# Provider presets with default SMTP settings
PROVIDER_PRESETS = {
    EmailProvider.GMAIL: {
        "host": "smtp.gmail.com",
        "port": 587,
        "use_tls": True,
        "notes": "Use App Password, not your regular password",
    },
    EmailProvider.MICROSOFT_365: {
        "host": "smtp.office365.com",
        "port": 587,
        "use_tls": True,
        "notes": "Use your Microsoft 365 email and password",
    },
    EmailProvider.SENDGRID: {
        "host": "smtp.sendgrid.net",
        "port": 587,
        "use_tls": True,
        "notes": "Username is 'apikey', password is your API key",
    },
    EmailProvider.MAILGUN: {
        "host": "smtp.mailgun.org",
        "port": 587,
        "use_tls": True,
        "notes": "Use SMTP credentials from Mailgun dashboard",
    },
    EmailProvider.AWS_SES: {
        "host": "email-smtp.us-east-1.amazonaws.com",
        "port": 587,
        "use_tls": True,
        "notes": "Use IAM SMTP credentials, update region in host",
    },
    EmailProvider.CUSTOM: {
        "host": "",
        "port": 587,
        "use_tls": True,
        "notes": "Enter your SMTP server details",
    },
}


@dataclass
class EmailConfig:
    """Email configuration."""

    provider: str
    host: str
    port: int
    username: str
    password: str
    from_email: str
    from_name: str
    use_tls: bool = True
    api_key: str | None = None  # For API providers like sparQ Mail
    site_id: str | None = None  # For sparQ Mail identification

    @classmethod
    def from_env_and_settings(cls) -> "EmailConfig | None":
        """
        Build config from environment variables (priority) + DB settings.
        Returns None if no email provider is configured.

        sparQ Mail: env vars SPARQMAIL_API_KEY / SPARQMAIL_FROM_EMAIL,
        falling back to per-workspace DB settings.
        SMTP: env vars SMTP_HOST / SMTP_PASSWORD, falling back to DB.
        """
        # Check for sparQ Mail first (API-based, no SMTP)
        sparqmail_key = os.environ.get("SPARQMAIL_API_KEY")
        if sparqmail_key:
            return cls(
                provider="sparqmail",
                host="",
                port=0,
                username="",
                password="",
                from_email=os.environ.get("SPARQMAIL_FROM_EMAIL") or "",
                from_name=os.environ.get("SPARQMAIL_FROM_NAME") or "sparQ",
                use_tls=False,
                api_key=sparqmail_key,
                site_id=os.environ.get("SPARQMAIL_SITE_ID"),
            )

        # Try InstanceSettings first (server-wide, no tenant context needed)
        try:
            from modules.base.msa.models.instance_settings import InstanceSettings

            instance = InstanceSettings.query.first()
            if instance and (instance.email_password or os.environ.get("SMTP_PASSWORD")):
                password = os.environ.get("SMTP_PASSWORD") or instance.get_email_password()
                host = os.environ.get("SMTP_HOST") or instance.email_host
                if host and password:
                    return cls(
                        provider=os.environ.get("SMTP_PROVIDER") or instance.email_provider or "custom",
                        host=host,
                        port=int(os.environ.get("SMTP_PORT", 0)) or instance.email_port or 587,
                        username=os.environ.get("SMTP_USERNAME") or instance.email_username or "",
                        password=password,
                        from_email=os.environ.get("SMTP_FROM_EMAIL") or instance.email_from or "",
                        from_name=os.environ.get("SMTP_FROM_NAME") or "sparQ",
                        use_tls=instance.email_use_tls if instance.email_use_tls is not None else True,
                    )
        except Exception:
            pass

        # Fall back to per-workspace WorkspaceSettings
        try:
            from modules.base.core.models.workspace_settings import WorkspaceSettings

            settings = WorkspaceSettings.get_instance()

            password = os.environ.get("SMTP_PASSWORD") or getattr(settings, "email_password", None)
            if not password:
                return None

            host = os.environ.get("SMTP_HOST") or getattr(settings, "email_host", None)
            if not host:
                return None

            return cls(
                provider=os.environ.get("SMTP_PROVIDER") or getattr(settings, "email_provider", None) or "custom",
                host=host,
                port=int(os.environ.get("SMTP_PORT", 0)) or getattr(settings, "email_port", None) or 587,
                username=os.environ.get("SMTP_USERNAME") or getattr(settings, "email_username", None) or "",
                password=password,
                from_email=os.environ.get("SMTP_FROM_EMAIL") or getattr(settings, "email_from", None) or "",
                from_name=os.environ.get("SMTP_FROM_NAME") or getattr(settings, "company_name", None) or "sparQ",
                use_tls=True,
            )
        except Exception:
            pass

        return None
