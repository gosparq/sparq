# -----------------------------------------------------------------------------
# sparQ — Presence API Routes
#
# Mobile-first endpoints: clock in/out (primary field action), read-only views
# for entries and timesheets, PTO balance and requests. No entry editing.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from datetime import date

from flask import Blueprint, g, jsonify, request

from system.api.decorators import jwt_required
from system.api.errors import api_error_response, validate_required
from system.api.pagination import paginated_response
from system.middleware.ratelimit import rate_limit

presence_bp = Blueprint("api_presence", __name__, url_prefix="/presence")


def _get_employee_id() -> int | None:
    """Resolve the current JWT user to their Employee record ID."""
    from modules.base.core.models.workspace_user import WorkspaceUser

    emp = WorkspaceUser.scoped().filter_by(user_id=g.current_user.id).first()
    return emp.id if emp else None


@presence_bp.route("/status", methods=["GET"])
@jwt_required
@rate_limit(limit=120, window=60)
def get_clock_status():
    """Current clock status for the user."""
    from modules.base.presence.models.clock_punch import ClockPunch

    emp_id = _get_employee_id()
    if not emp_id:
        return api_error_response("NOT_FOUND", "No employee profile found", 404)

    status = ClockPunch.get_current_status(emp_id)
    return jsonify({
        "is_clocked_in": status["is_clocked_in"],
        "clock_in_time": status["clock_in_time"].isoformat() if status.get("clock_in_time") else None,
        "elapsed_str": status.get("elapsed_str", ""),
        "outside_geofence": status.get("outside_geofence", False),
    }), 200


@presence_bp.route("/clock", methods=["POST"])
@jwt_required
@rate_limit(limit=60, window=60)
def clock_in_out():
    """Clock in or out. Auto-detects based on current state.

    Optional body: {"location": {"lat": float, "lng": float}}
    """
    from modules.base.presence.models.clock_punch import ClockPunch

    emp_id = _get_employee_id()
    if not emp_id:
        return api_error_response("NOT_FOUND", "No employee profile found", 404)

    data = request.get_json(silent=True) or {}
    location = data.get("location", {})
    lat = location.get("lat")
    lng = location.get("lng")

    is_clocked_in = ClockPunch.is_clocked_in(emp_id)

    if is_clocked_in:
        punch = ClockPunch.clock_out(
            member_id=emp_id,
            source="mobile",
            latitude=lat,
            longitude=lng,
        )
        action = "clock_out"
    else:
        punch = ClockPunch.clock_in(
            member_id=emp_id,
            source="mobile",
            latitude=lat,
            longitude=lng,
        )
        action = "clock_in"

    return jsonify({
        "action": action,
        "punch": punch.to_dict(),
    }), 201


@presence_bp.route("/entries", methods=["GET"])
@jwt_required
@rate_limit(limit=120, window=60)
def list_entries():
    """Paginated time entries for the current user."""
    from modules.base.presence.models.time_entry import TimeEntry

    emp_id = _get_employee_id()
    if not emp_id:
        return api_error_response("NOT_FOUND", "No employee profile found", 404)

    query = TimeEntry.get_for_user(emp_id)
    return paginated_response(query)


@presence_bp.route("/entries/<int:entry_id>", methods=["GET"])
@jwt_required
@rate_limit(limit=120, window=60)
def get_entry(entry_id):
    """Time entry detail."""
    from modules.base.presence.models.time_entry import TimeEntry

    entry = TimeEntry.scoped().filter_by(id=entry_id).first()
    emp_id = _get_employee_id()
    if not entry or entry.member_id != emp_id:
        return api_error_response("NOT_FOUND", "Time entry not found", 404)

    return jsonify(entry.to_dict()), 200


@presence_bp.route("/timesheets", methods=["GET"])
@jwt_required
@rate_limit(limit=120, window=60)
def list_timesheets():
    """List timesheet summaries (grouped by week) for the current user.

    Timesheets are a grouped view of TimeEntries by week period.
    """
    from modules.base.presence.models.time_entry import TimeEntry
    from system.utils.calendar_utils import get_week_start

    emp_id = _get_employee_id()
    if not emp_id:
        return api_error_response("NOT_FOUND", "No employee profile found", 404)

    entries = TimeEntry.get_by_member(emp_id)

    # Group entries by week start date
    weeks = {}
    for entry in entries:
        week_start = get_week_start(entry.date)
        week_key = week_start.isoformat()
        if week_key not in weeks:
            weeks[week_key] = {
                "week_start": week_key,
                "total_hours": 0,
                "entry_count": 0,
                "statuses": set(),
            }
        weeks[week_key]["total_hours"] += float(entry.hours or 0)
        weeks[week_key]["entry_count"] += 1
        if entry.status:
            weeks[week_key]["statuses"].add(entry.status.value)

    # Convert sets to lists for JSON serialization
    result = []
    for week in sorted(weeks.values(), key=lambda w: w["week_start"], reverse=True):
        week["statuses"] = list(week["statuses"])
        week["total_hours"] = round(week["total_hours"], 2)
        result.append(week)

    return jsonify({"timesheets": result}), 200


