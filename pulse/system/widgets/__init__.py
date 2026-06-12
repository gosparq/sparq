# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Dashboard widgets system for customizable quick links.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

from .registry import (
    ADMIN_WIDGETS,
    AVAILABLE_WIDGETS,
    get_admin_widgets,
    get_available_admin_widgets,
    get_available_widgets,
    get_default_admin_widgets,
    get_default_widgets,
    get_user_widgets,
    save_admin_widgets,
    save_user_widgets,
)

__all__ = [
    "ADMIN_WIDGETS",
    "AVAILABLE_WIDGETS",
    "get_admin_widgets",
    "get_available_admin_widgets",
    "get_available_widgets",
    "get_default_admin_widgets",
    "get_default_widgets",
    "get_user_widgets",
    "save_admin_widgets",
    "save_user_widgets",
]
