# -----------------------------------------------------------------------------
# sparQ - Database Initialization
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# Database Initialization
#
# Handles database schema creation, migrations, and default data seeding.
# -----------------------------------------------------------------------------

import logging
import os

from flask import Flask

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.version import get_version, is_production


def init_database(app: Flask, module_loader) -> None:
    """Initialize database schema and seed default data.

    Args:
        app: Flask application instance.
        module_loader: The module loader instance with plugin manager.
    """
    verbose = app.config.get("_VERBOSE", False)

    # Import LogEntry model so its table gets created
    from system.logging import LogEntry  # noqa: F401 (imported for side effects)

    # Import models that sit above workspace scope — needed before db.create_all()
    from modules.base.core.models.workspace import Workspace  # noqa: F401
    from modules.base.core.models.organization import Organization  # noqa: F401

    # Legacy table renames and defensive column patches — PostgreSQL only.
    # SQLite fresh installs create the correct schema via db.create_all().
    from sqlalchemy import text
    _is_pg = db.engine.dialect.name == "postgresql"
    if _is_pg:
        with db.engine.connect() as conn:
            conn.execute(text("ALTER TABLE IF EXISTS company_settings RENAME TO workspace_settings"))
            conn.execute(text("ALTER TABLE IF EXISTS timetracking_settings RENAME TO presence_settings"))
            conn.execute(text("ALTER TABLE IF EXISTS chat RENAME TO connect_message"))
            conn.execute(text("ALTER TABLE IF EXISTS chat_message_state RENAME TO connect_message_state"))
            conn.execute(text("ALTER TABLE IF EXISTS chat_like RENAME TO connect_message_reaction"))
            conn.execute(text("ALTER TABLE IF EXISTS connect_template RENAME TO update_template"))
            conn.execute(text("ALTER TABLE IF EXISTS connect_post RENAME TO update_post"))
            conn.execute(text("ALTER TABLE IF EXISTS connect_post_reaction RENAME TO update_post_reaction"))
            conn.execute(text("ALTER TABLE IF EXISTS connect_nudge_log RENAME TO update_nudge_log"))
            conn.execute(text("ALTER TABLE IF EXISTS channel RENAME TO update_channel"))
            conn.execute(text("ALTER TABLE IF EXISTS direct_message RENAME TO dm"))
            conn.execute(text("ALTER TABLE IF EXISTS dm_acknowledgment RENAME TO dm_ack"))
            conn.execute(text("ALTER TABLE IF EXISTS webhook RENAME TO update_webhook"))
            conn.execute(text("ALTER TABLE IF EXISTS content_follow RENAME TO update_follow"))
            conn.execute(text("ALTER TABLE IF EXISTS company_event RENAME TO event"))
            conn.execute(text("ALTER TABLE IF EXISTS sync_template RENAME TO update_template"))
            conn.execute(text("ALTER TABLE IF EXISTS sync_post RENAME TO update_post"))
            conn.execute(text("ALTER TABLE IF EXISTS sync_post_reaction RENAME TO update_post_reaction"))
            conn.execute(text("ALTER TABLE IF EXISTS sync_post_ack RENAME TO update_post_ack"))
            conn.execute(text("ALTER TABLE IF EXISTS sync_nudge_log RENAME TO update_nudge_log"))
            conn.execute(text("ALTER TABLE IF EXISTS sync_channel RENAME TO update_channel"))
            conn.execute(text("ALTER TABLE IF EXISTS sync_channel_read_state RENAME TO update_channel_read_state"))
            conn.execute(text("ALTER TABLE IF EXISTS sync_area RENAME TO update_area"))
            conn.execute(text("ALTER TABLE IF EXISTS sync_dm_thread RENAME TO dm_thread"))
            conn.execute(text("ALTER TABLE IF EXISTS sync_dm RENAME TO dm"))
            conn.execute(text("ALTER TABLE IF EXISTS sync_dm_reaction RENAME TO dm_reaction"))
            conn.execute(text("ALTER TABLE IF EXISTS sync_dm_ack RENAME TO dm_ack"))
            conn.execute(text("ALTER TABLE IF EXISTS sync_webhook RENAME TO update_webhook"))
            conn.execute(text("ALTER TABLE IF EXISTS sync_follow RENAME TO update_follow"))
            conn.execute(text("ALTER TABLE IF EXISTS sync_week_review RENAME TO update_week_review"))
            conn.execute(text("ALTER TABLE IF EXISTS sync_event RENAME TO event"))
            conn.execute(text("DROP TABLE IF EXISTS sync_blocker CASCADE"))
            for table in ["employee_note", "feature_locks", "board_post"]:
                conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))

            conn.execute(text(
                "ALTER TABLE IF EXISTS business RENAME TO organization"
            ))
            conn.execute(text("""
                DO $$ BEGIN
                    IF EXISTS (SELECT 1 FROM information_schema.columns
                               WHERE table_name='workspace' AND column_name='business_id')
                       AND NOT EXISTS (SELECT 1 FROM information_schema.columns
                                       WHERE table_name='workspace' AND column_name='organization_id') THEN
                        ALTER TABLE workspace RENAME COLUMN business_id TO organization_id;
                    END IF;
                    IF EXISTS (SELECT 1 FROM information_schema.tables
                               WHERE table_name='billing_subscription')
                       AND EXISTS (SELECT 1 FROM information_schema.columns
                                   WHERE table_name='billing_subscription' AND column_name='business_id')
                       AND NOT EXISTS (SELECT 1 FROM information_schema.columns
                                       WHERE table_name='billing_subscription' AND column_name='organization_id') THEN
                        ALTER TABLE billing_subscription RENAME COLUMN business_id TO organization_id;
                    END IF;
                END $$;
            """))

            conn.execute(text(
                "ALTER TABLE IF EXISTS update_channel "
                "ADD COLUMN IF NOT EXISTS project_id INTEGER "
                "REFERENCES project(id) ON DELETE SET NULL"
            ))
            conn.execute(text(
                "ALTER TABLE IF EXISTS update_post "
                "ADD COLUMN IF NOT EXISTS channel_id INTEGER "
                "REFERENCES update_channel(id) ON DELETE SET NULL"
            ))
            conn.execute(text(
                "ALTER TABLE IF EXISTS update_post "
                "ADD COLUMN IF NOT EXISTS is_win BOOLEAN NOT NULL DEFAULT FALSE"
            ))
            conn.execute(text(
                "ALTER TABLE IF EXISTS update_post "
                "ADD COLUMN IF NOT EXISTS parent_id INTEGER "
                "REFERENCES update_post(id) ON DELETE CASCADE"
            ))
            conn.execute(text(
                "ALTER TABLE IF EXISTS update_post "
                "ADD COLUMN IF NOT EXISTS subject VARCHAR(300)"
            ))
            conn.execute(text(
                "ALTER TABLE IF EXISTS update_post "
                "ADD COLUMN IF NOT EXISTS title VARCHAR(255)"
            ))
            conn.execute(text(
                "ALTER TABLE IF EXISTS update_post "
                "ADD COLUMN IF NOT EXISTS migrated_from VARCHAR(50)"
            ))
            conn.execute(text(
                "ALTER TABLE IF EXISTS project "
                "ADD COLUMN IF NOT EXISTS is_private BOOLEAN NOT NULL DEFAULT FALSE"
            ))
            conn.execute(text(
                "ALTER TABLE IF EXISTS workspace "
                "ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP"
            ))
            conn.execute(text(
                "ALTER TABLE IF EXISTS workspace "
                "ADD COLUMN IF NOT EXISTS deleted_by_id INTEGER "
                "REFERENCES \"user\"(id)"
            ))
            conn.commit()

    # Database initialization - hybrid strategy based on mode
    if is_production():
        if verbose:
            app.logger.info(
                f"Production mode (v{get_version()}): "
                "Using migration-based schema management"
            )
        # Production: Use hybrid migration strategy
        # - Fresh installs: db.create_all() + stamp HEAD
        # - Legacy installs: stamp baseline + run migrations
        # - Normal upgrades: run pending migrations
        from system.db.migrations import initialize_database
        initialize_database()
    else:
        # Development mode - auto-create/update tables directly
        db.create_all()

    # If migrations are still pending after initialize_database() — e.g. the
    # DB was stamped at a stale/flattened revision and got re-stamped to HEAD
    # without actually running 047-066 — bail out of the rest of init_database
    # cleanly. This lets `flask db upgrade` finish importing the app, run the
    # migrations, and the next boot does the full seed/init against a schema
    # that now matches the ORM. Without this, module init hooks blow up on
    # missing columns (organization_id, etc.) one after another.
    try:
        from system.db.migrations import get_pending_migrations
        pending = get_pending_migrations()
        if pending:
            app.logger.warning(
                f"Schema is behind HEAD — {len(pending)} migration(s) pending "
                f"({pending[:3]}{'...' if len(pending) > 3 else ''}). "
                "Skipping ORM seed + module init hooks. "
                "Run `flask db upgrade` to apply, then restart."
            )
            return
    except Exception as e:
        app.logger.warning(f"Could not check migration status: {e}")

    # Ensure new tables exist and add new columns to existing tables
    # (db.create_all creates missing tables but won't alter existing ones)
    db.create_all()
    if _is_pg:
        with db.engine.connect() as conn:
            conn.execute(text("""
                DO $$ BEGIN
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='workspace' AND column_name='organization_id')
                       AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='workspace' AND column_name='business_id')
                       AND EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='organization') THEN
                        ALTER TABLE workspace ADD COLUMN organization_id UUID REFERENCES organization(id);
                    END IF;
                END $$;
            """))
            conn.commit()

    # Ensure default workspace exists (for fresh installs and module init hooks)
    import uuid
    from flask import g
    default_workspace_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    default_workspace = Workspace.query.filter_by(id=default_workspace_id).first()
    if not default_workspace:
        default_workspace = Workspace(id=default_workspace_id, slug="default", name="Default Workspace")
        db.session.add(default_workspace)
        db.session.commit()

    # Ensure default organization exists and link to default workspace
    default_organization_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    default_organization = Organization.query.filter_by(id=default_organization_id).first()
    if not default_organization:
        default_organization = Organization(id=default_organization_id, name="Default", slug="default")
        db.session.add(default_organization)
        db.session.commit()
    if not default_workspace.organization_id:
        default_workspace.organization_id = default_organization_id
        db.session.commit()

    # Set workspace + organization context for default workspace (used by
    # module init hooks). OrganizationMixin.scoped() requires g.organization_id
    # as the hard tenant boundary.
    g.workspace_id = default_workspace_id
    g.organization_id = default_organization_id

    # Call init_database hooks for all modules (scope context set to default)
    module_loader.pm.hook.init_database()

    # Register event handlers for model lifecycle notifications
    from modules.base.core.notification_handler import notification_handler
    from modules.base.dashboard.activity_handler import activity_handler
    module_loader.pm.register(notification_handler, name="notification_handler")
    module_loader.pm.register(activity_handler, name="activity_handler")

    # Create notifications for any module loading errors
    from system.module.utils import create_module_error_notifications
    create_module_error_notifications(module_loader.errors)

    # Seed email settings from .env if not already in database
    # Wrapped in try/except: during migrations the schema may not match the model yet
    try:
        from modules.base.core.utils.email_setup import seed_email_settings_from_env
        seed_email_settings_from_env()
    except Exception:
        logging.getLogger(__name__).debug("Skipping email seed (schema not ready)")

    # Print model registry after all models are loaded
    ModelRegistry.print_summary()

    # Print concise startup summary (unless verbose mode prints full details)
    # Only print once - skip if this is the reloader child process
    if not verbose and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        enabled_modules = sum(1 for m in module_loader.manifests.values() if m.get("enabled"))
        apps = sum(1 for m in module_loader.manifests.values() if m.get("is_app") and m.get("enabled"))
        plugins = sum(1 for m in module_loader.manifests.values() if m.get("is_plugin") and m.get("enabled"))
        models = len(ModelRegistry.models)
        print(f"sparQ {get_version()}: {enabled_modules} modules ({apps} apps, {plugins} plugins), {models} models")

    # Clear scope context — request hooks will set it per-request from here on
    g.workspace_id = None
    g.organization_id = None


