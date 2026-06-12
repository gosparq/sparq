# -----------------------------------------------------------------------------
# sparQ - MSA (Multi-workspace System Admin)
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

manifest = {
    "name": "MSA",
    "version": "1.0",
    "main_route": "/msa",
    "icon_class": "fa-solid fa-server",
    "type": "System",
    "color": "#10b981",
    "depends": ["core"],
    "description": "Multi-workspace system administration",
    "long_description": "Workspace management console for platform operators. "
    "Create, configure, and monitor workspaces across the platform.",
    "admin_only": True,
}
