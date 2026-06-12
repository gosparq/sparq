# -----------------------------------------------------------------------------
# sparQ — Pagination Helper
#
# Standardized paginated JSON responses for API list endpoints.
# Caps per_page at 100 to prevent abuse.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from flask import jsonify, request

MAX_PER_PAGE = 100
DEFAULT_PER_PAGE = 20


def paginated_response(query, serialize=None, page=None, per_page=None):
    """Execute a paginated query and return a standardized JSON response.

    Args:
        query: SQLAlchemy query object (unpaginated).
        serialize: Optional callable to convert each item. Defaults to item.to_dict().
        page: Page number (defaults to request.args['page'] or 1).
        per_page: Items per page (defaults to request.args['per_page'] or 20, max 100).

    Returns:
        Flask JSON response with shape:
        {
            "items": [...],
            "pagination": {
                "page": int,
                "per_page": int,
                "total": int,
                "pages": int,
                "has_next": bool,
                "has_prev": bool
            }
        }
    """
    if page is None:
        page = request.args.get("page", 1, type=int)
    if per_page is None:
        per_page = request.args.get("per_page", DEFAULT_PER_PAGE, type=int)

    page = max(1, page)
    per_page = max(1, min(per_page, MAX_PER_PAGE))

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    if serialize is None:
        def serialize(item):
            return item.to_dict()

    return jsonify({
        "items": [serialize(item) for item in pagination.items],
        "pagination": {
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "pages": pagination.pages,
            "has_next": pagination.has_next,
            "has_prev": pagination.has_prev,
        },
    })
