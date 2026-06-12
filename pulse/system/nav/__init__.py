# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Navigation system module initialization.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

# Navigation system
from system.nav.sections import (
    NAV_SECTIONS,
    PRIMARY_NAV,
    DEFAULT_SECTION_ORDER,
    DEFAULT_PINNED_MODULES,
    get_nav_sections,
    get_primary_nav,
    get_default_order,
    get_default_pinned_modules,
)

__all__ = [
    "NAV_SECTIONS",
    "PRIMARY_NAV",
    "DEFAULT_SECTION_ORDER",
    "DEFAULT_PINNED_MODULES",
    "get_nav_sections",
    "get_primary_nav",
    "get_default_order",
    "get_default_pinned_modules",
]
