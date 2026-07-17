# -----------------------------------------------------------------------------
# sparQ - Configuration
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# Application Configuration
#
# Configures Flask application settings, logging, SQLAlchemy, and security.
# -----------------------------------------------------------------------------

import logging
import os
from datetime import timedelta
from flask import Flask


def configure_app(app: Flask) -> tuple[bool, bool]:
    """Configure the Flask application with all settings.

    Returns:
        Tuple of (debug_mode, verbose) flags for use by caller.
    """
    # Environment configuration
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    verbose = os.environ.get("SPARQ_VERBOSE", "").lower() in ("1", "true", "yes")
    log_level = logging.DEBUG if debug_mode else logging.INFO

    # Configure structured logging (JSON in production, human-readable in dev)
    from system.logging import init_logger
    env = "dev" if debug_mode else "production"
    init_logger(env)

    # Override root log level for debug mode (init_logger defaults to INFO)
    if debug_mode:
        logging.getLogger().setLevel(logging.DEBUG)

    # Set Flask app logger level
    app.logger.setLevel(log_level)

    # Silence noisy third-party loggers
    logging.getLogger("fsevents").setLevel(logging.WARNING)
    logging.getLogger("watchdog").setLevel(logging.WARNING)
    logging.getLogger("alembic").setLevel(logging.WARNING if not verbose else logging.INFO)
    logging.getLogger("geventwebsocket.handler").setLevel(logging.WARNING)
    logging.getLogger("data_apps").setLevel(logging.WARNING)

    # In non-verbose mode, reduce noise from internal components
    if not verbose:
        logging.getLogger("system").setLevel(logging.WARNING)
        logging.getLogger("modules").setLevel(logging.WARNING)

    # Configure werkzeug access logs - show requests in debug mode
    werkzeug_logger = logging.getLogger("werkzeug")
    werkzeug_logger.setLevel(logging.INFO if debug_mode else logging.WARNING)

    # Silence Flask-SocketIO/engineio verbose logging
    logging.getLogger("engineio.server").setLevel(logging.WARNING)
    logging.getLogger("socketio.server").setLevel(logging.WARNING)

    # Configure SQLAlchemy
    # Use SPARQ_DATA_DIR env var for data directory, or default to ./data/ for local dev
    data_dir = os.environ.get(
        "SPARQ_DATA_DIR",
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
    )
    os.makedirs(data_dir, exist_ok=True)  # Create if doesn't exist

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        sqlite_path = os.path.join(data_dir, "sparq.db")
        database_url = f"sqlite:///{sqlite_path}"
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    if database_url.startswith("sqlite"):
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
            "connect_args": {"check_same_thread": False},
        }
    else:
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
            "pool_pre_ping": True,
            "pool_recycle": 300,
            "pool_size": 10,
            "max_overflow": 10,
            "pool_timeout": 20,
        }

    # Security configuration — SECRET_KEY fail-fast in production
    secret_key = os.environ.get("SECRET_KEY")
    _insecure_keys = {"dev", "change-me-to-a-random-string", "change-me", "secret", ""}
    _is_insecure = not secret_key or secret_key in _insecure_keys
    if _is_insecure:
        if debug_mode:
            secret_key = "dev-only-insecure-key-do-not-use-in-production"
            if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
                print("WARNING: No SECRET_KEY set. Using insecure default (dev mode only).")
        else:
            raise RuntimeError(
                "FATAL: SECRET_KEY is not set or uses a placeholder value. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\" "
                "and set it in .env or as an environment variable."
            )
    app.config["SECRET_KEY"] = secret_key

    # Session cookie hardening — respect installer-set value, fall back to secure in production
    _secure_cookie = os.environ.get("SESSION_COOKIE_SECURE", "").lower()
    if _secure_cookie in ("true", "false"):
        app.config["SESSION_COOKIE_SECURE"] = _secure_cookie == "true"
    else:
        app.config["SESSION_COOKIE_SECURE"] = not debug_mode
    app.config["SESSION_COOKIE_HTTPONLY"] = True  # Prevent JavaScript access
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"  # CSRF protection

    # SocketIO CORS restriction — prevent cross-origin WebSocket hijacking
    cors_origins = os.environ.get("SOCKETIO_CORS_ORIGINS", "")
    if cors_origins:
        app.config["SOCKETIO_CORS_ORIGINS"] = [o.strip() for o in cors_origins.split(",")]
    elif debug_mode:
        app.config["SOCKETIO_CORS_ORIGINS"] = "*"  # Allow all in dev for ngrok/testing
    else:
        app.config["SOCKETIO_CORS_ORIGINS"] = None  # Same-origin only in production

    # Static asset caching — long-lived browser cache in production so CSS/JS/
    # fonts/images serve from disk without revalidating on every navigation.
    # Safe because static URLs are cache-busted with ?v=<version> (see
    # register_static_cache_busting), so a deploy changes the URL and forces a
    # refetch. In debug, disable caching so local asset edits show immediately.
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = (
        timedelta(seconds=0) if debug_mode else timedelta(days=365)
    )

    # Error handling configuration
    app.config["PROPAGATE_EXCEPTIONS"] = False  # Let error handlers catch exceptions

    # Store flags in app config for later use
    app.config["_DEBUG_MODE"] = debug_mode
    app.config["_VERBOSE"] = verbose
    app.config["_LOG_LEVEL"] = log_level

    return debug_mode, verbose
