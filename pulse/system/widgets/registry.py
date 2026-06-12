# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Widget registry for customizable dashboard quick links.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

import json
from typing import TypedDict

from system.module.registry import module_enabled


class WidgetConfig(TypedDict):
    """Type definition for a widget configuration."""

    id: str
    route: str
    label: str
    icon: str
    color: str


class ModuleWidgets(TypedDict):
    """Type definition for a module's widget collection."""

    module: str
    label: str
    widgets: list[WidgetConfig]


# All available widgets organized by module
AVAILABLE_WIDGETS: dict[str, ModuleWidgets] = {
    "connect": {
        "module": "Sync",
        "label": "Sync",
        "widgets": [
            {
                "id": "chat",
                "route": "sync_bp.chat_index",
                "label": "Chat",
                "icon": "fa-comments",
                "color": "#8b5cf6",
            },
            {
                "id": "dm",
                "route": "sync_bp.get_dm_threads",
                "label": "Direct Messages",
                "icon": "fa-envelope",
                "color": "#10b981",
            },
            {
                "id": "calendar",
                "route": "sync_bp.calendar_index",
                "label": "Calendar",
                "icon": "fa-calendar",
                "color": "#f97316",
            },
        ],
    },
    "presence": {
        "module": "Presence",
        "label": "Presence",
        "widgets": [
            {
                "id": "clock",
                "route": "clock_bp.index",
                "label": "In/Out",
                "icon": "fa-clock",
                "color": "#10b981",
            },
            {
                "id": "timeoff",
                "route": "pto_bp.index",
                "label": "Time Off",
                "icon": "fa-umbrella-beach",
                "color": "#3b82f6",
            },
        ],
    },
    "service": {
        "module": "Service",
        "label": "Service",
        "widgets": [
            {
                "id": "schedule",
                "route": "service_bp.schedule",
                "label": "Schedule",
                "icon": "fa-calendar-alt",
                "color": "#f97316",
            },
            {
                "id": "jobs",
                "route": "service_bp.jobs_list",
                "label": "Jobs",
                "icon": "fa-briefcase",
                "color": "#eab308",
            },
        ],
    },
    "people": {
        "module": "People",
        "label": "People",
        "widgets": [
            {
                "id": "people",
                "route": "people_bp.people",
                "label": "People",
                "icon": "fa-users",
                "color": "#ec4899",
            },
            {
                "id": "profile",
                "route": "people_bp.my_profile",
                "label": "Profile",
                "icon": "fa-user",
                "color": "#6b7280",
            },
        ],
    },
    "sales": {
        "module": "Sales",
        "label": "Sales",
        "widgets": [
            {
                "id": "requests",
                "route": "sales_bp.requests_list",
                "label": "Requests",
                "icon": "fa-bullhorn",
                "color": "#3b82f6",
            },
            {
                "id": "quotes",
                "route": "sales_bp.quotes_list",
                "label": "Quotes",
                "icon": "fa-file-invoice-dollar",
                "color": "#10b981",
            },
        ],
    },
    "finance": {
        "module": "Finance",
        "label": "Finance",
        "widgets": [
            {
                "id": "expenses",
                "route": "finance_bp.expenses",
                "label": "Expenses",
                "icon": "fa-receipt",
                "color": "#f59e0b",
            },
        ],
    },
}

