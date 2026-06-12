# -----------------------------------------------------------------------------
# sparQ - Presence Module
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""Presence module for member hours and leave management.

This module provides time entry, timesheet management,
and leave/PTO request handling.

Key Models:
    TimeEntry: Individual time entries with project/job linking.
    LeaveRequest: PTO and leave requests with approval workflow.

Key Features:
    - Clock in/out functionality
    - Manual time entry
    - Timesheet submission and approval
    - Leave request submission
    - Manager approval workflows
    - Job/project time allocation
    - Overtime tracking

Routes:
    /presence - Presence dashboard
    /presence/timesheets - Timesheet management
    /presence/leave - Leave requests
"""

from .module import PresenceModule

# Import all models to ensure they're registered with SQLAlchemy
# This is required even if the module is disabled, as other modules may reference them
from .models.clock_punch import ClockPunch, PunchType
from .models.clock_punch_adjustment import ClockPunchAdjustment
from .models.leave_request import LeaveRequest
from .models.punch_correction_request import PunchCorrectionRequest, PunchCorrectionRequestStatus
from .models.settings import TimeTrackingSettings
from .models.time_entry import TimeEntry, TimeEntryStatus

from . import events  # noqa: F401

module_instance = PresenceModule()

__all__ = [
    "module_instance",
    "ClockPunch",
    "ClockPunchAdjustment",
    "LeaveRequest",
    "PunchCorrectionRequest",
    "PunchCorrectionRequestStatus",
    "PunchType",
    "TimeEntry",
    "TimeEntryStatus",
    "TimeTrackingSettings",
]
