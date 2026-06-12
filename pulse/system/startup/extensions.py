# -----------------------------------------------------------------------------
# sparQ - Flask Extensions
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# Extension Initialization
#
# Initializes Flask extensions: database, login manager, SocketIO, flask-sock.
# -----------------------------------------------------------------------------

from flask import Flask, session
from flask_login import LoginManager
from flask_sock import Sock
from flask_socketio import SocketIO

from system.db.database import db


def init_extensions(app: Flask) -> tuple[LoginManager, SocketIO, Sock]:
    """Initialize Flask extensions.

    Returns:
        Tuple of (login_manager, socketio, sock) instances.
    """
    # Initialize database
    db.init_app(app)

    # SQLite: enable foreign keys and WAL mode for concurrency
    if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite"):
        import sqlite3
        from sqlalchemy import event as sa_event
        from sqlalchemy.engine import Engine

        @sa_event.listens_for(Engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _connection_record):
            if isinstance(dbapi_conn, sqlite3.Connection):
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA foreign_keys = ON")
                cursor.execute("PRAGMA journal_mode = WAL")
                cursor.close()
                # SQLite lacks GREATEST(); register it so PostgreSQL-targeted queries work.
                dbapi_conn.create_function("greatest", -1, lambda *args: max(
                    (a for a in args if a is not None), default=None
                ))

    # Import Workspace model first — all workspace-scoped models FK to workspace.id,
    # so it must be in SQLAlchemy metadata before any other model is loaded
    from modules.base.core.models.workspace import Workspace  # noqa: F401

    # Register multitenancy before_flush listeners
    from sqlalchemy import event
    from system.db.workspace import auto_set_organization_id, auto_set_workspace_id
    event.listen(db.session, "before_flush", auto_set_workspace_id)
    event.listen(db.session, "before_flush", auto_set_organization_id)

    # Session-level tenant filter (DB Access Standards §6.1)
    from system.db.tenant_filter import register_tenant_filter
    register_tenant_filter(db.session)

    # Dev/test lazy-load guard (DB Access Standards §7.4)
    from system.db.raise_on_lazy import register_raise_on_lazy
    register_raise_on_lazy(db.session)

    # Initialize login manager
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "core_bp.login"

    @login_manager.user_loader
    def load_user(user_id: str):
        from modules.base.core.models.user import User
        return db.session.get(User, int(user_id))

    @login_manager.request_loader
    def load_user_from_request(request):
        """Return synthetic MsaTransparentUser when transparent mode is active."""
        if session.get("msa_transparent_mode"):
            from system.auth.msa_user import MsaTransparentUser
            return MsaTransparentUser()
        return None

    # Initialize SocketIO
    # CORS controlled by config: "*" in dev, same-origin in production
    # Override via SOCKETIO_CORS_ORIGINS env var (see config.py)
    # Force threading mode: gevent is installed but can't be monkey-patched on Python 3.14,
    # so auto-detect picks broken gevent mode causing 60s hangs on page reload
    socketio = SocketIO(
        app,
        async_mode="threading",
        cors_allowed_origins=app.config.get("SOCKETIO_CORS_ORIGINS", []),
        ping_timeout=5,
        ping_interval=3,
    )
    app.socketio = socketio  # type: ignore[attr-defined]

    # Initialize flask-sock for native WebSocket support (used by chat module with HTMX)
    sock = Sock(app)
    app.sock = sock  # type: ignore[attr-defined]

    return login_manager, socketio, sock
