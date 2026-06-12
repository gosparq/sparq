# -----------------------------------------------------------------------------
# sparQ - In/Out Board Routes
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import Any

import pytz
from flask import Blueprint, abort, flash, g, make_response, redirect, request, url_for
from flask.typing import ResponseReturnValue
from sqlalchemy.orm import joinedload

from system.device.template import render_device_template
from flask_login import current_user, login_required

from modules.base.core.models.organization_user import OrganizationUser
from system.auth.decorators import admin_required
from system.i18n.translation import translate as _

from ..models.clock_punch import ClockPunch
from ..models.settings import TimeTrackingSettings
from ..queries.forecast import get_team_forecast


def _current_week_dates(local_today: date) -> list[date]:
    """Return [Monday, ..., Sunday] for the ISO week containing local_today."""
    monday = local_today - timedelta(days=local_today.weekday())
    return [monday + timedelta(days=i) for i in range(7)]

blueprint = Blueprint(
    "board_bp",
    __name__,
    template_folder="../views/templates",
    static_folder="../views/assets",
)


@blueprint.context_processor
def inject_presence_settings() -> dict[str, Any]:
    """Inject time tracking settings into all templates using this blueprint."""
    from . import presence_context
    return presence_context()


def board_required(f: Callable[..., ResponseReturnValue]) -> Callable[..., ResponseReturnValue]:
    """Decorator to check if In/Out Board feature is enabled and user has access."""
    from functools import wraps

    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> ResponseReturnValue:
        if not TimeTrackingSettings.is_board_visible_to_user(current_user):
            flash(_("In/Out Board is not available"), "warning")
            return redirect(url_for("presence_bp.index"))
        return f(*args, **kwargs)

    return decorated_function


def _get_forecast_context() -> tuple[list[date], dict, date, dict]:
    """Compute the current week's dates, team forecast dict, team schedules, and local today."""
    company_settings = g.get("company_settings")
    tz_name = company_settings.timezone if company_settings else "America/Chicago"
    local_today = datetime.now(pytz.UTC).astimezone(pytz.timezone(tz_name)).date()
    forecast_dates = _current_week_dates(local_today)
    forecasts = get_team_forecast(
        g.organization_id, g.workspace_id, forecast_dates[0], forecast_dates[-1]
    )
    from ..queries.forecast import get_team_schedules_for_board
    team_schedules = get_team_schedules_for_board(g.organization_id, g.workspace_id)
    return forecast_dates, forecasts, local_today, team_schedules


@blueprint.route("/")
@login_required
@board_required
def index() -> ResponseReturnValue:
    """In/Out Board - show all members' clock status."""
    members = ClockPunch.get_clocked_in_members()
    forecast_dates, forecasts, local_today, team_schedules = _get_forecast_context()

    return render_device_template(
        "presence/desktop/board.html",
        module_home="dashboard_bp.index",
        members=members,
        active_page="board",
        forecast_dates=forecast_dates,
        forecasts=forecasts,
        team_schedules=team_schedules,
        today=local_today,
    )


@blueprint.route("/partial")
@login_required
@board_required
def partial() -> ResponseReturnValue:
    """Get board list partial (HTMX polling)."""
    members = ClockPunch.get_clocked_in_members()
    forecast_dates, forecasts, local_today, team_schedules = _get_forecast_context()

    return render_device_template(
        "presence/desktop/partials/board_list.html",
        members=members,
        forecast_dates=forecast_dates,
        forecasts=forecasts,
        team_schedules=team_schedules,
        today=local_today,
    )


# --- Public Board Routes (no login required) ---


@blueprint.route("/public/<token>")
def public_board(token: str) -> ResponseReturnValue:
    """Public In/Out Board for TV display - no login required."""
    if not TimeTrackingSettings.validate_public_token(token):
        abort(404)

    # Get company timezone for display
    company_settings = g.get("company_settings")
    tz_name = company_settings.timezone if company_settings else "America/Chicago"
    local_tz = pytz.timezone(tz_name)
    local_now = datetime.now(pytz.UTC).astimezone(local_tz)

    members = ClockPunch.get_clocked_in_members()
    return render_device_template(
        "presence/desktop/board_public.html",
        members=members,
        token=token,
        today=local_now,
        timezone=tz_name,
    )


@blueprint.route("/public/<token>/partial")
def public_board_partial(token: str) -> ResponseReturnValue:
    """HTMX partial for public board polling."""
    if not TimeTrackingSettings.validate_public_token(token):
        abort(404)

    members = ClockPunch.get_clocked_in_members()
    return render_device_template(
        "presence/desktop/partials/_board_public_list.html",
        members=members,
    )


# --- Admin Edit Routes ---


