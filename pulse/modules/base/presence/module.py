# -----------------------------------------------------------------------------
# sparQ - Presence Module
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from system.module.hooks import hookimpl


class PresenceModule:
    def get_routes(self):
        from .controllers.board import blueprint as board_blueprint
        from .controllers.clock import blueprint as clock_blueprint
        from .controllers.flow import blueprint as flow_blueprint
        from .controllers.kiosk import blueprint as kiosk_blueprint
        from .controllers.pto import blueprint as pto_blueprint
        from .controllers.routes import blueprint as timesheets_blueprint

        return [
            (timesheets_blueprint, "/presence/timesheets"),
            (clock_blueprint, "/presence/clock"),
            (board_blueprint, "/presence/board"),
            (kiosk_blueprint, "/presence/kiosk"),
            (pto_blueprint, "/presence/pto"),
            (flow_blueprint, "/presence/flow"),
        ]

    @hookimpl
    def init_database(self) -> None:
        # Schema creation is handled centrally by app.py
        pass
