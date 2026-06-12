# -----------------------------------------------------------------------------
# sparQ - Device Detection Package
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# Device Detection Module
#
# Provides utilities for detecting mobile vs desktop devices and rendering
# device-appropriate templates.
# -----------------------------------------------------------------------------

from .detection import (
    is_mobile,
    get_device_type,
    detect_device,
    set_device_type,
    clear_device_type,
)
from .template import render_device_template

__all__ = [
    "is_mobile",
    "get_device_type",
    "detect_device",
    "set_device_type",
    "clear_device_type",
    "render_device_template",
]
