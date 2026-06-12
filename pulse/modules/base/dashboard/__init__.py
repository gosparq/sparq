# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Dashboard module initialization and route registration.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

"""Dashboard module providing the main application launchpad and activity feed.

This module displays the main dashboard with quick access to all apps,
recent activity, and system notifications.

Key Models:
    ActivityLog: Records user actions for activity feed display.

Key Features:
    - App launchpad with icons and quick access
    - Recent activity feed
    - System notifications display
    - Customizable dashboard widgets

Routes:
    /dashboard - Main dashboard view
    /dashboard/activity - Activity feed
"""

from .module import DashboardModule

# Import all models to ensure they're registered with SQLAlchemy
# This is required even if the module is disabled, as other modules may reference them
from .models.activity_log import ActivityLog  # noqa: F401

# Create module instance
# Routes are registered via the get_routes() hook in module.py
module_instance = DashboardModule()
