# -----------------------------------------------------------------------------
# sparQ - Backup CLI Commands
#
# Description:
#     Flask CLI commands for backup management. Allows backups to be created
#     via command line, used by getsparq installer for pre-upgrade backups.
#
# Usage:
#     flask backup create --reason=manual
#     flask backup create --reason=pre-upgrade
#     flask backup create --reason=scheduled
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

import click
from flask.cli import with_appcontext


@click.group()
def backup():
    """Backup management commands."""
    pass


@backup.command()
@click.option('--reason', default='manual', help='Backup reason (manual, scheduled, pre-upgrade)')
@with_appcontext
def create(reason):
    """Create a backup.

    Outputs the backup filename on success (for use by calling scripts).
    """
    from system.backup import create_backup

    try:
        filename = create_backup(reason=reason)
        # Output just the filename for easy parsing by shell scripts
        click.echo(filename)
    except Exception as e:
        click.echo(f"ERROR: {e}", err=True)
        raise SystemExit(1)


@backup.command()
@click.argument('filename')
@with_appcontext
def restore(filename):
    """Restore from a backup file.

    Usage: flask backup restore sparq-backup-20240115-100000-v0.5.174.zip

    This command is used by the orchestrator for automated rollbacks.
    Self-hosted users can continue using getsparq's existing restore mechanism.
    """
    from system.backup import get_backup_path, restore_backup

    # Check if backup exists
    backup_path = get_backup_path(filename)
    if not backup_path:
        click.echo(f"Error: Backup not found: {filename}", err=True)
        raise SystemExit(1)

    try:
        success, message = restore_backup(backup_path)
        if success:
            click.echo(message)
        else:
            click.echo(f"Error: {message}", err=True)
            raise SystemExit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
