# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - Form Timing Integration Tests
#
# Tests for the form timing middleware (system/middleware/form_timing.py).
# Verifies timestamp generation, validation with time control, and edge cases
# like missing tokens, tampered tokens, and custom min_seconds.
# -----------------------------------------------------------------------------

from unittest.mock import patch

import pytest


@pytest.mark.integration
class TestFormTiming:
    """Tests for generate_form_timestamp and validate_form_timing."""

    def test_generate_returns_non_empty_string(self, app):
        with app.app_context():
            from system.middleware.form_timing import generate_form_timestamp

            token = generate_form_timestamp()
            assert isinstance(token, str)
            assert len(token) > 0

    def test_valid_timing_passes(self, app):
        with app.app_context():
            from system.middleware.form_timing import (
                generate_form_timestamp,
                validate_form_timing,
            )

            with patch("system.middleware.form_timing.time") as mock_time:
                mock_time.time.return_value = 1000.0
                token = generate_form_timestamp()

            with app.test_request_context(
                "/submit", method="POST", data={"_form_ts": token}
            ):
                with patch("system.middleware.form_timing.time") as mock_time:
                    mock_time.time.return_value = 1005.0
                    assert validate_form_timing() is True

    def test_too_fast_fails(self, app):
        with app.app_context():
            from system.middleware.form_timing import (
                generate_form_timestamp,
                validate_form_timing,
            )

            with patch("system.middleware.form_timing.time") as mock_time:
                mock_time.time.return_value = 1000.0
                token = generate_form_timestamp()

            with app.test_request_context(
                "/submit", method="POST", data={"_form_ts": token}
            ):
                with patch("system.middleware.form_timing.time") as mock_time:
                    mock_time.time.return_value = 1001.0
                    assert validate_form_timing() is False

    def test_missing_token_fails(self, app):
        with app.app_context():
            from system.middleware.form_timing import validate_form_timing

            with app.test_request_context("/submit", method="POST", data={}):
                assert validate_form_timing() is False

    def test_tampered_token_fails(self, app):
        with app.app_context():
            from system.middleware.form_timing import validate_form_timing

            with app.test_request_context(
                "/submit", method="POST", data={"_form_ts": "tampered-garbage-token"}
            ):
                assert validate_form_timing() is False

    def test_custom_min_seconds_respected(self, app):
        with app.app_context():
            from system.middleware.form_timing import (
                generate_form_timestamp,
                validate_form_timing,
            )

            with patch("system.middleware.form_timing.time") as mock_time:
                mock_time.time.return_value = 1000.0
                token = generate_form_timestamp()

            with app.test_request_context(
                "/submit", method="POST", data={"_form_ts": token}
            ):
                # 4 seconds elapsed, min_seconds=5 -> should fail
                with patch("system.middleware.form_timing.time") as mock_time:
                    mock_time.time.return_value = 1004.0
                    assert validate_form_timing(min_seconds=5) is False

                # 6 seconds elapsed, min_seconds=5 -> should pass
                with patch("system.middleware.form_timing.time") as mock_time:
                    mock_time.time.return_value = 1006.0
                    assert validate_form_timing(min_seconds=5) is True
