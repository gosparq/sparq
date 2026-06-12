# -----------------------------------------------------------------------------
# sparQ - Password Policy Enforcement
#
# Description:
#     Password complexity validation and breach checking via HaveIBeenPwned API.
#     Uses k-anonymity protocol — only the first 5 characters of the SHA1 hash
#     are sent to the API. No passwords or full hashes are ever transmitted.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

"""Password policy enforcement.

Provides password complexity validation and breach checking against
the HaveIBeenPwned database using k-anonymity.

Functions:
    validate_password: Check password meets complexity requirements.
    is_breached: Check if password appears in known data breaches.

Example:
    Guard clause pattern in a route::

        from system.auth.password_policy import validate_password, is_breached

        errors = validate_password(new_password)
        if errors:
            flash(" ".join(errors), "error")
            return redirect(...)

        if is_breached(new_password):
            flash("This password has appeared in a data breach.", "error")
            return redirect(...)
"""

import hashlib
import re
import urllib.request

MIN_LENGTH = 8
MAX_LENGTH = 128


def validate_password(password: str) -> list[str]:
    """Return list of policy violations (empty = valid).

    Checks password against complexity requirements:
    - Minimum 8 characters
    - Maximum 128 characters
    - At least one uppercase letter (A-Z)
    - At least one lowercase letter (a-z)
    - At least one digit (0-9)

    Args:
        password: The password to validate.

    Returns:
        List of human-readable error strings. Empty list means valid.

    Example:
        >>> validate_password("weak")
        ['Password must be at least 8 characters.', 'Must contain at least one uppercase letter.', 'Must contain at least one number.']
        >>> validate_password("Str0ngPass")
        []
    """
    errors = []
    if len(password) < MIN_LENGTH:
        errors.append(f"Password must be at least {MIN_LENGTH} characters.")
    if len(password) > MAX_LENGTH:
        errors.append(f"Password must be at most {MAX_LENGTH} characters.")
    if not re.search(r"[A-Z]", password):
        errors.append("Must contain at least one uppercase letter.")
    if not re.search(r"[a-z]", password):
        errors.append("Must contain at least one lowercase letter.")
    if not re.search(r"[0-9]", password):
        errors.append("Must contain at least one number.")
    return errors


def is_breached(password: str) -> bool:
    """Check password against HaveIBeenPwned API (k-anonymity).

    Only the first 5 characters of the SHA1 hash are sent to the API.
    No passwords or full hashes are ever transmitted. Fails open if
    the API is unreachable — authentication is not blocked.

    Args:
        password: The password to check.

    Returns:
        True if the password has appeared in a known data breach,
        False otherwise (including on API errors).

    Example:
        >>> is_breached("Password1")  # Known breached password
        True
        >>> is_breached("xK9#mP2$vL7@nQ4")  # Likely not breached
        False
    """
    try:
        sha1 = hashlib.sha1(password.encode()).hexdigest().upper()
        prefix, suffix = sha1[:5], sha1[5:]
        url = f"https://api.pwnedpasswords.com/range/{prefix}"
        req = urllib.request.Request(url, headers={"User-Agent": "sparQ-PasswordCheck"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            for line in resp.read().decode().splitlines():
                hash_suffix, _count = line.split(":")
                if hash_suffix == suffix:
                    return True
    except Exception:
        pass  # Fail open — don't block auth if API is unreachable
    return False
