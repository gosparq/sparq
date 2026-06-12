# -----------------------------------------------------------------------------
# sparQ — API Error Handlers
#
# JSON error handlers for the /api/v1/ blueprint. Returns standardized
# error responses: {"error": {"code": "...", "message": "...", "details": {}}}
#
# Does NOT modify system/utils/responses.py (different shape, used by web).
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from flask import jsonify


def api_error_response(code: str, message: str, status: int = 400, details: dict | None = None):
    """Build a standardized API error response.

    Args:
        code: Machine-readable error code (e.g. "UNAUTHORIZED", "VALIDATION_ERROR").
        message: Human-readable error message.
        status: HTTP status code.
        details: Optional additional error details.

    Returns:
        Tuple of (Flask JSON response, HTTP status code).
    """
    payload = {
        "error": {
            "code": code,
            "message": message,
        }
    }
    if details:
        payload["error"]["details"] = details
    return jsonify(payload), status


def validate_required(data: dict | None, fields: list[str]) -> dict | None:
    """Check that required fields are present in request data.

    Args:
        data: Parsed JSON request body (may be None).
        fields: List of required field names.

    Returns:
        Error details dict if validation fails, None if all fields present.
    """
    if not data:
        return {"missing": fields}

    missing = [f for f in fields if not data.get(f)]
    if missing:
        return {"missing": missing}
    return None


def register_api_error_handlers(bp) -> None:
    """Register JSON error handlers on the API blueprint.

    Converts standard HTTP errors to the API error shape so mobile
    clients always receive JSON, never HTML error pages.

    Args:
        bp: Flask blueprint to register handlers on.
    """

    @bp.app_errorhandler(400)
    def bad_request(e):
        if not _is_api_request():
            return e
        return api_error_response("BAD_REQUEST", str(e.description), 400)

    @bp.app_errorhandler(401)
    def unauthorized(e):
        if not _is_api_request():
            return e
        return api_error_response("UNAUTHORIZED", "Authentication required", 401)

    @bp.app_errorhandler(403)
    def forbidden(e):
        if not _is_api_request():
            return e
        return api_error_response("FORBIDDEN", "Access denied", 403)

    @bp.app_errorhandler(404)
    def not_found(e):
        if not _is_api_request():
            return e
        return api_error_response("NOT_FOUND", "Resource not found", 404)

    @bp.app_errorhandler(429)
    def rate_limited(e):
        if not _is_api_request():
            return e
        return api_error_response("RATE_LIMITED", "Too many requests", 429)

    @bp.app_errorhandler(500)
    def server_error(e):
        if not _is_api_request():
            return e
        return api_error_response("SERVER_ERROR", "Internal server error", 500)


def _is_api_request() -> bool:
    """Check if the current request is for the API.

    Returns True if the request path starts with /api/ so that
    error handlers only intercept API requests, not web routes.
    """
    from flask import request
    return request.path.startswith("/api/")
