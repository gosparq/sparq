# -----------------------------------------------------------------------------
# sparQ - Navigation Sections
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# Navigation Sections Registry
#
# Single unified sidebar: Today / Connect / Work / People
# The primary icon rail has been removed; this sidebar is always visible.
# -----------------------------------------------------------------------------

# Primary nav — unused (icon rail removed)
PRIMARY_NAV = []

# Section order drives sidebar render order
DEFAULT_SECTION_ORDER = ["today", "connect", "work", "people"]

# Pinned modules matches section order
DEFAULT_PINNED_MODULES = ["today", "connect", "work", "people"]

NAV_SECTIONS = {
    "today": {
        "id": "today",
        "label": "Today",
        "collapsible": False,
        "items": [
            {
                "id": "home",
                "url": "/dashboard/",
                "icon": "fas fa-house",
                "label": "Home",
                "match_prefix": "/dashboard",
            },
            {
                "id": "calendar",
                "url": "/sync/calendar",
                "icon": "fas fa-calendar-day",
                "label": "Calendar",
                "match_prefix": "/sync/calendar",
            },
            {
                "id": "timeclock",
                "url": "/presence/clock",
                "icon": "fas fa-clock",
                "label": "Time Clock",
                "match_prefix": "/presence/clock",
                "module_check": "Presence",
            },
            {
                "id": "inoutboard",
                "url": "/presence/board",
                "icon": "fas fa-right-left",
                "label": "In/Out Board",
                "match_prefix": "/presence/board",
                "module_check": "Presence",
            },
        ],
    },
    "connect": {
        "id": "connect",
        "label": "Connect",
        "module_check": "Updates",
        "collapsible": False,
        "items": [
            {
                "id": "updates",
                "url": "/updates/",
                "icon": "fas fa-arrows-rotate",
                "label": "Status",
                "match_prefix": "/updates",
                "exclude_prefix": ["/updates/wins", "/updates/pulse"]
            },
            {
                "id": "wins",
                "url": "/updates/wins/",
                "icon": "fas fa-trophy",
                "label": "Wins",
                "match_prefix": "/updates/wins",
            },
            {
                "id": "board",
                "url": "/sync/board",
                "icon": "fas fa-clipboard-list",
                "label": "Board",
                "match_prefix": "/sync/board"
            },
        ],
    },
    "work": {
        "id": "work",
        "label": "Work",
        "collapsible": False,
        "items": [
            {
                "id": "projects",
                "url": "/projects/",
                "icon": "fas fa-folder",
                "label": "Projects",
                "match_prefix": "/projects",
            },
            {
                "id": "tasks",
                "url": "/tasks/board",
                "icon": "fas fa-list-check",
                "label": "Tasks",
                "match_prefix": "/tasks/board",
                "exclude_prefix": "/tasks/blockers",
            },
            {
                "id": "inbox",
                "url": "/notifications/inbox",
                "icon": "fas fa-inbox",
                "label": "Inbox",
                "match_prefix": "/notifications/inbox",
            },
            {
                "id": "blockers",
                "url": "/tasks/blockers",
                "icon": "fas fa-hand",
                "label": "Blockers",
                "match_prefix": "/tasks/blockers",
                
            },
            {
                "id": "docs_notes",
                "url": "/resources/docs/",
                "icon": "fas fa-file-lines",
                "label": "Docs & Notes",
                "match_prefix": "/resources",
            },
        ],
    },
    "people": {
        "id": "people",
        "label": "People",
        "collapsible": True,
        "default_open": False,
        "items": [
            {
                "id": "directory",
                "url": "/people/people",
                "icon": "fas fa-user",
                "label": "Directory",
                "match_prefix": "/people/people",
            },
            {
                "id": "hiring",
                "url": "/people/hiring",
                "icon": "fas fa-user-plus",
                "label": "Hiring",
                "match_prefix": "/people/hiring",
                "requires_access": "hr",
            },
            {
                "id": "onboarding",
                "url": "/people/onboarding",
                "icon": "fas fa-handshake",
                "label": "Onboarding",
                "match_prefix": "/people/onboarding",
                "requires_access": "hr",
            },
            {
                "id": "offboarding",
                "url": "/people/offboarding",
                "icon": "fas fa-door-open",
                "label": "Offboarding",
                "match_prefix": "/people/offboarding",
                "requires_access": "hr",
            },
            {
                "id": "timesheets",
                "url": "/presence/timesheets/day",
                "icon": "fas fa-table",
                "label": "Timesheets",
                "match_prefix": "/presence/timesheets",
                "module_check": "Presence",
            },
            {
                "id": "pto",
                "url": "/presence/pto/",
                "icon": "fas fa-plane",
                "label": "PTO & Leave",
                "match_prefix": "/presence/pto",
                "module_check": "Presence",
            },
        ],
    },
}



def get_nav_sections():
    """Return the nav sections dictionary."""
    return NAV_SECTIONS


def get_primary_nav():
    """Return the primary nav icon rail items (empty — rail removed)."""
    return PRIMARY_NAV


def get_default_order():
    """Return the default section order."""
    return DEFAULT_SECTION_ORDER


def get_default_pinned_modules():
    """Return the default pinned modules list."""
    return DEFAULT_PINNED_MODULES
