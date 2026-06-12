# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - Token Manager Unit Tests
#
# Tests for system/oauth/token_manager.py. Verifies Fernet-based encryption
# round-trips, empty-string handling, token expiry checks with buffer logic,
# and expiry calculation from seconds.
# -----------------------------------------------------------------------------

from datetime import datetime, timedelta, timezone

import pytest

from system.oauth.token_manager import TokenManager


# ---------------------------------------------------------------------------
# 1. TokenManager.encrypt / decrypt — Fernet symmetric encryption
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestTokenEncryption:

    @classmethod
    def setup_class(cls):
        TokenManager._init_fernet("test-secret")

    def test_roundtrip_encrypt_decrypt(self):
        plaintext = "oauth-access-token-abc123"
        ciphertext = TokenManager.encrypt(plaintext)
        assert TokenManager.decrypt(ciphertext) == plaintext

    def test_encrypt_empty_string_returns_empty(self):
        assert TokenManager.encrypt("") == ""

    def test_decrypt_empty_string_returns_empty(self):
        assert TokenManager.decrypt("") == ""

    def test_invalid_ciphertext_returns_empty(self):
        assert TokenManager.decrypt("not-valid-base64-ciphertext") == ""

    def test_wrong_key_returns_empty(self):
        TokenManager._init_fernet("key-one")
        ciphertext = TokenManager.encrypt("secret-data")

        TokenManager._init_fernet("key-two")
        assert TokenManager.decrypt(ciphertext) == ""

        # Restore for other tests
        TokenManager._init_fernet("test-secret")

    def test_two_encryptions_differ(self):
        """Fernet uses a random nonce so identical plaintext produces different ciphertext."""
        a = TokenManager.encrypt("same-value")
        b = TokenManager.encrypt("same-value")
        assert a != b


# ---------------------------------------------------------------------------
# 2. TokenManager.is_token_expired — buffer-aware expiry check
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestTokenExpiry:

    def test_far_future_not_expired(self):
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        assert TokenManager.is_token_expired(future) is False

    def test_past_is_expired(self):
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        assert TokenManager.is_token_expired(past) is True

    def test_within_buffer_is_expired(self):
        almost_expired = datetime.now(timezone.utc) + timedelta(minutes=3)
        assert TokenManager.is_token_expired(almost_expired, buffer_minutes=5) is True

    def test_none_never_expires(self):
        assert TokenManager.is_token_expired(None) is False

    def test_naive_datetime_treated_as_utc(self):
        naive_future = datetime.utcnow() + timedelta(hours=1)
        assert TokenManager.is_token_expired(naive_future) is False


# ---------------------------------------------------------------------------
# 3. TokenManager.calculate_expiry — seconds to UTC datetime
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCalculateExpiry:

    def test_positive_seconds_returns_future_datetime(self):
        before = datetime.now(timezone.utc)
        result = TokenManager.calculate_expiry(3600)
        after = datetime.now(timezone.utc)

        assert result is not None
        assert result.tzinfo is not None
        expected_low = before + timedelta(seconds=3600)
        expected_high = after + timedelta(seconds=3600)
        assert expected_low <= result <= expected_high

    def test_zero_returns_none(self):
        assert TokenManager.calculate_expiry(0) is None

    def test_negative_returns_none(self):
        assert TokenManager.calculate_expiry(-100) is None

    def test_none_returns_none(self):
        assert TokenManager.calculate_expiry(None) is None