@presence_bp.route("/timesheets/<week_start>", methods=["GET"])
@jwt_required
@rate_limit(limit=120, window=60)
def get_timesheet(week_start):
    """Timesheet detail: all entries for a specific week."""
    from datetime import timedelta

    from modules.base.presence.models.time_entry import TimeEntry

    try:
        start = date.fromisoformat(week_start)
    except ValueError:
        return api_error_response("VALIDATION_ERROR", "Invalid date format. Use YYYY-MM-DD", 400)

    emp_id = _get_employee_id()
    if not emp_id:
        return api_error_response("NOT_FOUND", "No employee profile found", 404)

    end = start + timedelta(days=6)
    entries = TimeEntry.get_by_member(emp_id, start_date=start, end_date=end)

    total_hours = sum(float(e.hours or 0) for e in entries)

    return jsonify({
        "week_start": start.isoformat(),
        "week_end": end.isoformat(),
        "total_hours": round(total_hours, 2),
        "entries": [e.to_dict() for e in entries],
    }), 200


@presence_bp.route("/timesheets/<week_start>/submit", methods=["POST"])
@jwt_required
@rate_limit(limit=60, window=60)
def submit_timesheet(week_start):
    """Submit a week's timesheet entries for approval."""
    from datetime import timedelta

    from modules.base.presence.models.time_entry import TimeEntry, TimeEntryStatus

    try:
        start = date.fromisoformat(week_start)
    except ValueError:
        return api_error_response("VALIDATION_ERROR", "Invalid date format. Use YYYY-MM-DD", 400)

    emp_id = _get_employee_id()
    if not emp_id:
        return api_error_response("NOT_FOUND", "No employee profile found", 404)

    end = start + timedelta(days=6)
    entries = TimeEntry.get_by_member(emp_id, start_date=start, end_date=end)

    submitted = 0
    for entry in entries:
        if entry.status == TimeEntryStatus.SUBMITTED:
            # Already submitted
            continue
        if entry.status in (TimeEntryStatus.APPROVED, TimeEntryStatus.INVOICED):
            continue
        entry.status = TimeEntryStatus.SUBMITTED
        submitted += 1

    from system.db.database import db
    db.session.commit()

    return jsonify({"submitted_count": submitted}), 200


@presence_bp.route("/pto", methods=["GET"])
@jwt_required
@rate_limit(limit=120, window=60)
def get_pto():
    """PTO balance and leave requests for the current user."""
    from modules.base.presence.models.leave_request import LeaveRequest

    emp_id = _get_employee_id()
    if not emp_id:
        return api_error_response("NOT_FOUND", "No employee profile found", 404)

    requests_list = LeaveRequest.get_by_member(emp_id)
    upcoming = LeaveRequest.get_upcoming_approved()

    return jsonify({
        "requests": [r.to_dict() for r in requests_list],
        "upcoming": [r.to_dict() for r in upcoming],
    }), 200


@presence_bp.route("/pto/request", methods=["POST"])
@jwt_required
@rate_limit(limit=60, window=60)
def create_pto_request():
    """Submit a new PTO request."""
    from modules.base.presence.models.leave_request import LeaveRequest, LeaveType

    data = request.get_json(silent=True)
    errors = validate_required(data, ["start_date", "end_date", "type"])
    if errors:
        return api_error_response("VALIDATION_ERROR", "Missing required fields", 400, errors)

    # Validate leave type
    try:
        leave_type = LeaveType(data["type"])
    except ValueError:
        valid_types = [lt.value for lt in LeaveType]
        return api_error_response("VALIDATION_ERROR", f"Invalid leave type. Must be one of: {valid_types}", 400)

    # Parse dates
    try:
        start_date = date.fromisoformat(data["start_date"])
        end_date = date.fromisoformat(data["end_date"])
    except ValueError:
        return api_error_response("VALIDATION_ERROR", "Invalid date format. Use YYYY-MM-DD", 400)

    if end_date < start_date:
        return api_error_response("VALIDATION_ERROR", "End date must be on or after start date", 400)

    # Check for overlapping requests
    emp_id = _get_employee_id()
    if not emp_id:
        return api_error_response("NOT_FOUND", "No employee profile found", 404)

    overlapping = LeaveRequest.find_overlapping(emp_id, start_date, end_date)
    if overlapping:
        return api_error_response("CONFLICT", "Overlapping leave request exists", 409)

    leave = LeaveRequest.create(
        member_id=emp_id,
        leave_type=leave_type,
        start_date=start_date,
        end_date=end_date,
        employee_notes=data.get("notes", ""),
    )
    leave.submit()

    return jsonify(leave.to_dict()), 201
