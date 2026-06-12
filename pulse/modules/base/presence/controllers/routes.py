# -----------------------------------------------------------------------------
# sparQ - Time Tracking Routes
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

import calendar
import json
from datetime import date, datetime, time, timedelta
from typing import Any

import pytz
from flask import Blueprint, flash, g, make_response, redirect, render_template, request, url_for
from markupsafe import Markup, escape
from flask.typing import ResponseReturnValue

from system.device.template import render_device_template
from flask_login import current_user, login_required

from sqlalchemy.orm import joinedload

from modules.base.core.models.organization import Organization
from modules.base.core.models.organization_user import OrganizationUser
from system.auth.decorators import admin_required
from system.i18n.translation import format_date, translate as _
from system.module.registry import module_enabled
from system.utils.calendar_utils import get_week_start

from ..models.clock_punch import ClockPunch
from ..models.clock_punch_adjustment import ClockPunchAdjustment
from ..models.punch_correction_request import PunchCorrectionRequest
from ..models.settings import TimeTrackingSettings
from ..models.time_entry import TimeEntry, TimeEntryStatus


def _send_timesheet_notification(member_name: str, entry_count: int, period: str) -> None:
    """Send notification email to configured recipients when timesheets are submitted."""
    from modules.base.core.models.workspace_settings import WorkspaceSettings
    from modules.base.presence.models.settings import TimeTrackingSettings
    from system.email import is_configured, send_email_async
    from system.email.templates import (
        get_timesheet_submitted_email_html,
        get_timesheet_submitted_email_text,
    )

    if not is_configured():
        return

    recipients = TimeTrackingSettings.get_notification_recipients()
    if not recipients:
        return

    try:
        company = WorkspaceSettings.get_instance()
        approve_url = url_for("presence_bp.approve_timesheets", _external=True)
        subject = _("Timesheet Submitted: %(name)s") % {"name": member_name}

        html_body = get_timesheet_submitted_email_html(
            employee_name=member_name,
            entry_count=entry_count,
            period=period,
            company_settings=company,
            approve_url=approve_url
        )
        text_body = get_timesheet_submitted_email_text(
            employee_name=member_name,
            entry_count=entry_count,
            period=period,
            company_settings=company,
            approve_url=approve_url
        )

        for recipient in recipients:
            send_email_async(
                to=recipient.email,
                subject=subject,
                html_body=html_body,
                text_body=text_body
            )

    except Exception:
        pass


def _get_today_in_company_timezone() -> date:
    """Get today's date in the company's configured timezone."""
    company_settings = g.get("company_settings")
    tz_name = company_settings.timezone if company_settings else "America/Chicago"
    local_tz = pytz.timezone(tz_name)
    return datetime.now(pytz.UTC).astimezone(local_tz).date()


def _get_admin_member_context(current_member: OrganizationUser) -> tuple[OrganizationUser, dict[str, Any]]:
    """Return (member, context_dict) for admin member-selector views."""
    ctx: dict[str, Any] = {"members": None, "selected_member_id": None, "viewing_other": False}
    member = current_member
    if current_user.is_admin:
        ctx["members"] = sorted(
            OrganizationUser.query
            .filter_by(organization_id=g.organization_id, employment_status="ACTIVE")
            .options(joinedload(OrganizationUser.user))
            .all(),
            key=lambda e: e.user.full_name if e.user else "ZZZZ",
        )
        sel_id = request.args.get("member_id", type=int)
        ctx["selected_member_id"] = sel_id
        if sel_id and sel_id != current_member.id:
            sel = (
                OrganizationUser.query
                .filter_by(organization_id=g.organization_id, id=sel_id)
                .options(joinedload(OrganizationUser.user))
                .first()
            )
            if sel:
                member = sel
                ctx["viewing_other"] = True
    return member, ctx


def _build_export_presets() -> list[dict[str, str]]:
    """Build period preset options for the payroll export UI.

    Returns:
        List of preset dicts with keys: value, label, dates.
    """
    today = date.today()
    current_week_start = get_week_start(today)

    tw_start = current_week_start
    tw_end = current_week_start + timedelta(days=6)
    lw_start = current_week_start - timedelta(days=7)
    lw_end = current_week_start - timedelta(days=1)
    l2w_start = current_week_start - timedelta(days=14)
    l2w_end = current_week_start - timedelta(days=1)
    tm_start = today.replace(day=1)
    if today.month == 1:
        pm_year, pm_month = today.year - 1, 12
    else:
        pm_year, pm_month = today.year, today.month - 1
    lm_start = date(pm_year, pm_month, 1)

    return [
        {"value": "this_week", "label": _("This Week"), "dates": f"{tw_start.strftime('%b %-d')} - {tw_end.strftime('%b %-d')}"},
        {"value": "last_week", "label": _("Last Week"), "dates": f"{lw_start.strftime('%b %-d')} - {lw_end.strftime('%b %-d')}"},
        {"value": "last_2w", "label": _("Last 2 Weeks"), "dates": f"{l2w_start.strftime('%b %-d')} - {l2w_end.strftime('%b %-d')}"},
        {"value": "this_month", "label": _("This Month"), "dates": tm_start.strftime('%B %Y')},
        {"value": "last_month", "label": _("Last Month"), "dates": lm_start.strftime('%B %Y')},
    ]


def _get_reimbursable_expenses(start_date: date, end_date: date) -> dict[int, float]:
    """Query reimbursable expense totals by user_id for a date range.

    Returns a dict mapping user_id -> total reimbursable amount.
    Returns empty dict if Finance module is not enabled.
    """
    if module_enabled("Finance"):
        from modules.base.finance.models.expense import Expense
        return Expense.get_reimbursable_totals(start_date, end_date)
    return {}


def _get_reimbursable_expense_items(start_date: date, end_date: date, user_id: int) -> list[Any]:
    """Query individual reimbursable expenses for a specific user and date range.

    Returns a list of Expense objects. Returns empty list if Finance module is not enabled.
    """
    if module_enabled("Finance"):
        from modules.base.finance.models.expense import Expense
        return Expense.get_reimbursable_line_items(user_id, start_date, end_date)
    return []


blueprint = Blueprint(
    "presence_bp",
    __name__,
    template_folder="../views/templates",
    static_folder="../views/assets",
)


@blueprint.context_processor
def inject_presence_settings() -> dict[str, Any]:
    """Inject time tracking settings into all templates using this blueprint."""
    from . import presence_context
    return presence_context()


# --- Member Timesheet Views ---


@blueprint.route("/")
@login_required
def index() -> ResponseReturnValue:
    """Redirect to presence overview."""
    return redirect(url_for("presence_flow_bp.overview"))


