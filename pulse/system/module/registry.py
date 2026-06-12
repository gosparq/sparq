# -----------------------------------------------------------------------------
# sparQ - Module Registry
#
# Description:
#     Provides utilities for checking module availability and managing
#     conditional features based on enabled modules.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""Module registry for runtime availability checks.

This module provides a singleton registry that tracks which modules
are enabled and allows conditional feature rendering.

Classes:
    ModuleRegistry: Singleton class tracking module state.

Functions:
    module_enabled: Convenience function to check if a module is enabled.
    is_required_module: Check if a module cannot be disabled.

The registry scans module directories for __DISABLED__ files to
determine which modules are active.

Example:
    Check module availability in Python::

        from system.module import module_enabled

        if module_enabled("Contacts"):
            # Show contacts-related features
            pass

    Check in Jinja templates::

        {% if module_enabled('Sales') %}
            <a href="{{ url_for('sales_bp.catalog') }}">Catalog</a>
        {% endif %}
"""

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flask import Flask


class ModuleRegistry:
    """
    Registry for checking module availability at runtime.

    Used for conditional imports and UI rendering based on which
    modules are enabled.
    """

    _instance: "ModuleRegistry | None" = None
    _app: "Flask | None" = None
    _enabled_modules: set[str]
    _module_info: dict[str, dict]

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._enabled_modules = set()
            cls._instance._module_info = {}
        return cls._instance

    @classmethod
    def init_app(cls, app: "Flask") -> None:
        """Initialize registry with Flask app context."""
        cls._app = app
        instance = cls()
        instance._scan_modules()

        # Add helper to Jinja globals
        app.jinja_env.globals['module_enabled'] = instance.is_enabled

    def _scan_modules(self) -> None:
        """Scan module folders and build enabled modules set."""
        self._enabled_modules.clear()
        self._module_info.clear()

        modules_root = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "modules")

        # Scan base modules
        for folder in ["base"]:
            folder_path = os.path.join(modules_root, folder)
            if not os.path.isdir(folder_path):
                continue

            for module_name in os.listdir(folder_path):
                module_path = os.path.join(folder_path, module_name)
                if not os.path.isdir(module_path) or module_name.startswith("_"):
                    continue

                # Check for __DISABLED__ file
                disabled_file = os.path.join(module_path, "__DISABLED__")
                is_enabled = not os.path.exists(disabled_file)

                # Try to get module display name and type from manifest
                display_name = module_name.title()
                module_type = "App"
                try:
                    import importlib
                    manifest = importlib.import_module(f"modules.{folder}.{module_name}.__manifest__").manifest
                    display_name = manifest.get("name", display_name)
                    module_type = manifest.get("type", "App")
                except Exception:
                    pass

                self._module_info[display_name.lower()] = {
                    "name": display_name,
                    "folder": folder,
                    "path": module_path,
                    "enabled": is_enabled,
                    "is_plugin": module_type == "Plugin",
                    "is_app": module_type != "Plugin",
                }

                if is_enabled:
                    self._enabled_modules.add(display_name.lower())

        # Scan the integrations root package — it lives at modules/integrations/
        # directly (not as a subdirectory of base/) after the consolidation.
        integrations_root = os.path.join(modules_root, "integrations")
        integrations_manifest_path = os.path.join(integrations_root, "__manifest__.py")
        if os.path.isdir(integrations_root) and os.path.isfile(integrations_manifest_path):
            disabled_file = os.path.join(integrations_root, "__DISABLED__")
            is_enabled = not os.path.exists(disabled_file)
            display_name = "Integrations"
            module_type = "System"
            try:
                import importlib
                manifest = importlib.import_module("modules.integrations.__manifest__").manifest
                display_name = manifest.get("name", display_name)
                module_type = manifest.get("type", "System")
            except Exception:
                pass
            self._module_info[display_name.lower()] = {
                "name": display_name,
                "folder": "integrations",
                "path": integrations_root,
                "enabled": is_enabled,
                "is_plugin": module_type == "Plugin",
                "is_app": module_type != "Plugin",
            }
            if is_enabled:
                self._enabled_modules.add(display_name.lower())

    def refresh(self) -> None:
        """Refresh the module registry (call after enabling/disabling modules)."""
        self._scan_modules()

    def is_enabled(self, module_name: str) -> bool:
        """
        Check if a module is enabled.

        Args:
            module_name: Module name (case-insensitive)

        Returns:
            True if module is enabled, False otherwise
        """
        return module_name.lower() in self._enabled_modules

    def get_enabled_modules(self) -> set[str]:
        """Get set of all enabled module names (lowercase)."""
        return self._enabled_modules.copy()

    def get_module_info(self, module_name: str) -> dict | None:
        """Get info dict for a module."""
        return self._module_info.get(module_name.lower())

    def is_plugin(self, module_name: str) -> bool:
        """Check if a module is a plugin (type: Plugin in manifest)."""
        info = self.get_module_info(module_name)
        return info.get("is_plugin", False) if info else False

    def is_app(self, module_name: str) -> bool:
        """Check if a module is an app (type: App in manifest, or default)."""
        info = self.get_module_info(module_name)
        return info.get("is_app", False) if info else False

    def get_plugins(self) -> list[dict]:
        """Get all plugin modules."""
        return [info for info in self._module_info.values() if info.get("is_plugin")]

    def get_apps(self) -> list[dict]:
        """Get all standalone app modules."""
        return [info for info in self._module_info.values() if info.get("is_app")]

    @classmethod
    def get_instance(cls) -> "ModuleRegistry":
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


# Convenience function for checking module availability
def module_enabled(module_name: str) -> bool:
    """
    Check if a module is enabled.

    This is the primary API for conditional imports and feature checks.

    Usage:
        from system.module.registry import module_enabled

        if module_enabled('Presence'):
            from modules.base.presence.models.time_entry import TimeEntry

        if module_enabled('Resources'):
            # Show attachments UI

    Args:
        module_name: Module name (case-insensitive)

    Returns:
        True if module is enabled
    """
    return ModuleRegistry.get_instance().is_enabled(module_name)


# List of required modules that cannot be disabled
REQUIRED_MODULES = frozenset([
    "core",
    "people",
    "dashboard",
    "resources",
])


def is_required_module(module_name: str) -> bool:
    """Check if a module is required (cannot be disabled)."""
    return module_name.lower() in REQUIRED_MODULES
