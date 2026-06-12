# -----------------------------------------------------------------------------
# sparQ - Finance Module
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

import logging

from system.module.hooks import hookimpl

logger = logging.getLogger(__name__)


class FinanceModule:
    def get_routes(self):
        from .controllers.routes import blueprint

        return [(blueprint, "/finance")]

    @hookimpl
    def init_database(self) -> None:
        """Initialize database with default chart of accounts."""
        from .models.accounting import AccountingAccount

        try:
            AccountingAccount.seed_defaults()
            logger.info("Chart of accounts initialized")
        except Exception as e:
            logger.error(f"Error seeding chart of accounts: {e}")
