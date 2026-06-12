# -----------------------------------------------------------------------------
# sparQ - Current Member Helper
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# Licensed under the GNU Affero General Public License v3.0 — see LICENSE
# -----------------------------------------------------------------------------

"""Per-request cached lookup for the current user's WorkspaceUser.

A typical page render touches this row from many places (template context
processors, sidebar partials, controllers). Without caching, each call
issues its own SELECT, adding up to 30+ duplicate queries on a single page.
This helper caches the row on ``flask.g`` so the DB is hit at most once
per request.
"""

from flask import g
from flask_login import current_user

_UNSET = object()


def current_member():
    """Return the WorkspaceUser for the logged-in user, or None.

    Cached on ``g._current_member_cache`` for the lifetime of the request.
    Returns None when the user is anonymous, or when the lookup fails
    (e.g. workspace context not yet established on this request).
    """
    if not current_user.is_authenticated:
        return None
    cached = getattr(g, "_current_member_cache", _UNSET)
    if cached is not _UNSET:
        return cached
    try:
        from modules.base.core.models.workspace_user import WorkspaceUser
        member = WorkspaceUser.get_by_user_id(current_user.id)
    except Exception:
        member = None
    g._current_member_cache = member
    return member
