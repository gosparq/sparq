# -----------------------------------------------------------------------------
# sparQ - Database Log Handler
#
# Description:
#     Custom logging handler that stores log entries in SQLite database.
#     Implements a rotating buffer that keeps the last N entries.
#     Also captures stdout/stderr for HTTP access logs.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

import json
import logging
import re
import sys
from datetime import datetime
from typing import Any, TextIO

from system.db.database import db

# Global reference to app for stdout capture
_app_instance: Any = None


def set_app_instance(app: Any) -> None:
    """Set the Flask app instance for stdout capture."""
    global _app_instance
    _app_instance = app


class LogEntry(db.Model):
    """Model for storing log entries in the database."""

    __tablename__ = "log_entry"

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    level = db.Column(db.String(10), nullable=False)  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    message = db.Column(db.Text, nullable=False)
    module = db.Column(db.String(100))  # Logger name / source module
    request_id = db.Column(db.String(50))  # Optional request correlation ID

    # Maximum number of entries to keep (rotating buffer)
    MAX_ENTRIES = 300

    @classmethod
    def add_entry(
        cls,
        level: str,
        message: str,
        module: str | None = None,
        request_id: str | None = None,
    ) -> "LogEntry":
        """Add a log entry and trim old entries if needed."""
        entry = cls(
            level=level,
            message=message,
            module=module,
            request_id=request_id,
        )
        db.session.add(entry)

        # Trim old entries to maintain rotating buffer
        cls._trim_old_entries()

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        return entry

    @classmethod
    def _trim_old_entries(cls) -> None:
        """Remove oldest entries to keep only MAX_ENTRIES."""
        count = cls.query.count()
        if count >= cls.MAX_ENTRIES:
            excess = count - cls.MAX_ENTRIES + 1
            oldest_ids = [
                r.id for r in cls.query.with_entities(cls.id).order_by(cls.id.asc()).limit(excess).all()
            ]
            if oldest_ids:
                cls.query.filter(cls.id.in_(oldest_ids)).delete(synchronize_session=False)

    @classmethod
    def get_recent(cls, limit: int = 300) -> list["LogEntry"]:
        """Get the most recent log entries."""
        return cls.query.order_by(cls.id.desc()).limit(limit).all()

    @classmethod
    def clear_all(cls) -> int:
        """Clear all log entries. Returns count of deleted entries."""
        count = cls.query.delete()
        db.session.commit()
        return count

    def __repr__(self) -> str:
        return f"<LogEntry {self.id} [{self.level}] {self.message[:50]}>"


class DatabaseLogHandler(logging.Handler):
    """Custom logging handler that writes log entries to the database."""

    def __init__(self, app: Any = None, level: int = logging.INFO) -> None:
        """Initialize the handler.

        Args:
            app: Flask application instance (optional, can set later)
            level: Minimum log level to capture (default: INFO)
        """
        super().__init__(level)
        self.app = app
        self._table_checked = False
        self._table_exists = False

    def init_app(self, app: Any) -> None:
        """Initialize with Flask app (for deferred initialization)."""
        self.app = app

    def _ensure_table_exists(self) -> bool:
        """Check if log_entry table exists, create if needed. Returns True if table is available."""
        if self._table_checked:
            return self._table_exists

        self._table_checked = True

        try:
            from sqlalchemy import inspect

            inspector = inspect(db.engine)
            if "log_entry" not in inspector.get_table_names():
                # Create the table
                LogEntry.__table__.create(db.engine, checkfirst=True)
            self._table_exists = True
        except Exception:
            self._table_exists = False

        return self._table_exists

    def emit(self, record: logging.LogRecord) -> None:
        """Write log record to database."""
        # Skip if no app context available
        if self.app is None:
            return

        # Skip database-related logs to avoid recursion
        if record.name in ("sqlalchemy.engine", "sqlalchemy.pool", "alembic"):
            return

        # Skip logs from this module to avoid recursion
        if record.name.startswith("system.logging"):
            return

        # Skip werkzeug HTTP request logs (they pollute the console, especially polling)
        if record.name == "werkzeug" or record.name.startswith("werkzeug"):
            return

        try:
            # Need to be within app context for database operations
            with self.app.app_context():
                # Ensure table exists before trying to use it
                if not self._ensure_table_exists():
                    return

                # Format the message
                message = self.format(record)

                # Get request ID if available (from Flask's g object)
                request_id = None
                try:
                    from flask import g, has_request_context

                    if has_request_context():
                        request_id = getattr(g, "request_id", None)
                except Exception:
                    pass

                # Add entry to database
                LogEntry.add_entry(
                    level=record.levelname,
                    message=message,
                    module=record.name,
                    request_id=request_id,
                )
        except Exception:
            # Don't let logging errors crash the application
            # Silently ignore - we don't want logging to break the app
            pass


