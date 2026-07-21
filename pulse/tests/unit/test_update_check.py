# -----------------------------------------------------------------------------
# sparQ - Update Check Tests
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""Unit tests for the anonymous update-check module."""

import logging

import pytest

from system import update_check


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    """Isolate state file to a temp dir and reset the opt-out env var."""
    monkeypatch.setenv("SPARQ_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("SPARQ_UPDATE_CHECK", raising=False)
    monkeypatch.delenv("SPARQ_UPDATE_URL", raising=False)


class TestVersionCompare:
    @pytest.mark.parametrize(
        "remote,local,expected",
        [
            ("1.1.0", "1.0.0", True),
            ("1.0.1", "1.0.0", True),
            ("2.0.0", "1.9.9", True),
            ("1.0.0", "1.0.0", False),
            ("1.0.0", "1.1.0", False),
            ("1.0", "1.0.0", False),
            ("v1.2.0", "1.1.0", True),
            ("1.2.0+abc.123", "1.2.0", False),
        ],
    )
    def test_is_newer(self, remote, local, expected):
        assert update_check.is_newer(remote, local) is expected

    def test_is_newer_handles_garbage(self):
        assert update_check.is_newer("dev", "1.0.0") is False
        assert update_check.is_newer("1.0.0", "dev") is False


class TestEnabled:
    def test_enabled_by_default(self, monkeypatch):
        monkeypatch.delenv("SPARQ_UPDATE_CHECK", raising=False)
        assert update_check.is_enabled() is True

    @pytest.mark.parametrize("value", ["false", "0", "no", "off", "FALSE"])
    def test_disabled_via_env(self, monkeypatch, value):
        monkeypatch.setenv("SPARQ_UPDATE_CHECK", value)
        assert update_check.is_enabled() is False


class TestRunCheck:
    def test_logs_when_behind(self, monkeypatch, caplog):
        monkeypatch.setattr(update_check, "_fetch_latest", lambda url: "99.0.0")
        # Target the module logger explicitly so the assertion is independent of
        # whatever level the parent "system" logger has been set to elsewhere.
        with caplog.at_level(logging.WARNING, logger="system.update_check"):
            update_check.run_check(force=True)
        assert "newer sparQ version" in caplog.text

    def test_silent_when_current(self, monkeypatch, caplog):
        monkeypatch.setattr(update_check, "_fetch_latest", lambda url: "0.0.1")
        with caplog.at_level(logging.WARNING, logger="system.update_check"):
            update_check.run_check(force=True)
        assert "newer sparQ version" not in caplog.text

    def test_network_failure_is_silent(self, monkeypatch):
        monkeypatch.setattr(update_check, "_fetch_latest", lambda url: None)
        update_check.run_check(force=True)  # must not raise

    def test_disabled_skips_fetch(self, monkeypatch):
        monkeypatch.setenv("SPARQ_UPDATE_CHECK", "false")
        calls = []
        monkeypatch.setattr(update_check, "_fetch_latest", lambda url: calls.append(url))
        update_check.run_check()
        assert calls == []

    def test_dedupe_same_day(self, monkeypatch):
        calls = []

        def _fake(url):
            calls.append(url)
            return "99.0.0"

        monkeypatch.setattr(update_check, "_fetch_latest", _fake)
        update_check.run_check()  # fetches and records today's date
        update_check.run_check()  # same day → skipped
        assert len(calls) == 1
