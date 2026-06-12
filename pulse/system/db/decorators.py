# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Database decorators for model registration and tracking.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

"""Model registration decorators for sparQ.

This module provides the ModelRegistry class which tracks all SQLAlchemy
models across the application. Use the @ModelRegistry.register decorator
on all model classes.

Example:
    Registering a model::

        from system.db.database import db
        from system.db.decorators import ModelRegistry

        @ModelRegistry.register
        class Customer(db.Model):
            __tablename__ = "customer"
            id = db.Column(db.Integer, primary_key=True)
            name = db.Column(db.String(255))

    The registry automatically tracks:
    - Which module the model belongs to
    - The model class name
    - The database table name
    - Registration order (for dependency resolution)
"""

import os
from typing import Any, TypeVar
from sqlalchemy import Table

T = TypeVar("T")


class ModelRegistry:
    """Registry to track all SQLAlchemy models across sparQ modules.

    This registry is used internally by sparQ to:
    - Track all models for database initialization
    - Maintain loading order for foreign key dependencies
    - Provide debugging information about registered models

    Attributes:
        models: List of registered model metadata dictionaries.
        registration_order: Counter for tracking registration sequence.
        MODULE_ORDER: Priority order for module loading (core first).

    Example:
        Using the register decorator::

            @ModelRegistry.register
            class MyModel(db.Model):
                __tablename__ = "my_model"
                id = db.Column(db.Integer, primary_key=True)
    """

    models: list[dict[str, Any]] = []
    registration_order: int = 1  # Track registration order

    # Define module loading order
    MODULE_ORDER: list[str] = ["core", "dashboard", "people"]  # Core first, then dashboard, people, rest alphabetically

    @classmethod
    def register(cls, model_class: type[T]) -> type[T]:
        """Decorator to register a SQLAlchemy model with the registry.

        Args:
            model_class: The SQLAlchemy model class to register.

        Returns:
            The same model class (decorator pattern).

        Example:
            @ModelRegistry.register
            class Product(db.Model):
                __tablename__ = "product"
                id = db.Column(db.Integer, primary_key=True)
        """
        # Get proper module name from full path
        # Path structures:
        # - modules.base.core.models.user
        # - data_apps.tasks.models.task (installed apps from data/modules/apps/)
        module_path = model_class.__module__.split(".")

        # Handle data modules (installed apps from data/modules/apps/)
        if module_path[0] == "data_apps" and len(module_path) > 1:
            module_name = module_path[1]  # e.g., "tasks", "nickname", "equipment"
        elif "modules" in module_path:
            idx = module_path.index("modules")
            # Skip past 'modules' and 'base'/'apps' to get the actual module name
            if len(module_path) > idx + 2 and module_path[idx + 1] in ("base", "apps"):
                module_name = module_path[idx + 2]
            else:
                module_name = module_path[idx + 1]
        else:
            module_name = "core"

        # Get table name - use type: ignore for __tablename__ access
        table_name = getattr(model_class, "__tablename__", model_class.__name__)

        cls.models.append(
            {
                "module": module_name,
                "model": model_class.__name__,
                "table": table_name,
                "order": cls.registration_order,
            }
        )
        cls.registration_order += 1
        return model_class

    @classmethod
    def register_table(cls, table: Table, module_name: str = "core") -> None:
        """Register a plain table (like association tables)"""
        cls.models.append(
            {
                "module": module_name,
                "model": table.name,
                "table": table.name,
                "order": cls.registration_order,
            }
        )
        cls.registration_order += 1

    @classmethod
    def _get_module_order(cls, module_name: str) -> int:
        """Helper to determine module sort order"""
        try:
            return cls.MODULE_ORDER.index(module_name)
        except ValueError:
            return len(cls.MODULE_ORDER)  # Put non-core/dashboard/team modules last

    @classmethod
    def print_summary(cls) -> None:
        """Print a summary of all registered models.

        In verbose mode (SPARQ_VERBOSE=1), prints full table.
        Otherwise, prints only a count summary.
        """
        # Only print in main process (not reloader)
        if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
            return

        verbose = os.environ.get("SPARQ_VERBOSE", "").lower() in ("1", "true", "yes")

        if verbose:
            print("\nDatabase Model Registry:")

            # Find the longest names for padding
            max_module = max(len(m["module"]) for m in cls.models)
            max_model = max(len(m["model"]) for m in cls.models)

            print(f"{'-' * max_module}---{'-' * max_model}---{'-' * 20}")
            # Print header
            print(f"Module{' ' * (max_module - 6)}   Model{' ' * (max_model - 2)}Table")
            print(f"{'-' * max_module}---{'-' * max_model}---{'-' * 20}")

            # Sort by module order first, then by registration order
            for model in sorted(
                cls.models, key=lambda x: (cls._get_module_order(x["module"]), x["module"], x["order"])
            ):
                module_pad = " " * (max_module - len(model["module"]))
                model_pad = " " * (max_model - len(model["model"]))
                print(f"{model['module']}{module_pad}   {model['model']}{model_pad}   {model['table']}")
            print()


def print_registry(models: list[dict[str, Any]]) -> None:
    """Print model registry"""
    if getattr(print_registry, "has_printed", False):
        return

    print("\nDatabase Model Registry:")
    print("------------------------")

    # Find the longest names for padding
    max_module = max(len(m["module"]) for m in models)
    max_model = max(len(m["model"]) for m in models)

    # Print header
    print(f"\nModule{' ' * (max_module - 6)}   Model{' ' * (max_model - 2)}   Table")
    print(f"{'-' * max_module}   {'-' * max_model}   {'-' * 20}")

    # Sort and print models
    for model in sorted(
        models,
        key=lambda x: (ModelRegistry._get_module_order(x["module"]), x["module"], x["order"]),
    ):
        module_pad = " " * (max_module - len(model["module"]))
        model_pad = " " * (max_model - len(model["model"]))
        print(f"{model['module']}{module_pad}   {model['model']}{model_pad}   {model['table']}")
    print()

    print_registry.has_printed = True  # type: ignore[attr-defined]
