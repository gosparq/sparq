# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Network utility functions for HTTP requests and connectivity.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

"""Network utility functions for IP detection and connectivity.

This module provides utilities for network-related operations.

Functions:
    get_local_ip: Detect the local IP address of the machine.

Example:
    Display server address at startup::

        from system.utils.network import get_local_ip

        local_ip = get_local_ip()
        print(f"Server running at http://{local_ip}:8000")
"""

import socket


def get_local_ip() -> str:
    """Get the local IP address of the machine."""
    try:
        # Connect to an external address to determine local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "127.0.0.1"
