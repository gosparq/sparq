# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - Email Gateway Unit Tests
#
# Tests for the email gateway fallback transport in system/email/service.py.
# Verifies gateway config detection, is_configured() with gateway-only setups,
# GatewayEmailService HTTP construction (Bearer auth, text_body, status codes),
# and send_email() provider-first / gateway-fallback selection.
# -----------------------------------------------------------------------------

from unittest.mock import MagicMock, patch

import pytest
import requests

from system.email.service import (
    GatewayEmailService,
    _gateway_config,
    is_configured,
    send_email,
)

GATEWAY_ENV = {
    "SPARQ_GATEWAY_URL": "https://mail.example.com",
    "SPARQ_GATEWAY_BYPASS_TOKEN": "bypass-123",
}


# ---------------------------------------------------------------------------
# 1. _gateway_config — env var presence check
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGatewayConfig:

    @patch.dict("os.environ", GATEWAY_ENV, clear=True)
    def test_both_set_returns_tuple(self):
        assert _gateway_config() == ("https://mail.example.com", "bypass-123")

    @patch.dict("os.environ", {"SPARQ_GATEWAY_URL": "https://x"}, clear=True)
    def test_token_missing_returns_none(self):
        assert _gateway_config() is None

    @patch.dict("os.environ", {"SPARQ_GATEWAY_BYPASS_TOKEN": "tok"}, clear=True)
    def test_url_missing_returns_none(self):
        assert _gateway_config() is None

    @patch.dict("os.environ", {}, clear=True)
    def test_nothing_set_returns_none(self):
        assert _gateway_config() is None


# ---------------------------------------------------------------------------
# 2. is_configured — true when a provider OR the gateway is available
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestIsConfigured:

    @patch("system.email.service.EmailConfig.from_env_and_settings", return_value=None)
    @patch.dict("os.environ", GATEWAY_ENV, clear=True)
    def test_gateway_only_is_configured(self, _mock_cfg):
        assert is_configured() is True

    @patch("system.email.service.EmailConfig.from_env_and_settings", return_value=None)
    @patch.dict("os.environ", {}, clear=True)
    def test_nothing_configured(self, _mock_cfg):
        assert is_configured() is False


# ---------------------------------------------------------------------------
# 3. GatewayEmailService.send — HTTP POST with Bearer auth
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGatewayEmailService:

    @patch("requests.post")
    @patch.dict("os.environ", {}, clear=True)
    def test_send_posts_bearer_and_text_body(self, mock_post):
        mock_post.return_value = MagicMock(status_code=202)

        svc = GatewayEmailService("https://mail.example.com/", "tok")
        ok = svc.send("u@example.com", "Subj", "<p>hi</p>", text_body="hi")

        assert ok is True
        url = mock_post.call_args[0][0]
        kwargs = mock_post.call_args.kwargs
        assert url == "https://mail.example.com/send"  # trailing slash stripped
        assert kwargs["headers"]["Authorization"] == "Bearer tok"
        assert kwargs["json"]["body"] == "<p>hi</p>"
        assert kwargs["json"]["text_body"] == "hi"  # plain-text part preserved
        assert kwargs["json"]["site_id"] == "sparq"  # generic, not "sparq-signup"

    @patch("requests.post")
    @patch.dict("os.environ", {}, clear=True)
    def test_text_body_omitted_when_absent(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        svc = GatewayEmailService("https://mail.example.com", "tok")
        assert svc.send("u@example.com", "S", "<p>x</p>") is True
        assert "text_body" not in mock_post.call_args.kwargs["json"]

    @patch("requests.post")
    @patch.dict("os.environ", {}, clear=True)
    def test_send_returns_false_on_error_status(self, mock_post):
        mock_post.return_value = MagicMock(status_code=500, text="boom")
        svc = GatewayEmailService("https://mail.example.com", "tok")
        assert svc.send("u@example.com", "S", "<p>x</p>") is False

    @patch("requests.post", side_effect=requests.exceptions.Timeout)
    @patch.dict("os.environ", {}, clear=True)
    def test_send_returns_false_on_network_error(self, _mock_post):
        svc = GatewayEmailService("https://mail.example.com", "tok")
        assert svc.send("u@example.com", "S", "<p>x</p>") is False


# ---------------------------------------------------------------------------
# 4. send_email — provider-first, gateway-fallback selection
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSendEmailSelection:

    @patch("requests.post")
    @patch("system.email.service.EmailConfig.from_env_and_settings", return_value=None)
    @patch.dict("os.environ", GATEWAY_ENV, clear=True)
    def test_falls_back_to_gateway_when_no_provider(self, _mock_cfg, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        assert send_email("u@example.com", "S", "<p>x</p>", text_body="x") is True
        assert mock_post.called

    @patch("requests.post")
    @patch("system.email.service.EmailConfig.from_env_and_settings", return_value=None)
    @patch.dict("os.environ", {}, clear=True)
    def test_not_configured_returns_false_without_gateway(self, _mock_cfg, mock_post):
        assert send_email("u@example.com", "S", "<p>x</p>") is False
        assert not mock_post.called

    @patch("requests.post")
    @patch("system.email.service.EmailService")
    @patch.dict("os.environ", GATEWAY_ENV, clear=True)
    def test_prefers_provider_over_gateway(self, mock_email_service, mock_post):
        fake_cfg = MagicMock()
        fake_cfg.provider = "custom"
        mock_email_service.return_value.send.return_value = True

        with patch(
            "system.email.service.EmailConfig.from_env_and_settings",
            return_value=fake_cfg,
        ):
            assert send_email("u@example.com", "S", "<p>x</p>") is True

        mock_email_service.return_value.send.assert_called_once()
        assert not mock_post.called  # gateway never hit when a provider exists
