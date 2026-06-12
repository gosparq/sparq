# -----------------------------------------------------------------------------
# sparQ - OrganizationMixin (org-first tenant isolation)
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""Multitenancy: OrganizationMixin is the single tenant isolation boundary.

Every tenant-scoped row carries organization_id NOT NULL. Optional filters
(workspace_id, project_id) narrow within an org but never cross it.

WorkspaceMixin is retained as a thin convenience: OrganizationMixin + a
nullable workspace_id column. Historical callers keep working; new models
should inherit OrganizationMixin directly and add workspace_id only if they
need per-workspace filtering.

auto_set_organization_id is a before_flush listener that stamps g.organization_id
onto new rows. auto_set_workspace_id stamps g.workspace_id on rows that have
a workspace_id column — skipped when g.scope == "organization" so org-wide
creates stay at workspace_id=NULL.
"""

from flask import g
from sqlalchemy.ext.declarative import declared_attr
from werkzeug.exceptions import NotFound

from system.db.database import db


class _ScopedQuery:
    """Wrapper around a filtered query that makes get_or_404 work correctly.

    SQLAlchemy's Query.get() raises InvalidRequestError when called on a
    query that already carries filter criteria. This wrapper redirects
    get() / get_or_404() to use filter_by(id=...) instead.
    """

    def __init__(self, query, model_class):
        self._query = query
        self._model_class = model_class

    def get_or_404(self, ident, description=None):
        rv = self._query.filter_by(id=ident).first()
        if rv is None:
            raise NotFound(description)
        return rv

    def get(self, ident):
        return self._query.filter_by(id=ident).first()

    def __getattr__(self, name):
        return getattr(self._query, name)

    def __iter__(self):
        return iter(self._query)


class OrganizationMixin:
    """Hard tenant isolation at the organization level.

    Add to any model that belongs to a single Organization::

        class Foo(db.Model, OrganizationMixin):
            ...

    scoped() always filters by g.organization_id. If the model also carries
    a workspace_id column, scoped() additionally narrows by g.workspace_id
    (workspace scope) or to rows where workspace_id IS NULL (organization
    scope). This means the same scoped() call Just Works in both scopes
    without callers branching on g.scope.
    """

    @declared_attr
    def organization_id(cls):
        return db.Column(
            db.UUID(as_uuid=True),
            db.ForeignKey("organization.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )

    @classmethod
    def scoped(cls) -> "_ScopedQuery":
        organization_id = getattr(g, "organization_id", None)
        if organization_id is None:
            raise RuntimeError(
                f"{cls.__name__}.scoped() called without organization context. "
                "Set g.organization_id before querying, or use .for_organization(id)."
            )
        q = cls.query.filter_by(organization_id=organization_id)

        if hasattr(cls, "workspace_id"):
            scope = getattr(g, "scope", "workspace")
            if scope == "organization":
                q = q.filter(cls.workspace_id.is_(None))
            else:
                workspace_id = getattr(g, "workspace_id", None)
                if workspace_id is not None:
                    q = q.filter_by(workspace_id=workspace_id)

        return _ScopedQuery(q, cls)

    @classmethod
    def org_wide(cls) -> "_ScopedQuery":
        """Return a query for rows that belong to the org but no workspace."""
        organization_id = getattr(g, "organization_id", None)
        if organization_id is None:
            raise RuntimeError(
                f"{cls.__name__}.org_wide() called without organization context."
            )
        q = cls.query.filter_by(organization_id=organization_id)
        if hasattr(cls, "workspace_id"):
            q = q.filter(cls.workspace_id.is_(None))
        return _ScopedQuery(q, cls)

    @classmethod
    def for_organization(cls, organization_id) -> "_ScopedQuery":
        """Explicit org override — use from admin tools / background jobs."""
        return _ScopedQuery(
            cls.query.filter_by(organization_id=organization_id), cls
        )

    @classmethod
    def for_workspace(cls, workspace_id) -> "_ScopedQuery":
        """Explicit workspace override on a model with a workspace_id column.

        Does NOT filter by organization — callers must ensure workspace_id
        corresponds to a workspace within the current org.
        """
        if not hasattr(cls, "workspace_id"):
            raise AttributeError(
                f"{cls.__name__} has no workspace_id column; "
                "for_workspace is not applicable."
            )
        return _ScopedQuery(cls.query.filter_by(workspace_id=workspace_id), cls)


class WorkspaceMixin(OrganizationMixin):
    """OrganizationMixin + a nullable workspace_id filter column.

    Convenience mixin for models that historically scoped per workspace.
    organization_id remains the tenant boundary; workspace_id is optional,
    so the same row can be "org-wide" (workspace_id IS NULL) or "scoped to
    a specific workspace". scoped() behavior is defined on OrganizationMixin
    and handles both cases automatically.
    """

    @declared_attr
    def workspace_id(cls):
        return db.Column(
            db.UUID(as_uuid=True),
            db.ForeignKey("workspace.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        )


def auto_set_organization_id(session, flush_context, instances):
    """before_flush listener — stamps g.organization_id on new rows."""
    organization_id = getattr(g, "organization_id", None)
    if organization_id is None:
        return

    for obj in session.new:
        if hasattr(obj, "organization_id") and obj.organization_id is None:
            obj.organization_id = organization_id


def auto_set_workspace_id(session, flush_context, instances):
    """before_flush listener — stamps g.workspace_id on new rows.

    Skipped in organization scope so that org-scope creates land with
    workspace_id=NULL (org-wide rows).
    """
    if getattr(g, "scope", None) == "organization":
        return

    workspace_id = getattr(g, "workspace_id", None)
    if workspace_id is None:
        return

    for obj in session.new:
        if hasattr(obj, "workspace_id") and obj.workspace_id is None:
            obj.workspace_id = workspace_id
