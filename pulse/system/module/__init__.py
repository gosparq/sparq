# -----------------------------------------------------------------------------
# sparQ - Module System
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""Module management system for sparQ's plugin architecture.

This package provides the module loading, registration, and lifecycle
management for sparQ's modular architecture.

Classes:
    ModuleRegistry: Singleton registry for checking module availability.
    ModuleLoader: Handles module discovery and initialization.
    ModuleSpecs: Pluggy hook specifications for module lifecycle.

Functions:
    module_enabled: Check if a module is currently enabled.
    is_required_module: Check if a module cannot be disabled.
    initialize_modules: Discover and load all modules at startup.

Constants:
    REQUIRED_MODULES: Set of module names that cannot be disabled.

Module Types:
    - Base modules (modules/base/): Core system modules bundled with sparQ
    - Data apps (data/modules/apps/): User-installed apps and plugins

Example:
    Check if a module is available before using it::

        from system.module import module_enabled

        if module_enabled("Presence"):
            from modules.base.presence.models.time_entry import TimeEntry
            entries = TimeEntry.query.all()

    Register a module's Jinja global::

        from system.module import ModuleRegistry

        ModuleRegistry.init_app(app)
        # Now {{ module_enabled('Contacts') }} works in templates
"""

from .registry import ModuleRegistry, module_enabled, is_required_module, REQUIRED_MODULES

__all__ = [
    "ModuleRegistry",
    "module_enabled",
    "is_required_module",
    "REQUIRED_MODULES",
]
