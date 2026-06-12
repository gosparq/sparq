# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - Database Log Handler Integration Tests
#
# Tests for system/logging/db_handler.py: LogEntry model, DatabaseLogHandler,
# and StdoutCapture. Verifies log creation, trimming, handler filtering,
# and stdout capture with noise suppression.
# -----------------------------------------------------------------------------

import logging
from unittest.mock import MagicMock, patch

import pytest


# =========================================================================
# 1. LogEntry Model
# =========================================================================

@pytest.mark.integration
class TestLogEntry:
    """Tests for the LogEntry database model."""

    def test_add_entry_creates_record(self, app, db_session):
        from system.logging.db_handler import LogEntry

        with app.app_context():
            entry = LogEntry.add_entry(level="INFO", message="hello world")
            assert entry.id is not None
            assert entry.level == "INFO"
            assert entry.message == "hello world"
            assert entry.timestamp is not None

    def test_add_entry_stores_request_id(self, app, db_session):
        from system.logging.db_handler import LogEntry

        with app.app_context():
            entry = LogEntry.add_entry(
                level="WARNING",
                message="with request id",
                module="test.module",
                request_id="req-abc-123",
            )
            assert entry.request_id == "req-abc-123"
            assert entry.module == "test.module"

    def test_get_recent_returns_newest_first(self, app, db_session):
        from system.logging.db_handler import LogEntry

        with app.app_context():
            LogEntry.add_entry(level="INFO", message="first")
            LogEntry.add_entry(level="INFO", message="second")
            LogEntry.add_entry(level="INFO", message="third")

            recent = LogEntry.get_recent(limit=3)
            assert len(recent) == 3
            assert recent[0].message == "third"
            assert recent[2].message == "first"

    def test_get_recent_respects_limit(self, app, db_session):
        from system.logging.db_handler import LogEntry

        with app.app_context():
            for i in range(5):
                LogEntry.add_entry(level="INFO", message=f"msg {i}")

            recent = LogEntry.get_recent(limit=2)
            assert len(recent) == 2

    def test_trim_enforces_max_entries(self, app, db_session):
        from system.logging.db_handler import LogEntry

        with app.app_context():
            original_max = LogEntry.MAX_ENTRIES
            LogEntry.MAX_ENTRIES = 5
            try:
                for i in range(8):
                    LogEntry.add_entry(level="INFO", message=f"entry {i}")

                count = LogEntry.query.count()
                assert count <= 5
            finally:
                LogEntry.MAX_ENTRIES = original_max

    def test_clear_all_removes_everything_and_returns_count(self, app, db_session):
        from system.logging.db_handler import LogEntry

        with app.app_context():
            LogEntry.add_entry(level="INFO", message="one")
            LogEntry.add_entry(level="INFO", message="two")
            LogEntry.add_entry(level="INFO", message="three")

            deleted = LogEntry.clear_all()
            assert deleted == 3
            assert LogEntry.query.count() == 0


# =========================================================================
# 2. DatabaseLogHandler
# =========================================================================

@pytest.mark.integration
class TestDatabaseLogHandler:
    """Tests for the DatabaseLogHandler logging handler."""

    def _make_record(self, name, level, message):
        """Create a LogRecord for testing."""
        return logging.LogRecord(
            name=name,
            level=level,
            pathname="test.py",
            lineno=1,
            msg=message,
            args=(),
            exc_info=None,
        )

    def test_emit_stores_record(self, app, db_session):
        from system.logging.db_handler import DatabaseLogHandler, LogEntry

        with app.app_context():
            handler = DatabaseLogHandler(app=app, level=logging.INFO)
            handler.setFormatter(logging.Formatter("%(message)s"))
            record = self._make_record("myapp", logging.INFO, "test log message")
            handler.emit(record)

            entries = LogEntry.get_recent(limit=1)
            assert len(entries) == 1
            assert entries[0].message == "test log message"
            assert entries[0].level == "INFO"

    def test_emit_skips_sqlalchemy_logs(self, app, db_session):
        from system.logging.db_handler import DatabaseLogHandler, LogEntry

        with app.app_context():
            handler = DatabaseLogHandler(app=app, level=logging.INFO)
            handler.setFormatter(logging.Formatter("%(message)s"))

            record = self._make_record("sqlalchemy.engine", logging.INFO, "SELECT 1")
            handler.emit(record)

            assert LogEntry.query.count() == 0

    def test_emit_skips_werkzeug_logs(self, app, db_session):
        from system.logging.db_handler import DatabaseLogHandler, LogEntry

        with app.app_context():
            handler = DatabaseLogHandler(app=app, level=logging.INFO)
            handler.setFormatter(logging.Formatter("%(message)s"))

            record = self._make_record("werkzeug", logging.INFO, "GET /health 200")
            handler.emit(record)

            assert LogEntry.query.count() == 0

    def test_emit_skips_own_module_logs(self, app, db_session):
        from system.logging.db_handler import DatabaseLogHandler, LogEntry

        with app.app_context():
            handler = DatabaseLogHandler(app=app, level=logging.INFO)
            handler.setFormatter(logging.Formatter("%(message)s"))

            record = self._make_record("system.logging.db_handler", logging.INFO, "internal")
            handler.emit(record)

            assert LogEntry.query.count() == 0

    def test_emit_survives_db_error(self, app, db_session):
        """Handler silently swallows database errors instead of crashing."""
        from system.logging.db_handler import DatabaseLogHandler

        with app.app_context():
            handler = DatabaseLogHandler(app=app, level=logging.INFO)
            handler.setFormatter(logging.Formatter("%(message)s"))

            with patch(
                "system.logging.db_handler.LogEntry.add_entry",
                side_effect=RuntimeError("db exploded"),
            ):
                record = self._make_record("myapp", logging.ERROR, "boom")
                # Should not raise
                handler.emit(record)


# =========================================================================
# 3. StdoutCapture
# =========================================================================

@pytest.mark.integration
class TestStdoutCapture:
    """Tests for the StdoutCapture stream wrapper."""

    def test_write_passes_through_to_original(self, app):
        from system.logging.db_handler import StdoutCapture

        original = MagicMock()
        original.write.return_value = 11
        capture = StdoutCapture(original, "stdout")

        result = capture.write("hello world")
        original.write.assert_called_once_with("hello world")
        assert result == 11

    def test_filters_accepted_connections(self, app):
        from system.logging.db_handler import StdoutCapture

        original = MagicMock()
        capture = StdoutCapture(original, "stdout")

        msg = "(12345) accepted connection"
        result = capture.write(msg)
        original.write.assert_not_called()
        assert result == len(msg)

    def test_filters_static_assets(self, app):
        from system.logging.db_handler import StdoutCapture

        original = MagicMock()
        capture = StdoutCapture(original, "stdout")

        msg = 'GET /assets/css/main.css HTTP/1.1'
        result = capture.write(msg)
        original.write.assert_not_called()
        assert result == len(msg)

    def test_prevents_recursion(self, app):
        from system.logging.db_handler import StdoutCapture

        original = MagicMock()
        original.write.return_value = 5
        capture = StdoutCapture(original, "stdout")

        # Simulate re-entrant write by setting the recursion guard
        capture._in_write = True
        capture.write("reentrant call")
        original.write.assert_called_once_with("reentrant call")
        # _capture_to_db should NOT be called because _in_write is True;
        # verify it stayed True throughout (no toggle)
        assert capture._in_write is True
