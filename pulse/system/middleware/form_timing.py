# -----------------------------------------------------------------------------
# Form Timing Middleware
#
# Prevents automated form submissions by enforcing a minimum time between
# page render and form POST. A signed timestamp is embedded in a hidden
# field at render time; on submit the server verifies the signature and
# checks that enough time has elapsed.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

import time

from flask import current_app, request
from itsdangerous import BadSignature, URLSafeSerializer

_SALT = "form-timing"


def generate_form_timestamp() -> str:
    """Return a signed token encoding the current Unix time."""
    s = URLSafeSerializer(current_app.secret_key, salt=_SALT)
    return s.dumps(int(time.time()))


def validate_form_timing(min_seconds: int = 3) -> bool:
    """Check that the form was rendered at least *min_seconds* ago.

    Reads the ``_form_ts`` hidden field from the current request form,
    verifies the cryptographic signature, and compares elapsed time.

    Returns:
        True if the token is valid and enough time has passed.
    """
    token = request.form.get("_form_ts", "")
    if not token:
        return False
    try:
        s = URLSafeSerializer(current_app.secret_key, salt=_SALT)
        ts: int = s.loads(token)
        return (time.time() - ts) >= min_seconds
    except (BadSignature, Exception):
        return False
