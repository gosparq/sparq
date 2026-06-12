# Copyright (c) 2025-2026 remarQable LLC

"""Integration framework — provider interface, registry, shared models, and settings routes.

This package serves as both the integration framework (IntegrationProvider ABC,
registry, IntegrationConnection/IntegrationRef models) and the root of all
integration providers (github/, jira/, etc. as subdirectories).

module_instance is loaded by the module loader alongside provider subdirectories.
"""

from .module import IntegrationsModule

# Import models so SQLAlchemy registers them on startup even when a provider
# is disabled — cross-module FK references require this.
from .models.integration_connection import IntegrationConnection  # noqa: F401
from .models.integration_ref import IntegrationRef  # noqa: F401

module_instance = IntegrationsModule()

__all__ = [
    "module_instance",
    "IntegrationConnection",
    "IntegrationRef",
]
