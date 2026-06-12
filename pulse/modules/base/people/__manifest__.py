# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Team module manifest defining module metadata, dependencies, and
#     configuration. Specifies core team and employee management features.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

manifest = {
    "name": "People",
    "version": "1.0",
    "main_route": "/people",
    "icon_class": "fa-solid fa-users",
    "type": "App",
    "color": "#10b981",
    "depends": ["core"],
    "description": "People and HR management",
    "long_description": "People management including employee profiles, onboarding, forms, and documents.",
}
