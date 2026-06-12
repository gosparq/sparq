# -----------------------------------------------------------------------------
# sparQ - Time Clock Routes
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import Any

import pytz
from flask import Blueprint, flash, g, make_response, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue

from system.device.template import render_device_template
from flask_login import current_user, login_required
from system.i18n.translation import translate as _

from modules.base.core.models.organization_user import OrganizationUser

from ..models.clock_punch import ClockPunch
from ..models.presence_forecast import ForecastStatus, PresenceForecast
from ..models.punch_correction_request import PunchCorrectionRequest
from ..models.settings import TimeTrackingSettings
from ..models.time_entry import TimeEntry
from system.services.geocoding import reverse_geocode
from system.auth.current_member import current_member


def _ws_member_id() -> int | None:
    """Return the WorkspaceUser.id for the current user (for MemberSchedule lookups)."""
    ws_member = current_member()
    return ws_member.id if ws_member else None


def _current_week_dates(local_today: date) -> list[date]:
    """Return [Monday, ..., Sunday] for the ISO week containing local_today."""
    monday = local_today - timedelta(days=local_today.weekday())
    return [monday + timedelta(days=i) for i in range(7)]

blueprint = Blueprint(
    "clock_bp",
    __name__,
    template_folder="../views/templates",
    static_folder="../views/assets",
)


@blueprint.context_processor
def inject_presence_settings() -> dict[str, Any]:
    """Inject time tracking settings into all templates using this blueprint."""
    from . import presence_context
    return presence_context()


def time_clock_required(f: Callable[..., ResponseReturnValue]) -> Callable[..., ResponseReturnValue]:
    """Decorator to check if Time Clock feature is enabled."""
    from functools import wraps

    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> ResponseReturnValue:
        if not TimeTrackingSettings.is_time_clock_enabled():
            flash(_("Time Clock feature is disabled"), "warning")
            return redirect(url_for("presence_bp.index"))
        return f(*args, **kwargs)

    return decorated_function


@blueprint.route("/")
@login_required
@time_clock_required
def index() -> ResponseReturnValue:
    """Time Clock main page - clock in/out interface."""
    member = OrganizationUser.get_for_user(current_user.id, g.organization_id)
    if not member:
        flash(_("Employee profile not found"), "error")
        return redirect(url_for("core_bp.index"))

    status = ClockPunch.get_current_status(member.id)
    todays_punches = ClockPunch.get_todays_punches(member.id)

    # Get pending correction requests for today's punches
    pending_requests = PunchCorrectionRequest.get_pending_map_for_punches(
        [p.id for p in todays_punches]
    )

    # Get company timezone for display
    company_settings = g.get("company_settings")
    tz_name = company_settings.timezone if company_settings else "America/Chicago"
    local_tz = pytz.timezone(tz_name)
    local_now = datetime.now(pytz.UTC).astimezone(local_tz)

    todays_total_hours = TimeEntry.get_total_hours_for_date(member.id, local_now.date())

    forecast_dates = _current_week_dates(local_now.date())
    raw_forecasts = PresenceForecast.get_for_member(
        member.id, forecast_dates[0], forecast_dates[-1]
    )
    my_forecasts = {f.forecast_date: f for f in raw_forecasts}

    from modules.base.presence.models.member_schedule import MemberSchedule

    ws_mid = _ws_member_id()
    weekly_schedule = MemberSchedule.get_weekly_schedule(ws_mid) if ws_mid else {}

    return render_device_template(
        "presence/desktop/clock.html",
        module_home="dashboard_bp.index",
        member=member,
        status=status,
        todays_punches=todays_punches,
        pending_requests=pending_requests,
        active_page="clock",
        today=local_now,
        timezone=tz_name,
        todays_total_hours=todays_total_hours,
        forecast_dates=forecast_dates,
        my_forecasts=my_forecasts,
        weekly_schedule=weekly_schedule,
    )


