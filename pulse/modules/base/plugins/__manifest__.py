# -----------------------------------------------------------------------------
# sparQ - Plugins Host Module
#
# Description:
#     Host module that discovers and registers plugins from modules/plugins/.
#     Adding a new plugin is as simple as dropping a folder in modules/plugins/.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

manifest = {
    "name": "Plugins",
    "version": "1.0",
    "main_route": "/plugins",
    "icon_class": "fa-solid fa-puzzle-piece",
    "color": "#8b5cf6",  # Purple
    "depends": ["core", "people"],
    "description": "Plugin host module",
    "long_description": "Host module that discovers and manages plugins from the modules/plugins/ folder. Each plugin extends sparQ's functionality.",
}
