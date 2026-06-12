# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Core module manifest defining module metadata, dependencies, and
#     configuration. Required for module discovery and initialization.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

manifest = {
    "name": "Core",
    "version": "1.0",
    "main_route": "/core",
    "icon_class": "fa-solid fa-home",
    "type": "System",
    "color": "#7c3aed",
    "depends": [],
    "description": "Core system functionality",
    "long_description": "Provides essential system features including user authentication, module management, and basic application framework. Required for all other modules to function.",
}