@blueprint.route("/punch", methods=["POST"])
@login_required
@time_clock_required
def punch() -> ResponseReturnValue:
    """Process clock in/out punch."""
    member = OrganizationUser.get_for_user(current_user.id, g.organization_id)
    if not member:
        flash(_("Employee profile not found"), "error")
        return redirect(url_for("core_bp.index"))

    # Get client IP
    ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)
    if ip_address and "," in ip_address:
        ip_address = ip_address.split(",")[0].strip()

    # Get geolocation data
    latitude = request.form.get("latitude")
    longitude = request.form.get("longitude")
    location_accuracy = request.form.get("location_accuracy")
    location_denied = request.form.get("location_denied") == "true"

    # Convert to float if provided
    try:
        latitude = float(latitude) if latitude else None
        longitude = float(longitude) if longitude else None
        location_accuracy = float(location_accuracy) if location_accuracy else None
    except (ValueError, TypeError):
        latitude = longitude = location_accuracy = None

    # Check geofence before processing
    blocked, _outside = TimeTrackingSettings.check_geofence(latitude, longitude, location_denied)
    if blocked:
        msg = _("You are not within the allowed location to clock in/out.")
        if location_denied:
            msg = _("Location access is required to clock in/out. Please enable location services and try again.")
        if request.headers.get("HX-Request"):
            return render_device_template(
                "presence/desktop/partials/clock_blocked.html",
                message=msg,
            )
        flash(msg, "error")
        return redirect(url_for("clock_bp.index"))

    # Split any overnight punches before processing clock-out
    ClockPunch.split_overnight_punches(member_id=member.id)

    try:
        if ClockPunch.is_clocked_in(member.id):
            punch = ClockPunch.clock_out(
                member.id,
                source="web",
                ip_address=ip_address,
                latitude=latitude,
                longitude=longitude,
                location_accuracy=location_accuracy,
                location_denied=location_denied,
            )
            action = "out"
        else:
            punch = ClockPunch.clock_in(
                member.id,
                source="web",
                ip_address=ip_address,
                latitude=latitude,
                longitude=longitude,
                location_accuracy=location_accuracy,
                location_denied=location_denied,
            )
            action = "in"
    except ValueError as e:
        flash(_(str(e)), "error")
        if request.headers.get("HX-Request"):
            status = ClockPunch.get_current_status(member.id)
            return render_device_template(
                "presence/desktop/partials/clock_status.html",
                status=status,
            )
        return redirect(url_for("clock_bp.index"))

    # Reverse-geocode location synchronously so the address is available for the template
    show_map = False
    address: str | None = None
    if latitude is not None and longitude is not None:
        show_map = True
        address = reverse_geocode(latitude, longitude, host=request.host)
        if address:
            ClockPunch.set_location_address(punch.id, address)

    # Return partial for HTMX or redirect
    if request.headers.get("HX-Request"):
        status = ClockPunch.get_current_status(member.id)
        todays_punches = ClockPunch.get_todays_punches(member.id)
        pending_requests = PunchCorrectionRequest.get_pending_map_for_punches(
            [p.id for p in todays_punches]
        )

        company_settings = g.get("company_settings")
        tz_name = company_settings.timezone if company_settings else "America/Chicago"
        local_now = datetime.now(pytz.UTC).astimezone(pytz.timezone(tz_name))
        todays_total_hours = TimeEntry.get_total_hours_for_date(member.id, local_now.date())

        main_html = render_device_template(
            "presence/desktop/partials/clock_status.html",
            status=status,
            todays_punches=todays_punches,
            pending_requests=pending_requests,
            todays_total_hours=todays_total_hours,
            is_htmx=True,
            show_map=show_map,
            punch_latitude=latitude,
            punch_longitude=longitude,
            punch_action=action,
            punch_address=address,
            geofence_warning=punch.outside_geofence,
        )

        # OOB swap the header clock badge so it updates without page refresh
        oob_html = render_template(
            "core/desktop/partials/_header_clock_badge.html",
            header_time_clock_enabled=True,
            header_clock_status=status,
        )
        oob_wrapped = f'<div id="header-clock-badge" hx-swap-oob="innerHTML">{oob_html}</div>'

        resp = make_response(main_html + oob_wrapped)
        return resp

    # Non-HTMX fallback
    if punch.outside_geofence:
        flash(_("Clocked %(action)s - Your entry is flagged for review (outside location)") % {"action": action}, "warning")
    else:
        flash(_("Clocked %(action)s successfully") % {"action": action}, "success")
    return redirect(url_for("clock_bp.index"))


