# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Team module hook specifications for plugin system integration.
#     Defines hooks for employee lifecycle events and data management.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

from system.module.hooks import hookspec


class TeamHookSpecs:
    @hookspec
    def modify_new_employee_form(self):
        """Add custom elements to the new employee form.
        Returns:
            list: List of HTML strings to be inserted into the new employee form
        """
        pass

    @hookspec
    def process_new_employee(self, form_data, employee):
        """Process additional employee data from form submission.
        Args:
            form_data: The submitted form data
            employee: The newly created employee instance
        """
        pass

    @hookspec
    def modify_edit_employee_form(self, employee):
        """Add additional fields to employee edit form.
        Args:
            employee: The employee being edited
        Returns:
            list: List of HTML strings to be inserted into the edit form
        """
        pass

    @hookspec
    def process_employee_update(self, form_data, employee):
        """Process additional form data when employee is updated.
        Args:
            form_data: The submitted form data
            employee: The employee being updated
        """
        pass

    @hookspec
    def employee_created(self, employee):
        """Called after a new employee is created"""
        pass

    @hookspec
    def employee_updated(self, employee, changes):
        """Called after an employee is updated"""
        pass

    @hookspec
    def get_employee_display_name(self, employee):
        """Get additional display name info for employee (e.g., nickname).
        Args:
            employee: The employee to get display name for
        Returns:
            str: Additional name info to display, or None
        """
        pass
