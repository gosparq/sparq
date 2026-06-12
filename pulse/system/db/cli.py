# -----------------------------------------------------------------------------
# sparQ - Database CLI Commands
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""
Flask CLI commands for database management.

Usage:
    flask db status     - Show migration status
    flask db upgrade    - Run pending migrations
    flask db migrate    - Create new migration (autogenerate)
    flask db stamp      - Stamp revision without running
    flask db history    - Show migration history
    flask db reset      - Reset database (development only)
"""

import click
from flask.cli import AppGroup

from alembic import command

from system.db.migrations import (
    get_alembic_config,
    get_migration_status,
    initialize_database,
    stamp_revision,
)

# Create CLI group
db_cli = AppGroup("db", help="Database migration commands")


@db_cli.command("status")
def status():
    """Show current migration status."""
    status = get_migration_status()

    click.echo("\n=== sparQ Database Status ===\n")

    if status["is_fresh_install"]:
        click.echo("Status: Fresh install (no database)")
        click.echo("  Run 'flask db upgrade' to initialize")
    else:
        click.echo(f"Current revision: {status['current_revision']}")
        click.echo(f"Head revision:    {status['head_revision']}")

        if status["pending_migrations"]:
            click.echo(f"\nPending migrations ({len(status['pending_migrations'])}):")
            for rev in status["pending_migrations"]:
                click.echo(f"  - {rev}")
            click.echo("\nRun 'flask db upgrade' to apply")
        else:
            click.secho("\nDatabase is up to date!", fg="green")

    click.echo()


@db_cli.command("upgrade")
def upgrade():
    """Run pending migrations (or initialize fresh install)."""
    click.echo("Initializing database...")
    initialize_database()
    click.secho("Done!", fg="green")


@db_cli.command("migrate")
@click.option("-m", "--message", required=True, help="Migration description")
def migrate(message):
    """Create a new migration from model changes."""
    from system.version import is_production

    if not is_production():
        click.secho(
            "Warning: Creating migration in development mode.\n"
            "Migrations are typically only needed after VERSION file exists.",
            fg="yellow",
        )

    config = get_alembic_config()
    command.revision(config, message=message, autogenerate=True)
    click.secho(f"Created migration: {message}", fg="green")
    click.echo("Review the generated file in migrations/versions/")


@db_cli.command("stamp")
@click.argument("revision")
def stamp(revision):
    """Stamp database with revision without running migrations.

    Use 'head' to stamp as current, or a specific revision ID.
    """
    stamp_revision(revision)
    click.secho(f"Stamped database at: {revision}", fg="green")


@db_cli.command("history")
@click.option("-v", "--verbose", is_flag=True, help="Show detailed info")
def history(verbose):
    """Show migration history."""
    config = get_alembic_config()
    if verbose:
        command.history(config, verbose=True)
    else:
        command.history(config)


@db_cli.command("current")
def current():
    """Show current revision."""
    config = get_alembic_config()
    command.current(config, verbose=True)


@db_cli.command("heads")
def heads():
    """Show available heads (latest revisions)."""
    config = get_alembic_config()
    command.heads(config, verbose=True)


@db_cli.command("downgrade")
@click.argument("revision")
@click.option("--yes", is_flag=True, help="Skip confirmation")
def downgrade(revision, yes):
    """Downgrade to a previous revision.

    Use '-1' for one step back, or a specific revision ID.
    """
    if not yes:
        click.confirm(
            f"This will downgrade the database to {revision}. Continue?", abort=True
        )

    config = get_alembic_config()
    command.downgrade(config, revision)
    click.secho(f"Downgraded to: {revision}", fg="yellow")


@db_cli.command("reset")
@click.option("--yes", is_flag=True, help="Skip confirmation")
def reset(yes):
    """Reset database (DESTRUCTIVE - development only).

    Drops all tables and recreates from models.
    """
    from system.version import is_production

    if is_production():
        click.secho(
            "ERROR: Cannot reset database in production mode!\n"
            "Remove VERSION file to enable development mode.",
            fg="red",
        )
        return

    if not yes:
        click.confirm(
            click.style("This will DELETE all data. Continue?", fg="red"), abort=True
        )

    from system.db.database import db

    click.echo("Dropping all tables...")
    db.drop_all()
    click.echo("Creating all tables...")
    db.create_all()
    click.echo("Stamping HEAD...")
    stamp_revision("head")
    click.secho("Database reset complete!", fg="green")


def register_commands(app):
    """Register database CLI commands with Flask app."""
    app.cli.add_command(db_cli)