# Admin-specific widgets (require admin access)
ADMIN_WIDGETS: dict[str, ModuleWidgets] = {
    "admin_presence": {
        "module": "Presence",
        "label": "Presence",
        "widgets": [
            {
                "id": "approve_timesheets",
                "route": "presence_bp.approve_timesheets",
                "label": "Timesheets",
                "icon": "fa-user-clock",
                "color": "#3b82f6",
            },
            {
                "id": "approve_leave",
                "route": "pto_bp.approve_pto",
                "label": "Leave",
                "icon": "fa-calendar-check",
                "color": "#10b981",
            },
        ],
    },
    "admin_settings": {
        "module": "Settings",
        "label": "Settings",
        "widgets": [
            {
                "id": "settings",
                "route": "core_bp.settings",
                "label": "Settings",
                "icon": "fa-cog",
                "color": "#6b7280",
            },
            {
                "id": "user_groups",
                "route": "core_bp.manage_permissions",
                "label": "Permissions",
                "icon": "fa-users-cog",
                "color": "#8b5cf6",
            },
        ],
    },
    "admin_people": {
        "module": "People",
        "label": "People",
        "widgets": [
            {
                "id": "employees",
                "route": "people_bp.people",
                "label": "People",
                "icon": "fa-id-card",
                "color": "#ec4899",
            },
            {
                "id": "hiring",
                "route": "people_bp.hiring",
                "label": "Hiring",
                "icon": "fa-user-plus",
                "color": "#f97316",
            },
        ],
    },
}

# Default widgets for FSM mode (field service management)
DEFAULT_FSM_WIDGETS: list[str] = ["chat", "clock", "schedule", "board", "people", "profile"]

# Default widgets for Office mode
DEFAULT_OFFICE_WIDGETS: list[str] = ["chat", "clock", "schedule", "board", "people", "profile"]

# Default admin widgets
DEFAULT_ADMIN_WIDGETS: list[str] = ["chat", "clock", "schedule", "board", "people", "profile"]


def get_widget_by_id(widget_id: str, include_admin: bool = False) -> WidgetConfig | None:
    """Get a widget configuration by its ID.

    Args:
        widget_id: The widget ID to look up
        include_admin: Whether to also search admin widgets
    """
    # Search regular widgets
    for module_data in AVAILABLE_WIDGETS.values():
        for widget in module_data["widgets"]:
            if widget["id"] == widget_id:
                return widget

    # Search admin widgets if requested
    if include_admin:
        for module_data in ADMIN_WIDGETS.values():
            for widget in module_data["widgets"]:
                if widget["id"] == widget_id:
                    return widget

    return None


def get_available_widgets() -> dict[str, ModuleWidgets]:
    """Get all available widgets filtered by enabled modules."""
    result: dict[str, ModuleWidgets] = {}

    for key, module_data in AVAILABLE_WIDGETS.items():
        module_name = module_data["module"]

        # Team module is always enabled (core functionality)
        if module_name == "Team" or module_enabled(module_name):
            # Filter widgets that have valid routes
            available = []
            for widget in module_data["widgets"]:
                available.append(widget)
            if available:
                result[key] = {
                    "module": module_name,
                    "label": module_data["label"],
                    "widgets": available,
                }

    return result


def get_default_widgets(is_fsm_mode: bool = False) -> list[WidgetConfig]:
    """Get the default widget configuration for new users.

    Args:
        is_fsm_mode: True for field service management mode, False for office mode

    Returns:
        List of widget configurations
    """
    widget_ids = DEFAULT_FSM_WIDGETS if is_fsm_mode else DEFAULT_OFFICE_WIDGETS
    widgets: list[WidgetConfig] = []

    for widget_id in widget_ids:
        widget = get_widget_by_id(widget_id)
        if widget:
            # Check if the module for this widget is enabled
            for module_data in AVAILABLE_WIDGETS.values():
                for w in module_data["widgets"]:
                    if w["id"] == widget_id:
                        module_name = module_data["module"]
                        if module_name == "Team" or module_enabled(module_name):
                            widgets.append(widget)
                        break

    return widgets


def get_user_widgets(user_id: int, is_fsm_mode: bool = False) -> list[WidgetConfig]:
    """Get the widget configuration for a user.

    Args:
        user_id: The user's ID
        is_fsm_mode: True for FSM mode, False for office mode

    Returns:
        List of widget configurations
    """
    from modules.base.core.models.user_setting import UserSetting

    setting = UserSetting.get(user_id, "dashboard_widgets")

    if setting:
        try:
            data = json.loads(setting)
            widgets = data.get("widgets", [])

            # Filter out widgets whose modules are no longer enabled
            valid_widgets: list[WidgetConfig] = []
            for widget in widgets:
                widget_id = widget.get("id")
                if widget_id:
                    # Check if the widget's module is still enabled
                    for module_data in AVAILABLE_WIDGETS.values():
                        for w in module_data["widgets"]:
                            if w["id"] == widget_id:
                                module_name = module_data["module"]
                                if module_name == "Team" or module_enabled(module_name):
                                    valid_widgets.append(widget)
                                break

            return valid_widgets
        except (json.JSONDecodeError, TypeError):
            pass

    # Return defaults if no saved config
    return get_default_widgets(is_fsm_mode)


