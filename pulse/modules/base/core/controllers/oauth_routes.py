# -----------------------------------------------------------------------------
# sparQ - OAuth Routes
#
# Description:
#     OAuth 2.0 / OpenID Connect authentication routes for login, callback,
#     and account connection/disconnection.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

import logging

from flask import Blueprint, flash, g, redirect, request, session, url_for
from flask_login import current_user, login_required, login_user

from modules.base.core.models.oauth_connection import OAuthConnection
from modules.base.core.models.user import User
from system.oauth import oauth
from system.oauth.providers import get_provider
from system.oauth.service import (
    get_client_credentials,
    is_provider_enabled,
)
from system.oauth.token_manager import TokenManager

logger = logging.getLogger(__name__)

blueprint = Blueprint("oauth_bp", __name__, url_prefix="/auth/oauth")


@blueprint.route("/<provider>")
def login(provider: str):
    """Initiate OAuth login flow.

    Redirects user to the OAuth provider's authorization page.
    """
    provider = provider.lower()

    # Check if provider is enabled
    if not is_provider_enabled(provider):
        flash(f"{provider.title()} login is not available.", "error")
        return redirect(url_for("core_bp.login"))

    # Get provider config
    provider_config = get_provider(provider)
    if not provider_config:
        flash("Invalid authentication provider.", "error")
        return redirect(url_for("core_bp.login"))

    # Get OAuth client
    client = getattr(oauth, provider, None)
    if not client:
        flash("Authentication service unavailable.", "error")
        return redirect(url_for("core_bp.login"))

    # Get credentials and configure client
    client_id, client_secret = get_client_credentials(provider)
    if not client_id or not client_secret:
        flash(f"{provider.title()} is not configured.", "error")
        return redirect(url_for("core_bp.login"))

    client.client_id = client_id
    client.client_secret = client_secret

    # Build callback URL
    redirect_uri = url_for("oauth_bp.callback", provider=provider, _external=True)

    # Store next URL if provided
    next_url = request.args.get("next")
    if next_url:
        session["oauth_next"] = next_url

    # Store whether this is a connect (linking) request vs login
    if current_user.is_authenticated:
        session["oauth_connect"] = True

    # Redirect to provider
    return client.authorize_redirect(redirect_uri)


