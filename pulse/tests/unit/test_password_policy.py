# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - Password Policy Unit Tests
#
# Tests for the password_policy module (P0 Stage 8). Verifies complexity
# validation rules and HaveIBeenPwned breach checking with mocked API.
# -----------------------------------------------------------------------------

import hashlib
from unittest.mock import MagicMock, patch

import pytest

from system.auth.password_policy import (
    MAX_LENGTH,
    MIN_LENGTH,
    is_breached,
    validate_password,
)


# ---------------------------------------------------------------------------
# 1. validate_password — complexity rules
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestValidatePassword:
    """Test password complexity validation rules."""

    def test_valid_password_returns_empty(self):
        """A password meeting all requirements should return no errors."""
        assert validate_password("Str0ngPass") == []

    def test_valid_password_minimum_viable(self):
        """The shortest possible valid password should pass."""
        assert validate_password("Abcdefg1") == []

    def test_too_short(self):
        """Passwords shorter than MIN_LENGTH should be rejected."""
        errors = validate_password("Ab1cdef")
        assert len(errors) == 1
        assert str(MIN_LENGTH) in errors[0]

    def test_too_long(self):
        """Passwords longer than MAX_LENGTH should be rejected."""
        password = "A" * (MAX_LENGTH + 1)
        errors = validate_password(password)
        assert any(str(MAX_LENGTH) in e for e in errors)

    def test_exactly_min_length(self):
        """A password exactly MIN_LENGTH chars with all rules met should pass."""
        password = "Abcdef1x"
        assert len(password) == MIN_LENGTH
        assert validate_password(password) == []

    def test_exactly_max_length(self):
        """A password exactly MAX_LENGTH chars with all rules met should pass."""
        password = "Aa1" + "x" * (MAX_LENGTH - 3)
        assert len(password) == MAX_LENGTH
        assert validate_password(password) == []

    def test_missing_uppercase(self):
        """Passwords without uppercase letters should be rejected."""
        errors = validate_password("alllower1")
        assert any("uppercase" in e.lower() for e in errors)

    def test_missing_lowercase(self):
        """Passwords without lowercase letters should be rejected."""
        errors = validate_password("ALLUPPER1")
        assert any("lowercase" in e.lower() for e in errors)

    def test_missing_digit(self):
        """Passwords without digits should be rejected."""
        errors = validate_password("NoDigitsHere")
        assert any("number" in e.lower() for e in errors)

    def test_all_rules_violated(self):
        """A password violating every rule should return multiple errors."""
        errors = validate_password("!@#")
        assert len(errors) >= 3  # too short + no upper + no lower + no digit

    def test_multiple_violations_reported(self):
        """All failing rules should be reported, not just the first."""
        errors = validate_password("12345678")  # no upper, no lower
        assert len(errors) == 2

    def test_special_chars_allowed(self):
        """Special characters should not cause rejection."""
        assert validate_password("P@ssw0rd!") == []

    def test_unicode_allowed(self):
        """Unicode characters should be counted toward length."""
        assert validate_password("Pässw0rd") == []

    def test_spaces_allowed(self):
        """Spaces in passwords should not cause rejection."""
        assert validate_password("My Pass1 word") == []

    def test_empty_password(self):
        """Empty password should report all violations."""
        errors = validate_password("")
        assert len(errors) >= 3  # too short + no upper + no lower + no digit


# ---------------------------------------------------------------------------
# 2. is_breached — HaveIBeenPwned API (mocked)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestIsBreached:
    """Test breach checking against HaveIBeenPwned API."""

    def _build_api_response(self, password: str, include_match: bool) -> str:
        """Build a fake HIBP API response body.

        The API returns lines of HASH_SUFFIX:COUNT for all hashes sharing
        the same 5-char prefix.
        """
        sha1 = hashlib.sha1(password.encode()).hexdigest().upper()
        suffix = sha1[5:]

        lines = []
        # Add some decoy entries
        lines.append("0000000000000000000000000000000000A:3")
        lines.append("1111111111111111111111111111111111B:7")
        if include_match:
            lines.append(f"{suffix}:42")
        lines.append("FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF:1")
        return "\n".join(lines)

    @patch("system.auth.password_policy.urllib.request.urlopen")
    def test_breached_password_returns_true(self, mock_urlopen):
        """A password found in the breach database should return True."""
        password = "Password1"
        response_body = self._build_api_response(password, include_match=True)

        mock_resp = MagicMock()
        mock_resp.read.return_value = response_body.encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        assert is_breached(password) is True

    @patch("system.auth.password_policy.urllib.request.urlopen")
    def test_clean_password_returns_false(self, mock_urlopen):
        """A password NOT in the breach database should return False."""
        password = "xK9mP2vL7nQ4zR8"
        response_body = self._build_api_response(password, include_match=False)

        mock_resp = MagicMock()
        mock_resp.read.return_value = response_body.encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        assert is_breached(password) is False

    @patch("system.auth.password_policy.urllib.request.urlopen")
    def test_network_error_fails_open(self, mock_urlopen):
        """Network errors should fail open (return False)."""
        mock_urlopen.side_effect = ConnectionError("Network unreachable")
        assert is_breached("AnyPassword1") is False

    @patch("system.auth.password_policy.urllib.request.urlopen")
    def test_timeout_fails_open(self, mock_urlopen):
        """Timeout errors should fail open (return False)."""
        from urllib.error import URLError
        mock_urlopen.side_effect = URLError("timeout")
        assert is_breached("AnyPassword1") is False

    @patch("system.auth.password_policy.urllib.request.urlopen")
    def test_api_sends_only_prefix(self, mock_urlopen):
        """Only the first 5 chars of the SHA1 hash should be sent to the API."""
        password = "TestPassword1"
        sha1 = hashlib.sha1(password.encode()).hexdigest().upper()
        expected_prefix = sha1[:5]

        mock_resp = MagicMock()
        mock_resp.read.return_value = b"0000000000000000000000000000000000A:1"
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        is_breached(password)

        # Verify the URL contains only the prefix
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        assert req.full_url == f"https://api.pwnedpasswords.com/range/{expected_prefix}"

    @patch("system.auth.password_policy.urllib.request.urlopen")
    def test_user_agent_header_set(self, mock_urlopen):
        """The request should include a sparQ User-Agent header."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"0000000000000000000000000000000000A:1"
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        is_breached("TestPassword1")

        req = mock_urlopen.call_args[0][0]
        assert req.get_header("User-agent") == "sparQ-PasswordCheck"

    @patch("system.auth.password_policy.urllib.request.urlopen")
    def test_malformed_api_response_fails_open(self, mock_urlopen):
        """Malformed API response should fail open."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"not a valid response\ngarbage data"
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        # Should not raise, should return False
        assert is_breached("TestPassword1") is False
