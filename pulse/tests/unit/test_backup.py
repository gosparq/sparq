# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - Backup Service Unit Tests
#
# Tests for system/backup/__init__.py. Verifies human-readable size formatting,
# backup zip validation (manifest + DB presence), SQLite hot backup via the
# backup API, and retention enforcement that trims oldest backups.
# -----------------------------------------------------------------------------

import json
import os
import sqlite3
import zipfile
from unittest.mock import patch

import pytest

from system.backup import (
    MAX_BACKUPS,
    backup_database,
    enforce_retention,
    format_size,
    validate_backup,
)


# ---------------------------------------------------------------------------
# 1. format_size — human-readable byte sizes
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFormatSize:

    def test_bytes(self):
        assert format_size(500) == "500.0 B"

    def test_zero_bytes(self):
        assert format_size(0) == "0.0 B"

    def test_kilobytes(self):
        assert format_size(1024) == "1.0 KB"

    def test_megabytes(self):
        assert format_size(1024 * 1024) == "1.0 MB"

    def test_gigabytes(self):
        assert format_size(1024 ** 3) == "1.0 GB"


# ---------------------------------------------------------------------------
# 2. validate_backup — zip file structure checks
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestValidateBackup:

    def test_valid_backup_passes(self, tmp_path):
        zip_path = tmp_path / "backup.zip"
        manifest = {"version": "0.5.0", "schema_version": 1}
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("manifest.json", json.dumps(manifest))
            zf.writestr("sparq.db", "fake-db-content")

        is_valid, msg, info = validate_backup(str(zip_path))
        assert is_valid is True
        assert msg == ""
        assert info is not None

    def test_missing_manifest_fails(self, tmp_path):
        zip_path = tmp_path / "backup.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("sparq.db", "fake-db-content")

        is_valid, msg, info = validate_backup(str(zip_path))
        assert is_valid is False
        assert "manifest" in msg.lower()
        assert info is None

    def test_missing_database_fails(self, tmp_path):
        zip_path = tmp_path / "backup.zip"
        manifest = {"version": "0.5.0", "schema_version": 1}
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("manifest.json", json.dumps(manifest))

        is_valid, msg, info = validate_backup(str(zip_path))
        assert is_valid is False
        assert "sparq.db" in msg
        assert info is None

    def test_invalid_zip_fails(self, tmp_path):
        bad_file = tmp_path / "notazip.zip"
        bad_file.write_text("this is not a zip file")

        is_valid, msg, info = validate_backup(str(bad_file))
        assert is_valid is False
        assert "zip" in msg.lower()
        assert info is None

    def test_manifest_parsed_into_info(self, tmp_path):
        zip_path = tmp_path / "backup.zip"
        manifest = {
            "version": "0.5.173",
            "schema_version": 1,
            "reason": "manual",
        }
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("manifest.json", json.dumps(manifest))
            zf.writestr("sparq.db", "fake-db-content")

        _, _, info = validate_backup(str(zip_path))
        assert info["version"] == "0.5.173"
        assert info["reason"] == "manual"


# ---------------------------------------------------------------------------
# 3. backup_database — SQLite Backup API copy
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBackupDatabase:

    def test_creates_valid_copy_of_source_db(self, tmp_path):
        src_path = str(tmp_path / "source.db")
        dst_path = str(tmp_path / "backup.db")

        conn = sqlite3.connect(src_path)
        conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO items (name) VALUES ('alpha')")
        conn.execute("INSERT INTO items (name) VALUES ('beta')")
        conn.commit()
        conn.close()

        backup_database(src_path, dst_path)

        assert os.path.exists(dst_path)
        dst_conn = sqlite3.connect(dst_path)
        rows = dst_conn.execute("SELECT name FROM items ORDER BY name").fetchall()
        dst_conn.close()
        assert rows == [("alpha",), ("beta",)]


# ---------------------------------------------------------------------------
# 4. enforce_retention — delete oldest beyond MAX_BACKUPS
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEnforceRetention:

    def _create_fake_backups(self, backup_dir, count):
        """Create numbered backup zips with manifests for sorting."""
        os.makedirs(backup_dir, exist_ok=True)
        for i in range(count):
            ts = f"2026010{i + 1:01d}-120000" if i < 9 else f"202601{i + 1}-120000"
            filename = f"sparq-backup-{ts}-v0.5.0.zip"
            zip_path = os.path.join(backup_dir, filename)
            manifest = {
                "version": "0.5.0",
                "schema_version": 1,
                "created_at": f"2026-01-{i + 1:02d}T12:00:00Z",
                "reason": "test",
            }
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("manifest.json", json.dumps(manifest))
                zf.writestr("sparq.db", "fake")

    @patch("system.backup.get_backup_dir")
    @patch("system.backup.get_data_dir")
    def test_deletes_oldest_beyond_max(self, mock_data_dir, mock_backup_dir, tmp_path):
        backup_dir = str(tmp_path / "backups")
        mock_backup_dir.return_value = backup_dir
        mock_data_dir.return_value = str(tmp_path)

        self._create_fake_backups(backup_dir, MAX_BACKUPS + 3)

        enforce_retention()

        remaining = [f for f in os.listdir(backup_dir) if f.endswith(".zip")]
        assert len(remaining) == MAX_BACKUPS

    @patch("system.backup.get_backup_dir")
    @patch("system.backup.get_data_dir")
    def test_keeps_all_when_under_max(self, mock_data_dir, mock_backup_dir, tmp_path):
        backup_dir = str(tmp_path / "backups")
        mock_backup_dir.return_value = backup_dir
        mock_data_dir.return_value = str(tmp_path)

        count = MAX_BACKUPS - 2
        self._create_fake_backups(backup_dir, count)

        enforce_retention()

        remaining = [f for f in os.listdir(backup_dir) if f.endswith(".zip")]
        assert len(remaining) == count
