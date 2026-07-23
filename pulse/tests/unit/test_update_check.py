# -----------------------------------------------------------------------------
# sparQ - Update Check Tests
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""Unit tests for the update-check module and its non-identifying payload."""

import logging

import pytest

from system import update_check

# Every key the payload is ever allowed to contain — the guardrail behind the
# "no identifying information" promise. If a key is added here it must also be
# disclosed in the README, the first-boot notice, and /legal/telemetry.
ALLOWED_KEYS = {
    "product",
    "sparq_version",
    "edition",
    "operating_system",
    "architecture",
    "runtime_version",
    "locale",
    "installed_modules",
}

# Keys that would leak identity/instance data and must never appear.
FORBIDDEN_KEYS = {
    "instance_id", "id", "uuid", "identifier", "fingerprint",
    "hostname", "host", "ip", "ip_address", "mac",
    "email", "user", "username", "name", "organization", "org",
    "repository", "repo", "url", "location",
}


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    """Isolate state/status files to a temp dir and reset env vars."""
    monkeypatch.setenv("SPARQ_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("SPARQ_UPDATE_CHECK", raising=False)
    monkeypatch.delenv("SPARQ_CHECK_URL", raising=False)


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


class TestBuildPayload:
    def test_only_allowed_keys(self):
        payload = update_check.build_payload()
        assert set(payload) == ALLOWED_KEYS

    def test_no_identifying_keys(self):
        payload = update_check.build_payload()
        assert FORBIDDEN_KEYS.isdisjoint(payload)

    def test_product_is_sparq(self):
        assert update_check.build_payload()["product"] == "sparq"

    def test_scalar_fields_are_strings(self):
        payload = update_check.build_payload()
        for key in (
            "product", "sparq_version", "edition",
            "operating_system", "architecture", "runtime_version", "locale",
        ):
            assert isinstance(payload[key], str)
            assert payload[key]  # non-empty

    def test_installed_modules_shape(self):
        modules = update_check.build_payload()["installed_modules"]
        assert isinstance(modules, list)
        for module in modules:
            assert set(module) == {"name", "version"}
            assert isinstance(module["name"], str)
            assert isinstance(module["version"], str)


class TestRunCheck:
    def test_logs_when_behind(self, monkeypatch, caplog):
        monkeypatch.setattr(
            update_check, "_post_check",
            lambda url, payload: {"latest_version": "99.0.0"},
        )
        with caplog.at_level(logging.WARNING, logger="system.update_check"):
            status = update_check.run_check(force=True)
        assert "newer sparQ version" in caplog.text
        assert status is not None
        assert status["update_available"] is True
        assert status["latest_version"] == "99.0.0"

    def test_silent_when_current(self, monkeypatch, caplog):
        monkeypatch.setattr(
            update_check, "_post_check",
            lambda url, payload: {"latest_version": "0.0.1", "update_available": False},
        )
        with caplog.at_level(logging.WARNING, logger="system.update_check"):
            status = update_check.run_check(force=True)
        assert "newer sparQ version" not in caplog.text
        assert status["update_available"] is False

    def test_network_failure_is_silent(self, monkeypatch):
        monkeypatch.setattr(update_check, "_post_check", lambda url, payload: None)
        assert update_check.run_check(force=True) is None  # must not raise

    def test_failure_does_not_burn_the_day(self, monkeypatch):
        """A failed response must not record the day, so it retries next time."""
        monkeypatch.setattr(update_check, "_post_check", lambda url, payload: None)
        update_check.run_check()
        assert update_check._checked_today() is False

    def test_disabled_skips_request(self, monkeypatch):
        monkeypatch.setenv("SPARQ_UPDATE_CHECK", "false")
        calls = []
        monkeypatch.setattr(
            update_check, "_post_check",
            lambda url, payload: calls.append(url),
        )
        assert update_check.run_check() is None
        assert calls == []

    def test_dedupe_same_day(self, monkeypatch):
        calls = []

        def _fake(url, payload):
            calls.append(url)
            return {"latest_version": "99.0.0"}

        monkeypatch.setattr(update_check, "_post_check", _fake)
        update_check.run_check()  # posts and records today's date
        update_check.run_check()  # same day → skipped
        assert len(calls) == 1

    def test_status_is_persisted_and_readable(self, monkeypatch):
        monkeypatch.setattr(
            update_check, "_post_check",
            lambda url, payload: {
                "latest_version": "99.0.0",
                "update_available": True,
                "security_update": True,
                "release_url": "https://www.gosparq.com/changelog/",
            },
        )
        update_check.run_check(force=True)
        status = update_check.read_status()
        assert status is not None
        assert status["latest_version"] == "99.0.0"
        assert status["security_update"] is True
        assert status["release_url"] == "https://www.gosparq.com/changelog/"

    def test_posts_the_payload(self, monkeypatch):
        """run_check must send exactly build_payload() to the endpoint."""
        captured = {}

        def _fake(url, payload):
            captured["payload"] = payload
            return {"latest_version": "0.0.1"}

        monkeypatch.setattr(update_check, "_post_check", _fake)
        update_check.run_check(force=True)
        assert set(captured["payload"]) == ALLOWED_KEYS
        assert FORBIDDEN_KEYS.isdisjoint(captured["payload"])
