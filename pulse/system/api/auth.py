# -----------------------------------------------------------------------------
# sparQ — Mobile API Auth Endpoints
#
# JWT authentication endpoints for the mobile app: login, refresh, logout,
# magic-link, and OAuth callback. All responses are JSON.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

import logging

from flask import Blueprint, jsonify, request

from system.api.decorators import jwt_required
from system.api.errors import api_error_response, validate_required
from system.api.jwt import (
    create_access_token,
    create_refresh_token,
    revoke_all_user_tokens,
    revoke_refresh_token,
    verify_refresh_token,
)
from system.middleware.ratelimit import rate_limit

logger = logging.getLogger(__name__)

auth_bp = Blueprint("api_auth", __name__, url_prefix="/auth")


@auth_bp.route("/login", methods=["POST"])
@rate_limit(limit=10, window=60)
def login():
    """Authenticate with email and password, return JWT pair.

    Request body:
        {"email": "...", "password": "...", "device_info": "..." (optional)}

    Returns:
        200: {"access_token", "refresh_token", "expires_in", "user"}
        401: Invalid credentials, locked account, or inactive user.
    """
    data = request.get_json(silent=True)
    errors = validate_required(data, ["email", "password"])
    if errors:
        return api_error_response("VALIDATION_ERROR", "Missing required fields", 400, errors)

    from modules.base.core.models.user import User

    user = User.get_by_email(data["email"])
    if not user:
        return api_error_response("INVALID_CREDENTIALS", "Invalid email or password", 401)

    if user.is_locked:
        return api_error_response("ACCOUNT_LOCKED", "Account is temporarily locked due to too many failed attempts", 401)

    if not user.check_password(data["password"]):
        user.record_failed_login()
        return api_error_response("INVALID_CREDENTIALS", "Invalid email or password", 401)

    if not user.is_active:
        return api_error_response("ACCOUNT_INACTIVE", "Account is deactivated", 401)

    user.reset_failed_logins()

    device_info = data.get("device_info")
    access_token, expires_in = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id, device_info=device_info)

    return jsonify({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": expires_in,
        "user": user.to_dict(),
    })


@auth_bp.route("/refresh", methods=["POST"])
def refresh():
    """Exchange a refresh token for a new JWT pair (token rotation).

    Request body:
        {"refresh_token": "...", "device_info": "..." (optional)}

    Returns:
        200: {"access_token", "refresh_token", "expires_in"}
        401: Invalid, expired, or revoked refresh token.
    """
    data = request.get_json(silent=True)
    errors = validate_required(data, ["refresh_token"])
    if errors:
        return api_error_response("VALIDATION_ERROR", "Missing required fields", 400, errors)

    record = verify_refresh_token(data["refresh_token"])
    if not record:
        return api_error_response("INVALID_TOKEN", "Refresh token is invalid, expired, or revoked", 401)

    # Rotate: revoke old, issue new
    record.revoke()

    device_info = data.get("device_info") or record.device_info
    access_token, expires_in = create_access_token(record.user_id)
    new_refresh_token = create_refresh_token(record.user_id, device_info=device_info)

    return jsonify({
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "expires_in": expires_in,
    })


@auth_bp.route("/logout", methods=["POST"])
@jwt_required
def logout():
    """Revoke a specific refresh token (single device logout).

    Request body:
        {"refresh_token": "..."}

    Returns:
        200: {"status": "ok"}
    """

    data = request.get_json(silent=True)
    if data and data.get("refresh_token"):
        revoke_refresh_token(data["refresh_token"])

    return jsonify({"status": "ok"})


@auth_bp.route("/logout/all", methods=["POST"])
@jwt_required
def logout_all():
    """Revoke all refresh tokens for the current user (all-device logout).

    Returns:
        200: {"status": "ok", "revoked": <count>}
    """
    from flask import g

    count = revoke_all_user_tokens(g.current_user.id)
    return jsonify({"status": "ok", "revoked": count})


@auth_bp.route("/magic-link", methods=["POST"])
@rate_limit(limit=5, window=300)
def magic_link_request():
    """Request a magic link for passwordless login.

    Generates a token and sends an email with a deep link
    (sparq://auth/magic-link?token=...) for the mobile app.

    Request body:
        {"email": "..."}

    Returns:
        200: {"status": "ok"} (always, to prevent email enumeration)
    """
    data = request.get_json(silent=True)
    errors = validate_required(data, ["email"])
    if errors:
        return api_error_response("VALIDATION_ERROR", "Missing required fields", 400, errors)

    from modules.base.core.models.user import User

    user = User.get_by_email(data["email"])
    if user and user.is_active:
        token = user.generate_magic_link_token()
        deep_link = f"sparq://auth/magic-link?token={token}"

        try:
            from system.email.service import send_email_async
            send_email_async(
                to=user.email,
                subject="Your sparQ login link",
                html_body=f'<p>Tap the link below to sign in to sparQ:</p><p><a href="{deep_link}">Sign in to sparQ</a></p><p>This link expires in 15 minutes.</p>',
                text_body=f"Sign in to sparQ: {deep_link}\n\nThis link expires in 15 minutes.",
            )
        except Exception:
            logger.exception("Failed to send magic link email")

    # Always return ok to prevent email enumeration
    return jsonify({"status": "ok"})


