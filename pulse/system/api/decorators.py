# -----------------------------------------------------------------------------
# sparQ — JWT Decorators
#
# Route decorators for JWT-protected API endpoints. Extract Bearer token
# from Authorization header, verify, and set g.current_user.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from functools import wraps

from flask import g, request

from system.api.errors import api_error_response
from system.api.jwt import verify_access_token


def jwt_required(f):
    """Require a valid JWT access token.

    Extracts Bearer token from Authorization header, verifies it,
    loads the User, checks is_active, and sets g.current_user.

    Returns 401 on missing/invalid/expired token or inactive user.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return api_error_response("UNAUTHORIZED", "Missing or invalid Authorization header", 401)

        token = auth_header[7:]
        payload = verify_access_token(token)
        if not payload:
            return api_error_response("TOKEN_EXPIRED", "Token is invalid or expired", 401)

        from modules.base.core.models.user import User
        user = User.get_by_id(payload["user_id"])
        if not user or not user.is_active:
            return api_error_response("UNAUTHORIZED", "User not found or inactive", 401)

        g.current_user = user

        # Set workspace + organization context from JWT claim — verify user actually belongs.
        workspace_id = payload.get("workspace_id")
        if workspace_id:
            import uuid
            try:
                ws_id = uuid.UUID(workspace_id)
            except (ValueError, AttributeError):
                return api_error_response("INVALID_TOKEN", "Invalid workspace_id in token", 401)

            from modules.base.core.models.workspace import Workspace
            from modules.base.core.models.workspace_user import WorkspaceUser
            membership = WorkspaceUser.query.filter_by(
                user_id=user.id, workspace_id=ws_id
            ).filter(WorkspaceUser.deleted_at.is_(None)).first()
            if not membership:
                return api_error_response("FORBIDDEN", "User does not belong to this workspace", 403)
            g.workspace_id = ws_id
            ts = Workspace.query.get(ws_id)
            if ts:
                g.organization_id = ts.organization_id

        return f(*args, **kwargs)

    return decorated


def jwt_admin_required(f):
    """Require a valid JWT token from an admin user.

    Applies jwt_required first, then checks admin group membership.
    Returns 403 if user is not an admin.
    """
    @wraps(f)
    @jwt_required
    def decorated(*args, **kwargs):
        if not g.current_user.is_admin:
            return api_error_response("FORBIDDEN", "Admin access required", 403)
        return f(*args, **kwargs)

    return decorated


def jwt_permission_required(*areas):
    """Require a valid JWT token from a user with one of the specified permission areas.

    Args:
        *areas: Permission area names the user must have (at least one).

    Returns 403 if user does not have any of the specified permissions.
    Admins always pass.
    """
    def decorator(f):
        @wraps(f)
        @jwt_required
        def decorated(*args, **kwargs):
            user = g.current_user
            if any(user.has_access(area) for area in areas):
                return f(*args, **kwargs)

            return api_error_response("FORBIDDEN", "Insufficient permissions", 403)

        return decorated
    return decorator


# Backward compat alias
jwt_group_required = jwt_permission_required