@blueprint.route("/day")
@blueprint.route("/day/<date_str>")
@login_required
def day_view(date_str: str | None = None) -> ResponseReturnValue:
    """Show member's timesheet for a specific day.

    Admins can view any member's timesheet via ?member_id= query param.
    """
    # Get current member
    current_member = OrganizationUser.get_for_user(current_user.id, g.organization_id)
    if not current_member:
        flash(_("Employee profile not found"), "error")
        return redirect(url_for("core_bp.index"))

    # Admin: handle member selection
    member, admin_ctx = _get_admin_member_context(current_member)
    members = admin_ctx["members"]
    selected_member_id = admin_ctx["selected_member_id"]
    viewing_other = admin_ctx["viewing_other"]

    # Parse date
    if date_str:
        try:
            view_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            view_date = _get_today_in_company_timezone()
    else:
        view_date = _get_today_in_company_timezone()

    # Split any overnight punches before rendering
    ClockPunch.split_overnight_punches(member_id=member.id)

    # Get time entries for the day
    entries = TimeEntry.get_for_date(member.id, view_date)
    total_hours = sum(float(e.hours) for e in entries)

    # Check if SERVICE module is enabled (for job linking)
    service_enabled = module_enabled("Service")

    # Calculate week_start for the add-time modal URL
    week_start = get_week_start(view_date)

    # Admin viewing another member: also fetch clock punches
    punches = []
    if viewing_other:
        company_settings = g.get("company_settings")
        tz_name = company_settings.timezone if company_settings else "America/Chicago"
        punches = ClockPunch.get_for_day(member.id, view_date, tz_name)

    member_name_html = Markup("<strong>%s</strong>") % escape(member.user.full_name) if viewing_other else None

    return render_device_template(
        "presence/desktop/day_view.html",
        module_home="dashboard_bp.index",
        active_page="day",
        member=member,
        view_date=view_date,
        today=_get_today_in_company_timezone(),
        entries=entries,
        total_hours=total_hours,
        timedelta=timedelta,
        service_enabled=service_enabled,
        week_start=week_start,
        # Admin member management context
        members=members,
        selected_member_id=selected_member_id,
        viewing_other=viewing_other,
        punches=punches,
        member_name_html=member_name_html,
    )


@blueprint.route("/week")
@blueprint.route("/week/<date_str>")
@login_required
def week_view(date_str: str | None = None) -> ResponseReturnValue:
    """Show member's timesheet for a week.

    Admins can view any member's timesheet via ?member_id= query param.
    """
    # Get current member
    current_member = OrganizationUser.get_for_user(current_user.id, g.organization_id)
    if not current_member:
        flash(_("Employee profile not found"), "error")
        return redirect(url_for("core_bp.index"))

    # Admin: handle member selection
    member, admin_ctx = _get_admin_member_context(current_member)
    members = admin_ctx["members"]
    selected_member_id = admin_ctx["selected_member_id"]
    viewing_other = admin_ctx["viewing_other"]

    # Parse date
    if date_str:
        try:
            view_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            view_date = _get_today_in_company_timezone()
    else:
        view_date = _get_today_in_company_timezone()

    # Get week start based on company setting
    week_start = get_week_start(view_date)
    week_end = week_start + timedelta(days=6)

    # Get time entries grouped by job/category
    entries_by_job = TimeEntry.get_entries_grouped_by_job(member.id, week_start, week_end)

    # Calculate daily totals from grouped entries
    all_entries = [
        entry
        for job_data in entries_by_job.values()
        for date_entries in job_data["entries"].values()
        for entry in date_entries
    ]
    daily_totals = {}
    current_date = week_start
    while current_date <= week_end:
        date_key = current_date.isoformat()
        daily_totals[date_key] = sum(
            float(entry.hours) for entry in all_entries if entry.date == current_date
        )
        current_date += timedelta(days=1)

    # Calculate week total
    week_total = sum(daily_totals.values())

    member_name_html = Markup("<strong>%s</strong>") % escape(member.user.full_name) if viewing_other else None

    return render_device_template(
        "presence/desktop/week_view.html",
        module_home="dashboard_bp.index",
        active_page="day",
        member=member,
        week_start=week_start,
        week_end=week_end,
        entries_by_job=entries_by_job,
        daily_totals=daily_totals,
        week_total=week_total,
        timedelta=timedelta,
        today=_get_today_in_company_timezone(),
        # Admin member management context
        members=members,
        selected_member_id=selected_member_id,
        viewing_other=viewing_other,
        member_name_html=member_name_html,
    )


# --- Time Entry CRUD ---


@blueprint.route("/add-time-form/<date_str>")
@login_required
def add_time_form(date_str: str) -> ResponseReturnValue:
    """Return the add time form partial for mobile bottom sheet (HTMX)."""
    try:
        view_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        view_date = date.today()

    service_enabled = module_enabled("Service")

    # Admin can pass member_id to create entries on behalf of another member
    member_id = request.args.get("member_id", type=int) if current_user.is_admin else None

    return render_device_template(
        "presence/mobile/partials/add_time_form.html",
        view_date=view_date,
        service_enabled=service_enabled,
        member_id=member_id,
    )


@blueprint.route("/add-time-modal/<week_start_str>")
@login_required
def add_time_modal(week_start_str: str) -> ResponseReturnValue:
    """Return the add time modal partial for the week view (HTMX endpoint)."""
    try:
        week_start = datetime.strptime(week_start_str, "%Y-%m-%d").date()
    except ValueError:
        week_start = get_week_start(_get_today_in_company_timezone())

    week_end = week_start + timedelta(days=6)
    today = _get_today_in_company_timezone()

    # Default to today if within this week, otherwise week start (Monday)
    default_date = today if week_start <= today <= week_end else week_start

    service_enabled = module_enabled("Service")
    member_id = request.args.get("member_id", type=int) if current_user.is_admin else None

    # Support return_to parameter for day view redirects
    return_to = request.args.get("return_to", "week")
    day_date = request.args.get("day_date", "")

    # When opened from day view, override default_date to the specific day
    if return_to == "day" and day_date:
        try:
            default_date = datetime.strptime(day_date, "%Y-%m-%d").date()
        except ValueError:
            pass

    mode = "day" if return_to == "day" and day_date else "week"

    return render_device_template(
        "presence/desktop/partials/_add_time_modal.html",
        week_start=week_start,
        week_end=week_end,
        default_date=default_date,
        today=today,
        service_enabled=service_enabled,
        member_id=member_id,
        timedelta=timedelta,
        return_to=return_to,
        day_date=day_date,
        mode=mode,
    )


