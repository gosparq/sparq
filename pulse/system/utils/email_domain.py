# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Email domain utilities for signup routing and organization domain claims.
#     Provides a free-email provider blocklist, domain extraction, and
#     normalization helpers used by PendingSignup and Organization models.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

from __future__ import annotations

import encodings.idna


# Full-domain blocklist — matched against the complete domain after the @.
# Per spec: gmail.com, outlook.com, hotmail.com, yahoo.com, icloud.com,
# protonmail.com, proton.me, aol.com, mail.com, gmx.com, yandex.com, zoho.com
# plus disposable/ISP domains that should never trigger domain-based org routing.
FREE_EMAIL_DOMAINS: frozenset[str] = frozenset({
    # Major providers (spec-listed)
    "gmail.com",
    "outlook.com",
    "hotmail.com",
    "yahoo.com",
    "icloud.com",
    "protonmail.com",
    "proton.me",
    "aol.com",
    "mail.com",
    "gmx.com",
    "yandex.com",
    "zoho.com",
    # Additional common free providers
    "tutanota.com",
    "fastmail.com",
    "hey.com",
    "live.com",
    "msn.com",
    "me.com",
    "mac.com",
    # US ISP domains
    "comcast.net",
    "verizon.net",
    "att.net",
    "cox.net",
    "sbcglobal.net",
    "bellsouth.net",
    "charter.net",
    "earthlink.net",
    "optonline.net",
    "frontier.com",
    "windstream.net",
    "centurylink.net",
    # Yahoo variants
    "yahoo.co.uk",
    "yahoo.ca",
    "ymail.com",
    "rocketmail.com",
    # Outlook/Hotmail variants
    "hotmail.co.uk",
    "outlook.co.uk",
    "live.co.uk",
})


def _punycode_domain(domain: str) -> str:
    """Encode an internationalized domain name to ASCII (punycode)."""
    try:
        return encodings.idna.ToASCII(domain).decode("ascii")
    except (UnicodeError, UnicodeDecodeError):
        return domain


def extract_domain(email: str) -> str:
    """Extract and normalize the domain from an email address.

    Args:
        email: An email address (e.g., "joe@Example.COM").

    Returns:
        Lowercase, punycode-normalized domain (e.g., "example.com").
        Empty string if the email has no @ sign.
    """
    email = (email or "").strip().lower()
    if "@" not in email:
        return ""
    domain = email.rsplit("@", 1)[1]
    return _punycode_domain(domain)


def normalize_domain(domain: str) -> str:
    """Normalize a raw domain string for storage.

    Strips whitespace, leading '@', lowercases, and applies punycode.

    Args:
        domain: Raw domain string (e.g., "@Example.COM ").

    Returns:
        Normalized domain (e.g., "example.com"), or empty string.
    """
    domain = (domain or "").strip().lower().lstrip("@")
    if not domain:
        return ""
    return _punycode_domain(domain)


def is_free_email(email: str) -> bool:
    """Check if an email address belongs to a free/personal email provider.

    Args:
        email: An email address.

    Returns:
        True if the domain is on the free-email blocklist.
    """
    domain = extract_domain(email)
    return domain in FREE_EMAIL_DOMAINS