class StdoutCapture:
    """Captures stdout/stderr and writes to both original stream and database."""

    # Pattern to match HTTP access logs: 127.0.0.1 - - [date] "METHOD /path HTTP/1.1" status ...
    HTTP_LOG_PATTERN = re.compile(r'^\d+\.\d+\.\d+\.\d+ - - \[.+\] ".+" \d+ ')
    # Pattern for "accepted" connection logs
    ACCEPTED_PATTERN = re.compile(r"^\(\d+\) (accepted|wsgi starting)")
    # Pattern to filter out static assets and polling requests
    STATIC_ASSET_PATTERN = re.compile(r'/assets/|/admin/console|/api/version-check')

    def __init__(self, original: TextIO, stream_name: str = "stdout") -> None:
        self.original = original
        self.stream_name = stream_name
        self._in_write = False  # Prevent recursion

    def write(self, msg: str) -> int:
        # Skip empty messages or just newlines
        if not msg or msg.strip() == "":
            return self.original.write(msg)

        # Filter out noise BEFORE writing to terminal
        if self.ACCEPTED_PATTERN.match(msg) or self.STATIC_ASSET_PATTERN.search(msg):
            return len(msg)  # Pretend we wrote it

        # Write to original stream
        result = self.original.write(msg)

        # Prevent recursion
        if self._in_write:
            return result

        # Try to capture to database
        self._in_write = True
        try:
            self._capture_to_db(msg)
        except Exception:
            pass  # Never let logging break the app
        finally:
            self._in_write = False

        return result

    def _capture_to_db(self, msg: str) -> None:
        """Capture message to database if app is available."""
        global _app_instance

        if _app_instance is None:
            return

        # Skip if message is just whitespace
        msg = msg.strip()
        if not msg:
            return

        # Skip traceback continuation lines (keep only first line of errors)
        if msg.startswith("  File ") or msg.startswith("    ") or msg.startswith("Traceback"):
            return

        # Convert gunicorn JSON access logs to traditional format for web console
        if msg.startswith("{") and '"gunicorn.access"' in msg:
            try:
                data = json.loads(msg)
                msg = (
                    f'{data.get("remote_addr", "-")} - - '
                    f'"{data.get("method", "?")} {data.get("path", "/")} HTTP/1.1" '
                    f'{data.get("status", "-")} -'
                )
            except (json.JSONDecodeError, KeyError):
                pass

        # Determine log level based on content
        level = "INFO"
        if "ERROR" in msg.upper() or "EXCEPTION" in msg.upper():
            level = "ERROR"
        elif "WARNING" in msg.upper() or "WARN" in msg.upper():
            level = "WARNING"
        elif "DEBUG" in msg.upper():
            level = "DEBUG"

        # Determine module based on content
        module = "stdout" if self.stream_name == "stdout" else "stderr"
        if self.HTTP_LOG_PATTERN.match(msg):
            module = "http"

        try:
            with _app_instance.app_context():
                LogEntry.add_entry(
                    level=level,
                    message=msg,
                    module=module,
                )
        except Exception:
            pass

    def flush(self) -> None:
        self.original.flush()

    def fileno(self) -> int:
        return self.original.fileno()

    def isatty(self) -> bool:
        return self.original.isatty()


def install_stdout_capture(app: Any) -> None:
    """Install stdout/stderr capture for the web console."""
    global _app_instance
    _app_instance = app

    # Only install if not already installed
    if not isinstance(sys.stdout, StdoutCapture):
        sys.stdout = StdoutCapture(sys.stdout, "stdout")  # type: ignore[assignment]
    if not isinstance(sys.stderr, StdoutCapture):
        sys.stderr = StdoutCapture(sys.stderr, "stderr")  # type: ignore[assignment]