@blueprint.route("/<provider>/callback")
def callback(provider: str):
    """Handle OAuth callback from provider.

    Exchanges authorization code for tokens, fetches user info,
    and either logs in or connects the account.
    """
    provider = provider.lower()

    # Check if provider is enabled
    if not is_provider_enabled(provider):
        flash(f"{provider.title()} login is not available.", "error")
        return redirect(url_for("core_bp.login"))

    # Get provider config
    provider_config = get_provider(provider)
    if not provider_config:
        flash("Invalid authentication provider.", "error")
        return redirect(url_for("core_bp.login"))

    # Check for error from provider
    error = request.args.get("error")
    if error:
        error_description = request.args.get("error_description", "Authentication failed")
        logger.warning(f"OAuth error from {provider}: {error} - {error_description}")
        flash(f"Authentication failed: {error_description}", "error")
        return redirect(url_for("core_bp.login"))

    # Get OAuth client
    client = getattr(oauth, provider, None)
    if not client:
        flash("Authentication service unavailable.", "error")
        return redirect(url_for("core_bp.login"))

    # Configure client
    client_id, client_secret = get_client_credentials(provider)
    client.client_id = client_id
    client.client_secret = client_secret

    try:
        # Exchange code for token
        token = client.authorize_access_token()
    except Exception as e:
        logger.error(f"OAuth token exchange failed for {provider}: {e}")
        flash("Authentication failed. Please try again.", "error")
        return redirect(url_for("core_bp.login"))

    # Get user info from provider
    try:
        if provider_config.is_oidc:
            # OpenID Connect - parse ID token or fetch userinfo
            userinfo = token.get("userinfo") or client.userinfo()
        else:
            # OAuth 2.0 only (e.g., GitHub) - fetch from API
            resp = client.get(provider_config.userinfo_url)
            userinfo = resp.json()

            # GitHub special case: email might be null if private
            if provider == "github" and not userinfo.get("email"):
                # Fetch emails from GitHub API
                emails_resp = client.get("https://api.github.com/user/emails")
                emails = emails_resp.json()
                primary_email = next(
                    (e["email"] for e in emails if e.get("primary") and e.get("verified")),
                    None,
                )
                if primary_email:
                    userinfo["email"] = primary_email

    except Exception as e:
        logger.error(f"Failed to get user info from {provider}: {e}")
        flash("Failed to retrieve account information.", "error")
        return redirect(url_for("core_bp.login"))

    # Extract user data
    provider_user_id = str(userinfo.get(provider_config.user_id_field))
    email = userinfo.get(provider_config.email_field)
    first_name = userinfo.get("given_name") or userinfo.get("name", "").split()[0] if userinfo.get("name") else None
    last_name = userinfo.get("family_name") or (userinfo.get("name", "").split()[-1] if userinfo.get("name") and len(userinfo.get("name", "").split()) > 1 else None)

    if not email:
        flash("Could not retrieve email from provider.", "error")
        return redirect(url_for("core_bp.login"))

    # Encrypt tokens for storage
    access_token_encrypted = TokenManager.encrypt(token.get("access_token", ""))
    refresh_token_encrypted = TokenManager.encrypt(token.get("refresh_token", "")) if token.get("refresh_token") else None
    token_expires_at = TokenManager.calculate_expiry(token.get("expires_in"))

    # Check if this is a connect (linking) request
    is_connect = session.pop("oauth_connect", False)

    if is_connect and current_user.is_authenticated:
        # Connect to existing logged-in user
        OAuthConnection.create_or_update(
            user_id=current_user.id,
            provider=provider,
            provider_user_id=provider_user_id,
            email=email,
            access_token=access_token_encrypted,
            refresh_token=refresh_token_encrypted,
            token_expires_at=token_expires_at,
            scopes=" ".join(provider_config.scopes),
        )
        flash(f"{provider.title()} account connected successfully.", "success")
        return redirect(url_for("core_bp.settings_security"))

    # Login flow - find or create user
    # OAuth callback has no workspace context, so query globally first,
    # then set workspace context from the user's membership.

    from modules.base.core.models.pending_signup import route_new_signup, _seed_after_commit
    from modules.base.core.models.workspace_user import WorkspaceUser
    from system.db.database import db as _db

    signup_result = None

    # First, check if this OAuth connection already exists (global query)
    existing_connection = OAuthConnection.query.filter_by(
        provider=provider, provider_user_id=str(provider_user_id)
    ).first()

    if existing_connection:
        # User has logged in with this provider before
        user = _db.session.get(User, existing_connection.user_id)
        if not user:
            logger.warning(f"Orphaned OAuth connection: {provider}:{provider_user_id}")
            _db.session.delete(existing_connection)
            _db.session.commit()
            flash("Account error. Please try again.", "error")
            return redirect(url_for("core_bp.login"))

        # Set workspace context from user's membership
        membership = WorkspaceUser.query.filter_by(user_id=user.id).filter(WorkspaceUser.deleted_at.is_(None)).first()
        if membership:
            g.workspace_id = membership.workspace_id
            session["active_workspace_id"] = str(membership.workspace_id)

        # Update tokens
        existing_connection.access_token = access_token_encrypted
        if refresh_token_encrypted:
            existing_connection.refresh_token = refresh_token_encrypted
        if token_expires_at:
            existing_connection.token_expires_at = token_expires_at
        _db.session.commit()
    else:
        # No existing connection - check if email matches existing user
        user = User.query.filter_by(email=email).first()

        if user:
            logger.info(f"Auto-linking {provider} to existing user: {email}")
        else:
            # New user via OAuth — use shared 5-rule domain routing
            logger.info(f"Creating new user via OAuth {provider}: {email}")

            user = User(
                email=email,
                first_name=first_name,
                last_name=last_name,
            )
            _db.session.add(user)
            _db.session.flush()

            signup_result = route_new_signup(user)
            _db.session.commit()

            if signup_result.rule == 2 and signup_result.workspace and signup_result.ts_user:
                _seed_after_commit(signup_result.workspace, user, signup_result.ts_user)

            logger.info(f"OAuth signup rule {signup_result.rule} for {email}")

        # Set workspace/org context from user's membership
        membership = WorkspaceUser.query.filter_by(user_id=user.id).filter(WorkspaceUser.deleted_at.is_(None)).first()
        if membership:
            g.workspace_id = membership.workspace_id
            session["active_workspace_id"] = str(membership.workspace_id)

        # Set org context for OAuthConnection creation
        if signup_result and signup_result.primary_organization_id:
            g.organization_id = signup_result.primary_organization_id

        # Create/update OAuth connection.
        # OAuthConnection requires organization_id (NOT NULL via OrganizationMixin).
        # For rules 4/5 (personal shell, no org), skip creation — the email
        # auto-link path handles subsequent logins.
        existing_conn = OAuthConnection.query.filter_by(
            user_id=user.id, provider=provider
        ).first()

        if existing_conn:
            existing_conn.provider_user_id = str(provider_user_id)
            if email:
                existing_conn.email = email
            if access_token_encrypted:
                existing_conn.access_token = access_token_encrypted
            if refresh_token_encrypted:
                existing_conn.refresh_token = refresh_token_encrypted
            if token_expires_at:
                existing_conn.token_expires_at = token_expires_at
            existing_conn.scopes = " ".join(provider_config.scopes)
            _db.session.commit()
        elif getattr(g, "organization_id", None):
            new_conn = OAuthConnection(
                user_id=user.id,
                provider=provider,
                provider_user_id=str(provider_user_id),
                email=email,
                access_token=access_token_encrypted,
                refresh_token=refresh_token_encrypted,
                token_expires_at=token_expires_at,
                scopes=" ".join(provider_config.scopes),
            )
            _db.session.add(new_conn)
            _db.session.commit()

    # Check if user is active
    if not user.is_active:
        flash("Your account has been deactivated.", "error")
        return redirect(url_for("core_bp.login"))

    # Log in the user
    login_user(user, remember=True)
    logger.info(f"User logged in via {provider}: {user.email}")

    # Redirect to next URL or default
    next_url = session.pop("oauth_next", None)

    # New OAuth signups: rule-based redirect matching confirm_signup()
    if signup_result:
        if signup_result.rule == 1:
            default_redirect = url_for("dashboard_bp.index")
        elif signup_result.rule == 2:
            default_redirect = url_for("core_bp.onboarding")
        elif signup_result.rule == 3:
            default_redirect = url_for("core_bp.org_landing")
        else:
            default_redirect = url_for("core_bp.personal_shell")
    elif user.is_admin and hasattr(g, "workspace_id") and g.workspace_id:
        from modules.base.core.models.workspace_settings import WorkspaceSettings
        settings = WorkspaceSettings.get_instance()
        if not settings.onboarding_completed:
            default_redirect = url_for("core_bp.onboarding")
        else:
            default_redirect = url_for("dashboard_bp.index")
    else:
        default_redirect = url_for("dashboard_bp.index")

    return redirect(next_url or default_redirect)


@blueprint.route("/<provider>/disconnect", methods=["POST"])
@login_required
def disconnect(provider: str):
    """Disconnect an OAuth provider from the current user's account."""
    provider = provider.lower()

    # Find the connection
    connection = OAuthConnection.get_by_user_and_provider(current_user.id, provider)

    if not connection:
        flash(f"No {provider.title()} account connected.", "warning")
        return redirect(url_for("core_bp.settings_security"))

    # Check if user has a password or other OAuth connections
    # (prevent locking themselves out)
    other_connections = [
        c for c in OAuthConnection.get_user_connections(current_user.id)
        if c.provider != provider
    ]

    if not current_user.has_password() and not other_connections:
        flash(
            "Cannot disconnect - you need at least one login method. "
            "Set a password first or connect another account.",
            "error"
        )
        return redirect(url_for("core_bp.settings_security"))

    # Delete the connection
    connection.delete()
    flash(f"{provider.title()} account disconnected.", "success")

    return redirect(url_for("core_bp.settings_security"))