def save_user_widgets(user_id: int, widgets: list[WidgetConfig]) -> None:
    """Save the widget configuration for a user.

    Args:
        user_id: The user's ID
        widgets: List of widget configurations to save
    """
    from modules.base.core.models.user_setting import UserSetting

    data = {"widgets": widgets}
    UserSetting.set(user_id, "dashboard_widgets", json.dumps(data))


def get_available_admin_widgets() -> dict[str, ModuleWidgets]:
    """Get all available admin widgets filtered by enabled modules."""
    result: dict[str, ModuleWidgets] = {}

    for key, module_data in ADMIN_WIDGETS.items():
        module_name = module_data["module"]

        # Settings is always available, other modules check if enabled
        if module_name == "Settings" or module_name == "Team" or module_enabled(module_name):
            available = []
            for widget in module_data["widgets"]:
                available.append(widget)
            if available:
                result[key] = {
                    "module": module_name,
                    "label": module_data["label"],
                    "widgets": available,
                }

    # Also include regular widgets that admins might want
    regular = get_available_widgets()
    result.update(regular)

    return result


def get_default_admin_widgets() -> list[WidgetConfig]:
    """Get the default widget configuration for admin users.

    Returns:
        List of widget configurations
    """
    widgets: list[WidgetConfig] = []

    for widget_id in DEFAULT_ADMIN_WIDGETS:
        widget = get_widget_by_id(widget_id, include_admin=True)
        if widget:
            # Check if the module for this widget is enabled
            all_widgets = {**AVAILABLE_WIDGETS, **ADMIN_WIDGETS}
            for module_data in all_widgets.values():
                for w in module_data["widgets"]:
                    if w["id"] == widget_id:
                        module_name = module_data["module"]
                        if module_name in ("Team", "Settings") or module_enabled(module_name):
                            widgets.append(widget)
                        break

    return widgets


def get_admin_widgets(user_id: int) -> list[WidgetConfig]:
    """Get the widget configuration for an admin user.

    Args:
        user_id: The user's ID

    Returns:
        List of widget configurations
    """
    from modules.base.core.models.user_setting import UserSetting

    setting = UserSetting.get(user_id, "dashboard_admin_widgets")

    if setting:
        try:
            data = json.loads(setting)
            widgets = data.get("widgets", [])

            # Filter out widgets whose modules are no longer enabled
            valid_widgets: list[WidgetConfig] = []
            all_widgets = {**AVAILABLE_WIDGETS, **ADMIN_WIDGETS}
            for widget in widgets:
                widget_id = widget.get("id")
                if widget_id:
                    # Check if the widget's module is still enabled
                    for module_data in all_widgets.values():
                        for w in module_data["widgets"]:
                            if w["id"] == widget_id:
                                module_name = module_data["module"]
                                if module_name in ("Team", "Settings") or module_enabled(module_name):
                                    valid_widgets.append(widget)
                                break

            return valid_widgets
        except (json.JSONDecodeError, TypeError):
            pass

    # Return defaults if no saved config
    return get_default_admin_widgets()


def save_admin_widgets(user_id: int, widgets: list[WidgetConfig]) -> None:
    """Save the admin widget configuration for a user.

    Args:
        user_id: The user's ID
        widgets: List of widget configurations to save
    """
    from modules.base.core.models.user_setting import UserSetting

    data = {"widgets": widgets}
    UserSetting.set(user_id, "dashboard_admin_widgets", json.dumps(data))
