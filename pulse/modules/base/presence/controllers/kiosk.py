# -----------------------------------------------------------------------------
# sparQ - Kiosk Time Clock Routes
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from datetime import datetime

import pytz
from flask import Blueprint, abort, g, render_template, request

from system.i18n.translation import translate as _

from ..models.clock_punch import ClockPunch
from ..models.settings import TimeTrackingSettings

blueprint = Blueprint(
    "kiosk_bp",
    __name__,
    template_folder="../views/templates",
    static_folder="../views/assets",
)


@blueprint.route("/")
def index():
    """Kiosk PIN entry page - no login required."""
    if not TimeTrackingSettings.is_time_clock_enabled():
        abort(404)

    # Get company timezone for display
    company_settings = g.get("company_settings")
    tz_name = company_settings.timezone if company_settings else "America/Chicago"
    local_tz = pytz.timezone(tz_name)
    local_now = datetime.now(pytz.UTC).astimezone(local_tz)

    return render_template(
        "presence/desktop/kiosk.html",
        today=local_now,
        timezone=tz_name,
    )


@blueprint.route("/punch", methods=["POST"])
def punch():
    """Process kiosk punch via PIN."""
    if not TimeTrackingSettings.is_time_clock_enabled():
        abort(404)

    pin = request.form.get("pin", "").strip()

    # Validate PIN format
    if len(pin) != 4 or not pin.isdigit():
        return render_template(
            "presence/desktop/partials/kiosk_error.html",
            error=_("Invalid PIN format"),
        )

    # Look up member by PIN
    member = ClockPunch.get_employee_by_pin(pin)
    if not member:
        return render_template(
            "presence/desktop/partials/kiosk_error.html",
            error=_("PIN not found"),
        )

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
        return render_template(
            "presence/desktop/partials/kiosk_blocked.html",
            member=member,
        )

    # Split any overnight punches before processing clock-out
    ClockPunch.split_overnight_punches(member_id=member.id)

    # Clock in or out
    try:
        if ClockPunch.is_clocked_in(member.id):
            punch = ClockPunch.clock_out(
                member.id,
                source="kiosk",
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
                source="kiosk",
                ip_address=ip_address,
                latitude=latitude,
                longitude=longitude,
                location_accuracy=location_accuracy,
                location_denied=location_denied,
            )
            action = "in"

        return render_template(
            "presence/desktop/partials/kiosk_success.html",
            member=member,
            action=action,
            outside_geofence=punch.outside_geofence,
        )
    except ValueError as e:
        return render_template(
            "presence/desktop/partials/kiosk_error.html",
            error=str(e),
        )
