# -----------------------------------------------------------------------------
# sparQ - Email Setup Utilities
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# Email Settings Setup
#
# Seeds email settings from environment variables to database.
# -----------------------------------------------------------------------------

import logging
import os


def seed_email_settings_from_env() -> None:
    """Seed email settings from .env to database if not already set.

    This runs once on startup to populate WorkspaceSettings with Gmail SMTP
    configuration from environment variables. Only seeds if DB values are empty.
    """
    from modules.base.core.models.workspace_settings import WorkspaceSettings

    settings = WorkspaceSettings.get_instance()

    # Only seed if DB values are empty
    updates: dict[str, str | int] = {}

    if not settings.email_password and os.environ.get("SMTP_PASSWORD"):
        updates["email_password"] = os.environ.get("SMTP_PASSWORD")

    if not settings.email_from and os.environ.get("SMTP_FROM_EMAIL"):
        updates["email_from"] = os.environ.get("SMTP_FROM_EMAIL")

    if not settings.email_username and os.environ.get("SMTP_USERNAME"):
        updates["email_username"] = os.environ.get("SMTP_USERNAME")

    # Set Gmail defaults if seeding any values
    if updates:
        updates.setdefault("email_provider", "gmail")
        updates.setdefault("email_host", "smtp.gmail.com")
        updates.setdefault("email_port", 587)
        settings.update(**updates)
        logging.getLogger(__name__).info("Seeded email settings from .env file")
