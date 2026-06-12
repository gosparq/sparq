# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

from system.module.hooks import hookimpl

from .controllers import blueprint
from .controllers.updates import updates_bp
from .controllers.webhook_api import webhook_api_bp


class UpdatesModule:
    """Updates module — status updates, channels, chat, and calendar."""

    def __init__(self) -> None:
        self.blueprint = blueprint

    def get_routes(self):
        """Return routes for this module."""
        return [
            (self.blueprint, "/sync"),
            (updates_bp, "/updates"),
            (webhook_api_bp, ""),
        ]

    @hookimpl
    def init_database(self) -> None:
        """Initialize database tables for this module."""
        from system.db.database import db

        # Import models to register them with SQLAlchemy
        from .models import UpdateChannel, UpdateChannelReadState, Event, UpdateWebhook  # noqa: F401
        from .models.template import UpdateTemplate  # noqa: F401
        from .models.nudge_log import UpdateNudgeLog  # noqa: F401

        # Create default channels
        UpdateChannel.create_default_channels()

        # Seed built-in post templates (idempotent)
        try:
            UpdateTemplate.seed_builtin_templates()
            UpdateTemplate.seed_board_templates()
        except Exception:
            db.session.rollback()

        # Seed US federal holidays for current year + 5 years out (idempotent)
        try:
            from datetime import date

            from system.utils.holidays import get_us_federal_holidays

            current_year = date.today().year
            holidays = []
            for year in range(current_year, current_year + 6):
                holidays.extend(get_us_federal_holidays(year))
            Event.populate_holidays(holidays)
        except Exception:
            db.session.rollback()

        # Initialize read state for existing members who don't have it
        try:
            from modules.base.core.models.workspace_user import WorkspaceUser
            for member in WorkspaceUser.scoped().all():
                existing = UpdateChannelReadState.scoped().filter_by(member_id=member.id).first()
                if not existing:
                    UpdateChannelReadState.initialize_member_read_state(member.id)
        except Exception:
            db.session.rollback()

    @hookimpl
    def process_new_employee(self, form_data, employee) -> None:
        """Initialize chat read state for new members."""
        from .models.channel_read_state import UpdateChannelReadState

        UpdateChannelReadState.initialize_user_read_state(employee.user_id)
