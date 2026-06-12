# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Core module loading system that handles dynamic module discovery,
#     initialization, and registration. Manages plugin system and module hooks.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

"""Module loading and discovery system.

This module provides the core functionality for discovering, loading,
and registering sparQ modules dynamically at runtime.

Classes:
    ModuleLoader: Main class for module discovery and initialization.

The loader handles two types of module locations:
1. Base modules in modules/base/ (bundled with sparQ)
2. Data modules in data/modules/apps/ (user-installed)

Loading Process:
    1. Required modules (core, dashboard, team) are loaded first
    2. Remaining base modules are loaded
    3. Data apps/plugins from data/modules/apps/ are loaded
    4. Each module's hooks are registered with the plugin manager

Example:
    Initialize modules during app startup::

        from system.module.loader import ModuleLoader

        loader = ModuleLoader()
        loader.discover_modules()

        # Register blueprints
        loader.register_routes(app)

        # Call database initialization hooks
        loader.pm.hook.init_database()
"""

import importlib
import importlib.util
import os
import sys
from typing import Any

import pluggy
from flask import Flask

from .hooks import ModuleSpecs


def _get_data_dir() -> str:
    """Get the data directory path."""
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.environ.get("SPARQ_DATA_DIR", os.path.join(project_root, "data"))


