# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Module management system that defines hook specifications and implements
#     the plugin architecture for module extensibility. Provides core hooks
#     for database initialization and other module lifecycle events.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

"""Pluggy hook specifications for module lifecycle events.

This module defines the hook specifications that modules can implement
to participate in system lifecycle events.

Classes:
    ModuleSpecs: Hook specification class defining available hooks.

Attributes:
    hookspec: Decorator for defining hook specifications.
    hookimpl: Decorator for implementing hooks in modules.

Available Hooks:
    init_database: Called after all modules load to initialize tables.

Example:
    Implementing the init_database hook in a module::

        from system.module.hooks import hookimpl

        class MyModule:
            @hookimpl
            def init_database(self):
                from .models import MyModel
                # Create sample data if needed
                if MyModel.query.count() == 0:
                    MyModel.create(name="Default")
"""

import pluggy

# Define hookspecs and hookimpl markers
hookspec = pluggy.HookspecMarker("sparQOne")
hookimpl = pluggy.HookimplMarker("sparQOne")


class ModuleSpecs:
    @hookspec
    def init_database(self) -> None:
        """Optional: Initialize database tables and sample data for the module.
        This hook is called after all modules are loaded and the database
        connection is established.
        """
        pass

    @hookspec
    def register_ai_tools(self, registry) -> None:
        """Optional: Register AI tools with the tool registry.
        This hook is called when the AI system collects tools from all modules.

        Args:
            registry: ToolRegistry instance to register tools with

        Example:
            @hookimpl
            def register_ai_tools(self, registry):
                from .tools import my_tool
                registry.register(my_tool)
        """
        pass

    @hookspec
    def record_created(self, model_type: str, record, user_id: int | None) -> None:
        """Called after a model record is created and committed.

        Args:
            model_type: The model class name (e.g., "ServiceRequest")
            record: The created model instance
            user_id: ID of user who created the record
        """
        pass

    @hookspec
    def record_updated(self, model_type: str, record, user_id: int | None, changes: dict) -> None:
        """Called after a model record is updated and committed.

        Args:
            model_type: The model class name
            record: The updated model instance
            user_id: ID of user who updated the record
            changes: Dictionary of changed fields {field: (old_value, new_value)}
        """
        pass

    @hookspec
    def record_deleted(self, model_type: str, record_id: int, user_id: int | None, soft: bool) -> None:
        """Called after a model record is deleted.

        Args:
            model_type: The model class name
            record_id: ID of the deleted record
            user_id: ID of user who deleted the record
            soft: True if this was a soft delete
        """
        pass

    @hookspec
    def record_custom(self, model_type: str, event: str, record, user_id: int | None) -> None:
        """Called for custom domain events (status transitions, etc.).

        Args:
            model_type: The model class name (e.g., "ServiceRequest")
            event: The custom event name (e.g., "contacted", "won", "sent")
            record: The model instance
            user_id: ID of user who triggered the event
        """
        pass