@blueprint.route("/edit/<int:member_id>")
@login_required
@admin_required
def edit_clock_in_modal(member_id: int) -> ResponseReturnValue:
    """Render the edit clock-in modal for a member."""
    member = OrganizationUser.query.filter_by(organization_id=g.organization_id, id=member_id).options(joinedload(OrganizationUser.user)).first_or_404()

    # Get the current clock-in punch
    clock_in_punch = ClockPunch.get_last_clock_in(member_id)
    if not clock_in_punch:
        flash(_("Employee is not currently clocked in"), "error")
        return redirect(url_for("board_bp.index"))

    # Convert to company timezone for display
    company_settings = g.get("company_settings")
    tz_name = company_settings.timezone if company_settings else "America/Chicago"
    local_tz = pytz.timezone(tz_name)
    clock_in_local = clock_in_punch.punch_time.replace(tzinfo=pytz.UTC).astimezone(local_tz)

    return render_device_template(
        "presence/desktop/partials/_edit_clock_in_modal.html",
        member=member,
        clock_in_punch=clock_in_punch,
        clock_in_local=clock_in_local,
    )


@blueprint.route("/edit/<int:member_id>", methods=["POST"])
@login_required
@admin_required
def save_clock_in_edit(member_id: int) -> ResponseReturnValue:
    """Save the updated clock-in time."""
    member = OrganizationUser.query.filter_by(organization_id=g.organization_id, id=member_id).options(joinedload(OrganizationUser.user)).first_or_404()

    # Get the current clock-in punch
    clock_in_punch = ClockPunch.get_last_clock_in(member_id)
    if not clock_in_punch:
        flash(_("Employee is not currently clocked in"), "error")
        members = ClockPunch.get_clocked_in_members()
        return render_device_template(
            "presence/desktop/partials/board_list.html",
            members=members,
        )

    # Get company timezone
    company_settings = g.get("company_settings")
    tz_name = company_settings.timezone if company_settings else "America/Chicago"
    local_tz = pytz.timezone(tz_name)
    original_local = clock_in_punch.punch_time.replace(tzinfo=pytz.UTC).astimezone(local_tz)

    def _render_modal_error(error_msg: str) -> ResponseReturnValue:
        """Re-render the edit modal with an inline error message."""
        return render_device_template(
            "presence/desktop/partials/_edit_clock_in_modal.html",
            member=member,
            clock_in_punch=clock_in_punch,
            clock_in_local=original_local,
            error=error_msg,
        ), 422

    # Get form data
    new_time_str = request.form.get("new_time")

    if not new_time_str:
        return _render_modal_error(_("New time is required"))

    # Delegate parsing, validation, audit trail, and update to the model
    error = clock_in_punch.update_clock_in_time(new_time_str, tz_name, current_user.id)
    if error:
        return _render_modal_error(_(error))

    flash(f"{_('Clock-in time updated for')} {member.user.full_name}", "success")

    # Clear modal and refresh board list
    response = make_response("")
    response.headers["HX-Trigger"] = "boardUpdated"
    return response


@blueprint.route("/punch/<int:member_id>", methods=["POST"])
@login_required
@admin_required
def buddy_punch(member_id: int) -> ResponseReturnValue:
    """Admin buddy punch - clock in a member on their behalf."""
    member = OrganizationUser.query.filter_by(organization_id=g.organization_id, id=member_id).options(joinedload(OrganizationUser.user)).first_or_404()

    # Check if already clocked in
    if ClockPunch.is_clocked_in(member_id):
        flash(f"{member.user.full_name} {_('is already clocked in')}", "warning")
    else:
        # Clock in with source="admin" to identify buddy punch
        ClockPunch.clock_in(
            member_id,
            source="admin",
            ip_address=request.remote_addr,
        )
        flash(f"{_('Clocked in')} {member.user.full_name}", "success")

    # Return updated board list
    members = ClockPunch.get_clocked_in_members()
    return render_device_template(
        "presence/desktop/partials/board_list.html",
        members=members,
    )


@blueprint.route("/clock-out/<int:member_id>", methods=["POST"])
@login_required
@admin_required
def buddy_clock_out(member_id: int) -> ResponseReturnValue:
    """Admin buddy clock-out - clock out a member on their behalf."""
    member = OrganizationUser.query.filter_by(organization_id=g.organization_id, id=member_id).options(joinedload(OrganizationUser.user)).first_or_404()

    # Check if actually clocked in
    if not ClockPunch.is_clocked_in(member_id):
        flash(f"{member.user.full_name} {_('is not clocked in')}", "warning")
    else:
        # Clock out with source="admin" to identify buddy clock-out
        ClockPunch.clock_out(
            member_id,
            source="admin",
            ip_address=request.remote_addr,
        )
        flash(f"{_('Clocked out')} {member.user.full_name}", "success")

    # Return updated board list
    members = ClockPunch.get_clocked_in_members()
    return render_device_template(
        "presence/desktop/partials/board_list.html",
        members=members,
    )


@blueprint.route("/clear-modal")
@login_required
def clear_modal() -> ResponseReturnValue:
    """Clear the modal container (HTMX endpoint)."""
    return ""
