# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - Device Detection Integration Tests
#
# Tests for system/device/detection.py: detect_device(), get_device_type(),
# set_device_type(), clear_device_type(), and is_mobile(). Requires Flask
# request context for request headers, session, and query parameters.
# -----------------------------------------------------------------------------

import pytest


MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
)
DESKTOP_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


@pytest.mark.integration
class TestDetectDevice:
    """Test User-Agent based device detection."""

    def test_mobile_user_agent_returns_mobile(self, app):
        with app.test_request_context(headers={"User-Agent": MOBILE_UA}):
            from system.device.detection import detect_device

            assert detect_device() == "mobile"

    def test_desktop_user_agent_returns_desktop(self, app):
        with app.test_request_context(headers={"User-Agent": DESKTOP_UA}):
            from system.device.detection import detect_device

            assert detect_device() == "desktop"

    def test_empty_user_agent_returns_desktop(self, app):
        with app.test_request_context(headers={"User-Agent": ""}):
            from system.device.detection import detect_device

            assert detect_device() == "desktop"

    def test_android_user_agent_returns_mobile(self, app):
        android_ua = "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120.0"
        with app.test_request_context(headers={"User-Agent": android_ua}):
            from system.device.detection import detect_device

            assert detect_device() == "mobile"


@pytest.mark.integration
class TestGetDeviceType:
    """Test get_device_type() with query param and session overrides."""

    def test_query_param_overrides_user_agent(self, app):
        with app.test_request_context(
            "/?device=mobile", headers={"User-Agent": DESKTOP_UA}
        ):
            app.config["SECRET_KEY"] = "test-secret"
            from system.device.detection import get_device_type

            assert get_device_type() == "mobile"

    def test_query_param_desktop_overrides_mobile_ua(self, app):
        with app.test_request_context(
            "/?device=desktop", headers={"User-Agent": MOBILE_UA}
        ):
            app.config["SECRET_KEY"] = "test-secret"
            from system.device.detection import get_device_type

            assert get_device_type() == "desktop"

    def test_falls_back_to_user_agent(self, app):
        with app.test_request_context(headers={"User-Agent": MOBILE_UA}):
            from system.device.detection import get_device_type

            assert get_device_type() == "mobile"


@pytest.mark.integration
class TestSetDeviceType:
    """Test manual device type override via session."""

    def test_sets_session_value(self, app):
        with app.test_request_context():
            app.config["SECRET_KEY"] = "test-secret"
            from flask import session

            from system.device.detection import DEVICE_OVERRIDE_KEY, set_device_type

            set_device_type("mobile")
            assert session[DEVICE_OVERRIDE_KEY] == "mobile"

    def test_rejects_invalid_type(self, app):
        with app.test_request_context():
            from system.device.detection import set_device_type

            with pytest.raises(ValueError, match="mobile.*desktop|desktop.*mobile"):
                set_device_type("tablet")


@pytest.mark.integration
class TestClearDeviceType:
    """Test clearing device type override from session."""

    def test_clears_session_value(self, app):
        with app.test_request_context():
            app.config["SECRET_KEY"] = "test-secret"
            from flask import session

            from system.device.detection import (
                DEVICE_OVERRIDE_KEY,
                clear_device_type,
                set_device_type,
            )

            set_device_type("mobile")
            assert DEVICE_OVERRIDE_KEY in session

            clear_device_type()
            assert DEVICE_OVERRIDE_KEY not in session

    def test_clear_when_not_set_is_safe(self, app):
        with app.test_request_context():
            app.config["SECRET_KEY"] = "test-secret"
            from system.device.detection import clear_device_type

            clear_device_type()


@pytest.mark.integration
class TestIsMobile:
    """Test the is_mobile() convenience function."""

    def test_returns_true_for_mobile(self, app):
        with app.test_request_context(headers={"User-Agent": MOBILE_UA}):
            from system.device.detection import is_mobile

            assert is_mobile() is True

    def test_returns_false_for_desktop(self, app):
        with app.test_request_context(headers={"User-Agent": DESKTOP_UA}):
            from system.device.detection import is_mobile

            assert is_mobile() is False