def _parse_weekly_entries(
    weekly_entries_json: str,
    local_tz: Any,
) -> list[dict] | None:
    """Parse weekly_entries JSON from week modal into batch dicts.

    Returns list of entry dicts on success, or None on validation failure
    (caller should check flash messages).
    """
    try:
        weekly_entries = json.loads(weekly_entries_json)
        if not isinstance(weekly_entries, list):
            raise ValueError("Expected list")
    except (json.JSONDecodeError, TypeError, ValueError):
        flash(_("Invalid entry data"), "error")
        return None

    batch: list[dict] = []
    for entry_data in weekly_entries:
        try:
            entry_date = datetime.strptime(entry_data["date"], "%Y-%m-%d").date()
            hours = float(entry_data["hours"])
        except (KeyError, ValueError, TypeError):
            flash(_("Invalid date or hours format"), "error")
            return None

        if hours <= 0 or hours > 24:
            flash(_("Hours must be between 0 and 24"), "error")
            return None

        description = str(entry_data.get("description", "")).strip()
        category = str(entry_data.get("category", "")).strip() or None
        job_id_raw = entry_data.get("job_id")
        job_id = int(job_id_raw) if job_id_raw else None
        is_billable = bool(entry_data.get("is_billable", False))

        # Handle range mode per entry (timezone conversion is controller's job)
        entry_timer_start = entry_timer_end = None
        entry_time_mode = str(entry_data.get("time_mode", "duration"))
        if entry_time_mode == "range":
            start_str = str(entry_data.get("start_time", "")).strip()
            end_str = str(entry_data.get("end_time", "")).strip()
            if start_str and end_str:
                try:
                    sh, sm = map(int, start_str.split(":"))
                    eh, em = map(int, end_str.split(":"))
                    local_start = local_tz.localize(datetime.combine(entry_date, time(sh, sm)))
                    local_end = local_tz.localize(datetime.combine(entry_date, time(eh, em)))
                    entry_timer_start = local_start.astimezone(pytz.UTC).replace(tzinfo=None)
                    entry_timer_end = local_end.astimezone(pytz.UTC).replace(tzinfo=None)
                    if entry_timer_end <= entry_timer_start:
                        flash(_("End time must be after start time"), "error")
                        return None
                except (ValueError, IndexError):
                    pass  # Fall back to duration-only

        batch.append({
            "date": entry_date,
            "hours": hours,
            "description": description,
            "category": category,
            "job_id": job_id,
            "is_billable": is_billable,
            "timer_start": entry_timer_start,
            "timer_end": entry_timer_end,
        })

    if not batch:
        flash(_("No entries to create"), "error")
        return None

    return batch


@blueprint.route("/entry/create", methods=["POST"])
@login_required
def create_entry() -> ResponseReturnValue:
    """Create one or more time entries.

    Supports three submission modes:

    1. **Per-day tab entries** (week modal): ``weekly_entries`` JSON string
       containing a list of per-day entry objects, each with its own hours,
       category, job, notes, and time range.
    2. **Multi-date** (legacy week modal): ``dates`` field list with shared
       hours/category/job across all selected dates.
    3. **Single-date** (day form): ``date`` field with a single entry.

    Form fields:
        weekly_entries: JSON string of per-day entry objects (week modal tab mode).
            Each object: {date, hours, category, job_id, description,
            is_billable, time_mode, start_time, end_time}
        dates: List of ISO date strings (legacy week modal).
        date: Single ISO date string (day form fallback).
        hours: Decimal hours worked.
        category: Optional category string.
        job_id: Optional job association.
        description: Optional work description.
        is_billable: Billable flag.
        time_mode: ``"duration"`` or ``"range"``.
        start_time / end_time: ``HH:MM`` strings when *time_mode* is range.
        return_to / week_start: Redirect hints for week view.
        member_id: Admin override for target member.
    """

    def _redirect_back(date_str: str | None = None, member_id: int | None = None) -> ResponseReturnValue:
        """Redirect to the appropriate view (week view for HTMX modal, day view otherwise)."""
        return_to = request.form.get("return_to")
        week_start_str = request.form.get("week_start")

        if request.headers.get("HX-Request") == "true":
            if return_to == "day":
                day_date = request.form.get("day_date", date_str)
                redirect_url = url_for("presence_bp.day_view", date_str=day_date, member_id=member_id)
                response = make_response("")
                response.headers["HX-Redirect"] = redirect_url
                return response
            if return_to == "week" and week_start_str:
                redirect_url = url_for("presence_bp.week_view", date_str=week_start_str, member_id=member_id)
                response = make_response("")
                response.headers["HX-Redirect"] = redirect_url
                return response

        return redirect(url_for("presence_bp.day_view", date_str=date_str, member_id=member_id))

    # Determine which member to create the entry for
    target_member_id = request.form.get("member_id", type=int)
    redirect_member_id = None

    if current_user.is_admin and target_member_id:
        # Admin creating on behalf of another member
        member = (
            OrganizationUser.query
            .filter_by(organization_id=g.organization_id, id=target_member_id)
            .options(joinedload(OrganizationUser.user))
            .first()
        )
        if not member:
            flash(_("Employee not found"), "error")
            return redirect(url_for("core_bp.index"))
        redirect_member_id = target_member_id
    else:
        # Regular flow: create for current user
        member = OrganizationUser.get_for_user(current_user.id, g.organization_id)
        if not member:
            flash(_("Employee profile not found"), "error")
            return redirect(url_for("core_bp.index"))

    company_settings = g.get("company_settings")
    tz_name = company_settings.timezone if company_settings else "America/Chicago"
    local_tz = pytz.timezone(tz_name)

    # --- Per-day tab entries from week modal (weekly_entries JSON) ---
    weekly_entries_json = request.form.get("weekly_entries")
    if weekly_entries_json:
        batch = _parse_weekly_entries(weekly_entries_json, local_tz)
        if batch is None:
            return _redirect_back(member_id=redirect_member_id)

        try:
            created = TimeEntry.create_batch(member.id, batch)
        except ValueError as e:
            flash(_(str(e)), "error")
            return _redirect_back(member_id=redirect_member_id)

        entry_dates = [e.date for e in created]

        if len(created) == 1:
            flash(_("Time entry created"), "success")
        else:
            flash(_("%(count)d time entries created") % {"count": len(created)}, "success")

        # Send notification to admins
        member_name = f"{member.user.first_name} {member.user.last_name}"
        if len(entry_dates) == 1:
            period = format_date(entry_dates[0], "long")
        else:
            sorted_dates = sorted(entry_dates)
            period = f"{format_date(sorted_dates[0], 'long')} - {format_date(sorted_dates[-1], 'long')}"
        _send_timesheet_notification(
            member_name=member_name,
            entry_count=len(created),
            period=period,
        )
        return _redirect_back(date_str=entry_dates[0].isoformat(), member_id=redirect_member_id)

    # --- Legacy path: shared fields across dates (day form / old week modal) ---

    # Parse form data
    hours = request.form.get("hours")
    description = request.form.get("description", "").strip()
    category = request.form.get("category", "").strip()
    job_id = request.form.get("job_id")
    is_billable = request.form.get("is_billable") == "on"
    time_mode = request.form.get("time_mode", "duration")
    start_time_str = request.form.get("start_time", "").strip()
    end_time_str = request.form.get("end_time", "").strip()

    # Parse dates (multi-date from week modal, or single from day form)
    entry_dates_raw = request.form.getlist("dates")
    if not entry_dates_raw:
        single_date = request.form.get("date")
        entry_dates_raw = [single_date] if single_date else []

    # Validation
    if not entry_dates_raw:
        flash(_("Date is required"), "error")
        return _redirect_back(member_id=redirect_member_id)

    if not hours:
        flash(_("Hours is required"), "error")
        return _redirect_back(member_id=redirect_member_id)

    try:
        entry_dates = [datetime.strptime(d, "%Y-%m-%d").date() for d in entry_dates_raw]
        hours = float(hours)
    except ValueError:
        flash(_("Invalid date or hours format"), "error")
        return _redirect_back(member_id=redirect_member_id)

    # Parse start/end times once (reused per date in range mode)
    use_range = time_mode == "range" and start_time_str and end_time_str
    start_hour = start_min = end_hour = end_min = 0
    if use_range:
        try:
            start_hour, start_min = map(int, start_time_str.split(":"))
            end_hour, end_min = map(int, end_time_str.split(":"))
        except (ValueError, IndexError):
            use_range = False

    # Build normalized entry dicts and delegate to model
    try:
        batch: list[dict] = []
        for entry_date in entry_dates:
            entry_timer_start = None
            entry_timer_end = None
            if use_range:
                local_start = local_tz.localize(datetime.combine(entry_date, time(start_hour, start_min)))
                local_end = local_tz.localize(datetime.combine(entry_date, time(end_hour, end_min)))
                entry_timer_start = local_start.astimezone(pytz.UTC).replace(tzinfo=None)
                entry_timer_end = local_end.astimezone(pytz.UTC).replace(tzinfo=None)
                if entry_timer_end <= entry_timer_start:
                    flash(_("End time must be after start time"), "error")
                    return _redirect_back(date_str=entry_date.isoformat(), member_id=redirect_member_id)

            batch.append({
                "date": entry_date,
                "hours": hours,
                "description": description,
                "category": category if category else None,
                "job_id": int(job_id) if job_id else None,
                "is_billable": is_billable,
                "timer_start": entry_timer_start,
                "timer_end": entry_timer_end,
            })

        created = TimeEntry.create_batch(member.id, batch)

        if len(created) == 1:
            flash(_("Time entry created"), "success")
        else:
            flash(_("%(count)d time entries created") % {"count": len(created)}, "success")

        # Send notification to admins (entries are auto-submitted)
        member_name = f"{member.user.first_name} {member.user.last_name}"
        if len(entry_dates) == 1:
            period = format_date(entry_dates[0], "long")
        else:
            period = f"{format_date(entry_dates[0], 'long')} - {format_date(entry_dates[-1], 'long')}"
        _send_timesheet_notification(
            member_name=member_name,
            entry_count=len(created),
            period=period,
        )
    except ValueError as e:
        flash(_(str(e)), "error")
        return _redirect_back(member_id=redirect_member_id)
    except Exception:
        flash(_("Error creating entry"), "error")
        return _redirect_back(member_id=redirect_member_id)

    return _redirect_back(date_str=entry_dates[0].isoformat(), member_id=redirect_member_id)


