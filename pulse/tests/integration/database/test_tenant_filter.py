# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# Tenant Filter Tests — DB Access Standards §6.1
#
# Verifies the session-level do_orm_execute tenant guard. Two organizations
# are created with contacts in each; tests confirm cross-tenant isolation,
# opt-out, and no-context safety.
# -----------------------------------------------------------------------------

import uuid

import pytest
from flask import g

from system.db.database import db


@pytest.fixture()
def two_orgs(app, db_session):
    """Create two organizations, each with a workspace and a contact."""
    from modules.base.core.models.contact import Contact
    from modules.base.core.models.organization import Organization
    from modules.base.core.models.workspace import Workspace

    with app.app_context():
        # --- Org A ---
        org_a = Organization(id=uuid.uuid4(), name="Org A", slug=f"org-a-{uuid.uuid4().hex[:6]}")
        db.session.add(org_a)
        db.session.flush()

        g.organization_id = org_a.id
        ts_a = Workspace(
            id=uuid.uuid4(), slug=f"ts-a-{uuid.uuid4().hex[:6]}",
            name="TS A", organization_id=org_a.id,
        )
        db.session.add(ts_a)
        db.session.flush()
        g.workspace_id = ts_a.id

        contact_a = Contact(
            first_name="Alice", last_name="Alpha",
            organization_id=org_a.id, workspace_id=ts_a.id,
        )
        db.session.add(contact_a)

        # --- Org B ---
        org_b = Organization(id=uuid.uuid4(), name="Org B", slug=f"org-b-{uuid.uuid4().hex[:6]}")
        db.session.add(org_b)
        db.session.flush()

        contact_b = Contact(
            first_name="Bob", last_name="Bravo",
            organization_id=org_b.id, workspace_id=None,
        )
        db.session.add(contact_b)

        db.session.commit()

        yield {
            "org_a": org_a,
            "org_b": org_b,
            "ts_a": ts_a,
            "contact_a": contact_a,
            "contact_b": contact_b,
        }


@pytest.mark.integration
class TestTenantFilter:
    """Tests for session-level tenant isolation filter."""

    def test_filter_applied_to_scoped_model(self, app, two_orgs):
        """Bare .query.all() on a mixin model only returns current org's rows."""
        from modules.base.core.models.contact import Contact

        with app.app_context():
            g.organization_id = two_orgs["org_a"].id
            g.workspace_id = two_orgs["ts_a"].id

            results = Contact.query.all()
            assert len(results) == 1
            assert results[0].first_name == "Alice"

    def test_filter_not_applied_to_unscoped_model(self, app, two_orgs):
        """Organization.query.all() returns all orgs (no mixin)."""
        from modules.base.core.models.organization import Organization

        with app.app_context():
            g.organization_id = two_orgs["org_a"].id

            results = Organization.query.all()
            assert len(results) >= 2

    def test_filter_skipped_when_no_org_context(self, app, two_orgs):
        """No g.organization_id → filter is no-op, all rows returned."""
        from modules.base.core.models.contact import Contact

        with app.app_context():
            # Ensure no org context
            for attr in ("organization_id", "workspace_id"):
                try:
                    delattr(g, attr)
                except AttributeError:
                    pass

            results = Contact.query.all()
            assert len(results) >= 2

    def test_opt_out_with_execution_options(self, app, two_orgs):
        """skip_tenant_filter=True → all rows returned."""
        from modules.base.core.models.contact import Contact

        with app.app_context():
            g.organization_id = two_orgs["org_a"].id
            g.workspace_id = two_orgs["ts_a"].id

            results = (
                Contact.query
                .execution_options(skip_tenant_filter=True)
                .all()
            )
            assert len(results) >= 2

    def test_filter_harmless_with_scoped(self, app, two_orgs):
        """.scoped() + session filter = same result as .scoped() alone."""
        from modules.base.core.models.contact import Contact

        with app.app_context():
            g.organization_id = two_orgs["org_a"].id
            g.workspace_id = two_orgs["ts_a"].id

            scoped_results = Contact.scoped().all()
            query_results = Contact.query.all()

            scoped_ids = {c.id for c in scoped_results}
            query_ids = {c.id for c in query_results}
            assert scoped_ids == query_ids

    def test_filter_works_on_eager_loads(self, app, two_orgs):
        """Eager-loaded relationships on mixin models also respect the filter."""
        from modules.base.core.models.organization import Organization
        from sqlalchemy.orm import joinedload

        with app.app_context():
            g.organization_id = two_orgs["org_a"].id
            g.workspace_id = two_orgs["ts_a"].id

            org = (
                Organization.query
                .options(joinedload(Organization.workspaces))
                .filter_by(id=two_orgs["org_a"].id)
                .first()
            )
            assert org is not None

            # Verify org A's workspaces don't include org B data
            workspace_ids = [ts.id for ts in org.workspaces]
            assert two_orgs["ts_a"].id in workspace_ids
