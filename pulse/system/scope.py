# -----------------------------------------------------------------------------
# sparQ - Scope Middleware
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""g.scope middleware — resolves workspace vs organization scope per request.

Phase 6 of the Organization Hierarchy spec (§5). Organization-level surfaces
live **inline** with existing modules via URL path segments — e.g.
`/people/organization/` flips the People module to its organization view.
There is no parallel `/organization/` route tree.

This hook runs AFTER `set_workspace_context` (which sets g.workspace_id and
g.organization_id) and BEFORE the main before_request that populates the
module metadata. It decorates `g` with:

    g.scope                  : "workspace" (default) | "organization"
    g.is_organization_admin  : bool — True if the current user has an active
                                OrganizationUser with role='admin' in the
                                current organization.
    g.workspace_access       : "member" | "audit" | None — whether the user
                                is a full member of g.workspace_id or is
                                accessing it via organization-admin audit
                                access (§12.2).

Detection strictness (Q8): only the **literal** segment `organization`
immediately after a module's main_route switches scope. Any other use of
"organization" in paths is unaffected.
"""

from __future__ import annotations

from flask import Flask, g, request
from flask_login import current_user


def register_scope_hook(app: Flask) -> None:
    """Register the scope-resolution before_request hook."""

    @app.before_request
    def set_scope_context() -> None:  # type: ignore[misc]
        # Default values so every request-handling code path has consistent `g`.
        g.scope = "workspace"
        g.is_organization_admin = False
        g.workspace_access = None
        g.workspace_count = 0

        path = request.path or ""
        # Per-module scope marker: if any path segment is literally "organization"
        # we flip to organization scope. URL shapes vary across blueprints —
        # /people/people/organization, /resources/docs/organization,
        # /updates/organization/wins — so segment-index matching is unreliable.
        segments = [s.lower() for s in path.split("/") if s]
        if "organization" in segments:
            g.scope = "organization"

        # Authenticated-user derived flags.
        if not current_user.is_authenticated:
            return

        organization_id = getattr(g, "organization_id", None)
        workspace_id = getattr(g, "workspace_id", None)

        if organization_id is not None:
            # Read from g if available (populated by set_workspace_context Path 1)
            org_membership = getattr(g, "_organization_user", None)
            if org_membership is None:
                from modules.base.core.models.organization_user import OrganizationUser

                org_membership = OrganizationUser.get_for_user(
                    current_user.id, organization_id
                )
            if (
                org_membership is not None
                and org_membership.is_active
                and org_membership.role == "admin"
            ):
                g.is_organization_admin = True

            cached_count = getattr(g, "_workspace_count_cache", None)
            if cached_count is not None:
                g.workspace_count = cached_count
            else:
                from modules.base.core.models.workspace import Workspace
                from modules.base.core.models.workspace_user import WorkspaceUser

                g.workspace_count = (
                    WorkspaceUser.query
                    .join(Workspace, Workspace.id == WorkspaceUser.workspace_id)
                    .filter(WorkspaceUser.user_id == current_user.id)
                    .filter(WorkspaceUser.deleted_at.is_(None))
                    .filter(Workspace.organization_id == organization_id)
                    .filter(Workspace.deleted_at.is_(None))
                    .count()
                )

        if workspace_id is not None:
            membership = getattr(g, "_workspace_membership", None)
            if membership is not None:
                g.workspace_access = "member"
            elif g.is_organization_admin:
                # Org admin visiting a workspace they're not a member of.
                g.workspace_access = "audit"
