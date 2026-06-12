# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Synthetic user for MSA transparent mode. Provides a Flask-Login compatible
#     user object that is not backed by a real database record, preserving
#     privacy by ensuring no real user's data (DMs, settings) is visible.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

"""Synthetic MSA observer user for transparent login mode.

When an MSA enters a workspace in transparent mode, Flask-Login's
request_loader returns an MsaTransparentUser instead of a real User.
This object satisfies all template and route expectations (is_authenticated,
is_admin, workspace_membership, etc.) while having id=0 so that
user-scoped queries (DMs, personal settings, notifications) return empty.
"""

from __future__ import annotations

import uuid

from flask import session


class MsaTransparentMembership:
    """Stub workspace membership for MSA transparent mode.

    Prevents AttributeError in templates that access
    current_user.workspace_membership.id or .role.
    """

    id: int = 0
    role: str = "admin"
    has_active_onboarding: bool = False
    is_field_worker: bool = False
    status: None = None

    def has_permission(self, area: str) -> bool:
        """MSA observer can view all permission areas."""
        return True


class MsaTransparentUser:
    """Synthetic Flask-Login user for MSA transparent mode.

    Satisfies the Flask-Login user interface and all template/route
    expectations without being backed by a real database record.
    Uses id=0 as a safe sentinel (real user IDs start at 1).
    """

    # Flask-Login required interface
    is_authenticated: bool = True
    is_active: bool = True
    is_anonymous: bool = False
    id: int = 0

    # Display attributes used in templates
    first_name: str = "MSA"
    last_name: str = "Observer"
    email: str = "msa@system"
    avatar_color: str = "#4A7EC0"
    is_admin: bool = True
    is_online: bool = False
    presence_status: str = "offline"
    is_sample: bool = False
    needs_password_setup: bool = False

    @property
    def full_name(self) -> str:
        """Display name shown in nav dropdown."""
        return "MSA Observer"

    @property
    def workspace_membership(self) -> MsaTransparentMembership:
        """Return stub membership to prevent template AttributeError."""
        return MsaTransparentMembership()

    @property
    def workspace_id(self) -> uuid.UUID | None:
        """Return active workspace ID from session (legacy fallback support)."""
        active_ws = session.get("active_workspace_id")
        if active_ws:
            try:
                return uuid.UUID(active_ws)
            except ValueError:
                return None
        return None

    def get_id(self) -> str:
        """Flask-Login calls this to store user ID in session.

        Returns a non-numeric sentinel so user_loader won't find it.
        """
        return "msa-transparent"

    def has_access(self, area: str) -> bool:
        """MSA observer can view all permission areas."""
        return True

    def update_last_seen(self) -> None:
        """No-op — SocketIO calls this on connect."""
        pass
