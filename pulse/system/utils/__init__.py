# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Utility functions module initialization.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

"""System utility functions for sparQ applications.

This package provides common utility functions for network operations,
HTTP responses, and input validation.

Submodules:
    network: Network utilities (IP detection).
    responses: HTMX and API response helpers.
    validation: Input validation and guard clauses.

Example:
    Using HTMX response helpers::

        from system.utils.responses import htmx_redirect, htmx_refresh

        @route("/save", methods=["POST"])
        def save():
            # Process form...
            return htmx_redirect("mymodule_bp.index")

    Using validation helpers::

        from system.utils.validation import require_fields, validate_email

        @route("/register", methods=["POST"])
        def register():
            require_fields("email", "password")
            validate_email(request.form["email"])
            # Continue processing...

    Using API response helpers::

        from system.utils.responses import api_response, api_error

        @route("/api/items")
        def api_items():
            items = Item.query.all()
            return api_response(data=[i.to_dict() for i in items])
"""

from system.utils.responses import htmx_redirect, htmx_refresh, api_response, api_error
from system.utils.validation import require_fields, require_json_fields, validate_email
from system.utils.network import get_local_ip
from system.utils.calendar_utils import get_first_day_of_week, get_python_firstweekday, get_week_start, get_week_dates_list, get_month_calendar_weeks, get_weekday_headers

__all__ = [
    "htmx_redirect",
    "htmx_refresh",
    "api_response",
    "api_error",
    "require_fields",
    "require_json_fields",
    "validate_email",
    "get_local_ip",
    "get_first_day_of_week",
    "get_python_firstweekday",
    "get_week_start",
    "get_week_dates_list",
    "get_month_calendar_weeks",
    "get_weekday_headers",
]