def init_realtime(app: Flask, socketio, sock) -> None:
    """Initialize real-time communication handlers (SocketIO and WebSocket).

    Args:
        app: Flask application instance.
        socketio: SocketIO instance.
        sock: Flask-Sock instance.
    """
    # Initialize socketio handlers for team module (legacy)
    try:
        from modules.base.people.controllers.chat import init_socketio_handlers
        init_socketio_handlers(socketio)
    except ImportError:
        pass  # Chat has been moved to its own module

    # Initialize SocketIO handlers for Sync chat module
    try:
        from modules.base.updates.controllers.socketio_events import init_socketio_handlers as init_chat_socketio
        init_chat_socketio(socketio)
    except ImportError:
        pass  # Sync module not loaded

    # Initialize WebSocket routes for Sync module (flask-sock)
    try:
        from modules.base.updates.controllers.websocket import init_websocket_routes
        init_websocket_routes(sock)
    except ImportError:
        app.logger.warning("Could not initialize Sync module WebSocket routes")


def init_logging_capture(app: Flask) -> None:
    """Initialize database log handler and stdout capture for web console.

    Args:
        app: Flask application instance.
    """
    log_level = app.config.get("_LOG_LEVEL", logging.INFO)

    # Add database log handler for console feature
    from system.logging import DatabaseLogHandler, install_stdout_capture

    db_log_handler = DatabaseLogHandler(app=app, level=log_level)
    db_log_handler.setFormatter(logging.Formatter("%(message)s"))
    app.logger.addHandler(db_log_handler)

    # Also capture root logger for broader coverage
    logging.getLogger().addHandler(db_log_handler)

    # Install stdout/stderr capture to get HTTP access logs in web console
    install_stdout_capture(app)
