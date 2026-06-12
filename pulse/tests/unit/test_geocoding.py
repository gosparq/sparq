# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - Geocoding Service Unit Tests
#
# Tests for system/services/geocoding.py. Verifies short address formatting
# from Nominatim response data, reverse geocode fallback to display_name,
# truncation of long addresses, and graceful handling of network/parse errors.
# -----------------------------------------------------------------------------

import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from system.services.geocoding import _format_short_address, reverse_geocode


# ---------------------------------------------------------------------------
# 1. _format_short_address — structured address formatting
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFormatShortAddress:

    def test_full_address(self):
        data = {
            "address": {
                "house_number": "123",
                "road": "Main Street",
                "city": "Springfield",
                "state": "Illinois",
                "postcode": "62701",
                "country": "United States",
            }
        }
        result = _format_short_address(data)
        assert result == "123 Main Street, Springfield, Illinois 62701, United States"

    def test_road_only(self):
        data = {"address": {"road": "Elm Street"}}
        result = _format_short_address(data)
        assert result == "Elm Street"

    def test_city_fallback_to_town(self):
        data = {"address": {"town": "Smallville", "state": "Kansas"}}
        result = _format_short_address(data)
        assert result == "Smallville, Kansas"

    def test_city_fallback_to_village(self):
        data = {"address": {"village": "Hobbiton", "country": "New Zealand"}}
        result = _format_short_address(data)
        assert result == "Hobbiton, New Zealand"

    def test_postcode_appended_to_last_part(self):
        data = {"address": {"city": "Portland", "postcode": "97201"}}
        result = _format_short_address(data)
        assert result == "Portland 97201"

    def test_empty_address_returns_none(self):
        data = {"address": {}}
        assert _format_short_address(data) is None

    def test_missing_address_key_returns_none(self):
        data = {}
        assert _format_short_address(data) is None


# ---------------------------------------------------------------------------
# 2. reverse_geocode — Nominatim API integration
# ---------------------------------------------------------------------------


def _mock_urlopen(data: dict):
    """Create a mock urlopen context manager returning JSON data."""
    response_bytes = json.dumps(data).encode("utf-8")
    mock_response = MagicMock()
    mock_response.read.return_value = response_bytes
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)
    return mock_response


@pytest.mark.unit
class TestReverseGeocode:

    @patch("system.services.geocoding.urllib.request.urlopen")
    def test_success_returns_formatted_address(self, mock_urlopen):
        data = {
            "address": {
                "road": "Broadway",
                "city": "New York",
                "state": "New York",
                "postcode": "10001",
                "country": "United States",
            }
        }
        mock_urlopen.return_value = _mock_urlopen(data)
        result = reverse_geocode(40.7128, -74.0060)
        assert result == "Broadway, New York, New York 10001, United States"

    @patch("system.services.geocoding.urllib.request.urlopen")
    def test_falls_back_to_display_name(self, mock_urlopen):
        data = {"address": {}, "display_name": "Somewhere on Earth"}
        mock_urlopen.return_value = _mock_urlopen(data)
        result = reverse_geocode(0.0, 0.0)
        assert result == "Somewhere on Earth"

    @patch("system.services.geocoding.urllib.request.urlopen")
    def test_truncates_long_display_name(self, mock_urlopen):
        long_name = "A" * 200
        data = {"address": {}, "display_name": long_name}
        mock_urlopen.return_value = _mock_urlopen(data)
        result = reverse_geocode(0.0, 0.0)
        assert len(result) == 150
        assert result.endswith("...")

    @patch("system.services.geocoding.urllib.request.urlopen")
    def test_network_error_returns_none(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("DNS failure")
        assert reverse_geocode(0.0, 0.0) is None

    @patch("system.services.geocoding.urllib.request.urlopen")
    def test_json_parse_error_returns_none(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = b"not json"
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response
        assert reverse_geocode(0.0, 0.0) is None

    @patch("system.services.geocoding.urllib.request.urlopen")
    def test_timeout_returns_none(self, mock_urlopen):
        mock_urlopen.side_effect = TimeoutError("timed out")
        assert reverse_geocode(0.0, 0.0) is None

    @patch("system.services.geocoding.urllib.request.urlopen")
    @patch("system.services.geocoding.urllib.request.Request")
    def test_user_agent_uses_host_param(self, mock_request_cls, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen({"address": {"city": "Test"}})
        reverse_geocode(1.0, 2.0, host="myapp.example.com")

        _, kwargs = mock_request_cls.call_args
        assert kwargs["headers"]["User-Agent"] == "myapp.example.com"
