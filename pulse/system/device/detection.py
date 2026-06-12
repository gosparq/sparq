# -----------------------------------------------------------------------------
# sparQ - Device Detection
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# Device Detection
#
# Detects mobile vs desktop devices via User-Agent parsing.
# Supports query param override (?device=mobile or ?device=desktop).
# -----------------------------------------------------------------------------

import re
from flask import request, session

# Mobile User-Agent patterns
MOBILE_PATTERNS = [
    r"Mobile",
    r"Android",
    r"webOS",
    r"iPhone",
    r"iPad",
    r"iPod",
    r"BlackBerry",
    r"Windows Phone",
    r"Opera Mini",
    r"IEMobile",
]

# Compiled regex for performance
_MOBILE_REGEX = re.compile("|".join(MOBILE_PATTERNS), re.IGNORECASE)

# Session key for manual device override
DEVICE_OVERRIDE_KEY = "device_override"


def detect_device() -> str:
    """
    Detect device type from User-Agent header.

    Returns:
        'mobile' or 'desktop'
    """
    user_agent = request.headers.get("User-Agent", "")

    if _MOBILE_REGEX.search(user_agent):
        return "mobile"
    return "desktop"


def get_device_type() -> str:
    """
    Get device type with the following priority:
    1. Query param ?device=mobile or ?device=desktop (also sets session override)
    2. Session override (from previous query param or manual set)
    3. User-Agent detection (fresh each request)

    Returns:
        'mobile' or 'desktop'
    """
    # Check for query param override (and save it to session)
    device_param = request.args.get("device")
    if device_param in ("mobile", "desktop"):
        session[DEVICE_OVERRIDE_KEY] = device_param
        return device_param

    # Check for session override
    if DEVICE_OVERRIDE_KEY in session:
        return session[DEVICE_OVERRIDE_KEY]

    # Detect from User-Agent (fresh each request, no caching)
    return detect_device()


def is_mobile() -> bool:
    """
    Check if current request is from a mobile device.

    Returns:
        True if mobile, False if desktop
    """
    return get_device_type() == "mobile"


def set_device_type(device_type: str) -> None:
    """
    Manually set device type override (for user preference).

    Args:
        device_type: 'mobile' or 'desktop'
    """
    if device_type not in ("mobile", "desktop"):
        raise ValueError("device_type must be 'mobile' or 'desktop'")
    session[DEVICE_OVERRIDE_KEY] = device_type


def clear_device_type() -> None:
    """Clear device override from session, reverting to User-Agent detection."""
    session.pop(DEVICE_OVERRIDE_KEY, None)
