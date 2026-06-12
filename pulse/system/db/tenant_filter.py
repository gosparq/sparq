# -----------------------------------------------------------------------------
# sparQ — Session-Level Tenant Filter (DB Access Standards §6.1)
#
# Defense-in-depth: injects WHERE organization_id = <current_org> on every
# ORM SELECT against models inheriting OrganizationMixin. Additive to the
# existing .scoped() convention — double-filtering is harmless (same predicate).
#
# No-op when no org context exists (CLI, migrations, pre-auth requests).
# Opt out per-query with .execution_options(skip_tenant_filter=True).
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from flask import g
from sqlalchemy import event
from sqlalchemy.orm import ORMExecuteState, Session, with_loader_criteria

from system.db.workspace import OrganizationMixin


def _add_tenant_filter(execute_state: ORMExecuteState) -> None:
    if not execute_state.is_select:
        return
    if execute_state.execution_options.get("skip_tenant_filter"):
        return
    try:
        org_id = g.organization_id
    except (RuntimeError, AttributeError):
        return
    if org_id is None:
        return
    execute_state.statement = execute_state.statement.options(
        with_loader_criteria(
            OrganizationMixin,
            lambda cls: cls.organization_id == org_id,
            include_aliases=True,
        )
    )


def register_tenant_filter(session_factory: Session) -> None:
    event.listen(session_factory, "do_orm_execute", _add_tenant_filter)
