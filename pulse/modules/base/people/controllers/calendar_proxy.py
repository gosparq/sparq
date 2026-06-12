# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

"""Calendar and Timesheets proxy routes under /people/.

Proxies Calendar (formerly /sync/calendar/) and Timesheets (formerly
/presence/week) into the People section for unified navigation.
"""

from flask import redirect, url_for
from flask_login import login_required

from . import blueprint


@blueprint.route("/calendar/")
@login_required
def calendar():
    """Calendar — proxy to sync calendar routes."""
    return redirect(url_for("sync_bp.calendar_index"))


@blueprint.route("/timesheets/")
@login_required
def timesheets():
    """Timesheets — proxy to presence routes."""
    return redirect(url_for("presence_bp.week_view"))
