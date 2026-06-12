# Copyright (c) 2025-2026 remarQable LLC

"""IntegrationRegistry — central registry of available integration providers.

Providers register themselves at import time by calling register().
The UI and framework look up providers via get() and all_providers().
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import IntegrationProvider

logger = logging.getLogger(__name__)

_registry: dict[str, type["IntegrationProvider"]] = {}


def register(cls: type["IntegrationProvider"]) -> None:
    """Register an IntegrationProvider subclass.

    Args:
        cls: A concrete IntegrationProvider subclass. Must have provider_name set.
    """
    name = cls.provider_name
    if not name:
        raise ValueError(f"{cls.__name__} must set provider_name")
    if name in _registry:
        logger.debug("IntegrationRegistry: replacing existing provider %s", name)
    _registry[name] = cls
    logger.debug("IntegrationRegistry: registered provider %s", name)


def get(name: str) -> type["IntegrationProvider"] | None:
    """Retrieve a registered provider class by name.

    Args:
        name: The provider slug (e.g. "github").

    Returns:
        The provider class, or None if not registered.
    """
    return _registry.get(name)


def all_providers() -> list[type["IntegrationProvider"]]:
    """Return all registered provider classes in registration order.

    Returns:
        List of IntegrationProvider subclasses.
    """
    return list(_registry.values())
