# -----------------------------------------------------------------------------
# sparQ — JWT Utilities
#
# Creates and verifies JWT access/refresh tokens for mobile API auth.
# Access tokens: 1hr, HS256. Refresh tokens: 30 days, stored as SHA-256
# hashes in the RefreshToken model.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from datetime import datetime, timedelta, timezone

import jwt
from flask import current_app

ACCESS_TOKEN_EXPIRY = timedelta(hours=1)
REFRESH_TOKEN_EXPIRY_DAYS = 30


def _get_secret() -> str:
    """Get JWT signing secret from app config.

    Returns:
        JWT secret key string.
    """
    return current_app.config.get("JWT_SECRET_KEY") or current_app.config["SECRET_KEY"]


def create_access_token(user_id: int, workspace_id: str | None = None) -> tuple[str, int]:
    """Create a JWT access token.

    Args:
        user_id: ID of the authenticated user.
        workspace_id: Optional workspace UUID string. If not provided,
            the user's first workspace membership is used.

    Returns:
        Tuple of (token string, expires_in seconds).
    """
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": user_id,
        "type": "access",
        "iat": now,
        "exp": now + ACCESS_TOKEN_EXPIRY,
    }

    # Include workspace_id if available
    if workspace_id:
        payload["workspace_id"] = workspace_id
    else:
        # Auto-resolve: pick the user's earliest membership (deterministic)
        from modules.base.core.models.workspace_user import WorkspaceUser
        membership = (
            WorkspaceUser.query
            .filter_by(user_id=user_id)
            .order_by(WorkspaceUser.id.asc())
            .first()
        )
        if membership:
            payload["workspace_id"] = str(membership.workspace_id)

    token = jwt.encode(payload, _get_secret(), algorithm="HS256")
    return token, int(ACCESS_TOKEN_EXPIRY.total_seconds())


def create_refresh_token(user_id: int, device_info: str | None = None) -> str:
    """Create a refresh token and store its hash in the database.

    Args:
        user_id: ID of the authenticated user.
        device_info: Optional device identifier.

    Returns:
        Raw refresh token string.
    """
    from system.api.models import RefreshToken
    return RefreshToken.create_for_user(user_id, device_info=device_info, expires_days=REFRESH_TOKEN_EXPIRY_DAYS)


def verify_access_token(token: str) -> dict | None:
    """Verify and decode a JWT access token.

    Args:
        token: JWT token string.

    Returns:
        Decoded payload dict if valid, None if invalid/expired.
    """
    try:
        payload = jwt.decode(token, _get_secret(), algorithms=["HS256"])
        if payload.get("type") != "access":
            return None
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def verify_refresh_token(raw_token: str):
    """Verify a refresh token against the database.

    Args:
        raw_token: Raw refresh token string.

    Returns:
        RefreshToken record if valid, None if invalid/expired/revoked.
    """
    from system.api.models import RefreshToken
    return RefreshToken.verify(raw_token)


def revoke_refresh_token(raw_token: str) -> bool:
    """Revoke a specific refresh token.

    Args:
        raw_token: Raw refresh token string.

    Returns:
        True if token was found and revoked, False otherwise.
    """
    from system.api.models import RefreshToken
    record = RefreshToken.verify(raw_token)
    if record:
        record.revoke()
        return True
    return False


def revoke_all_user_tokens(user_id: int) -> int:
    """Revoke all refresh tokens for a user.

    Args:
        user_id: ID of the user.

    Returns:
        Number of tokens revoked.
    """
    from system.api.models import RefreshToken
    return RefreshToken.revoke_all_for_user(user_id)
