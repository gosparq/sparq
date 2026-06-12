# -----------------------------------------------------------------------------
# sparQ - OAuth Service
#
# Description:
#     Main OAuth service using Authlib. Handles provider registration,
#     OAuth flow initiation, and callback processing.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

import logging
import os
import secrets
from typing import Any, Optional

from authlib.integrations.flask_client import OAuth
from flask import Flask, session, url_for

from .providers import PROVIDERS, ProviderConfig, get_provider
from .token_manager import TokenManager

logger = logging.getLogger(__name__)

# Global OAuth instance
oauth = OAuth()


def init_oauth(app: Flask) -> None:
    """Initialize OAuth with Flask app and register providers.

    This should be called during app initialization, after the database
    is set up so we can read provider configurations.

    Args:
        app: Flask application instance
    """
    oauth.init_app(app)
    TokenManager.init_app(app)

    # Register all providers (they'll only work if configured)
    for name, config in PROVIDERS.items():
        _register_provider(app, name, config)

    logger.info("OAuth system initialized")


def _register_provider(app: Flask, name: str, config: ProviderConfig) -> None:
    """Register a single OAuth provider with Authlib.

    Args:
        app: Flask application instance
        name: Provider name (e.g., 'google')
        config: Provider configuration
    """
    # Build client kwargs for Authlib
    client_kwargs = {
        "scope": " ".join(config.scopes),
    }

    # Add PKCE if supported
    if config.supports_pkce:
        client_kwargs["code_challenge_method"] = "S256"

    # Build registration kwargs
    register_kwargs: dict[str, Any] = {
        "name": name,
        "authorize_url": config.authorize_url,
        "access_token_url": config.access_token_url,
        "userinfo_endpoint": config.userinfo_url,
        "client_kwargs": client_kwargs,
        "fetch_token": _make_fetch_token(name),
    }

    # OIDC providers need server_metadata_url for jwks_uri discovery
    if config.server_metadata_url:
        register_kwargs["server_metadata_url"] = config.server_metadata_url

    oauth.register(**register_kwargs)


def _make_fetch_token(provider_name: str):
    """Create a fetch_token function for a provider.

    This allows dynamic client credentials from database/environment.
    """

    def fetch_token():
        # This is called when making API requests with stored tokens
        # Return None to use the token from the session
        return None

    return fetch_token


def get_oauth_client(provider_name: str):
    """Get an OAuth client for a provider.

    Args:
        provider_name: Name of the provider (e.g., 'google')

    Returns:
        Authlib OAuth client or None if not configured
    """
    provider_name = provider_name.lower()
    if provider_name not in PROVIDERS:
        logger.warning(f"Unknown OAuth provider: {provider_name}")
        return None

    return getattr(oauth, provider_name, None)


def get_client_credentials(provider_name: str) -> tuple[Optional[str], Optional[str]]:
    """Get client ID and secret for a provider.

    Checks environment variables first, then database.

    Args:
        provider_name: Name of the provider

    Returns:
        Tuple of (client_id, client_secret)
    """
    provider_name = provider_name.lower()

    # Environment variable names
    env_id = f"{provider_name.upper()}_CLIENT_ID"
    env_secret = f"{provider_name.upper()}_CLIENT_SECRET"

    # Check environment first
    client_id = os.environ.get(env_id)
    client_secret = os.environ.get(env_secret)

    if client_id and client_secret:
        return client_id, client_secret

    # Fall back to database
    try:
        from modules.base.core.models.auth_settings import AuthSettings

        settings = AuthSettings.get_instance()
        db_id = getattr(settings, f"{provider_name}_client_id", None)
        db_secret_encrypted = getattr(settings, f"{provider_name}_client_secret", None)

        if db_id:
            client_id = client_id or db_id
        if db_secret_encrypted:
            client_secret = client_secret or TokenManager.decrypt(db_secret_encrypted)

    except Exception as e:
        logger.debug(f"Could not load credentials from database: {e}")

    return client_id, client_secret


def is_provider_configured(provider_name: str) -> bool:
    """Check if a provider has valid credentials configured.

    Args:
        provider_name: Name of the provider

    Returns:
        True if both client_id and client_secret are set
    """
    client_id, client_secret = get_client_credentials(provider_name)
    return bool(client_id and client_secret)


def is_provider_enabled(provider_name: str) -> bool:
    """Check if a provider is enabled.

    Providers are auto-enabled when environment variable credentials are set.
    Falls back to checking the database enabled flag + database credentials.

    Args:
        provider_name: Name of the provider

    Returns:
        True if provider is enabled and configured
    """
    provider_name = provider_name.lower()

    # Auto-enable: if env var credentials are set, provider is enabled
    env_id = f"{provider_name.upper()}_CLIENT_ID"
    env_secret = f"{provider_name.upper()}_CLIENT_SECRET"
    if os.environ.get(env_id) and os.environ.get(env_secret):
        return True

    # Fall back to database: check both enabled flag and credentials
    try:
        from modules.base.core.models.auth_settings import AuthSettings

        settings = AuthSettings.get_instance()
        enabled = getattr(settings, f"{provider_name}_enabled", False)
        if not enabled:
            return False
        # Check database credentials exist
        client_id, client_secret = settings.get_provider_credentials(provider_name)
        return bool(client_id and client_secret)
    except Exception:
        return False


def get_enabled_providers() -> list[ProviderConfig]:
    """Get list of all enabled and configured providers.

    Returns:
        List of ProviderConfig for enabled providers
    """
    enabled = []
    for name, config in PROVIDERS.items():
        if is_provider_enabled(name):
            enabled.append(config)
    return enabled


def generate_state() -> str:
    """Generate a secure random state parameter for CSRF protection.

    The state is stored in the session and validated on callback.

    Returns:
        Random state string
    """
    state = secrets.token_urlsafe(32)
    session["oauth_state"] = state
    return state


def validate_state(state: str) -> bool:
    """Validate the state parameter from OAuth callback.

    Args:
        state: State parameter from callback

    Returns:
        True if state matches session value
    """
    expected = session.pop("oauth_state", None)
    if not expected or not state:
        return False
    return secrets.compare_digest(expected, state)


def build_callback_url(provider_name: str) -> str:
    """Build the OAuth callback URL for a provider.

    Args:
        provider_name: Name of the provider

    Returns:
        Full callback URL
    """
    return url_for("oauth_bp.callback", provider=provider_name, _external=True)


def get_authorization_url(provider_name: str, redirect_uri: str) -> Optional[str]:
    """Get the authorization URL to redirect user to.

    Args:
        provider_name: Name of the provider
        redirect_uri: Callback URL after authorization

    Returns:
        Authorization URL or None if provider not configured
    """
    client = get_oauth_client(provider_name)
    if not client:
        return None

    client_id, client_secret = get_client_credentials(provider_name)
    if not client_id:
        return None

    # Update client with credentials
    client.client_id = client_id
    client.client_secret = client_secret

    # Generate state for CSRF protection
    state = generate_state()

    # Create authorization URL
    config = get_provider(provider_name)
    if not config:
        return None

    return client.create_authorization_url(
        redirect_uri=redirect_uri,
        state=state,
    )
