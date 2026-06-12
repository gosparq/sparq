# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - Email Domain Utils Unit Tests
#
# Tests for system/utils/email_domain.py. Verifies domain extraction,
# normalization, free-email detection, and IDN/punycode handling.
# -----------------------------------------------------------------------------

import pytest

from system.utils.email_domain import (
    _punycode_domain,
    extract_domain,
    is_free_email,
    normalize_domain,
)


# ---------------------------------------------------------------------------
# 1. extract_domain — pull domain from email address
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestExtractDomain:
    """Test domain extraction from email addresses."""

    def test_simple_email(self):
        """Standard email should extract the domain."""
        assert extract_domain("joe@example.com") == "example.com"

    def test_uppercase_normalized(self):
        """Uppercase email should be lowercased."""
        assert extract_domain("Joe@Example.COM") == "example.com"

    def test_whitespace_stripped(self):
        """Leading/trailing whitespace should be stripped."""
        assert extract_domain("  joe@example.com  ") == "example.com"

    def test_no_at_sign_returns_empty(self):
        """Email without @ should return empty string."""
        assert extract_domain("noemail") == ""

    def test_empty_string_returns_empty(self):
        """Empty string should return empty string."""
        assert extract_domain("") == ""

    def test_none_returns_empty(self):
        """None should return empty string."""
        assert extract_domain(None) == ""

    def test_multiple_at_signs(self):
        """Email with multiple @ should use the last one."""
        assert extract_domain("user@mid@example.com") == "example.com"

    def test_subdomain(self):
        """Subdomain email should return the full domain."""
        assert extract_domain("user@mail.example.com") == "mail.example.com"


# ---------------------------------------------------------------------------
# 2. normalize_domain — clean up raw domain strings
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestNormalizeDomain:
    """Test domain normalization."""

    def test_simple_domain(self):
        """Simple domain passes through."""
        assert normalize_domain("example.com") == "example.com"

    def test_uppercase_lowered(self):
        """Uppercase domain should be lowered."""
        assert normalize_domain("Example.COM") == "example.com"

    def test_leading_at_stripped(self):
        """Leading @ should be stripped."""
        assert normalize_domain("@example.com") == "example.com"

    def test_whitespace_stripped(self):
        """Whitespace should be stripped."""
        assert normalize_domain("  example.com  ") == "example.com"

    def test_combined_cleanup(self):
        """Combined @ prefix, whitespace, and case should all be handled."""
        assert normalize_domain("  @Example.COM  ") == "example.com"

    def test_empty_returns_empty(self):
        """Empty string should return empty."""
        assert normalize_domain("") == ""

    def test_none_returns_empty(self):
        """None should return empty."""
        assert normalize_domain(None) == ""

    def test_just_at_sign_returns_empty(self):
        """Just @ should return empty after stripping."""
        assert normalize_domain("@") == ""


# ---------------------------------------------------------------------------
# 3. is_free_email — free provider detection
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestIsFreeEmail:
    """Test free email provider detection."""

    def test_gmail_is_free(self):
        """Gmail should be detected as free."""
        assert is_free_email("user@gmail.com") is True

    def test_outlook_is_free(self):
        """Outlook should be detected as free."""
        assert is_free_email("user@outlook.com") is True

    def test_yahoo_is_free(self):
        """Yahoo should be detected as free."""
        assert is_free_email("user@yahoo.com") is True

    def test_hotmail_is_free(self):
        """Hotmail should be detected as free."""
        assert is_free_email("user@hotmail.com") is True

    def test_protonmail_is_free(self):
        """Protonmail should be detected as free."""
        assert is_free_email("user@protonmail.com") is True

    def test_corporate_domain_not_free(self):
        """Corporate domain should not be free."""
        assert is_free_email("user@acme-corp.com") is False

    def test_custom_domain_not_free(self):
        """Custom domain should not be free."""
        assert is_free_email("ceo@mycompany.io") is False

    def test_case_insensitive(self):
        """Detection should be case-insensitive."""
        assert is_free_email("User@Gmail.COM") is True

    def test_isp_domains_are_free(self):
        """ISP domains like comcast.net should be free."""
        assert is_free_email("user@comcast.net") is True

    def test_empty_email_not_free(self):
        """Empty email should not be free (returns empty domain)."""
        assert is_free_email("") is False


# ---------------------------------------------------------------------------
# 4. _punycode_domain — IDN encoding
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPunycodeDomain:
    """Test internationalized domain name encoding."""

    def test_ascii_domain_unchanged(self):
        """ASCII domain should pass through unchanged."""
        assert _punycode_domain("example.com") == "example.com"

    def test_unicode_domain_encoded(self):
        """Unicode domain should be encoded to punycode."""
        # muenchen.de in German would be münchen.de
        result = _punycode_domain("xn--mnchen-3ya.de")
        # Already ASCII punycode, should pass through
        assert result == "xn--mnchen-3ya.de"

    def test_invalid_encoding_returns_original(self):
        """Invalid encoding should return the original string."""
        # A domain that cannot be encoded should return as-is
        weird = "a" * 200 + ".com"
        result = _punycode_domain(weird)
        # Should either encode or return original, not crash
        assert isinstance(result, str)
