# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Bypass setup wizards for development. Marks setup_completed and
#     configures timezone so developers land on the dashboard immediately.
#     Does NOT load demo data.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def dev_setup():
    """Mark setup complete for development."""
    from app import create_app

    app = create_app()

    with app.app_context():
        import uuid
        from flask import g
        from modules.base.core.models.workspace_settings import WorkspaceSettings
        g.workspace_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        g.organization_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        settings = WorkspaceSettings.get_instance()
        if not settings.setup_completed:
            settings.complete_setup(timezone="America/Chicago")


if __name__ == "__main__":
    dev_setup()
