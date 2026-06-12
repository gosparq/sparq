# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Dashboard module manifest defining module metadata, dependencies, and
#     configuration. Provides the main business dashboard view.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

manifest = {
    "name": "Home",
    "version": "1.0",
    "main_route": "/dashboard",
    "icon_class": "fa-solid fa-home",
    "type": "App",
    "color": "#7c3aed",
    "depends": ["core"],
    "description": "Business dashboard and analytics",
    "long_description": "Central dashboard showing business pipeline, metrics, and activity.",
}
