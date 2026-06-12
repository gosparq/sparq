# -----------------------------------------------------------------------------
# sparQ - Plugins Module
#
# Description:
#     Host module that discovers and registers plugins from modules/plugins/.
#     This is a shell/host - plugins are discovered automatically by placing
#     them in the modules/plugins/ directory.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

import importlib
import os
from typing import Any


class PluginsModule:
    """
    Host module for plugins.
    Discovers plugins in modules/plugins/ and registers their routes.
    """

    def __init__(self):
        self.discovered_plugins: list[dict[str, Any]] = []
        self._discover_plugins()

    def _discover_plugins(self) -> None:
        """Discover all plugins in the modules/plugins/ directory."""
        # Navigate to modules/plugins/ from modules/base/plugins/
        plugins_dir = os.path.join(
            os.path.dirname(__file__), "..", "..", "plugins"
        )
        plugins_dir = os.path.normpath(plugins_dir)

        if not os.path.isdir(plugins_dir):
            return

        for name in os.listdir(plugins_dir):
            plugin_path = os.path.join(plugins_dir, name)
            if os.path.isdir(plugin_path) and not name.startswith("_"):
                # Check for __DISABLED__ file
                disabled_file = os.path.join(plugin_path, "__DISABLED__")
                is_enabled = not os.path.exists(disabled_file)

                # Load manifest
                try:
                    manifest_module = importlib.import_module(
                        f"modules.plugins.{name}.__manifest__"
                    )
                    manifest = manifest_module.manifest.copy()
                    manifest["slug"] = name
                    manifest["enabled"] = is_enabled
                    self.discovered_plugins.append(manifest)
                except Exception as e:
                    print(f"Failed to load plugin manifest for {name}: {e}")

    def get_discovered_plugins(self) -> list[dict[str, Any]]:
        """Return list of discovered plugins with their manifests."""
        return self.discovered_plugins

    def get_enabled_plugins(self) -> list[dict[str, Any]]:
        """Return list of enabled plugins."""
        return [p for p in self.discovered_plugins if p.get("enabled")]

    def register_plugins_with_pm(self, pm) -> None:
        """Register all enabled plugins with the plugin manager for hooks."""
        for plugin in self.get_enabled_plugins():
            slug = plugin["slug"]
            try:
                plugin_module = importlib.import_module(
                    f"modules.plugins.{slug}"
                )
                if hasattr(plugin_module, "module_instance"):
                    instance = plugin_module.module_instance
                    # Register plugin for hook implementations
                    pm.register(instance)
            except Exception as e:
                print(f"Failed to register plugin {slug} with plugin manager: {e}")

    def get_routes(self):
        """Return routes for all enabled plugins."""
        from .controllers.index import plugins_blueprint

        routes = [(plugins_blueprint, "/plugins")]

        # Import and register each enabled plugin's routes
        for plugin in self.get_enabled_plugins():
            slug = plugin["slug"]
            try:
                # Import from modules.plugins.<slug>
                plugin_module = importlib.import_module(
                    f"modules.plugins.{slug}"
                )
                # Try to get routes from the module instance
                if hasattr(plugin_module, "module_instance"):
                    instance = plugin_module.module_instance
                    if hasattr(instance, "get_routes"):
                        for bp, _prefix in instance.get_routes():
                            # Mount under /plugins/<slug> (ignore original prefix)
                            routes.append((bp, f"/plugins/{slug}"))
            except Exception as e:
                print(f"Failed to load routes for plugin {slug}: {e}")

        return routes
