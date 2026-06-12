# -----------------------------------------------------------------------------
# sparQ - Migration Management
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""
Migration strategy for sparQ.

This module implements database schema management:
- Fresh installs: Use db.create_all() then stamp HEAD (fast, no migrations run)
- Upgrades: Run pending migrations only

This ensures fresh installs are fast while existing installs get proper
migration tracking for incremental updates.
"""

import logging
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

from system.db.database import db

logger = logging.getLogger(__name__)


_project_root = Path(__file__).parent.parent.parent
_migrations_dir = _project_root / "migrations"


def has_migrations_dir() -> bool:
    """Check if an Alembic migrations directory exists."""
    return (_migrations_dir / "alembic.ini").is_file()


def get_alembic_config() -> Config:
    """Get Alembic configuration pointing to our migrations directory."""
    alembic_ini = _migrations_dir / "alembic.ini"

    config = Config(str(alembic_ini))
    config.set_main_option("script_location", str(_migrations_dir))

    # Set database URL from current engine
    db_url = str(db.engine.url)
    # Handle password masking in URL
    if "***" in db_url:
        db_url = db_url.replace("***", "")
    config.set_main_option("sqlalchemy.url", db_url)

    return config


def get_current_revision() -> str | None:
    """Get current database revision from alembic_version table."""
    with db.engine.connect() as conn:
        context = MigrationContext.configure(conn)
        return context.get_current_revision()


def get_head_revision() -> str:
    """Get latest available migration revision (HEAD)."""
    config = get_alembic_config()
    script = ScriptDirectory.from_config(config)
    return script.get_current_head()


def has_migration_table() -> bool:
    """Check if alembic_version table exists in database."""
    inspector = inspect(db.engine)
    return "alembic_version" in inspector.get_table_names()


def is_fresh_install() -> bool:
    """
    Detect fresh install (no database or empty database).

    Returns True if:
    - Database file doesn't exist (SQLite)
    - No tables exist in database
    """
    # Check if SQLite file exists
    db_url = str(db.engine.url)
    if db_url.startswith("sqlite"):
        db_path = db_url.replace("sqlite:///", "")
        if not os.path.exists(db_path):
            return True

    # Check for any tables
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    return len(tables) == 0


def revision_exists(revision: str) -> bool:
    """Check if a revision exists in the migration scripts."""
    config = get_alembic_config()
    script = ScriptDirectory.from_config(config)
    try:
        script.get_revision(revision)
        return True
    except Exception:
        return False


def stamp_revision(revision: str) -> None:
    """
    Stamp database with a specific revision without running migrations.

    This marks the database as being at a certain schema version without
    actually executing the migration. Used for fresh installs
    (stamp HEAD after db.create_all()).
    """
    config = get_alembic_config()
    command.stamp(config, revision)
    logger.info(f"Stamped database at revision: {revision}")


def run_migrations() -> None:
    """Run all pending migrations to bring database to HEAD."""
    config = get_alembic_config()
    command.upgrade(config, "head")
    logger.info("Migrations completed successfully")


def get_pending_migrations() -> list[str]:
    """Get list of pending migration revisions."""
    if not has_migrations_dir() or not has_migration_table():
        return []

    current = get_current_revision()
    head = get_head_revision()

    if current == head:
        return []

    # Stale revision from pre-open-source — no pending migrations to compute
    if current and not revision_exists(current):
        return []

    config = get_alembic_config()
    script = ScriptDirectory.from_config(config)

    pending = []
    for revision in script.iterate_revisions(head, current):
        if revision.revision != current:
            pending.append(revision.revision)

    return list(reversed(pending))


def get_migration_status() -> dict:
    """
    Get comprehensive migration status information.

    Returns dict with:
    - is_fresh_install: bool
    - has_migration_table: bool
    - current_revision: str | None
    - head_revision: str
    - pending_migrations: list[str]
    """
    return {
        "is_fresh_install": is_fresh_install(),
        "has_migration_table": has_migration_table(),
        "current_revision": get_current_revision() if has_migration_table() else None,
        "head_revision": get_head_revision(),
        "pending_migrations": get_pending_migrations(),
    }


def initialize_database() -> None:
    """
    Initialize database with hybrid migration strategy.

    This is the main entry point called during app startup in production mode.

    Strategy:
    1. Fresh install: db.create_all() + stamp HEAD
       - Creates all tables from current models
       - Stamps as HEAD so future migrations work
       - Zero migrations executed

    2. Stale revision: re-stamp HEAD
       - Pre-open-source installs have revisions that no longer exist
       - Schema is already up to date, just reset the tracking

    3. Existing with migrations: run pending migrations
       - Normal upgrade path
       - Only runs migrations since last version
    """
    try:
        # No migrations directory — use db.create_all() for all installs
        if not has_migrations_dir():
            logger.info("No migrations directory — creating schema from models")
            db.create_all()
            return

        if is_fresh_install():
            logger.info("Fresh install detected - creating schema directly")
            db.create_all()
            stamp_revision("head")
            logger.info("Fresh install complete - database stamped at HEAD")

        else:
            # Existing install — check migration state
            current = get_current_revision()
            head = get_head_revision()

            if not has_migration_table() or current is None:
                # Tables created by db.create_all() but no migration tracking yet.
                # Stamp as HEAD since schema is already current.
                logger.info("Schema exists without migration tracking — stamping HEAD")
                stamp_revision("head")
            elif current and not revision_exists(current):
                # Pre-open-source install — migrations were flattened,
                # but schema is already up to date. Re-stamp to HEAD.
                logger.info(
                    f"Stale revision {current} (pre-open-source) — "
                    "re-stamping to HEAD"
                )
                stamp_revision("head")
            elif current == head:
                logger.info(f"Database is up to date (revision: {current})")
            else:
                logger.info(f"Running migrations from {current} to {head}")
                run_migrations()

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        logger.error(
            "Manual intervention may be required. "
            "Run 'flask db status' for details."
        )
        raise
