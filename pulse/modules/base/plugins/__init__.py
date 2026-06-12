# -----------------------------------------------------------------------------
# sparQ - Plugins Module
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""Plugins module for marketplace app management.

This module hosts the plugin/app system, providing the interface
for discovering, installing, and managing third-party apps from
the sparQ marketplace.

Key Features:
    - Marketplace app browsing
    - App installation and updates
    - Plugin enable/disable
    - App configuration
    - License management
    - Plugin hooks integration

Routes:
    /plugins - Installed plugins
    /plugins/marketplace - App marketplace
    /plugins/settings - Plugin configuration
"""

from .module import PluginsModule

module_instance = PluginsModule()
