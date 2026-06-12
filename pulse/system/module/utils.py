# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Utility functions for module management including status reporting
#     and module information formatting.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

"""Utility functions for module management.

This module provides helper functions for module initialization,
status reporting, and error notification.

Functions:
    initialize_modules: Discover and load all modules at startup.
    print_module_status: Print a formatted table of loaded modules.
    get_module_type: Derive module type from manifest.
    create_module_error_notifications: Create admin notifications for errors.

Example:
    Initialize modules during app startup::

        from system.module.utils import initialize_modules

        loader = initialize_modules()
        # loader.manifests contains all module metadata
        # loader.modules contains loaded module instances

    Print module status with verbose output::

        import os
        os.environ["SPARQ_VERBOSE"] = "1"

        from system.module.utils import print_module_status
        print_module_status(loader.manifests, loader.errors)
"""

import os
import random
import re
import string
from typing import Any

from .loader import ModuleLoader

# mappid constants
MAPPID_CHARS = string.ascii_lowercase + string.digits
MAPPID_LENGTH = 6
MAPPID_PATTERN = re.compile(r"^[a-z0-9]{6}$")


def generate_mappid() -> str:
    """Generate a unique 6-character marketplace app ID.

    Returns:
        A random 6-character string using lowercase letters and digits.

    Example:
        >>> generate_mappid()
        'a3x9k2'
    """
    return "".join(random.choices(MAPPID_CHARS, k=MAPPID_LENGTH))


def validate_mappid(mappid: str) -> tuple[bool, str]:
    """Validate a marketplace app ID format.

    Args:
        mappid: The mappid to validate

    Returns:
        Tuple of (is_valid, error_message). error_message is empty if valid.
    """
    if not mappid:
        return False, "mappid is required"
    if len(mappid) != MAPPID_LENGTH:
        return False, f"mappid must be exactly {MAPPID_LENGTH} characters"
    if not MAPPID_PATTERN.match(mappid):
        return False, "mappid must be lowercase alphanumeric only (a-z, 0-9)"
    return True, ""


def get_module_type(manifest: dict[str, Any]) -> str:
    """Derive module type from folder location"""
    if manifest.get("is_app"):
        return "App"
    elif manifest.get("is_plugin"):
        return "Plugin"
    else:
        return "Core"


def print_module_status(
    manifests: dict[str, dict[str, Any]], errors: list[str] | None = None
) -> None:
    """Print formatted table of module status.

    In verbose mode (SPARQ_VERBOSE=1), prints full table.
    Otherwise, prints only a summary with counts.
    """
    # Only print status in main process (not reloader)
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        return

    if not manifests:
        print("\nNo modules loaded!")
        if errors:
            print("\nErrors:")
            for error in errors:
                print(f"ERROR: {error}")
        return

    verbose = os.environ.get("SPARQ_VERBOSE", "").lower() in ("1", "true", "yes")

    if verbose:
        # Calculate column widths
        module_width = max(len(m["name"]) for m in manifests.values()) + 2
        type_width = 8  # "Plugin" is longest at 6 chars + padding

        # Print header
        print("\nLoading modules:")
        print("-" * (module_width + type_width + 15))
        print(f"{'Module':<{module_width}}{'Type':<{type_width}}Status")
        print("-" * (module_width + type_width + 15))

        # Print each module
        for manifest in manifests.values():
            status = "Enabled" if manifest.get("enabled", False) else "Disabled"
            module_type = get_module_type(manifest)
            print(f"{manifest['name']:<{module_width}}{module_type:<{type_width}}{status}")
        print("-" * (module_width + type_width + 15))

    # Print any errors (always show errors)
    if errors:
        print("\nModule Errors:")
        for error in errors:
            print(f"  ERROR: {error}")
        print()


def initialize_modules() -> ModuleLoader:
    """Initialize and validate required modules

    Returns:
        ModuleLoader: Initialized module loader instance

    Raises:
        SystemExit: If required modules are missing
    """
    # Load modules
    module_loader = ModuleLoader()
    module_loader.discover_modules()

    # Check for required modules
    required_modules = ["CoreModule", "DashboardModule", "PeopleModule"]
    loaded_modules = [m.__class__.__name__ for m in module_loader.modules]
    missing_modules = [m for m in required_modules if m not in loaded_modules]

    # Collect all errors
    errors = []
    if module_loader.errors:
        errors.extend(module_loader.errors)
    if missing_modules:
        errors.append(f"Required modules not found: {', '.join(missing_modules)}")

    # Print module status table with any errors
    print_module_status(module_loader.manifests, errors)

    # Exit if there are critical errors
    if missing_modules:
        print("Application cannot start without core, dashboard, and people modules.")
        os._exit(1)

    return module_loader


def create_module_error_notifications(errors: list[str]) -> None:
    """Create system notifications for module loading errors.

    This should be called after the Flask app context is available.
    """
    if not errors:
        return

    try:
        from modules.base.core.models.notification import SystemNotification

        for error in errors:
            # Check if this error notification already exists (avoid duplicates)
            existing = SystemNotification.scoped().filter(
                SystemNotification.title == "Module Failed to Load",
                SystemNotification.message == error,
                SystemNotification.is_dismissed == False,
            ).first()

            if not existing:
                SystemNotification.create(
                    title="Module Failed to Load",
                    message=error,
                    type="error",
                    target_role="admin",
                    icon="fa-exclamation-triangle",
                    color="#dc3545",
                    category="system",
                )
    except Exception as e:
        # Don't crash if notification creation fails
        print(f"Warning: Could not create module error notification: {e}")