class ModuleLoader:
    """
    Manages module discovery, loading, and registration.
    """

    def __init__(self, app: Flask | None = None):
        self.app: Flask | None = app
        self.modules: list[Any] = []
        self.pm: pluggy.PluginManager = pluggy.PluginManager("sparQOne")
        self.pm.add_hookspecs(ModuleSpecs)
        self.manifests: dict[str, dict[str, Any]] = {}
        self.errors: list[str] = []

    def load_module(self, module_name: str, folder: str) -> bool | None:
        """Load a single module from base or apps folder"""
        try:
            # Load manifest
            import_path = f"modules.{folder}.{module_name}"
            manifest = importlib.import_module(f"{import_path}.__manifest__").manifest
            manifest_copy = manifest.copy()  # Create a copy to avoid modifying the original

            # Check if module is disabled
            module_path = os.path.join("modules", folder, module_name)
            disabled_file = os.path.join(module_path, "__DISABLED__")
            is_enabled = not os.path.exists(disabled_file)
            manifest_copy["enabled"] = is_enabled
            manifest_copy["folder"] = folder
            manifest_copy["module_dir"] = module_name  # Directory name, used for translation lookup
            manifest_copy["is_plugin"] = manifest.get("type") == "Plugin"
            manifest_copy["is_app"] = manifest.get("type") != "Plugin"
            manifest_copy["is_data_module"] = False  # Base modules are not data modules
            # Base modules use main_route directly
            manifest_copy["url"] = manifest.get("main_route", "/")

            # Always import base modules to register their SQLAlchemy models
            # This ensures cross-module relationships work even when modules are disabled
            if folder == "base":
                importlib.import_module(import_path)

            if is_enabled:
                # Load the module (for non-base) or get already-imported module (for base)
                module = importlib.import_module(import_path)
                if hasattr(module, "module_instance"):
                    self.manifests[manifest_copy["name"]] = manifest_copy  # Use module name as key
                    instance = module.module_instance
                    # Register hook specifications if the module provides them
                    if hasattr(instance, "register_specs"):
                        instance.register_specs(self.pm)
                    else:
                        # Just register the module for hook implementations
                        self.pm.register(instance)
                    self.modules.append(instance)
                    return True
                else:
                    self.errors.append(f"Module '{module_name}' has no module_instance")
            else:
                self.manifests[manifest_copy["name"]] = (
                    manifest_copy  # Still track disabled modules
                )

        except Exception as e:
            self.errors.append(f"Failed to load module '{module_name}': {str(e)}")
            return False
        return None

    def load_data_module(
        self, module_name: str, module_path: str, module_type: str = "app"
    ) -> bool | None:
        """Load an app or plugin module from data/modules/ directory.

        Modules in the data directory are loaded dynamically using importlib.util
        since they're not part of the installed package.

        Args:
            module_name: Name of the module directory
            module_path: Full path to the module directory
            module_type: Either 'app' or 'plugin'
        """
        try:
            # Load manifest from file path
            manifest_path = os.path.join(module_path, "__manifest__.py")
            if not os.path.exists(manifest_path):
                self.errors.append(f"{module_type.title()} '{module_name}' has no __manifest__.py")
                return False

            # Load manifest using importlib.util for file-based loading
            package_prefix = f"data_{module_type}s"
            spec = importlib.util.spec_from_file_location(
                f"{package_prefix}.{module_name}.__manifest__", manifest_path
            )
            if spec is None or spec.loader is None:
                self.errors.append(f"Could not load manifest for {module_type} '{module_name}'")
                return False

            manifest_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(manifest_module)
            manifest = manifest_module.manifest
            manifest_copy = manifest.copy()

            # Check if module is disabled
            disabled_file = os.path.join(module_path, "__DISABLED__")
            is_enabled = not os.path.exists(disabled_file)
            manifest_copy["enabled"] = is_enabled
            manifest_copy["folder"] = "apps"
            manifest_copy["module_dir"] = module_name  # Directory name, used for translation lookup
            manifest_copy["is_plugin"] = manifest.get("type") == "Plugin"
            manifest_copy["is_app"] = manifest.get("type") != "Plugin"
            manifest_copy["is_data_module"] = True  # Mark as data module

            # Track install time from manifest file creation time
            manifest_copy["installed_at"] = os.path.getctime(manifest_path)

            # Validate mappid for marketplace apps
            mappid = manifest.get("mappid")
            if mappid:
                from .utils import validate_mappid

                is_valid, error_msg = validate_mappid(mappid)
                if not is_valid:
                    self.errors.append(f"Invalid mappid for '{module_name}': {error_msg}")
                    return False
                manifest_copy["mappid"] = mappid
                # Data modules with mappid use /m/{mappid}/{slug} format
                route_slug = manifest.get("main_route", "/").lstrip("/")
                manifest_copy["url"] = f"/m/{mappid}/{route_slug}"
            else:
                # Data modules without mappid use main_route directly (legacy)
                manifest_copy["url"] = manifest.get("main_route", "/")

            if is_enabled:
                # Get the modules directory (parent of module_path)
                modules_dir = os.path.dirname(module_path)

                # Ensure the parent package exists in sys.modules
                if package_prefix not in sys.modules:
                    import types

                    pkg = types.ModuleType(package_prefix)
                    pkg.__path__ = [modules_dir]
                    pkg.__package__ = package_prefix
                    sys.modules[package_prefix] = pkg

                # Create a virtual package structure for the module
                package_name = f"{package_prefix}.{module_name}"

                # Load the main module
                init_path = os.path.join(module_path, "__init__.py")
                if not os.path.exists(init_path):
                    self.errors.append(f"{module_type.title()} '{module_name}' has no __init__.py")
                    return False

                # Create spec with submodule_search_locations for proper package handling
                spec = importlib.util.spec_from_file_location(
                    package_name,
                    init_path,
                    submodule_search_locations=[module_path],
                )
                if spec is None or spec.loader is None:
                    self.errors.append(f"Could not load {module_type} '{module_name}'")
                    return False

                module = importlib.util.module_from_spec(spec)
                module.__package__ = package_name
                module.__path__ = [module_path]

                # Register in sys.modules before exec to allow relative imports
                sys.modules[package_name] = module

                # Also register as attribute of parent package
                setattr(sys.modules[package_prefix], module_name, module)

                spec.loader.exec_module(module)

                if hasattr(module, "module_instance"):
                    self.manifests[manifest_copy["name"]] = manifest_copy
                    instance = module.module_instance
                    # Register hook specifications if the module provides them
                    if hasattr(instance, "register_specs"):
                        instance.register_specs(self.pm)
                    else:
                        self.pm.register(instance)
                    self.modules.append(instance)
                    return True
                else:
                    self.errors.append(f"{module_type.title()} '{module_name}' has no module_instance")
            else:
                self.manifests[manifest_copy["name"]] = manifest_copy

        except Exception as e:
            self.errors.append(f"Failed to load {module_type} '{module_name}': {str(e)}")
            return False
        return None

    def load_data_app(self, module_name: str, app_path: str) -> bool | None:
        """Load an app module from data/modules/apps/ directory.

        Backward compatibility wrapper for load_data_module.
        """
        return self.load_data_module(module_name, app_path, "app")

    def _get_modules_in_folder(self, folder: str) -> list[str]:
        """Get list of module names in a folder"""
        folder_path = os.path.join("modules", folder)
        if not os.path.isdir(folder_path):
            return []
        return [
            d
            for d in os.listdir(folder_path)
            if os.path.isdir(os.path.join(folder_path, d))
            and not d.startswith("_")
            and os.path.exists(os.path.join(folder_path, d, "__manifest__.py"))
        ]

    def _get_data_modules(self, module_type: str = "apps") -> list[tuple[str, str]]:
        """Get list of modules from data/modules/apps/ directory.

        Args:
            module_type: Always 'apps' (plugins now also live in apps/)

        Returns:
            List of tuples: (module_name, full_path)
        """
        data_path = os.path.join(_get_data_dir(), "modules", "apps")
        if not os.path.isdir(data_path):
            return []
        return [
            (d, os.path.join(data_path, d))
            for d in os.listdir(data_path)
            if os.path.isdir(os.path.join(data_path, d)) and not d.startswith("_")
        ]

    def _get_data_apps(self) -> list[tuple[str, str]]:
        """Get list of app modules from data/modules/apps/ directory.

        Backward compatibility wrapper for _get_data_modules.
        """
        return self._get_data_modules("apps")

    def discover_modules(self) -> None:
        """Discover and load all modules in correct order"""
        # Get modules from all folders
        base_modules = self._get_modules_in_folder("base")
        # All apps and plugins are loaded from data/modules/apps/
        # Type is determined by manifest "type" field: "App" or "Plugin"
        data_apps = self._get_data_modules("apps")

        # First load required base modules in order
        for required in ["core", "dashboard", "people"]:
            if required in base_modules:
                self.load_module(required, "base")
                base_modules.remove(required)
            else:
                self.errors.append(f"{required.title()} module not found - required for system operation")
                return

        # Load remaining base modules
        for module_name in base_modules:
            self.load_module(module_name, "base")

        # Load the integrations root package (framework: settings, palette commands,
        # shared models). Must run before provider subdirectories so the registry
        # and models are in place when providers register themselves.
        try:
            root_manifest = importlib.import_module("modules.integrations.__manifest__").manifest
            manifest_copy = root_manifest.copy()
            manifest_copy["enabled"] = True
            manifest_copy["folder"] = "integrations"
            manifest_copy["module_dir"] = ""
            manifest_copy["is_plugin"] = root_manifest.get("type") == "Plugin"
            manifest_copy["is_app"] = root_manifest.get("type") != "Plugin"
            manifest_copy["is_data_module"] = False
            manifest_copy["url"] = root_manifest.get("main_route", "/")
            root = importlib.import_module("modules.integrations")
            if hasattr(root, "module_instance"):
                instance = root.module_instance
                self.manifests[manifest_copy["name"]] = manifest_copy
                self.pm.register(instance)
                self.modules.append(instance)
        except Exception as e:  # noqa: BLE001
            self.errors.append(f"Failed to load integrations root package: {e}")

        # Load integration provider modules from modules/integrations/ subdirectories
        integrations_modules = self._get_modules_in_folder("integrations")
        for module_name in integrations_modules:
            self.load_module(module_name, "integrations")

        # Load apps and plugins from data/modules/apps/
        for module_name, app_path in data_apps:
            self.load_data_module(module_name, app_path, "app")

        # Validate mappid uniqueness across all modules
        self._validate_mappid_uniqueness()

    def _validate_mappid_uniqueness(self) -> None:
        """Ensure no two modules share the same mappid."""
        mappid_to_module: dict[str, str] = {}
        for name, manifest in self.manifests.items():
            mappid = manifest.get("mappid")
            if mappid:
                if mappid in mappid_to_module:
                    self.errors.append(
                        f"Duplicate mappid '{mappid}': used by both "
                        f"'{mappid_to_module[mappid]}' and '{name}'"
                    )
                else:
                    mappid_to_module[mappid] = name

    def _get_manifest_for_module(self, module: Any) -> dict[str, Any] | None:
        """Find the manifest for a given module instance."""
        module_class_name = module.__class__.__name__
        for manifest in self.manifests.values():
            # Match by module class name pattern (e.g., NotesModule -> Notes)
            expected_name = manifest.get("name", "").replace(" ", "")
            if module_class_name == f"{expected_name}Module":
                return manifest
        return None

    def register_routes(self, app: Flask) -> None:
        """Register routes from all modules.

        For data modules with a mappid, routes are prefixed with /m/{mappid}/
        For base modules, routes use the module's url_prefix directly.
        """
        for module in self.modules:
            if hasattr(module, "get_routes"):
                routes = module.get_routes()
                manifest = self._get_manifest_for_module(module)

                for blueprint, url_prefix in routes:
                    if manifest and manifest.get("is_data_module") and manifest.get("mappid"):
                        # Data module with mappid: use /m/{mappid}/{route}
                        mappid = manifest["mappid"]
                        route_slug = url_prefix.lstrip("/")
                        final_prefix = f"/m/{mappid}/{route_slug}"
                    else:
                        # Base module or data module without mappid: use original prefix
                        final_prefix = url_prefix

                    app.register_blueprint(blueprint, url_prefix=final_prefix)