@blueprint.route("/status")
@login_required
@time_clock_required
def status() -> ResponseReturnValue:
    """Get current clock status (HTMX partial)."""
    member = OrganizationUser.get_for_user(current_user.id, g.organization_id)
    if not member:
        return f'<div class="text-danger">{_("Employee profile not found")}</div>'

    status = ClockPunch.get_current_status(member.id)
    todays_punches = ClockPunch.get_todays_punches(member.id)

    # Get pending correction requests for today's punches
    pending_requests = PunchCorrectionRequest.get_pending_map_for_punches(
        [p.id for p in todays_punches]
    )

    company_settings = g.get("company_settings")
    tz_name = company_settings.timezone if company_settings else "America/Chicago"
    local_now = datetime.now(pytz.UTC).astimezone(pytz.timezone(tz_name))
    todays_total_hours = TimeEntry.get_total_hours_for_date(member.id, local_now.date())

    return render_device_template(
        "presence/desktop/partials/clock_status.html",
        status=status,
        todays_punches=todays_punches,
        pending_requests=pending_requests,
        todays_total_hours=todays_total_hours,
    )


# --- Forecast Routes ---


def _get_member_or_error(error_html: str = "") -> "OrganizationUser | None":
    """Return the current user's OrganizationUser, or None on missing profile."""
    return OrganizationUser.get_for_user(current_user.id, g.organization_id)


def _forecast_week_response(member_id: int, local_today: date) -> ResponseReturnValue:
    """Render the forecast week partial, optionally firing forecastUpdated."""
    from modules.base.presence.models.member_schedule import MemberSchedule

    forecast_dates = _current_week_dates(local_today)
    raw = PresenceForecast.get_for_member(member_id, forecast_dates[0], forecast_dates[-1])
    my_forecasts = {f.forecast_date: f for f in raw}

    ws_mid = _ws_member_id()
    weekly_schedule = MemberSchedule.get_weekly_schedule(ws_mid) if ws_mid else {}

    html = render_device_template(
        "presence/desktop/partials/_forecast_week.html",
        forecast_dates=forecast_dates,
        my_forecasts=my_forecasts,
        weekly_schedule=weekly_schedule,
        today=local_today,
    )
    resp = make_response(html)
    resp.headers["HX-Trigger"] = "forecastUpdated"
    return resp


@blueprint.route("/forecast-week")
@login_required
@time_clock_required
def forecast_week() -> ResponseReturnValue:
    """Return the forecast week strip partial (HTMX refresh)."""
    member = _get_member_or_error()
    if not member:
        return f'<div class="text-danger">{_("Employee profile not found")}</div>'

    company_settings = g.get("company_settings")
    tz_name = company_settings.timezone if company_settings else "America/Chicago"
    local_today = datetime.now(pytz.UTC).astimezone(pytz.timezone(tz_name)).date()
    return _forecast_week_response(member.id, local_today)


