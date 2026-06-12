# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - SMS Service Unit Tests
#
# Tests for system/sms/service.py. Verifies configuration detection, HTTP
# request construction with Bearer auth, success/failure status codes,
# timeout/network error handling, and phone number masking.
# -----------------------------------------------------------------------------

from unittest.mock import MagicMock, patch

import pytest
import requests

from system.sms.service import _mask_phone, is_configured, send_sms


# ---------------------------------------------------------------------------
# 1. is_configured — env var presence check
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestIsConfigured:

    @patch.dict("os.environ", {"SPARQSMS_API_KEY": "key123"})
    @patch("system.sms.service.SPARQSMS_API_URL", "https://api.example.com/sms")
    def test_both_set_returns_true(self):
        assert is_configured() is True

    @patch.dict("os.environ", {"SPARQSMS_API_KEY": "key123"}, clear=False)
    @patch("system.sms.service.SPARQSMS_API_URL", "")
    def test_url_missing_returns_false(self):
        assert is_configured() is False

    @patch.dict("os.environ", {}, clear=True)
    @patch("system.sms.service.SPARQSMS_API_URL", "https://api.example.com/sms")
    def test_key_missing_returns_false(self):
        assert is_configured() is False


# ---------------------------------------------------------------------------
# 2. send_sms — HTTP POST with Bearer auth
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSendSms:

    @patch("system.sms.service.requests.post")
    @patch.dict("os.environ", {"SPARQSMS_API_KEY": "test-key"})
    @patch("system.sms.service.SPARQSMS_API_URL", "https://api.example.com/sms")
    def test_success_200(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        assert send_sms("+15551234567", "Hello") is True

    @patch("system.sms.service.requests.post")
    @patch.dict("os.environ", {"SPARQSMS_API_KEY": "test-key"})
    @patch("system.sms.service.SPARQSMS_API_URL", "https://api.example.com/sms")
    def test_success_202(self, mock_post):
        mock_post.return_value = MagicMock(status_code=202)
        assert send_sms("+15551234567", "Hello") is True

    @patch("system.sms.service.requests.post")
    @patch.dict("os.environ", {"SPARQSMS_API_KEY": "test-key"})
    @patch("system.sms.service.SPARQSMS_API_URL", "https://api.example.com/sms")
    def test_failure_500(self, mock_post):
        mock_post.return_value = MagicMock(status_code=500, text="Internal Server Error")
        assert send_sms("+15551234567", "Hello") is False

    @patch("system.sms.service.requests.post")
    @patch.dict("os.environ", {"SPARQSMS_API_KEY": "test-key"})
    @patch("system.sms.service.SPARQSMS_API_URL", "https://api.example.com/sms")
    def test_timeout_returns_false(self, mock_post):
        mock_post.side_effect = requests.Timeout("timed out")
        assert send_sms("+15551234567", "Hello") is False

    @patch("system.sms.service.requests.post")
    @patch.dict("os.environ", {"SPARQSMS_API_KEY": "test-key"})
    @patch("system.sms.service.SPARQSMS_API_URL", "https://api.example.com/sms")
    def test_network_error_returns_false(self, mock_post):
        mock_post.side_effect = requests.ConnectionError("refused")
        assert send_sms("+15551234567", "Hello") is False

    @patch.dict("os.environ", {}, clear=True)
    @patch("system.sms.service.SPARQSMS_API_URL", "")
    def test_not_configured_returns_false(self):
        assert send_sms("+15551234567", "Hello") is False

    @patch("system.sms.service.requests.post")
    @patch.dict("os.environ", {"SPARQSMS_API_KEY": "my-secret-key"})
    @patch("system.sms.service.SPARQSMS_API_URL", "https://api.example.com/sms")
    def test_request_includes_bearer_auth(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        send_sms("+15551234567", "Hello")

        _, kwargs = mock_post.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer my-secret-key"

    @patch("system.sms.service.requests.post")
    @patch.dict("os.environ", {"SPARQSMS_API_KEY": "test-key"})
    @patch("system.sms.service.SPARQSMS_API_URL", "https://api.example.com/sms")
    def test_request_body_has_to_and_body(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        send_sms("+15551234567", "Test message")

        _, kwargs = mock_post.call_args
        assert kwargs["json"]["to"] == "+15551234567"
        assert kwargs["json"]["body"] == "Test message"


# ---------------------------------------------------------------------------
# 3. _mask_phone — phone number masking for logs
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMaskPhone:

    def test_full_number(self):
        assert _mask_phone("+15551234567") == "***4567"

    def test_short_number(self):
        assert _mask_phone("1234") == "***1234"

    def test_number_with_formatting(self):
        assert _mask_phone("(555) 123-4567") == "***4567"
