# -----------------------------------------------------------------------------
# sparQ - Sync Module Calendar Routes
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

from flask import flash, jsonify, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user, login_required

if TYPE_CHECKING:
    from modules.base.tasks.models.task import Task
    from modules.base.presence.models.leave_request import LeaveRequest

from system.device import is_mobile
from system.device.template import render_device_template
from system.i18n.translation import translate as _
from system.utils.calendar_utils import (
    assign_spanning_lanes,
    compute_spanning_segments,
    get_week_start,
)

from ..models import Event
from . import blueprint


def is_htmx_request() -> bool:
    """Check if request is from HTMX."""
    return request.headers.get("HX-Request") == "true"


def require_admin() -> bool:
    """Check if current user is admin. Flash error and return False if not."""
    if not current_user.is_admin:
        flash(_("You don't have permission to perform this action."), "error")
        return False
    return True


# --- Main Calendar View ---


@blueprint.route("/calendar/")
@login_required
def calendar_index() -> ResponseReturnValue:
    """Main calendar view."""
    view = request.args.get("view", "month")

    date_str = request.args.get("date")
    if date_str:
        try:
            current_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            current_date = date.today()
    else:
        current_date = date.today()

    # Calculate date range and navigation dates based on view
    if view == "day":
        start_date = current_date
        end_date = current_date
        prev_date = current_date - timedelta(days=1)
        next_date = current_date + timedelta(days=1)
    elif view == "week":
        start_date = get_week_start(current_date)
        end_date = start_date + timedelta(days=6)
        prev_date = current_date - timedelta(days=7)
        next_date = current_date + timedelta(days=7)
    else:  # month
        start_date = current_date.replace(day=1)
        if current_date.month == 12:
            end_date = current_date.replace(year=current_date.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_date = current_date.replace(month=current_date.month + 1, day=1) - timedelta(days=1)
        prev_date = (current_date.replace(day=1) - timedelta(days=1)).replace(day=1)
        next_date = (current_date.replace(day=28) + timedelta(days=4)).replace(day=1)

    # Compute full grid date range (covers leading/trailing days in month view)
    if view == "month":
        cal_start = get_week_start(start_date)
        cal_end = cal_start + timedelta(days=41)  # 6 weeks × 7 days - 1
    else:
        cal_start = start_date
        cal_end = end_date

    # Fetch events (expanded to full grid range)
    events = Event.get_for_date_range(cal_start, cal_end)

    # Fetch integrated data sources
    from modules.base.presence.models.leave_request import LeaveRequest
    leave_requests = LeaveRequest.get_approved_in_range(cal_start, cal_end)

    from modules.base.tasks.models.task import Task
    tasks = Task.get_with_due_date_in_range(cal_start, cal_end)

    # Build spanning entries list for PTO bars
    spanning_entries = _build_spanning_entries(leave_requests)

    calendar_data = build_calendar_data(
        view, current_date, start_date, end_date, events,
        spanning_entries=spanning_entries,
        tasks=tasks,
        cal_start=cal_start,
    )

    template_ctx = dict(
        view=view,
        current_date=current_date,
        start_date=start_date,
        end_date=end_date,
        prev_date=prev_date,
        next_date=next_date,
        events=events,
        calendar_data=calendar_data,
    )

    if is_htmx_request():
        if is_mobile():
            return render_template(
                "updates/mobile/calendar/index.html",
                active_page="calendar",
                module_home="sync_bp.index",
                **template_ctx,
            )
        else:
            return render_template(
                "updates/desktop/calendar/_calendar_container.html",
                **template_ctx,
            )

    open_event_id = request.args.get("event", type=int)

    return render_device_template(
        "updates/desktop/calendar/index.html",
        active_page="calendar",
        module_home="sync_bp.index",
        open_event_id=open_event_id,
        **template_ctx,
    )


def _build_spanning_entries(leave_requests: list[LeaveRequest]) -> list[dict]:
    """Normalize PTO/leave records into a spanning entry format."""
    entries = []

    for lr in leave_requests:
        member_name = ""
        if lr.member and lr.member.user:
            member_name = lr.member.user.first_name or ""
        label = f"{member_name} — {lr.leave_type.value}" if member_name else lr.leave_type.value
        entries.append({
            "id": lr.id,
            "type": "pto",
            "label": label,
            "url": url_for("pto_bp.detail", request_id=lr.id),
            "start_date": lr.start_date,
            "end_date": lr.end_date,
        })

    return entries


def build_calendar_data(
    view: str, current_date: date, start_date: date, end_date: date,
    events: list[Event], spanning_entries: list[dict] | None = None,
    tasks: list[Task] | None = None, cal_start: date | None = None,
) -> dict:
    """Build calendar data structure for template rendering."""
    spanning_entries = spanning_entries or []
    tasks = tasks or []

    # Create dicts keyed by date
    events_by_date: dict[date, list] = {}
    for event in events:
        if event.scheduled_date not in events_by_date:
            events_by_date[event.scheduled_date] = []
        events_by_date[event.scheduled_date].append({
            "id": event.id,
            "title": event.title,
            "time": event.display_time,
            "is_all_day": event.is_all_day,
            "location": event.location,
            "is_holiday": event.is_holiday,
            "type": "event",
        })

    tasks_by_date: dict[date, list] = {}
    for item in tasks:
        if item.due_date not in tasks_by_date:
            tasks_by_date[item.due_date] = []
        assignee_name = ""
        if item.assignee and item.assignee.user:
            assignee_name = item.assignee.user.first_name or ""
        tasks_by_date[item.due_date].append({
            "id": item.id,
            "title": item.title,
            "assignee": assignee_name,
            "url": url_for("tasks_bp.detail", item_id=item.id),
            "type": "task",
        })

    if view == "month":
        weeks = []
        grid_start = cal_start or get_week_start(start_date)

        for week_idx in range(6):
            week_start = grid_start + timedelta(days=week_idx * 7)
            week_end = week_start + timedelta(days=6)

            week_days = []
            for day_offset in range(7):
                cal_date = week_start + timedelta(days=day_offset)
                week_days.append({
                    "date": cal_date,
                    "day": cal_date.day,
                    "is_current_month": cal_date.month == current_date.month,
                    "is_today": cal_date == date.today(),
                    "events": events_by_date.get(cal_date, []),
                    "tasks": tasks_by_date.get(cal_date, []),
                })

            segments = compute_spanning_segments(spanning_entries, week_start, week_end)
            max_lanes = assign_spanning_lanes(segments)

            weeks.append({
                "days": week_days,
                "spanning_entries": segments,
                "max_spanning_rows": max_lanes,
            })

        return {"weeks": weeks}

    elif view == "week":
        days = []
        for i in range(7):
            cal_date = start_date + timedelta(days=i)
            days.append({
                "date": cal_date,
                "day_name": cal_date.strftime("%a"),
                "day": cal_date.day,
                "is_today": cal_date == date.today(),
                "events": events_by_date.get(cal_date, []),
                "tasks": tasks_by_date.get(cal_date, []),
            })

        segments = compute_spanning_segments(spanning_entries, start_date, end_date)
        assign_spanning_lanes(segments)

        return {
            "days": days,
            "spanning_entries": segments,
        }

    else:  # day
        day_spanning = []
        for entry in spanning_entries:
            if entry["start_date"] <= current_date <= entry["end_date"]:
                day_spanning.append(entry)

        return {
            "date": current_date,
            "events": events_by_date.get(current_date, []),
            "tasks": tasks_by_date.get(current_date, []),
            "spanning_entries": day_spanning,
        }


# --- Event CRUD ---


@blueprint.route("/calendar/event/new", methods=["GET", "POST"])
@login_required
def event_new() -> ResponseReturnValue:
    """Create a new company event."""
    if not require_admin():
        return redirect(url_for("sync_bp.calendar_index"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        scheduled_date_str = request.form.get("scheduled_date", "")
        scheduled_start_time_str = request.form.get("scheduled_start_time", "")
        scheduled_end_time_str = request.form.get("scheduled_end_time", "")
        is_all_day = request.form.get("is_all_day") == "on"
        location = request.form.get("location", "").strip()

        if not title:
            flash(_("Title is required."), "error")
            return redirect(url_for("sync_bp.event_new"))

        if not scheduled_date_str:
            flash(_("Date is required."), "error")
            return redirect(url_for("sync_bp.event_new"))

        try:
            scheduled_date = datetime.strptime(scheduled_date_str, "%Y-%m-%d").date()
        except ValueError:
            flash(_("Invalid date format."), "error")
            return redirect(url_for("sync_bp.event_new"))

        scheduled_start_time = None
        scheduled_end_time = None
        if not is_all_day and scheduled_start_time_str:
            try:
                scheduled_start_time = datetime.strptime(scheduled_start_time_str, "%H:%M").time()
            except ValueError:
                pass
        if not is_all_day and scheduled_end_time_str:
            try:
                scheduled_end_time = datetime.strptime(scheduled_end_time_str, "%H:%M").time()
            except ValueError:
                pass

        if not is_all_day and scheduled_start_time and scheduled_end_time:
            if scheduled_end_time <= scheduled_start_time:
                flash(_("End time must be after start time."), "error")
                return redirect(url_for("sync_bp.event_new", date=scheduled_date_str, view=request.form.get("view", "month")))

        Event.create(
            title=title,
            description=description or None,
            scheduled_date=scheduled_date,
            scheduled_start_time=scheduled_start_time,
            scheduled_end_time=scheduled_end_time,
            is_all_day=is_all_day,
            location=location or None,
        )

        flash(_("Event created successfully."), "success")
        view = request.form.get("view", "month")
        return redirect(url_for("sync_bp.calendar_index", view=view, date=scheduled_date_str))

    prefill_date = request.args.get("date", date.today().strftime("%Y-%m-%d"))
    view = request.args.get("view", "month")

    return render_template(
        "updates/desktop/calendar/_event_form.html",
        event=None,
        prefill_date=prefill_date,
        view=view,
        is_edit=False,
    )


@blueprint.route("/calendar/event/<int:event_id>")
@login_required
def event_detail(event_id: int) -> ResponseReturnValue:
    """Show event detail modal."""
    event = Event.get_by_id(event_id)
    if not event:
        flash(_("Event not found."), "error")
        return redirect(url_for("sync_bp.calendar_index"))

    view = request.args.get("view", "month")
    return render_device_template(
        "updates/desktop/calendar/_event_detail_modal.html",
        event=event,
        view=view,
    )


@blueprint.route("/calendar/event/<int:event_id>/edit", methods=["GET", "POST"])
@login_required
def event_edit(event_id: int) -> ResponseReturnValue:
    """Edit an existing company event."""
    if not require_admin():
        return redirect(url_for("sync_bp.calendar_index"))

    event = Event.get_by_id(event_id)
    if not event:
        flash(_("Event not found."), "error")
        return redirect(url_for("sync_bp.calendar_index"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        scheduled_date_str = request.form.get("scheduled_date", "")
        scheduled_start_time_str = request.form.get("scheduled_start_time", "")
        scheduled_end_time_str = request.form.get("scheduled_end_time", "")
        is_all_day = request.form.get("is_all_day") == "on"
        location = request.form.get("location", "").strip()

        if not title:
            flash(_("Title is required."), "error")
            return redirect(url_for("sync_bp.event_edit", event_id=event_id))

        if not scheduled_date_str:
            flash(_("Date is required."), "error")
            return redirect(url_for("sync_bp.event_edit", event_id=event_id))

        try:
            scheduled_date = datetime.strptime(scheduled_date_str, "%Y-%m-%d").date()
        except ValueError:
            flash(_("Invalid date format."), "error")
            return redirect(url_for("sync_bp.event_edit", event_id=event_id))

        scheduled_start_time = None
        scheduled_end_time = None
        if not is_all_day and scheduled_start_time_str:
            try:
                scheduled_start_time = datetime.strptime(scheduled_start_time_str, "%H:%M").time()
            except ValueError:
                pass
        if not is_all_day and scheduled_end_time_str:
            try:
                scheduled_end_time = datetime.strptime(scheduled_end_time_str, "%H:%M").time()
            except ValueError:
                pass

        if not is_all_day and scheduled_start_time and scheduled_end_time:
            if scheduled_end_time <= scheduled_start_time:
                flash(_("End time must be after start time."), "error")
                return redirect(url_for("sync_bp.event_edit", event_id=event_id, view=request.form.get("view", "month")))

        event.update(
            title=title,
            description=description or None,
            scheduled_date=scheduled_date,
            scheduled_start_time=scheduled_start_time,
            scheduled_end_time=scheduled_end_time,
            is_all_day=is_all_day,
            location=location or None,
        )

        flash(_("Event updated successfully."), "success")
        view = request.form.get("view", "month")
        return redirect(url_for("sync_bp.calendar_index", view=view, date=scheduled_date_str))

    view = request.args.get("view", "month")
    return render_template(
        "updates/desktop/calendar/_event_form.html",
        event=event,
        prefill_date=event.scheduled_date.strftime("%Y-%m-%d"),
        view=view,
        is_edit=True,
    )


@blueprint.route("/calendar/event/<int:event_id>/delete", methods=["POST"])
@login_required
def event_delete(event_id: int) -> ResponseReturnValue:
    """Delete a company event."""
    if not require_admin():
        return redirect(url_for("sync_bp.calendar_index"))

    event = Event.get_by_id(event_id)
    if not event:
        flash(_("Event not found."), "error")
        return redirect(url_for("sync_bp.calendar_index"))

    event.delete()
    flash(_("Event deleted successfully."), "success")

    return redirect(url_for("sync_bp.calendar_index"))


# --- API Endpoints ---


@blueprint.route("/calendar/api/events")
@login_required
def api_events() -> ResponseReturnValue:
    """Get events as JSON for a date range."""
    start_str = request.args.get("start")
    end_str = request.args.get("end")

    try:
        start_date = datetime.strptime(start_str, "%Y-%m-%d").date() if start_str else date.today()
        end_date = datetime.strptime(end_str, "%Y-%m-%d").date() if end_str else start_date + timedelta(days=30)
    except ValueError:
        start_date = date.today()
        end_date = start_date + timedelta(days=30)

    events = Event.get_for_date_range(start_date, end_date)

    return jsonify([{
        "id": e.id,
        "title": e.title,
        "description": e.description,
        "scheduled_date": e.scheduled_date.isoformat(),
        "display_time": e.display_time,
        "is_all_day": e.is_all_day,
        "is_holiday": e.is_holiday,
        "location": e.location,
    } for e in events])


@blueprint.route("/calendar/api/upcoming")
@login_required
def api_upcoming() -> ResponseReturnValue:
    """Get upcoming events for dashboard widget."""
    limit = request.args.get("limit", 5, type=int)
    events = Event.get_upcoming(limit=limit)

    return jsonify([{
        "id": e.id,
        "title": e.title,
        "scheduled_date": e.scheduled_date.isoformat(),
        "display_time": e.display_time,
        "is_all_day": e.is_all_day,
        "is_today": e.is_today,
    } for e in events])