@blueprint.route("/forecast-day/<date_str>")
@login_required
@time_clock_required
def forecast_day(date_str: str) -> ResponseReturnValue:
    """Return the inline edit form for one day's forecast (renders into #modals)."""
    member = _get_member_or_error()
    if not member:
        return f'<div class="text-danger">{_("Employee profile not found")}</div>'

    try:
        forecast_date = date.fromisoformat(date_str)
    except ValueError:
        return "", 400

    existing = PresenceForecast.scoped().filter_by(
        member_id=member.id, forecast_date=forecast_date
    ).first()

    # Pre-fill available hours from member's default schedule if not yet set
    from modules.base.presence.models.member_schedule import MemberSchedule

    default_start = None
    default_end = None
    ws_mid = _ws_member_id()
    if ws_mid and (not existing or (not existing.available_from and not existing.available_until)):
        effective = MemberSchedule.get_effective_schedule(ws_mid, forecast_date)
        if effective:
            default_start, default_end = effective

    return render_device_template(
        "presence/desktop/partials/_forecast_day_edit.html",
        forecast_date=forecast_date,
        existing=existing,
        default_start=default_start,
        default_end=default_end,
        statuses=ForecastStatus,
    )


@blueprint.route("/forecast", methods=["POST"])
@login_required
@time_clock_required
def set_forecast() -> ResponseReturnValue:
    """Save or update a forecast for the current user."""
    member = _get_member_or_error()
    if not member:
        return f'<div class="text-danger">{_("Employee profile not found")}</div>', 422

    date_str = request.form.get("forecast_date", "")
    status_str = request.form.get("status", "").strip()
    from_str = request.form.get("available_from", "").strip()
    until_str = request.form.get("available_until", "").strip()
    note = request.form.get("note", "").strip() or None

    try:
        forecast_date = date.fromisoformat(date_str)
    except ValueError:
        return "", 400

    if status_str not in {s.value for s in ForecastStatus}:
        return "", 400

    def _parse_time(s: str) -> "datetime.time | None":
        from datetime import time as dtime
        if not s:
            return None
        try:
            h, m = s.split(":")
            return dtime(int(h), int(m))
        except (ValueError, AttributeError):
            return None

    available_from = _parse_time(from_str)
    available_until = _parse_time(until_str)

    PresenceForecast.set_forecast(
        member_id=member.id,
        forecast_date=forecast_date,
        status=status_str,
        available_from=available_from,
        available_until=available_until,
        note=note,
    )

    # Write/clear schedule override based on forecast status
    from modules.base.presence.models.member_schedule import MemberScheduleOverride

    ws_mid = _ws_member_id()
    if ws_mid and status_str in ("in", "remote") and available_from and available_until:
        MemberScheduleOverride.set_override(
            member_id=ws_mid,
            override_date=forecast_date,
            start_time=available_from,
            end_time=available_until,
        )
    elif ws_mid and status_str in ("out", "pto"):
        MemberScheduleOverride.clear_override(
            member_id=ws_mid,
            override_date=forecast_date,
        )

    company_settings = g.get("company_settings")
    tz_name = company_settings.timezone if company_settings else "America/Chicago"
    local_today = datetime.now(pytz.UTC).astimezone(pytz.timezone(tz_name)).date()

    resp = make_response(_forecast_week_response(member.id, local_today))
    resp.headers["HX-Trigger"] = '{"forecastUpdated": true, "clearModals": true}'
    return resp


@blueprint.route("/forecast/<date_str>", methods=["DELETE"])
@login_required
@time_clock_required
def clear_forecast(date_str: str) -> ResponseReturnValue:
    """Clear the forecast for the current user on a given date."""
    member = _get_member_or_error()
    if not member:
        return f'<div class="text-danger">{_("Employee profile not found")}</div>', 422

    try:
        forecast_date = date.fromisoformat(date_str)
    except ValueError:
        return "", 400

    PresenceForecast.clear_forecast(member.id, forecast_date)

    company_settings = g.get("company_settings")
    tz_name = company_settings.timezone if company_settings else "America/Chicago"
    local_today = datetime.now(pytz.UTC).astimezone(pytz.timezone(tz_name)).date()

    resp = make_response(_forecast_week_response(member.id, local_today))
    resp.headers["HX-Trigger"] = '{"forecastUpdated": true, "clearModals": true}'
    return resp
