# -----------------------------------------------------------------------------
# sparQ - OAuth Provider Configurations
#
# Description:
#     Provider-specific OAuth 2.0 / OpenID Connect configurations for
#     Google, Microsoft, GitHub, and LinkedIn.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from dataclasses import dataclass
from typing import Optional


@dataclass
class ProviderConfig:
    """Configuration for an OAuth provider."""

    name: str
    display_name: str
    icon_class: str  # Font Awesome class
    color: str  # Brand color for button
    authorize_url: str
    access_token_url: str
    userinfo_url: str
    scopes: list[str]
    # OpenID Connect providers use 'sub', others use 'id'
    user_id_field: str = "sub"
    # Some providers return email in userinfo, others in a separate endpoint
    email_field: str = "email"
    # For PKCE support
    supports_pkce: bool = True
    # OpenID Connect compliance
    is_oidc: bool = True
    # OIDC discovery URL (required for ID token verification)
    server_metadata_url: str = ""


# Provider configurations
PROVIDERS: dict[str, ProviderConfig] = {
    "google": ProviderConfig(
        name="google",
        display_name="Google",
        icon_class="fa-brands fa-google",
        color="#4285F4",
        authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        access_token_url="https://oauth2.googleapis.com/token",
        userinfo_url="https://openidconnect.googleapis.com/v1/userinfo",
        scopes=["openid", "email", "profile"],
        user_id_field="sub",
        email_field="email",
        supports_pkce=True,
        is_oidc=True,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    ),
    "microsoft": ProviderConfig(
        name="microsoft",
        display_name="Microsoft",
        icon_class="fa-brands fa-microsoft",
        color="#00A4EF",
        # Using 'common' tenant for both personal and work accounts
        authorize_url="https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        access_token_url="https://login.microsoftonline.com/common/oauth2/v2.0/token",
        userinfo_url="https://graph.microsoft.com/oidc/userinfo",
        scopes=["openid", "email", "profile"],
        user_id_field="sub",
        email_field="email",
        supports_pkce=True,
        is_oidc=True,
        server_metadata_url="https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration",
    ),
    "github": ProviderConfig(
        name="github",
        display_name="GitHub",
        icon_class="fa-brands fa-github",
        color="#333333",
        authorize_url="https://github.com/login/oauth/authorize",
        access_token_url="https://github.com/login/oauth/access_token",
        userinfo_url="https://api.github.com/user",
        scopes=["user:email"],
        user_id_field="id",  # GitHub uses numeric 'id'
        email_field="email",
        supports_pkce=False,  # GitHub doesn't support PKCE
        is_oidc=False,
    ),
    "linkedin": ProviderConfig(
        name="linkedin",
        display_name="LinkedIn",
        icon_class="fa-brands fa-linkedin",
        color="#0A66C2",
        authorize_url="https://www.linkedin.com/oauth/v2/authorization",
        access_token_url="https://www.linkedin.com/oauth/v2/accessToken",
        userinfo_url="https://api.linkedin.com/v2/userinfo",
        scopes=["openid", "profile", "email"],
        user_id_field="sub",
        email_field="email",
        supports_pkce=True,
        is_oidc=True,
        server_metadata_url="https://www.linkedin.com/oauth/.well-known/openid-configuration",
    ),
}


def get_provider(name: str) -> Optional[ProviderConfig]:
    """Get provider configuration by name."""
    return PROVIDERS.get(name.lower())


def get_all_providers() -> list[ProviderConfig]:
    """Get all provider configurations."""
    return list(PROVIDERS.values())


def get_provider_names() -> list[str]:
    """Get list of all provider names."""
    return list(PROVIDERS.keys())