@blueprint.route("/entry/<int:entry_id>/start-timer", methods=["POST"])
@login_required
def start_timer(entry_id: int) -> ResponseReturnValue:
    """Start timer for a time entry"""
    entry = TimeEntry.scoped().get_or_404(entry_id)

    # Verify ownership
    member = OrganizationUser.get_for_user(current_user.id, g.organization_id)
    if not member or entry.member_id != member.id:
        flash(_("Unauthorized"), "error")
        return redirect(url_for("presence_bp.index"))

    try:
        entry.start_timer()
        flash(_("Timer started"), "success")
    except ValueError as e:
        flash(_(str(e)), "error")

    return redirect(url_for("presence_bp.day_view", date_str=entry.date.isoformat()))


@blueprint.route("/entry/<int:entry_id>/stop-timer", methods=["POST"])
@login_required
def stop_timer(entry_id: int) -> ResponseReturnValue:
    """Stop timer for a time entry"""
    entry = TimeEntry.scoped().get_or_404(entry_id)

    # Verify ownership
    member = OrganizationUser.get_for_user(current_user.id, g.organization_id)
    if not member or entry.member_id != member.id:
        flash(_("Unauthorized"), "error")
        return redirect(url_for("presence_bp.index"))

    try:
        entry.stop_timer()
        flash(_("Timer stopped"), "success")
    except ValueError as e:
        flash(_(str(e)), "error")

    return redirect(url_for("presence_bp.day_view", date_str=entry.date.isoformat()))


@blueprint.route("/entry/<int:entry_id>/edit")
@login_required
def edit_entry_modal(entry_id: int) -> ResponseReturnValue:
    """Return the edit time entry modal for HTMX."""
    from sqlalchemy.orm import joinedload as _jl

    entry = TimeEntry.scoped().options(
        _jl(TimeEntry.clock_punch),
    ).filter_by(id=entry_id).first_or_404()

    # Verify ownership (admins can edit on behalf of members)
    member = OrganizationUser.get_for_user(current_user.id, g.organization_id)
    if not current_user.is_admin and (not member or entry.member_id != member.id):
        flash(_("Unauthorized"), "error")
        return redirect(url_for("presence_bp.index"))

    # Block editing approved/invoiced entries
    if entry.status in (TimeEntryStatus.APPROVED, TimeEntryStatus.INVOICED):
        return ""

    # Clock punch entries use the correction request flow
    if entry.is_from_clock_punch:
        out_punch = entry.clock_punch
        in_punch = out_punch.get_matching_in() if out_punch else None
        # Check for pending corrections on each punch
        in_pending = PunchCorrectionRequest.get_pending_for_punch(in_punch.id) if in_punch else None
        out_pending = PunchCorrectionRequest.get_pending_for_punch(out_punch.id) if out_punch else None
        # Convert punch times to local timezone for inline correction forms
        company_settings = g.get("company_settings")
        tz_name: str = company_settings.timezone if company_settings else "America/Chicago"
        local_tz: pytz.BaseTzInfo = pytz.timezone(tz_name)
        in_punch_local: datetime | None = in_punch.punch_time.replace(tzinfo=pytz.UTC).astimezone(local_tz) if in_punch else None
        out_punch_local: datetime | None = out_punch.punch_time.replace(tzinfo=pytz.UTC).astimezone(local_tz) if out_punch else None
        return render_device_template(
            "presence/desktop/partials/_edit_clock_entry_message.html",
            entry=entry,
            in_punch=in_punch,
            out_punch=out_punch,
            in_pending=in_pending,
            out_pending=out_pending,
            in_punch_local=in_punch_local,
            out_punch_local=out_punch_local,
        )

    service_enabled = module_enabled("Service")

    # Pass company timezone so template can pre-populate local times
    company_settings = g.get("company_settings")
    company_tz = company_settings.timezone if company_settings else "America/Chicago"

    return render_device_template(
        "presence/desktop/partials/_edit_time_modal.html",
        entry=entry,
        service_enabled=service_enabled,
        company_tz=company_tz,
    )


