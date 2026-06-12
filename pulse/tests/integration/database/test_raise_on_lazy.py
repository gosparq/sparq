# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# Lazy-Load Guard Tests — DB Access Standards §7.4
#
# Verifies the session-level raiseload('*') override. When enabled, any
# unanticipated lazy load throws InvalidRequestError. Explicit joinedload
# and the skip_raise_on_lazy opt-out bypass the guard.
# -----------------------------------------------------------------------------

import os
import uuid

import pytest
from flask import g
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.orm import joinedload

from system.db.database import db


@pytest.fixture()
def _enable_raise_on_lazy(app):
    """Temporarily enable SPARQ_RAISE_ON_LAZY and register the guard."""
    prev = os.environ.get("SPARQ_RAISE_ON_LAZY")
    os.environ["SPARQ_RAISE_ON_LAZY"] = "1"

    from sqlalchemy import event
    from system.db.raise_on_lazy import _enforce_raise_on_lazy

    event.listen(db.session, "do_orm_execute", _enforce_raise_on_lazy)
    yield
    event.remove(db.session, "do_orm_execute", _enforce_raise_on_lazy)

    if prev is None:
        os.environ.pop("SPARQ_RAISE_ON_LAZY", None)
    else:
        os.environ["SPARQ_RAISE_ON_LAZY"] = prev


@pytest.fixture()
def member_with_user(app, db_session):
    """Create a WorkspaceUser→User pair for lazy-load testing."""
    from modules.base.core.models.organization import Organization
    from modules.base.core.models.organization_user import OrganizationUser
    from modules.base.core.models.workspace import Workspace
    from modules.base.core.models.workspace_user import WorkspaceUser
    from modules.base.core.models.user import User

    with app.app_context():
        org = Organization(id=uuid.uuid4(), name="Lazy Org", slug=f"lazy-{uuid.uuid4().hex[:6]}")
        db.session.add(org)
        db.session.flush()
        g.organization_id = org.id

        ts = Workspace(
            id=uuid.uuid4(), slug=f"lazy-ts-{uuid.uuid4().hex[:6]}",
            name="Lazy TS", organization_id=org.id,
        )
        db.session.add(ts)
        db.session.flush()
        g.workspace_id = ts.id

        user = User.create(
            email=f"lazy-{uuid.uuid4().hex[:6]}@test.com",
            password="testpass123", first_name="Lazy", last_name="Tester",
            is_admin=False,
        )

        org_user = OrganizationUser.create(
            organization_id=org.id, user_id=user.id, role="member",
        )

        member = WorkspaceUser(
            user_id=user.id, workspace_id=ts.id,
            organization_user_id=org_user.id, role="member",
        )
        db.session.add(member)
        db.session.commit()

        yield {"member": member, "user": user, "org": org, "ts": ts}


@pytest.mark.integration
class TestRaiseOnLazy:
    """Tests for the lazy-load guard that prevents unanticipated N+1 queries."""

    def test_lazy_load_raises_when_enabled(self, app, _enable_raise_on_lazy, member_with_user):
        """Accessing a lazy relationship without joinedload raises InvalidRequestError."""
        from modules.base.core.models.workspace_user import WorkspaceUser

        with app.app_context():
            g.organization_id = member_with_user["org"].id
            g.workspace_id = member_with_user["ts"].id

            member = db.session.get(WorkspaceUser, member_with_user["member"].id)
            assert member is not None

            with pytest.raises(InvalidRequestError):
                _ = member.user

    def test_joinedload_bypasses_raiseload(self, app, _enable_raise_on_lazy, member_with_user):
        """Explicit joinedload works even with the raiseload guard active."""
        from modules.base.core.models.workspace_user import WorkspaceUser

        with app.app_context():
            g.organization_id = member_with_user["org"].id
            g.workspace_id = member_with_user["ts"].id

            member = (
                WorkspaceUser.query
                .options(joinedload(WorkspaceUser.user))
                .filter_by(id=member_with_user["member"].id)
                .first()
            )
            assert member is not None
            assert member.user.first_name == "Lazy"

    def test_opt_out_allows_lazy_load(self, app, _enable_raise_on_lazy, member_with_user):
        """skip_raise_on_lazy=True allows lazy loading even with the guard active."""
        from modules.base.core.models.workspace_user import WorkspaceUser
        from sqlalchemy.orm import joinedload

        with app.app_context():
            g.organization_id = member_with_user["org"].id
            g.workspace_id = member_with_user["ts"].id

            member = (
                WorkspaceUser.query
                .execution_options(skip_raise_on_lazy=True)
                .options(joinedload(WorkspaceUser.user))
                .filter_by(id=member_with_user["member"].id)
                .first()
            )
            assert member is not None
            assert member.user.first_name == "Lazy"

    def test_guard_inactive_without_env_var(self, app, member_with_user):
        """Without the per-test fixture guard, joinedload bypasses raiseload.

        Note: SPARQ_RAISE_ON_LAZY=1 is set globally for the test suite, so the
        session-level raiseload('*') listener is always registered. This test
        verifies that explicit joinedload still works without the fixture's
        extra event listener.
        """
        from modules.base.core.models.workspace_user import WorkspaceUser
        from sqlalchemy.orm import joinedload

        with app.app_context():
            g.organization_id = member_with_user["org"].id
            g.workspace_id = member_with_user["ts"].id

            member = (
                WorkspaceUser.query
                .options(joinedload(WorkspaceUser.user))
                .filter_by(id=member_with_user["member"].id)
                .first()
            )
            assert member is not None
            assert member.user.first_name == "Lazy"
