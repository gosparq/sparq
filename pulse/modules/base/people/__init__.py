# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Team module initialization and route registration. Sets up core team
#     and employee management functionality.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

"""Team module for employee and organizational management.

This module provides employee profiles, departments, onboarding workflows,
and organizational structure management.

Key Models:
    WorkspaceUser: Workspace membership profile linked to User, with status, type, rates.
    Department: Organizational departments.

Key Features:
    - Employee profiles with personal info, rates, emergency contacts
    - Employee status tracking (Active, On Leave, Terminated, Contractor)
    - Employee types (Full Time, Part Time, Contractor, Intern)
    - Labor cost and bill rates for time tracking
    - Manager/reports hierarchy
    - Onboarding workflow

Example:
    Creating a workspace member::

        from modules.base.core.models.workspace_user import WorkspaceUser

        member = WorkspaceUser.create(
            email="john@example.com",
            password="secure123",
            first_name="John",
            last_name="Doe",
            department="Engineering",
            position="Developer"
        )

    Querying members::

        from modules.base.core.models.workspace_user import WorkspaceUser, EmployeeStatus

        active = WorkspaceUser.scoped().filter_by(status=EmployeeStatus.ACTIVE).all()
"""

from .module import PeopleModule

# Import all models to ensure they're registered with SQLAlchemy
# This is required even if the module is disabled, as other modules may reference them
from modules.base.core.models.workspace_user import WorkspaceUser, EmployeeStatus, EmployeeType

# Create module instance
# Routes are registered via the get_routes() hook in module.py
# Filters are registered in controllers/__init__.py when the blueprint is created
module_instance = PeopleModule()

__all__ = [
    "module_instance",
    "WorkspaceUser",
    "EmployeeStatus",
    "EmployeeType",
]
