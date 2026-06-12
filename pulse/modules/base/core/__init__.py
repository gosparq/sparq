# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Core module initialization and route registration. Sets up the core
#     functionality including authentication, user management, and system
#     settings blueprints.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

"""Core module providing authentication, user management, and system settings.

This is the foundational module that all sparQ applications depend on.
It provides user authentication, group-based permissions, workspace settings,
and contact management.

Key Models:
    User: Core user model with authentication methods (password, OAuth, magic link, SMS).
    WorkspaceSettings: Singleton for workspace-wide configuration.
    Contact: Customer/vendor contact information.
    ServiceLocation: Organization service locations.

Example:
    Importing core models in your app::

        from modules.base.core.models.user import User
        from modules.base.core.models.workspace_settings import WorkspaceSettings

        # Get current workspace settings
        settings = WorkspaceSettings.get_instance()

        # Query users
        admins = WorkspaceUser.scoped().filter_by(role="admin").all()
"""

from .module import CoreModule

# Import all core models to ensure they're registered with SQLAlchemy
# This is required even if not directly used, as disabled modules may reference them
# Workspace must be imported first — all other models FK to workspace.id
from .models.workspace import Workspace  # noqa: F401
from .models.organization import Organization
from .models.user import User
from .models.organization_user import OrganizationUser
from .models.workspace_user import WorkspaceUser  # noqa: F401
from .models.audit_log import AuditLog
from .models.workspace_settings import WorkspaceSettings
from .models.contact import Contact
from .models.service_location import ServiceLocation
from .models.user_setting import UserSetting
from .models.notification import SystemNotification
from .models.oauth_connection import OAuthConnection
from .models.auth_settings import AuthSettings
from .models.push_subscription import PushSubscription
from .models.pending_signup import PendingSignup
from .models.organization_invitation import OrganizationInvitation

# Create module instance
# Routes are registered via the get_routes() hook in module.py
module_instance = CoreModule()

__all__ = [
    "module_instance",
    "AuditLog",
    "Organization",
    "OrganizationUser",
    "User",
    "Group",
    "WorkspaceSettings",
    "Contact",
    "ServiceLocation",
    "UserSetting",
    "SystemNotification",
    "OAuthConnection",
    "AuthSettings",
    "PushSubscription",
    "PendingSignup",
    "OrganizationInvitation",
]
