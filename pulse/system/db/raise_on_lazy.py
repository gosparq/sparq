# -----------------------------------------------------------------------------
# sparQ — Dev/Test Lazy-Load Guard (DB Access Standards §7.4)
#
# In dev and test environments, applies raiseload('*') to every ORM SELECT so
# that unanticipated lazy loads throw InvalidRequestError at the point of
# access instead of silently issuing extra queries.
#
# Gated behind SPARQ_RAISE_ON_LAZY=1 env var.  Opt out per-query with
# .execution_options(skip_raise_on_lazy=True).
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

import os

from sqlalchemy import event
from sqlalchemy.orm import ORMExecuteState, Session, raiseload

_raise_enabled = os.environ.get("SPARQ_RAISE_ON_LAZY", "").lower() in ("1", "true")

LAZY = "raise_on_sql" if _raise_enabled else "select"


def _enforce_raise_on_lazy(execute_state: ORMExecuteState) -> None:
    """Apply raiseload('*') to catch unanticipated lazy loads."""
    if not execute_state.is_select:
        return
    if execute_state.execution_options.get("skip_raise_on_lazy"):
        return
    execute_state.statement = execute_state.statement.options(raiseload("*"))


def register_raise_on_lazy(session_factory: Session) -> None:
    """Register the lazy-load guard if SPARQ_RAISE_ON_LAZY is enabled."""
    if _raise_enabled:
        event.listen(session_factory, "do_orm_execute", _enforce_raise_on_lazy)