@blueprint.route("/entry/<int:entry_id>/update", methods=["POST"])
@login_required
def update_entry(entry_id: int) -> ResponseReturnValue:
    """Update a manual time entry."""
    entry = TimeEntry.scoped().get_or_404(entry_id)

    # Verify ownership (admins can edit on behalf of members)
    member = OrganizationUser.get_for_user(current_user.id, g.organization_id)
    if not current_user.is_admin and (not member or entry.member_id != member.id):
        flash(_("Unauthorized"), "error")
        return redirect(url_for("presence_bp.index"))

    # Track whether admin is managing another member for redirect
    managing_other = current_user.is_admin and (not member or entry.member_id != member.id)

    # Parse form data
    hours = request.form.get("hours", "").strip()
    category = request.form.get("category", "").strip()
    job_id = request.form.get("job_id", "").strip()
    description = request.form.get("description", "").strip()
    is_billable = request.form.get("is_billable") == "on"
    time_mode = request.form.get("time_mode", "duration")
    start_time_str = request.form.get("start_time", "").strip()
    end_time_str = request.form.get("end_time", "").strip()

    # Validate hours
    if not hours:
        flash(_("Hours is required"), "error")
        return redirect(url_for(
            "presence_bp.day_view",
            date_str=entry.date.isoformat(),
            member_id=entry.member_id if managing_other else None,
        ))

    try:
        hours = float(hours)
    except ValueError:
        flash(_("Invalid hours format"), "error")
        return redirect(url_for(
            "presence_bp.day_view",
            date_str=entry.date.isoformat(),
            member_id=entry.member_id if managing_other else None,
        ))

    # Build timer_start/timer_end from Start/End Time mode
    timer_start = None
    timer_end = None
    if time_mode == "range" and start_time_str and end_time_str:
        try:
            sh, sm = map(int, start_time_str.split(":"))
            eh, em = map(int, end_time_str.split(":"))
            company_settings = g.get("company_settings")
            tz_name = company_settings.timezone if company_settings else "America/Chicago"
            local_tz = pytz.timezone(tz_name)
            local_start = local_tz.localize(datetime.combine(entry.date, time(sh, sm)))
            local_end = local_tz.localize(datetime.combine(entry.date, time(eh, em)))
            timer_start = local_start.astimezone(pytz.UTC).replace(tzinfo=None)
            timer_end = local_end.astimezone(pytz.UTC).replace(tzinfo=None)
            if timer_end <= timer_start:
                flash(_("End time must be after start time"), "error")
                return redirect(url_for(
                    "presence_bp.day_view",
                    date_str=entry.date.isoformat(),
                    member_id=entry.member_id if managing_other else None,
                ))
        except (ValueError, IndexError):
            timer_start = None
            timer_end = None

    try:
        entry.update_fields(
            hours=hours,
            category=category or None,
            job_id=int(job_id) if job_id else None,
            description=description,
            is_billable=is_billable,
            timer_start=timer_start if time_mode == "range" else None,
            timer_end=timer_end if time_mode == "range" else None,
            updated_by_id=current_user.id,
        )
        flash(_("Time entry updated"), "success")
    except ValueError as e:
        flash(_(str(e)), "error")

    return redirect(url_for(
        "presence_bp.day_view",
        date_str=entry.date.isoformat(),
        member_id=entry.member_id if managing_other else None,
    ))


@blueprint.route("/entry/<int:entry_id>/delete", methods=["POST"])
@login_required
def delete_entry(entry_id: int) -> ResponseReturnValue:
    """Delete a time entry (submitted or rejected only)."""
    entry = TimeEntry.scoped().get_or_404(entry_id)

    # Verify ownership (admins can delete on behalf of members)
    member = OrganizationUser.get_for_user(current_user.id, g.organization_id)
    if not current_user.is_admin and (not member or entry.member_id != member.id):
        flash(_("Unauthorized"), "error")
        return redirect(url_for("presence_bp.index"))

    # Track whether admin is managing another member for redirect
    managing_other = current_user.is_admin and (not member or entry.member_id != member.id)
    entry_date = entry.date
    entry_member_id = entry.member_id

    try:
        entry.delete()
        flash(_("Time entry deleted"), "success")
    except ValueError as e:
        flash(_(str(e)), "error")
        return redirect(url_for("presence_bp.day_view", date_str=entry.date.isoformat()))

    return redirect(url_for(
        "presence_bp.day_view",
        date_str=entry_date.isoformat(),
        member_id=entry_member_id if managing_other else None,
    ))


# --- Admin Approval Views ---


@blueprint.route("/approve")
@login_required
@admin_required
def approve_timesheets() -> ResponseReturnValue:
    """Admin view to approve timesheets and punch correction requests."""
    # Get today's date in company timezone
    company_settings = g.get("company_settings")
    tz_name = company_settings.timezone if company_settings else "America/Chicago"
    local_tz = pytz.timezone(tz_name)
    today_local = datetime.now(pytz.UTC).astimezone(local_tz).date()

    # Parse through_date filter (defaults to today)
    through_date_str = request.args.get("through_date")
    try:
        through_date = date.fromisoformat(through_date_str) if through_date_str else today_local
    except ValueError:
        through_date = today_local

    # Get pending entries grouped by member
    entries_by_member = TimeEntry.get_pending_grouped_by_member(through_date=through_date)

    # Get pending punch correction requests grouped by member
    requests_by_member = PunchCorrectionRequest.get_pending_grouped_by_member()

    # Check which requests affect already-submitted/approved entries
    affected_entry_status: dict[int, str] = {}
    for data in requests_by_member.values():
        for req in data["requests"]:
            entry = req.affected_time_entry
            if entry and entry.status in (TimeEntryStatus.SUBMITTED, TimeEntryStatus.APPROVED):
                affected_entry_status[req.id] = entry.status.value

    return render_device_template(
        "presence/desktop/approve.html",
        module_home="dashboard_bp.index",
        active_page="day",
        entries_by_member=entries_by_member,
        through_date=through_date.isoformat(),
        requests_by_member=requests_by_member,
        affected_entry_status=affected_entry_status,
        timezone=tz_name,
    )


@blueprint.route("/approve/<int:entry_id>", methods=["POST"])
@login_required
@admin_required
def approve_entry(entry_id: int) -> ResponseReturnValue:
    """Approve a time entry."""
    entry = TimeEntry.scoped().get_or_404(entry_id)
    through_date = request.form.get("through_date")

    try:
        entry.approve(current_user.id)
        flash(_("Time entry approved"), "success")
    except ValueError as e:
        flash(_(str(e)), "error")

    return redirect(url_for("presence_bp.approve_timesheets", through_date=through_date))


@blueprint.route("/approve/person/<int:member_id>", methods=["POST"])
@login_required
@admin_required
def approve_all_for_person(member_id: int) -> ResponseReturnValue:
    """Approve all pending time entries for a member."""
    through_date_str = request.form.get("through_date")
    try:
        through_date = date.fromisoformat(through_date_str) if through_date_str else None
    except ValueError:
        through_date = None

    try:
        count = TimeEntry.approve_all_for_member(
            member_id, current_user.id, through_date=through_date
        )
        flash(_("%(count)d time entries approved") % {"count": count}, "success")
    except ValueError as e:
        flash(_(str(e)), "error")

    return redirect(url_for("presence_bp.approve_timesheets", through_date=through_date_str))


@blueprint.route("/reject/<int:entry_id>", methods=["POST"])
@login_required
@admin_required
def reject_entry(entry_id: int) -> ResponseReturnValue:
    """Reject a time entry."""
    entry = TimeEntry.scoped().get_or_404(entry_id)
    reason = request.form.get("reason", "").strip()
    through_date = request.form.get("through_date")

    try:
        entry.reject(reason, current_user.id)
        flash(_("Time entry rejected"), "success")
    except ValueError as e:
        flash(_(str(e)), "error")

    return redirect(url_for("presence_bp.approve_timesheets", through_date=through_date))


# --- Payroll View ---


