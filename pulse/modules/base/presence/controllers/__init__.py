# -----------------------------------------------------------------------------
# sparQ - Presence Controllers
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from typing import Any

from flask_login import current_user

from ..models.settings import TimeTrackingSettings


def presence_context() -> dict[str, Any]:
    """Shared context processor for all presence blueprints.

    Injects time tracking settings, board visibility, and admin-only
    pending counts into templates. Returns safe defaults when no
    workspace context exists (e.g., public invite pages).
    """
    from flask import g

    if not getattr(g, "workspace_id", None):
        return {
            "time_clock_enabled": False,
            "board_visible": False,
        }

    settings = TimeTrackingSettings.get()
    ctx: dict[str, Any] = {
        "time_clock_enabled": settings.time_clock_enabled,
        "board_visible": TimeTrackingSettings.is_board_visible_to_user(current_user) if current_user.is_authenticated else False,
    }
    if current_user.is_authenticated and current_user.is_admin:
        ctx["public_board_token"] = TimeTrackingSettings.get_or_create_public_token()
        from ..models.leave_request import LeaveRequest
        from ..models.punch_correction_request import PunchCorrectionRequest
        ctx["pending_pto_count"] = LeaveRequest.pending_count()
        ctx["pending_approval_count"] = PunchCorrectionRequest.pending_count()
    return ctx
