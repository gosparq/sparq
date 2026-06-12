# -----------------------------------------------------------------------------
# Rate Limiting Middleware
#
# In-memory rate limiting for auth endpoints. Prevents credential
# brute-forcing, email enumeration, and SMS credit exhaustion.
#
# Uses in-memory storage — appropriate for sparQ's single-worker
# Gunicorn architecture (1 worker + 4 threads). Multi-worker setups
# would need Redis-backed storage.
#
# Usage:
#   from system.middleware.ratelimit import rate_limit
#
#   @blueprint.route("/login", methods=["GET", "POST"])
#   @rate_limit(limit=10, window=60)
#   def login(): ...
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

import time
from collections import defaultdict
from functools import wraps
from typing import Callable

from flask import abort, jsonify, request

_buckets: dict[str, list[float]] = defaultdict(list)


def _get_client_ip() -> str:
    """Get client IP, handling proxies.

    Checks ``X-Forwarded-For`` header first (takes the first entry),
    then falls back to ``request.remote_addr``.

    Returns:
        Client IP address string.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "127.0.0.1"


def rate_limit(
    limit: int = 10, window: int = 60, key_func: Callable | None = None
):
    """Rate limit decorator.

    Args:
        limit: Max requests per window.
        window: Window size in seconds.
        key_func: Optional callable returning a custom key string.
    """

    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            # Only rate-limit state-changing methods (brute-force protection)
            if request.method in ("GET", "HEAD", "OPTIONS"):
                return f(*args, **kwargs)

            ip = _get_client_ip()
            key = key_func() if key_func else f"{f.__name__}:{ip}"
            now = time.time()

            # Prune expired entries
            _buckets[key] = [t for t in _buckets[key] if now - t < window]

            if len(_buckets[key]) >= limit:
                if request.content_type and "json" in request.content_type:
                    return jsonify({"error": "Too many requests. Try again later."}), 429
                abort(429)

            _buckets[key].append(now)
            return f(*args, **kwargs)

        return decorated

    return decorator