@blueprint.route("/payroll")
@login_required
@admin_required
def payroll() -> ResponseReturnValue:
    """Admin view to review payroll with export options."""
    format_type = request.args.get("format", "html")
    member_id = request.args.get("member_id", type=int)

    # Week filter - default to current week
    week_start_str = request.args.get("week_start")
    if week_start_str:
        week_start = datetime.strptime(week_start_str, "%Y-%m-%d").date()
    else:
        today = date.today()
        week_start = get_week_start(today)
    week_end = week_start + timedelta(days=6)

    # CSV Export (with expenses)
    if format_type == "csv":
        expense_totals = _get_reimbursable_expenses(week_start, week_end)
        csv_content, filename = TimeEntry.export_payroll_csv_range(
            week_start, week_end, member_id, expense_totals
        )
        response = make_response(csv_content)
        response.headers["Content-Type"] = "text/csv"
        response.headers["Content-Disposition"] = f"attachment; filename={filename}"
        return response

    # Per-member Excel export (with itemized expenses)
    if format_type == "excel" and member_id:
        emp = OrganizationUser.query.filter_by(organization_id=g.organization_id, id=member_id).first()
        expense_items = _get_reimbursable_expense_items(week_start, week_end, emp.user_id) if emp else []
        excel_bytes, filename = TimeEntry.export_member_excel(
            week_start, week_end, member_id, expense_items=expense_items
        )
        response = make_response(excel_bytes)
        response.headers["Content-Type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        response.headers["Content-Disposition"] = f"attachment; filename={filename}"
        return response

    # Get payroll summary from model for HTML view (with expense enrichment)
    expense_totals = _get_reimbursable_expenses(week_start, week_end)
    entries_by_member = TimeEntry.get_payroll_summary(
        week_start, week_end, member_id, expense_totals=expense_totals
    )

    # Calculate prev/next week for navigation
    prev_week = week_start - timedelta(days=7)
    next_week = week_start + timedelta(days=7)

    presets = _build_export_presets()

    return render_device_template(
        "presence/desktop/payroll.html",
        module_home="dashboard_bp.index",
        active_page="day",
        entries_by_member=entries_by_member,
        week_start=week_start,
        week_end=week_end,
        prev_week=prev_week,
        next_week=next_week,
        presets=presets,
    )


@blueprint.route("/payroll/export-modal")
@login_required
@admin_required
def export_payroll_modal() -> ResponseReturnValue:
    """Render the export payroll modal (HTMX endpoint)."""
    presets = _build_export_presets()

    return render_template(
        "presence/desktop/partials/_export_payroll_modal.html",
        presets=presets,
    )


@blueprint.route("/payroll/export")
@login_required
@admin_required
def export_payroll() -> ResponseReturnValue:
    """Unified payroll export — resolves preset to dates server-side."""
    preset = request.args.get("preset", "last_2w")
    fmt = request.args.get("format", "excel")

    today = date.today()
    current_week_start = get_week_start(today)

    if preset == "custom":
        start_str = request.args.get("start_date")
        end_str = request.args.get("end_date")
        if not start_str or not end_str:
            flash(_("Start and end dates are required for custom range."), "danger")
            return redirect(url_for("presence_bp.payroll"))
        try:
            start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
        except ValueError:
            flash(_("Invalid date format."), "danger")
            return redirect(url_for("presence_bp.payroll"))
        if end_date < start_date:
            flash(_("End date must be after start date."), "danger")
            return redirect(url_for("presence_bp.payroll"))
    elif preset == "this_week":
        start_date = current_week_start
        end_date = current_week_start + timedelta(days=6)
    elif preset == "last_week":
        start_date = current_week_start - timedelta(days=7)
        end_date = current_week_start - timedelta(days=1)
    elif preset == "last_2w":
        start_date = current_week_start - timedelta(days=14)
        end_date = current_week_start - timedelta(days=1)
    elif preset == "this_month":
        start_date = today.replace(day=1)
        end_date = today.replace(day=calendar.monthrange(today.year, today.month)[1])
    elif preset == "last_month":
        if today.month == 1:
            pm_year, pm_month = today.year - 1, 12
        else:
            pm_year, pm_month = today.year, today.month - 1
        start_date = date(pm_year, pm_month, 1)
        end_date = date(pm_year, pm_month, calendar.monthrange(pm_year, pm_month)[1])
    else:
        flash(_("Invalid preset."), "danger")
        return redirect(url_for("presence_bp.payroll"))

    if fmt == "csv":
        expense_totals = _get_reimbursable_expenses(start_date, end_date)
        csv_content, filename = TimeEntry.export_payroll_csv_range(
            start_date, end_date, expense_totals=expense_totals
        )
        response = make_response(csv_content)
        response.headers["Content-Type"] = "text/csv"
        response.headers["Content-Disposition"] = f"attachment; filename={filename}"
        return response

    # Default to Excel (with expenses summary)
    expense_totals = _get_reimbursable_expenses(start_date, end_date)
    excel_bytes, filename = TimeEntry.export_payroll_excel(
        start_date, end_date, expense_totals=expense_totals
    )
    response = make_response(excel_bytes)
    response.headers["Content-Type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response


# --- API/HTMX Endpoints ---


@blueprint.route("/search-jobs")
@login_required
def search_jobs() -> ResponseReturnValue:
    """Search jobs for HTMX autocomplete (requires SERVICE module)"""
    if not module_enabled("Service"):
        return f'<div class="text-muted small p-2">{_("Service module not enabled")}</div>'

    from modules.base.service.models.job import Job

    query = request.args.get("q", "").strip()

    if not query or len(query) < 2:
        return ""

    # Search by job number, title, or contact name
    jobs = Job.search(query, include_contact=True, limit=10)

    return render_device_template(
        "presence/desktop/partials/_job_search_results.html",
        jobs=jobs,
    )


@blueprint.route("/punch/<int:punch_id>/edit")
@login_required
@admin_required
def edit_punch_modal(punch_id: int) -> ResponseReturnValue:
    """Render the edit punch modal."""
    punch = ClockPunch.scoped().get_or_404(punch_id)

    # Convert to company timezone for display
    company_settings = g.get("company_settings")
    tz_name = company_settings.timezone if company_settings else "America/Chicago"
    local_tz = pytz.timezone(tz_name)
    punch_local = punch.punch_time.replace(tzinfo=pytz.UTC).astimezone(local_tz)

    # Get adjustment info
    adjustment_count = punch.adjustments.count()
    last_adjustment = punch.adjustments.order_by(ClockPunchAdjustment.created_at.desc()).first() if adjustment_count > 0 else None

    return render_device_template(
        "presence/desktop/partials/_edit_punch_modal.html",
        punch=punch,
        punch_local=punch_local,
        adjustment_count=adjustment_count,
        last_adjustment=last_adjustment,
    )


@blueprint.route("/punch/<int:punch_id>/update", methods=["POST"])
@login_required
@admin_required
def update_punch(punch_id: int) -> ResponseReturnValue:
    """Save the updated punch time."""
    from flask import make_response

    punch = ClockPunch.scoped().get_or_404(punch_id)

    # Get company timezone (needed for all error responses)
    company_settings = g.get("company_settings")
    tz_name = company_settings.timezone if company_settings else "America/Chicago"
    local_tz = pytz.timezone(tz_name)

    # Helper to return modal with error
    def _return_modal_with_error(error_msg: str, punch_local_time: datetime) -> ResponseReturnValue:
        adjustment_count = punch.adjustments.count()
        last_adjustment = punch.adjustments.order_by(ClockPunchAdjustment.created_at.desc()).first() if adjustment_count > 0 else None
        return render_device_template(
            "presence/desktop/partials/_edit_punch_modal.html",
            punch=punch,
            punch_local=punch_local_time,
            adjustment_count=adjustment_count,
            last_adjustment=last_adjustment,
            error=error_msg,
        )

    # Get form data
    new_time_str = request.form.get("new_time")
    reason = request.form.get("reason", "").strip()

    # Convert existing punch time to local for the date
    original_local = punch.punch_time.replace(tzinfo=pytz.UTC).astimezone(local_tz)

    if not new_time_str:
        return _return_modal_with_error("New time is required", original_local)

    # Parse the new time
    try:
        new_time_parts = new_time_str.split(":")
        new_hour = int(new_time_parts[0])
        new_minute = int(new_time_parts[1])
    except (ValueError, IndexError):
        return _return_modal_with_error("Invalid time format", original_local)

    # Create new local datetime with the new time, then convert to UTC
    new_local = original_local.replace(hour=new_hour, minute=new_minute, second=0, microsecond=0)
    new_utc = new_local.astimezone(pytz.UTC).replace(tzinfo=None)

    # Validate using model method
    error = punch.validate_new_time(new_utc, tz_name)
    if error:
        return _return_modal_with_error(error, new_local)

    # Update using model method (handles audit trail and TimeEntry recalculation)
    punch.update_time(new_utc, adjusted_by=current_user, reason=reason if reason else None)

    flash(_("Clock punch time updated"), "success")

    # Return empty response - modal will close and trigger content refresh
    response = make_response("")
    response.headers["HX-Trigger"] = "punchUpdated"
    return response


@blueprint.route("/clear-modal")
@login_required
def clear_punch_modal() -> ResponseReturnValue:
    """Clear the modal container (HTMX endpoint)."""
    return ""


# --- Punch Correction Request Routes ---


@blueprint.route("/punch/<int:punch_id>/request-edit")
@login_required
def request_punch_edit_modal(punch_id: int) -> ResponseReturnValue:
    """Render the request-edit modal for a member's punch."""
    punch = ClockPunch.scoped().get_or_404(punch_id)

    # Validate member owns the punch
    member = OrganizationUser.get_for_user(current_user.id, g.organization_id)
    if not member or punch.member_id != member.id:
        return f'<div class="text-danger">{_("Unauthorized")}</div>', 403

    # Check for existing pending request
    pending_request = PunchCorrectionRequest.get_pending_for_punch(punch_id)

    # Convert to company timezone for display
    company_settings = g.get("company_settings")
    tz_name = company_settings.timezone if company_settings else "America/Chicago"
    local_tz = pytz.timezone(tz_name)
    punch_local = punch.punch_time.replace(tzinfo=pytz.UTC).astimezone(local_tz)

    return render_device_template(
        "presence/desktop/partials/_request_punch_edit_modal.html",
        punch=punch,
        punch_local=punch_local,
        pending_request=pending_request,
    )


@blueprint.route("/punch/<int:punch_id>/request-edit", methods=["POST"])
@login_required
def submit_punch_edit_request(punch_id: int) -> ResponseReturnValue:
    """Submit a punch correction request."""
    punch = ClockPunch.scoped().get_or_404(punch_id)

    # Validate member owns the punch
    member = OrganizationUser.get_for_user(current_user.id, g.organization_id)
    if not member or punch.member_id != member.id:
        return f'<div class="text-danger">{_("Unauthorized")}</div>', 403

    # Parse the new time (same pattern as update_punch)
    new_time_str = request.form.get("new_time")
    reason = request.form.get("reason", "").strip()

    # Get company timezone
    company_settings = g.get("company_settings")
    tz_name = company_settings.timezone if company_settings else "America/Chicago"
    local_tz = pytz.timezone(tz_name)

    # Convert existing punch time to local for the date
    original_local = punch.punch_time.replace(tzinfo=pytz.UTC).astimezone(local_tz)

    # Helper to re-render modal with an error
    def render_modal_error(error_msg: str) -> ResponseReturnValue:
        return render_device_template(
            "presence/desktop/partials/_request_punch_edit_modal.html",
            punch=punch,
            punch_local=original_local,
            pending_request=None,
            error=_(error_msg),
        ), 422

    if not new_time_str:
        return render_modal_error("New time is required")

    try:
        new_time_parts = new_time_str.split(":")
        new_hour = int(new_time_parts[0])
        new_minute = int(new_time_parts[1])
    except (ValueError, IndexError):
        return render_modal_error("Invalid time format")

    # Create new local datetime, convert to UTC
    new_local = original_local.replace(hour=new_hour, minute=new_minute, second=0, microsecond=0)
    new_utc = new_local.astimezone(pytz.UTC).replace(tzinfo=None)

    # Validate the new time (future check, overlap check, etc.)
    error = punch.validate_new_time(new_utc, tz_name)
    if error:
        return render_modal_error(error)

    try:
        PunchCorrectionRequest.create(
            clock_punch_id=punch.id,
            member_id=member.id,
            requested_time=new_utc,
            reason=reason if reason else None,
        )
        flash(_("Correction request submitted for approval"), "success")
    except ValueError as e:
        return render_modal_error(str(e))

    # Return empty response with HX-Trigger for HTMX
    response = make_response("")
    response.headers["HX-Trigger"] = "punchUpdated"
    return response


@blueprint.route("/punch-changes")
@blueprint.route("/punch-corrections")
@login_required
@admin_required
def punch_corrections() -> ResponseReturnValue:
    """Redirect to approve page (punch corrections are now merged there)."""
    return redirect(url_for("presence_bp.approve_timesheets"))


@blueprint.route("/punch-correction/<int:request_id>/approve", methods=["POST"])
@login_required
@admin_required
def approve_punch_correction(request_id: int) -> ResponseReturnValue:
    """Approve a punch correction request."""
    from sqlalchemy.orm import joinedload

    correction_request = (
        PunchCorrectionRequest.scoped()
        .options(joinedload(PunchCorrectionRequest.clock_punch))
        .filter_by(id=request_id)
        .first_or_404()
    )
    notes = request.form.get("notes", "").strip()

    try:
        correction_request.approve(current_user.id, notes=notes if notes else None)
        flash(_("Punch correction approved"), "success")
    except ValueError as e:
        flash(_(str(e)), "error")

    return redirect(url_for("presence_bp.approve_timesheets"))


@blueprint.route("/punch-correction/<int:request_id>/deny", methods=["POST"])
@login_required
@admin_required
def deny_punch_correction(request_id: int) -> ResponseReturnValue:
    """Deny a punch correction request."""
    correction_request = PunchCorrectionRequest.scoped().get_or_404(request_id)

    try:
        correction_request.deny(current_user.id)
        flash(_("Punch correction denied"), "success")
    except ValueError as e:
        flash(_(str(e)), "error")

    return redirect(url_for("presence_bp.approve_timesheets"))


# --- Settings Routes ---


@blueprint.route("/settings")
@login_required
@admin_required
def settings() -> ResponseReturnValue:
    """Time tracking settings page (admin only)."""
    from modules.base.core.models.organization import Organization
    from modules.base.core.models.workspace import Workspace
    from modules.base.core.models.user import User
    from system.email import is_configured as email_is_configured

    settings = TimeTrackingSettings.get()
    workspace = Workspace.get_by_id(g.workspace_id)
    organization = Organization.query.get(workspace.organization_id) if workspace and workspace.organization_id else None
    geofence_coords = TimeTrackingSettings.get_geofence_coords()

    # Get admin users for notification settings (users who can approve timesheets)
    admin_members = OrganizationUser.query.filter_by(organization_id=g.organization_id, role="admin", is_active=True).all()
    eligible_member_ids = list({m.user_id for m in admin_members})
    eligible_users = sorted(
        User.get_by_ids(eligible_member_ids),
        key=lambda u: (u.last_name or "", u.first_name or ""),
    )

    # Get active tab from query param (for redirect back to same tab)
    active_tab = request.args.get('tab', 'timeclock')

    return render_device_template(
        "presence/desktop/settings.html",
        module_home="dashboard_bp.index",
        settings=settings,
        organization=organization,
        geofence_coords=geofence_coords,
        eligible_users=eligible_users,
        active_tab=active_tab,
        active_page="settings",
        email_configured=email_is_configured(),
    )


@blueprint.route("/settings", methods=["POST"])
@login_required
@admin_required
def save_settings() -> ResponseReturnValue:
    """Save time tracking settings."""
    settings = TimeTrackingSettings.get()

    # Handle timesheets tab settings
    if request.args.get('tab') == 'timesheets':
        settings.notify_on_submission = request.form.get('notify_on_submission') == 'on'
        recipient_ids = request.form.getlist('notification_recipients')
        TimeTrackingSettings.set_notification_recipients([int(id) for id in recipient_ids if id])
        flash(_("Notification settings saved"), "success")
        return redirect(url_for("presence_bp.settings") + "?tab=timesheets")

    # Parse geofence fields from form
    lat = lng = None
    if request.form.get("geofence_location") != "company":
        try:
            lat_str = request.form.get("geofence_latitude")
            lng_str = request.form.get("geofence_longitude")
            lat = float(lat_str) if lat_str else None
            lng = float(lng_str) if lng_str else None
        except (ValueError, TypeError):
            pass

    settings.update_geofence(
        enabled=request.form.get("geofence_enabled") == "on",
        enforcement=request.form.get("geofence_enforcement", "soft"),
        use_company_address=request.form.get("geofence_location") == "company",
        radius_meters=int(request.form.get("geofence_radius", 100)),
        address=request.form.get("custom_address", "").strip() or None,
        city=request.form.get("custom_city", "").strip() or None,
        state=request.form.get("custom_state", "").strip() or None,
        zip_code=request.form.get("custom_zip", "").strip() or None,
        latitude=lat,
        longitude=lng,
    )
    flash(_("Settings saved successfully"), "success")

    return redirect(url_for("presence_bp.settings"))


@blueprint.route("/settings/geocode", methods=["POST"])
@login_required
@admin_required
def geocode_address() -> ResponseReturnValue:
    """Geocode an address using selected provider. Returns HTML partial for HTMX."""
    import json
    import urllib.parse
    import urllib.request

    from modules.base.core.models.workspace import Workspace

    provider = request.form.get("provider", "openstreetmap")
    address_type = request.form.get("type", "company")

    # Build address string based on type
    if address_type == "custom":
        address_parts = [
            request.form.get("custom_address", ""),
            request.form.get("custom_city", ""),
            request.form.get("custom_state", ""),
            request.form.get("custom_zip", ""),
            "USA",
        ]
    else:
        workspace = Workspace.get_by_id(g.workspace_id)
        organization = Organization.query.get(workspace.organization_id) if workspace and workspace.organization_id else None
        address_parts = [
            organization.address if organization else None,
            organization.city if organization else None,
            organization.state if organization else None,
            organization.zip_code if organization else None,
            organization.country if organization else None,
        ]

    address = ", ".join(p for p in address_parts if p)

    if not address or address == "USA":
        error_msg = _("No address provided")
        if address_type == "company":
            return render_device_template(
                "presence/desktop/partials/_company_coords.html",
                settings=TimeTrackingSettings.get(),
                error=error_msg,
            )
        else:
            return render_device_template(
                "presence/desktop/partials/_custom_coords.html",
                latitude=None,
                longitude=None,
                error=error_msg,
            )

    try:
        if provider == "census":
            # US Census Geocoder (US addresses only)
            encoded_address = urllib.parse.quote(address)
            url = f"https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?address={encoded_address}&benchmark=2020&format=json"

            req = urllib.request.Request(url, headers={"User-Agent": "sparQ/1.0"})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())

            matches = data.get("result", {}).get("addressMatches", [])
            if not matches:
                error_msg = _("Address not found (US Census)")
                if address_type == "company":
                    return render_device_template(
                        "presence/desktop/partials/_company_coords.html",
                        settings=TimeTrackingSettings.get(),
                        error=error_msg,
                    )
                else:
                    return render_device_template(
                        "presence/desktop/partials/_custom_coords.html",
                        latitude=None,
                        longitude=None,
                        error=error_msg,
                    )

            coords = matches[0].get("coordinates", {})
            lat = coords.get("y")
            lng = coords.get("x")

        else:
            # OpenStreetMap Nominatim (default)
            encoded_address = urllib.parse.quote(address)
            url = f"https://nominatim.openstreetmap.org/search?q={encoded_address}&format=json&limit=1"

            req = urllib.request.Request(url, headers={"User-Agent": "sparQ/1.0"})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())

            if not data:
                error_msg = _("Address not found (OpenStreetMap)")
                if address_type == "company":
                    return render_device_template(
                        "presence/desktop/partials/_company_coords.html",
                        settings=TimeTrackingSettings.get(),
                        error=error_msg,
                    )
                else:
                    return render_device_template(
                        "presence/desktop/partials/_custom_coords.html",
                        latitude=None,
                        longitude=None,
                        error=error_msg,
                    )

            lat = float(data[0]["lat"])
            lng = float(data[0]["lon"])

        # Save and return appropriate partial based on type
        if address_type == "company":
            settings = TimeTrackingSettings.save_geofence_coords(lat, lng)

            return render_device_template(
                "presence/desktop/partials/_company_coords.html",
                settings=settings,
            )
        else:
            # Custom address - return partial with coordinates in hidden fields
            return render_device_template(
                "presence/desktop/partials/_custom_coords.html",
                latitude=lat,
                longitude=lng,
            )

    except Exception as e:
        error_msg = _("Geocoding failed: %(error)s") % {"error": str(e)}
        if address_type == "company":
            return render_device_template(
                "presence/desktop/partials/_company_coords.html",
                settings=TimeTrackingSettings.get(),
                error=error_msg,
            )
        else:
            return render_device_template(
                "presence/desktop/partials/_custom_coords.html",
                latitude=None,
                longitude=None,
                error=error_msg,
            )