@auth_bp.route("/magic-link/verify", methods=["POST"])
@rate_limit(limit=10, window=60)
def magic_link_verify():
    """Exchange a magic link token for a JWT pair.

    Request body:
        {"token": "...", "device_info": "..." (optional)}

    Returns:
        200: {"access_token", "refresh_token", "expires_in", "user"}
        401: Invalid or expired magic link token.
    """
    data = request.get_json(silent=True)
    errors = validate_required(data, ["token"])
    if errors:
        return api_error_response("VALIDATION_ERROR", "Missing required fields", 400, errors)

    from modules.base.core.models.user import User

    user = User.get_by_magic_link_token(data["token"])
    if not user:
        return api_error_response("INVALID_TOKEN", "Magic link is invalid or expired", 401)

    if not user.is_active:
        return api_error_response("ACCOUNT_INACTIVE", "Account is deactivated", 401)

    user.clear_magic_link_token()

    device_info = data.get("device_info")
    access_token, expires_in = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id, device_info=device_info)

    return jsonify({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": expires_in,
        "user": user.to_dict(),
    })


@auth_bp.route("/oauth/callback", methods=["POST"])
@rate_limit(limit=10, window=60)
def oauth_callback():
    """Exchange an OAuth authorization code for a JWT pair.

    Mobile app performs OAuth natively (PKCE), then sends the code
    to this endpoint. Server exchanges code for tokens, fetches
    userinfo, finds/creates the user, and returns a JWT pair.

    Request body:
        {"provider": "google", "code": "...", "code_verifier": "...",
         "redirect_uri": "...", "device_info": "..." (optional)}

    Returns:
        200: {"access_token", "refresh_token", "expires_in", "user"}
        401: OAuth exchange failed or provider not configured.
    """
    data = request.get_json(silent=True)
    errors = validate_required(data, ["provider", "code", "redirect_uri"])
    if errors:
        return api_error_response("VALIDATION_ERROR", "Missing required fields", 400, errors)

    provider_name = data["provider"].lower()

    from system.oauth.service import get_client_credentials, get_oauth_client

    client = get_oauth_client(provider_name)
    if not client:
        return api_error_response("INVALID_PROVIDER", f"Unknown or unconfigured provider: {provider_name}", 401)

    client_id, client_secret = get_client_credentials(provider_name)
    if not client_id or not client_secret:
        return api_error_response("PROVIDER_NOT_CONFIGURED", "OAuth provider is not configured", 401)

    # Exchange authorization code for tokens
    try:
        client.client_id = client_id
        client.client_secret = client_secret

        token_endpoint = client.access_token_url
        token_data = {
            "grant_type": "authorization_code",
            "code": data["code"],
            "redirect_uri": data["redirect_uri"],
        }
        if data.get("code_verifier"):
            token_data["code_verifier"] = data["code_verifier"]

        client.fetch_access_token(
            url=token_endpoint,
            **token_data,
        )
    except Exception:
        logger.exception("OAuth token exchange failed")
        return api_error_response("OAUTH_ERROR", "Failed to exchange authorization code", 401)

    # Fetch user info
    try:
        userinfo = client.userinfo()
    except Exception:
        logger.exception("OAuth userinfo fetch failed")
        return api_error_response("OAUTH_ERROR", "Failed to fetch user info", 401)

    email = userinfo.get("email")
    if not email:
        return api_error_response("OAUTH_ERROR", "Provider did not return an email address", 401)

    # Find or create user
    from modules.base.core.models.user import User

    user = User.get_by_email(email)
    if not user:
        user = User.create_from_oauth(
            email=email,
            first_name=userinfo.get("given_name"),
            last_name=userinfo.get("family_name"),
        )

    if not user.is_active:
        return api_error_response("ACCOUNT_INACTIVE", "Account is deactivated", 401)

    device_info = data.get("device_info")
    access_token, expires_in = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id, device_info=device_info)

    return jsonify({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": expires_in,
        "user": user.to_dict(),
    })
