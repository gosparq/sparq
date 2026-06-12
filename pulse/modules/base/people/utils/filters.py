# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Team module filters for custom template filters.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

from datetime import datetime, timezone

import humanize
from flask import Blueprint, Flask


def timeago_filter(value: datetime | str | None) -> str:
    """Convert datetime to '... time ago' text"""
    if not value:
        return ""

    try:
        if isinstance(value, str):
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))

        if value.tzinfo is not None:
            now = datetime.now(timezone.utc)
        else:
            now = datetime.utcnow()

        return humanize.naturaltime(now - value)  # type: ignore[no-any-return]
    except Exception as e:
        print(f"Error in timeago filter: {e}")
        return ""


def init_filters(app: Flask | Blueprint) -> None:
    """Initialize custom template filters"""
    # Register with both app and blueprint
    if isinstance(app, Blueprint):
        app.add_app_template_filter(timeago_filter, "timeago")
    else:
        app.jinja_env.filters["timeago"] = timeago_filter
        # Also register as a template filter
        app.template_filter("timeago")(timeago_filter)
