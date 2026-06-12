# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Response utilities for HTMX and API responses.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

"""Response utilities for HTMX and JSON API responses.

This module provides helper functions for creating standardized
HTTP responses in sparQ applications.

HTMX Response Helpers:
    htmx_redirect: Trigger a full page redirect via HTMX.
    htmx_refresh: Trigger a full page refresh via HTMX.

API Response Helpers:
    api_response: Create a standardized JSON response.
    api_error: Shortcut for error responses.

Example:
    HTMX form submission with redirect::

        @route("/items/create", methods=["POST"])
        def create():
            Item.create(name=request.form["name"])
            return htmx_redirect("items_bp.index")

    API endpoint with standardized responses::

        @route("/api/items/<int:id>")
        def get_item(id):
            item = Item.query.get(id)
            if not item:
                return api_error("Item not found", status=404)
            return api_response(data=item.to_dict())
"""

from typing import Any
from flask import Response, jsonify, make_response, url_for


def htmx_redirect(endpoint: str, **kwargs: Any) -> Response:
    """Create an HTMX redirect response.

    Use this when handling HTMX form submissions that should
    trigger a full page redirect.

    Args:
        endpoint: Flask endpoint name (e.g., 'core_bp.index')
        **kwargs: URL parameters for url_for

    Returns:
        Flask response with HX-Redirect header

    Example:
        @blueprint.route("/create", methods=["POST"])
        def create():
            Item.create(request.form.get("name"))
            return htmx_redirect("yourmodule_bp.index")
    """
    response = make_response()
    response.headers["HX-Redirect"] = url_for(endpoint, **kwargs)
    return response


def htmx_refresh() -> Response:
    """Create an HTMX refresh response.

    Triggers a full page refresh via HTMX.

    Returns:
        Flask response with HX-Refresh header
    """
    response = make_response()
    response.headers["HX-Refresh"] = "true"
    return response


def api_response(
    success: bool = True, data: Any = None, error: str | None = None, status: int = 200
) -> tuple[Response, int]:
    """Create a standardized API JSON response.

    Args:
        success: Whether the operation succeeded
        data: Response data (dict, list, or serializable)
        error: Error message if not successful
        status: HTTP status code

    Returns:
        Flask JSON response

    Example:
        @blueprint.route("/api/items")
        def api_items():
            items = Item.get_all()
            return api_response(data=[i.to_dict() for i in items])

        @blueprint.route("/api/items/<int:id>")
        def api_item(id):
            item = Item.get_by_id(id)
            if not item:
                return api_response(success=False, error="Not found", status=404)
            return api_response(data=item.to_dict())
    """
    response_data: dict[str, Any] = {"success": success}

    if data is not None:
        response_data["data"] = data

    if error is not None:
        response_data["error"] = error

    return jsonify(response_data), status


def api_error(message: str, status: int = 400) -> tuple[Response, int]:
    """Create an API error response.

    Shortcut for api_response with success=False.

    Args:
        message: Error message
        status: HTTP status code (default 400)

    Returns:
        Flask JSON response
    """
    return api_response(success=False, error=message, status=status)
