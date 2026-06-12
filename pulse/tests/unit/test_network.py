# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - Network Utils Unit Tests
#
# Tests for system/utils/network.py. Verifies local IP detection
# and fallback behavior.
# -----------------------------------------------------------------------------

import re
from unittest.mock import patch, MagicMock

import pytest

from system.utils.network import get_local_ip


# ---------------------------------------------------------------------------
# 1. get_local_ip — local IP address detection
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetLocalIP:
    """Test local IP address detection."""

    def test_returns_string(self):
        """Should return a string."""
        result = get_local_ip()
        assert isinstance(result, str)

    def test_matches_ip_pattern(self):
        """Should return a valid IPv4 address."""
        result = get_local_ip()
        pattern = r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$"
        assert re.match(pattern, result), f"'{result}' does not match IPv4 pattern"

    def test_each_octet_in_valid_range(self):
        """Each octet should be 0-255."""
        result = get_local_ip()
        octets = result.split(".")
        assert len(octets) == 4
        for octet in octets:
            assert 0 <= int(octet) <= 255

    def test_fallback_on_socket_error(self):
        """Should return 127.0.0.1 when socket fails."""
        with patch("system.utils.network.socket.socket") as mock_sock:
            mock_instance = MagicMock()
            mock_instance.connect.side_effect = OSError("Network unreachable")
            mock_sock.return_value = mock_instance
            result = get_local_ip()
            assert result == "127.0.0.1"
