# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Dev seed script. Loads demo data and bypasses setup wizard so
#     developers land on the dashboard immediately after make reset.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

#!/usr/bin/env python
"""
Dev Seed Script for sparQ

This script:
1. Loads full demo data (Demo Company)
2. Marks setup_completed=True (bypasses setup wizard)
3. Sets timezone to America/Chicago

Usage:
    python system/db/seed_minimal.py
    # or
    make seed
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def seed_dev():
    """Load demo data and bypass setup wizard."""
    print("=" * 50)
    print("sparQ Dev Seed")
    print("=" * 50)

    from app import create_app

    print("\n[1/3] Creating Flask application...")
    app = create_app()

    print("[2/3] Loading sample data...")
    from system.db.seed_sample import seed_sample_data
    with app.app_context():
        from modules.base.core.models.workspace_user import WorkspaceUser
        membership = WorkspaceUser.query.first()
        if membership:
            seed_sample_data(membership.workspace_id, membership.user_id, membership.id)

    print("[3/3] Marking setup complete...")
    with app.app_context():
        from modules.base.core.models.workspace_settings import WorkspaceSettings
        settings = WorkspaceSettings.get_instance()
        if not settings.setup_completed:
            settings.complete_setup(timezone="America/Chicago")

    print("\n" + "=" * 50)
    print("Dev seed complete!")
    print("Log in with demo credentials to reach the dashboard.")
    print("=" * 50)


if __name__ == "__main__":
    seed_dev()
