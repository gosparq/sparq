# -----------------------------------------------------------------------------
# sparQ - MSA Module
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""MSA (Multi-workspace System Admin) module.

Platform-level admin console for workspace management. Operates independently
of workspace context — works on bare domain with its own session auth.

Routes:
    /msa/login  - Admin login (admin/password)
    /msa/       - Dashboard overview
    /msa/workspaces - Workspace list with CRUD
    /msa/workspaces/<id> - Workspace detail drill-down
"""

from .module import MSAModule

module_instance = MSAModule()

__all__ = ["module_instance"]
