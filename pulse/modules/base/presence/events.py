# -----------------------------------------------------------------------------
# sparQ - Time Tracking Module Event Registrations
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""Event registrations for Time Tracking module models.

This file registers notification configurations for LeaveRequest
and PunchCorrectionRequest lifecycle events. Handlers in core module
process these registrations.
"""

from system.events import notifications
from system.i18n.translation import translate as _

# =============================================================================
# LeaveRequest Event Registrations
# =============================================================================

# Notification: Admin alert when PTO request is submitted
notifications.register(
    "LeaveRequest", "submitted",
    title=lambda r: _("PTO Request Submitted"),
    message=lambda r: (
        f"{r.member.user.first_name} {r.member.user.last_name} "
        + _("requested %(leave_type)s (%(start)s - %(end)s)") % {
            "leave_type": r.leave_type.value,
            "start": r.start_date.strftime("%b %d"),
            "end": r.end_date.strftime("%b %d"),
        }
    ),
    target="admin",
    icon="fa-umbrella-beach",
    url=lambda r: "/presence/pto/approve",
    category="system",
)

# =============================================================================
# PunchCorrectionRequest Event Registrations
# =============================================================================

# Notification: Admin alert when punch correction is requested
notifications.register(
    "PunchCorrectionRequest", "created",
    title=lambda r: _("Punch Change Requested"),
    message=lambda r: (
        f"{r.member.user.first_name} {r.member.user.last_name} "
        + _("requested a punch correction")
    ),
    target="admin",
    icon="fa-clock",
    url=lambda r: "/presence/timesheets/approve",
    category="system",
)
