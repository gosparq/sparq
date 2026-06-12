# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - Core Model Integration Tests
#
# Tests for all core models: Organization, OrganizationUser,
# OrganizationInvitation, Workspace, WorkspaceUser, WorkspaceSettings,
# AuthSettings, Contact, SystemNotification, OAuthConnection, PendingSignup,
# PushSubscription, ServiceLocation, UserSetting, AuditLog.
# -----------------------------------------------------------------------------

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

import pytest

from flask import g


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _set_g_context(ws_dict):
    """Set g.organization_id and g.workspace_id from seeded_workspace dict."""
    g.organization_id = ws_dict["organization"].id
    g.workspace_id = ws_dict["workspace"].id


# =========================================================================
# 1. Organization
# =========================================================================

@pytest.mark.integration
class TestOrganization:
    """Tests for Organization model."""

    def test_create_organization(self, app, db_session):
        """Test creating an organization via the create classmethod."""
        from modules.base.core.models.organization import Organization

        with app.app_context():
            org = Organization.create(name="Acme Corp", slug="acme-corp")
            assert org.id is not None
            assert org.name == "Acme Corp"
            assert org.slug == "acme-corp"
            assert org.plan == "free"
            assert org.is_active is True

    def test_create_organization_strips_name(self, app, db_session):
        """Test that create strips leading/trailing whitespace from name."""
        from modules.base.core.models.organization import Organization

        with app.app_context():
            org = Organization.create(name="  Padded Name  ", slug="padded")
            assert org.name == "Padded Name"

    def test_create_invalid_slug_raises(self, app, db_session):
        """Test that an invalid slug raises ValueError."""
        from modules.base.core.models.organization import Organization

        with app.app_context():
            with pytest.raises(ValueError, match="Invalid slug"):
                Organization.create(name="Bad", slug="A")  # uppercase

    def test_create_duplicate_slug_raises(self, app, db_session):
        """Test that a duplicate slug raises ValueError."""
        from modules.base.core.models.organization import Organization

        with app.app_context():
            Organization.create(name="First", slug="dup-slug")
            with pytest.raises(ValueError, match="already exists"):
                Organization.create(name="Second", slug="dup-slug")

    def test_update_organization(self, app, db_session):
        """Test updating organization fields."""
        from modules.base.core.models.organization import Organization

        with app.app_context():
            org = Organization.create(name="Old Name", slug="old-name")
            org.update(name="New Name", plan="pro")
            assert org.name == "New Name"
            assert org.plan == "pro"

    def test_update_slug_validation(self, app, db_session):
        """Test that updating to an invalid slug raises ValueError."""
        from modules.base.core.models.organization import Organization

        with app.app_context():
            org = Organization.create(name="Test", slug="test-slug")
            with pytest.raises(ValueError, match="Invalid slug"):
                org.update(slug="!invalid!")

    def test_update_info(self, app, db_session):
        """Test updating legal entity info fields."""
        from modules.base.core.models.organization import Organization

        with app.app_context():
            org = Organization.create(name="Info Org", slug="info-org")
            org.update_info(
                name="Updated Info Org",
                phone="555-1234",
                email="info@org.com",
                city="Austin",
                state="TX",
            )
            assert org.name == "Updated Info Org"
            assert org.phone == "555-1234"
            assert org.email == "info@org.com"
            assert org.city == "Austin"

    def test_update_info_empty_string_becomes_none(self, app, db_session):
        """Test that empty strings in update_info become None."""
        from modules.base.core.models.organization import Organization

        with app.app_context():
            org = Organization.create(name="Info Org2", slug="info-org2")
            org.update_info(phone="555-1234")
            assert org.phone == "555-1234"
            org.update_info(phone="")
            assert org.phone is None

    def test_deactivate_and_activate(self, app, db_session):
        """Test deactivating and reactivating an organization."""
        from modules.base.core.models.organization import Organization

        with app.app_context():
            org = Organization.create(name="Toggle Org", slug="toggle-org")
            assert org.is_active is True

            org.deactivate()
            assert org.is_active is False

            org.activate()
            assert org.is_active is True

    def test_find_by_domain(self, app, db_session):
        """Test domain query helpers."""
        from modules.base.core.models.organization import Organization

        with app.app_context():
            Organization.create(
                name="Domain Org", slug="domain-org", claimed_domain="example.com",
            )
            results = Organization.find_by_domain("example.com")
            assert len(results) == 1
            assert results[0].name == "Domain Org"

    def test_count_by_domain(self, app, db_session):
        """Test counting organizations by domain."""
        from modules.base.core.models.organization import Organization

        with app.app_context():
            Organization.create(
                name="D1", slug="d1-org", claimed_domain="counted.com",
            )
            assert Organization.count_by_domain("counted.com") == 1
            assert Organization.count_by_domain("nonexistent.com") == 0

    def test_get_sole_claimer(self, app, db_session):
        """Test get_sole_claimer returns one org or None."""
        from modules.base.core.models.organization import Organization

        with app.app_context():
            org = Organization.create(
                name="Sole", slug="sole-org", claimed_domain="sole.com",
            )
            assert Organization.get_sole_claimer("sole.com") == org

            # Add a second claimer — should return None
            Organization.create(
                name="Sole2", slug="sole-org2", claimed_domain="sole.com",
            )
            assert Organization.get_sole_claimer("sole.com") is None

    def test_claimed_domain_normalized(self, app, db_session):
        """Test that claimed_domain is normalized on write."""
        from modules.base.core.models.organization import Organization

        with app.app_context():
            org = Organization.create(
                name="Norm", slug="norm-org", claimed_domain="  EXAMPLE.COM  ",
            )
            assert org.claimed_domain == "example.com"

    def test_can_delete(self, app, db_session):
        """Test can_delete checks ownership and multiple orgs."""
        from modules.base.core.models.organization import Organization
        from modules.base.core.models.user import User

        with app.app_context():
            user = User.create(
                email="org-owner@test.com", password="pass123",
                first_name="Org", last_name="Owner",
            )
            org1 = Organization.create(name="Org1", slug="org1-del", owner_id=user.id)
            Organization.create(name="Org2", slug="org2-del", owner_id=user.id)

            # Owner with 2 orgs can delete either
            assert Organization.can_delete(org1.id, user.id) is True

            # Non-owner cannot delete
            assert Organization.can_delete(org1.id, 99999) is False

    def test_get_all_and_count(self, app, db_session):
        """Test get_all and count class methods."""
        from modules.base.core.models.organization import Organization

        with app.app_context():
            Organization.create(name="Count1", slug="count1-org")
            Organization.create(name="Count2", slug="count2-org")
            assert Organization.count() >= 2
            all_orgs = Organization.get_all()
            assert len(all_orgs) >= 2

    def test_get_by_ids(self, app, db_session):
        """Test retrieving multiple organizations by ID set."""
        from modules.base.core.models.organization import Organization

        with app.app_context():
            org1 = Organization.create(name="IDs1", slug="ids1-org")
            org2 = Organization.create(name="IDs2", slug="ids2-org")
            result = Organization.get_by_ids({org1.id, org2.id})
            assert org1.id in result
            assert org2.id in result


# =========================================================================
# 2. OrganizationUser
# =========================================================================

@pytest.mark.integration
class TestOrganizationUser:
    """Tests for OrganizationUser model."""

    def test_create_membership(self, app, db_session, seeded_workspace):
        """Test creating an organization membership."""
        from modules.base.core.models.organization_user import OrganizationUser
        from modules.base.core.models.user import User

        with app.app_context():
            _set_g_context(seeded_workspace)
            user = User.create(
                email="ou-test@test.com", password="pass123",
                first_name="OU", last_name="Test",
            )
            ou = OrganizationUser.create(
                organization_id=seeded_workspace["organization"].id,
                user_id=user.id,
                role="member",
            )
            assert ou.id is not None
            assert ou.role == "member"
            assert ou.is_active is True

    def test_create_with_invalid_role_raises(self, app, db_session, seeded_workspace):
        """Test that creating with invalid role raises ValueError."""
        from modules.base.core.models.organization_user import OrganizationUser

        with app.app_context():
            _set_g_context(seeded_workspace)
            with pytest.raises(ValueError, match="Invalid role"):
                OrganizationUser.create(
                    organization_id=seeded_workspace["organization"].id,
                    user_id=seeded_workspace["user"].id,
                    role="superuser",
                )

    def test_set_role(self, app, db_session, seeded_workspace):
        """Test changing an org membership role."""
        from modules.base.core.models.organization_user import OrganizationUser
        from modules.base.core.models.user import User

        with app.app_context():
            _set_g_context(seeded_workspace)
            user = User.create(
                email="role-change@test.com", password="pass123",
                first_name="Role", last_name="Change",
            )
            ou = OrganizationUser.create(
                organization_id=seeded_workspace["organization"].id,
                user_id=user.id,
                role="member",
            )
            ou.set_role("admin")
            assert ou.role == "admin"

    def test_set_role_invalid_raises(self, app, db_session, seeded_workspace):
        """Test that set_role with invalid role raises ValueError."""
        from modules.base.core.models.organization_user import OrganizationUser
        from modules.base.core.models.user import User

        with app.app_context():
            _set_g_context(seeded_workspace)
            user = User.create(
                email="role-bad@test.com", password="pass123",
                first_name="Role", last_name="Bad",
            )
            ou = OrganizationUser.create(
                organization_id=seeded_workspace["organization"].id,
                user_id=user.id,
                role="member",
            )
            with pytest.raises(ValueError):
                ou.set_role("superuser")

    def test_deactivate_and_reactivate(self, app, db_session, seeded_workspace):
        """Test deactivating and reactivating a membership."""
        from modules.base.core.models.organization_user import OrganizationUser
        from modules.base.core.models.user import User

        with app.app_context():
            _set_g_context(seeded_workspace)
            user = User.create(
                email="deact-ou@test.com", password="pass123",
                first_name="Deact", last_name="OU",
            )
            ou = OrganizationUser.create(
                organization_id=seeded_workspace["organization"].id,
                user_id=user.id,
            )
            ou.deactivate()
            assert ou.is_active is False

            ou.reactivate()
            assert ou.is_active is True

    def test_is_organization_admin_property(self, app, db_session, seeded_workspace):
        """Test is_organization_admin property."""
        from modules.base.core.models.organization_user import OrganizationUser
        from modules.base.core.models.user import User

        with app.app_context():
            _set_g_context(seeded_workspace)
            user = User.create(
                email="admin-prop@test.com", password="pass123",
                first_name="Admin", last_name="Prop",
            )
            ou = OrganizationUser.create(
                organization_id=seeded_workspace["organization"].id,
                user_id=user.id,
                role="admin",
            )
            assert ou.is_organization_admin is True
            ou.deactivate()
            assert ou.is_organization_admin is False

    def test_get_for_user(self, app, db_session, seeded_workspace):
        """Test get_for_user query."""
        from modules.base.core.models.organization_user import OrganizationUser

        with app.app_context():
            _set_g_context(seeded_workspace)
            ws = seeded_workspace
            found = OrganizationUser.get_for_user(ws["user"].id, ws["organization"].id)
            assert found is not None
            assert found.user_id == ws["user"].id

    def test_list_for_user(self, app, db_session, seeded_workspace):
        """Test list_for_user query."""
        from modules.base.core.models.organization_user import OrganizationUser

        with app.app_context():
            _set_g_context(seeded_workspace)
            memberships = OrganizationUser.list_for_user(seeded_workspace["user"].id)
            assert len(memberships) >= 1

    def test_list_for_organization(self, app, db_session, seeded_workspace):
        """Test list_for_organization query."""
        from modules.base.core.models.organization_user import OrganizationUser

        with app.app_context():
            _set_g_context(seeded_workspace)
            members = OrganizationUser.list_for_organization(
                seeded_workspace["organization"].id,
            )
            assert len(members) >= 1

    def test_get_or_create_existing(self, app, db_session, seeded_workspace):
        """Test get_or_create returns existing membership."""
        from modules.base.core.models.organization_user import OrganizationUser

        with app.app_context():
            _set_g_context(seeded_workspace)
            ws = seeded_workspace
            existing = OrganizationUser.get_for_user(ws["user"].id, ws["organization"].id)
            result = OrganizationUser.get_or_create(
                organization_id=ws["organization"].id,
                user_id=ws["user"].id,
            )
            assert result.id == existing.id

    def test_get_or_create_reactivates_inactive(self, app, db_session, seeded_workspace):
        """Test get_or_create reactivates an inactive membership."""
        from modules.base.core.models.organization_user import OrganizationUser
        from modules.base.core.models.user import User

        with app.app_context():
            _set_g_context(seeded_workspace)
            user = User.create(
                email="reactivate-ou@test.com", password="pass123",
                first_name="Reactivate", last_name="OU",
            )
            ou = OrganizationUser.create(
                organization_id=seeded_workspace["organization"].id,
                user_id=user.id,
            )
            ou.deactivate()
            assert ou.is_active is False

            result = OrganizationUser.get_or_create(
                organization_id=seeded_workspace["organization"].id,
                user_id=user.id,
            )
            assert result.is_active is True
            assert result.id == ou.id

    def test_count_admins(self, app, db_session, seeded_workspace):
        """Test count_admins method."""
        from modules.base.core.models.organization_user import OrganizationUser

        with app.app_context():
            _set_g_context(seeded_workspace)
            count = OrganizationUser.count_admins(seeded_workspace["organization"].id)
            assert count >= 1

    def test_can_leave_as_owner(self, app, db_session, seeded_workspace):
        """Test that the owner cannot leave the organization."""
        from modules.base.core.models.organization_user import OrganizationUser
        from modules.base.core.models.organization import Organization
        from modules.base.core.models.user import User

        with app.app_context():
            _set_g_context(seeded_workspace)
            # Create a fresh org with an explicit owner
            owner = User.create(
                email="leave-owner@test.com", password="pass123",
                first_name="Leave", last_name="Owner",
            )
            org = Organization.create(
                name="Leave Org", slug="leave-org", owner_id=owner.id,
            )
            OrganizationUser.create(
                organization_id=org.id, user_id=owner.id, role="admin",
            )

            can, reason = OrganizationUser.can_leave(owner.id, org.id)
            assert can is False
            assert "owner" in reason.lower()

    def test_can_leave_as_member(self, app, db_session, seeded_workspace):
        """Test that a non-owner member can leave."""
        from modules.base.core.models.organization_user import OrganizationUser
        from modules.base.core.models.user import User

        with app.app_context():
            _set_g_context(seeded_workspace)
            user = User.create(
                email="can-leave@test.com", password="pass123",
                first_name="Can", last_name="Leave",
            )
            OrganizationUser.create(
                organization_id=seeded_workspace["organization"].id,
                user_id=user.id,
            )
            can, reason = OrganizationUser.can_leave(
                user.id, seeded_workspace["organization"].id,
            )
            assert can is True

    def test_formatted_rates(self, app, db_session, seeded_workspace):
        """Test formatted_labor_cost_rate and formatted_bill_rate."""
        from modules.base.core.models.organization_user import OrganizationUser
        from modules.base.core.models.user import User
        from system.db.database import db

        with app.app_context():
            _set_g_context(seeded_workspace)
            user = User.create(
                email="rates@test.com", password="pass123",
                first_name="Rates", last_name="Test",
            )
            ou = OrganizationUser.create(
                organization_id=seeded_workspace["organization"].id,
                user_id=user.id,
            )
            ou.labor_cost_rate = Decimal("45.00")
            ou.bill_rate = Decimal("85.50")
            db.session.commit()

            assert ou.formatted_labor_cost_rate == "$45.00/hr"
            assert ou.formatted_bill_rate == "$85.50/hr"

    def test_formatted_rates_none(self, app, db_session, seeded_workspace):
        """Test formatted rates when not set."""
        from modules.base.core.models.organization_user import OrganizationUser
        from modules.base.core.models.user import User

        with app.app_context():
            _set_g_context(seeded_workspace)
            user = User.create(
                email="no-rates@test.com", password="pass123",
                first_name="NoRates", last_name="Test",
            )
            ou = OrganizationUser.create(
                organization_id=seeded_workspace["organization"].id,
                user_id=user.id,
            )
            assert ou.formatted_labor_cost_rate is None
            assert ou.formatted_bill_rate is None

    def test_is_employment_active(self, app, db_session, seeded_workspace):
        """Test is_employment_active property."""
        from modules.base.core.models.organization_user import OrganizationUser
        from modules.base.core.models.user import User
        from system.db.database import db

        with app.app_context():
            _set_g_context(seeded_workspace)
            user = User.create(
                email="emp-active@test.com", password="pass123",
                first_name="Emp", last_name="Active",
            )
            ou = OrganizationUser.create(
                organization_id=seeded_workspace["organization"].id,
                user_id=user.id,
            )
            assert ou.is_employment_active is True
            ou.employment_status = "TERMINATED"
            db.session.commit()
            assert ou.is_employment_active is False

    def test_dismiss_auto_join_banner(self, app, db_session, seeded_workspace):
        """Test dismiss_auto_join_banner method."""
        from modules.base.core.models.organization_user import OrganizationUser
        from modules.base.core.models.user import User

        with app.app_context():
            _set_g_context(seeded_workspace)
            user = User.create(
                email="banner-test@test.com", password="pass123",
                first_name="Banner", last_name="Test",
            )
            ou = OrganizationUser.create(
                organization_id=seeded_workspace["organization"].id,
                user_id=user.id,
            )
            assert ou.auto_join_banner_dismissed is False
            ou.dismiss_auto_join_banner()
            assert ou.auto_join_banner_dismissed is True

    def test_get_by_pin(self, app, db_session, seeded_workspace):
        """Test get_by_pin lookup."""
        from modules.base.core.models.organization_user import OrganizationUser
        from modules.base.core.models.user import User
        from system.db.database import db

        with app.app_context():
            _set_g_context(seeded_workspace)
            user = User.create(
                email="pin-test@test.com", password="pass123",
                first_name="Pin", last_name="Test",
            )
            ou = OrganizationUser.create(
                organization_id=seeded_workspace["organization"].id,
                user_id=user.id,
            )
            ou.clock_pin = "1234"
            db.session.commit()

            found = OrganizationUser.get_by_pin("1234", seeded_workspace["organization"].id)
            assert found is not None
            assert found.id == ou.id

            # Empty pin returns None
            assert OrganizationUser.get_by_pin("", seeded_workspace["organization"].id) is None

    def test_get_member_counts(self, app, db_session, seeded_workspace):
        """Test get_member_counts aggregation."""
        from modules.base.core.models.organization_user import OrganizationUser

        with app.app_context():
            _set_g_context(seeded_workspace)
            counts = OrganizationUser.get_member_counts()
            assert isinstance(counts, dict)
            assert seeded_workspace["organization"].id in counts


# =========================================================================
# 3. OrganizationInvitation
# =========================================================================

@pytest.mark.integration
class TestOrganizationInvitation:
    """Tests for OrganizationInvitation model."""

    def test_create_invitation(self, app, db_session, seeded_workspace):
        """Test creating an organization invitation."""
        from modules.base.core.models.organization_invitation import OrganizationInvitation

        with app.app_context():
            _set_g_context(seeded_workspace)
            inv = OrganizationInvitation.create(
                organization_id=seeded_workspace["organization"].id,
                email="invite@test.com",
                role="member",
            )
            assert inv.id is not None
            assert inv.email == "invite@test.com"
            assert inv.role == "member"
            assert inv.token is not None
            assert inv.expires_at is not None
            assert inv.accepted_at is None

    def test_create_invitation_invalid_role(self, app, db_session, seeded_workspace):
        """Test that creating with an invalid role raises ValueError."""
        from modules.base.core.models.organization_invitation import OrganizationInvitation

        with app.app_context():
            _set_g_context(seeded_workspace)
            with pytest.raises(ValueError, match="Invalid role"):
                OrganizationInvitation.create(
                    organization_id=seeded_workspace["organization"].id,
                    email="bad-role@test.com",
                    role="superuser",
                )

    def test_create_normalizes_email(self, app, db_session, seeded_workspace):
        """Test that email is normalized to lowercase."""
        from modules.base.core.models.organization_invitation import OrganizationInvitation

        with app.app_context():
            _set_g_context(seeded_workspace)
            inv = OrganizationInvitation.create(
                organization_id=seeded_workspace["organization"].id,
                email="  UPPER@Example.COM  ",
            )
            assert inv.email == "upper@example.com"

    def test_get_by_token(self, app, db_session, seeded_workspace):
        """Test retrieving invitation by token."""
        from modules.base.core.models.organization_invitation import OrganizationInvitation

        with app.app_context():
            _set_g_context(seeded_workspace)
            inv = OrganizationInvitation.create(
                organization_id=seeded_workspace["organization"].id,
                email="token-test@test.com",
            )
            found = OrganizationInvitation.get_by_token(inv.token)
            assert found is not None
            assert found.id == inv.id

    def test_get_by_token_expired(self, app, db_session, seeded_workspace):
        """Test that expired token returns None."""
        from modules.base.core.models.organization_invitation import OrganizationInvitation
        from system.db.database import db

        with app.app_context():
            _set_g_context(seeded_workspace)
            inv = OrganizationInvitation.create(
                organization_id=seeded_workspace["organization"].id,
                email="expired@test.com",
            )
            # Manually expire the token
            inv.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
            db.session.commit()

            found = OrganizationInvitation.get_by_token(inv.token)
            assert found is None

    def test_get_by_token_already_accepted(self, app, db_session, seeded_workspace):
        """Test that an already-accepted token returns None."""
        from modules.base.core.models.organization_invitation import OrganizationInvitation
        from system.db.database import db

        with app.app_context():
            _set_g_context(seeded_workspace)
            inv = OrganizationInvitation.create(
                organization_id=seeded_workspace["organization"].id,
                email="accepted@test.com",
            )
            inv.accepted_at = datetime.now(timezone.utc)
            db.session.commit()

            found = OrganizationInvitation.get_by_token(inv.token)
            assert found is None

    def test_get_pending_for_email(self, app, db_session, seeded_workspace):
        """Test get_pending_for_email returns only valid pending invitations."""
        from modules.base.core.models.organization_invitation import OrganizationInvitation

        with app.app_context():
            _set_g_context(seeded_workspace)
            OrganizationInvitation.create(
                organization_id=seeded_workspace["organization"].id,
                email="pending@test.com",
            )
            pending = OrganizationInvitation.get_pending_for_email("pending@test.com")
            assert len(pending) == 1

    def test_accept_invitation(self, app, db_session, seeded_workspace):
        """Test accepting an invitation creates an OrganizationUser."""
        from modules.base.core.models.organization_invitation import OrganizationInvitation
        from modules.base.core.models.user import User
        from system.db.database import db

        with app.app_context():
            _set_g_context(seeded_workspace)
            inv = OrganizationInvitation.create(
                organization_id=seeded_workspace["organization"].id,
                email="accept@test.com",
                role="member",
            )
            user = User.create(
                email="accept@test.com", password="pass123",
                first_name="Accept", last_name="Test",
            )
            membership = inv.accept(user.id)
            db.session.commit()

            assert membership is not None
            assert membership.user_id == user.id
            assert membership.role == "member"
            assert inv.accepted_at is not None

    def test_ensure_for_org_idempotent(self, app, db_session, seeded_workspace):
        """Test ensure_for_org is idempotent."""
        from modules.base.core.models.organization_invitation import OrganizationInvitation

        with app.app_context():
            _set_g_context(seeded_workspace)
            org_id = seeded_workspace["organization"].id
            inv1 = OrganizationInvitation.ensure_for_org(
                email="ensure@test.com", organization_id=org_id,
            )
            assert inv1 is not None

            inv2 = OrganizationInvitation.ensure_for_org(
                email="ensure@test.com", organization_id=org_id,
            )
            assert inv2 is None  # Already exists


# =========================================================================
# 4. Workspace
# =========================================================================

@pytest.mark.integration
class TestWorkspace:
    """Tests for Workspace model."""

    def test_workspace_in_seeded_context(self, app, db_session, seeded_workspace):
        """Test that seeded workspace exists and has expected fields."""
        with app.app_context():
            ws = seeded_workspace["workspace"]
            assert ws.id is not None
            assert ws.name == "Test Workspace"
            assert ws.slug is not None
            assert ws.organization_id == seeded_workspace["organization"].id

    def test_workspace_color_hex(self, app, db_session, seeded_workspace):
        """Test color_hex property."""
        from modules.base.core.models.workspace import WORKSPACE_COLORS

        with app.app_context():
            ws = seeded_workspace["workspace"]
            assert ws.color_hex in WORKSPACE_COLORS.values()

    def test_generate_unique_slug(self, app, db_session):
        """Test _generate_unique_slug produces valid slugs."""
        from modules.base.core.models.workspace import Workspace

        with app.app_context():
            slug = Workspace._generate_unique_slug("My Cool Workspace")
            assert slug is not None
            assert " " not in slug

    def test_generate_unique_slug_deduplicates(self, app, db_session, seeded_workspace):
        """Test that duplicate workspace names produce unique slugs."""
        from modules.base.core.models.workspace import Workspace
        from system.db.database import db

        with app.app_context():
            _set_g_context(seeded_workspace)
            slug1 = Workspace._generate_unique_slug("Duplicate Name")
            # Create a workspace with the first slug
            ws = Workspace(
                slug=slug1, name="Duplicate Name",
                organization_id=seeded_workspace["organization"].id,
            )
            db.session.add(ws)
            db.session.flush()

            slug2 = Workspace._generate_unique_slug("Duplicate Name")
            assert slug2 != slug1

    def test_active_in_organization(self, app, db_session, seeded_workspace):
        """Test active_in_organization returns non-archived workspaces."""
        from modules.base.core.models.workspace import Workspace

        with app.app_context():
            _set_g_context(seeded_workspace)
            active = Workspace.active_in_organization(seeded_workspace["organization"].id)
            assert len(active) >= 1

    def test_active_count_for_organization(self, app, db_session, seeded_workspace):
        """Test active_count_for_organization."""
        from modules.base.core.models.workspace import Workspace

        with app.app_context():
            count = Workspace.active_count_for_organization(
                seeded_workspace["organization"].id,
            )
            assert count >= 1

    def test_archive_last_workspace_raises(self, app, db_session, seeded_workspace):
        """Test that archiving the last workspace raises ValueError."""

        with app.app_context():
            _set_g_context(seeded_workspace)
            ws = seeded_workspace["workspace"]
            # There is only one workspace so archiving it should fail
            with pytest.raises(ValueError, match="Cannot archive the last"):
                ws.archive(actor_user_id=seeded_workspace["user"].id)

    def test_archive_and_restore(self, app, db_session, seeded_workspace):
        """Test archiving and restoring a workspace."""
        from modules.base.core.models.workspace import Workspace
        from system.db.database import db

        with app.app_context():
            _set_g_context(seeded_workspace)
            org_id = seeded_workspace["organization"].id
            user_id = seeded_workspace["user"].id

            # Create a second workspace so we can archive one
            ws2 = Workspace(
                slug=f"archivable-{uuid.uuid4().hex[:6]}",
                name="Archivable",
                organization_id=org_id,
            )
            db.session.add(ws2)
            db.session.commit()

            ws2.archive(actor_user_id=user_id)
            assert ws2.deleted_at is not None

            archived = Workspace.archived_in_organization(org_id)
            assert any(w.id == ws2.id for w in archived)

            ws2.restore_archived(actor_user_id=user_id)
            assert ws2.deleted_at is None

    def test_count_and_count_active(self, app, db_session, seeded_workspace):
        """Test count and count_active class methods."""
        from modules.base.core.models.workspace import Workspace

        with app.app_context():
            total = Workspace.count()
            active = Workspace.count_active()
            assert total >= 1
            assert active >= 1

    def test_get_by_id(self, app, db_session, seeded_workspace):
        """Test get_by_id."""
        from modules.base.core.models.workspace import Workspace

        with app.app_context():
            ws = Workspace.get_by_id(seeded_workspace["workspace"].id)
            assert ws is not None
            assert ws.name == "Test Workspace"

    def test_for_organization(self, app, db_session, seeded_workspace):
        """Test for_organization query."""
        from modules.base.core.models.workspace import Workspace

        with app.app_context():
            workspaces = Workspace.for_organization(seeded_workspace["organization"].id)
            assert len(workspaces) >= 1


# =========================================================================
# 5. WorkspaceUser
# =========================================================================

@pytest.mark.integration
class TestWorkspaceUser:
    """Tests for WorkspaceUser model — employment fields, status, termination."""

    def test_workspace_user_in_seeded_context(self, app, db_session, seeded_workspace):
        """Test that seeded workspace has a member."""
        with app.app_context():
            _set_g_context(seeded_workspace)
            member = seeded_workspace["membership"]
            assert member.id is not None
            assert member.role == "admin"
            assert member.user_id == seeded_workspace["user"].id

    def test_scoped_query(self, app, db_session, seeded_workspace):
        """Test scoped() returns members in current workspace."""
        from modules.base.core.models.workspace_user import WorkspaceUser

        with app.app_context():
            _set_g_context(seeded_workspace)
            members = WorkspaceUser.scoped().all()
            assert len(members) >= 1

    def test_scoped_without_context_raises(self, app, db_session):
        """Test scoped() raises without workspace context."""
        from modules.base.core.models.workspace_user import WorkspaceUser

        with app.app_context():
            # Ensure no workspace_id in g
            if hasattr(g, "workspace_id"):
                delattr(g, "workspace_id")
            with pytest.raises(RuntimeError):
                WorkspaceUser.scoped()

    def test_permission_set_and_has_permission(self, app, db_session, seeded_workspace):
        """Test permission_set and has_permission."""
        from modules.base.core.models.workspace_user import WorkspaceUser
        from system.db.database import db

        with app.app_context():
            _set_g_context(seeded_workspace)
            member = seeded_workspace["membership"]

            # Admin has all permissions
            assert member.has_permission("hr") is True
            assert member.has_permission("finance") is True

            # Create a non-admin member with specific permissions
            from modules.base.core.models.user import User
            from modules.base.core.models.organization_user import OrganizationUser

            user2 = User.create(
                email="perm-test@test.com", password="pass123",
                first_name="Perm", last_name="Test",
            )
            ou2 = OrganizationUser.create(
                organization_id=seeded_workspace["organization"].id,
                user_id=user2.id,
            )
            member2 = WorkspaceUser(
                user_id=user2.id,
                workspace_id=seeded_workspace["workspace"].id,
                organization_user_id=ou2.id,
                role="member",
            )
            db.session.add(member2)
            db.session.commit()

            member2.set_permissions(["hr", "finance"])
            assert member2.permission_set == {"hr", "finance"}
            assert member2.has_permission("hr") is True
            assert member2.has_permission("operations") is False

    def test_formatted_salary(self, app, db_session, seeded_workspace):
        """Test formatted_salary property."""
        from modules.base.core.models.workspace_user import SalaryType
        from system.db.database import db

        with app.app_context():
            _set_g_context(seeded_workspace)
            member = seeded_workspace["membership"]
            member.salary = Decimal("75000.00")
            member.salary_type = SalaryType.YEARLY
            db.session.commit()
            assert member.formatted_salary == "$75,000.00/yr"

            member.salary_type = SalaryType.HOURLY
            db.session.commit()
            assert member.formatted_salary == "$75,000.00/hr"

    def test_formatted_salary_none(self, app, db_session, seeded_workspace):
        """Test formatted_salary when salary is not set."""
        with app.app_context():
            _set_g_context(seeded_workspace)
            member = seeded_workspace["membership"]
            member.salary = None
            assert member.formatted_salary is None

    def test_formatted_rates(self, app, db_session, seeded_workspace):
        """Test formatted_labor_cost_rate and formatted_bill_rate."""
        from system.db.database import db

        with app.app_context():
            _set_g_context(seeded_workspace)
            member = seeded_workspace["membership"]
            member.labor_cost_rate = Decimal("50.00")
            member.bill_rate = Decimal("100.00")
            db.session.commit()

            assert member.formatted_labor_cost_rate == "$50.00/hr"
            assert member.formatted_bill_rate == "$100.00/hr"

    def test_is_contactable(self, app, db_session, seeded_workspace):
        """Test is_contactable property."""
        from modules.base.core.models.workspace_user import EmployeeStatus
        from system.db.database import db

        with app.app_context():
            _set_g_context(seeded_workspace)
            member = seeded_workspace["membership"]
            member.status = EmployeeStatus.ACTIVE
            db.session.commit()
            assert member.is_contactable is True

            member.status = EmployeeStatus.TERMINATED
            db.session.commit()
            assert member.is_contactable is False

    def test_terminate_and_rehire(self, app, db_session, seeded_workspace):
        """Test terminate and rehire methods."""
        from modules.base.core.models.workspace_user import (
            EmployeeStatus, TerminationReason, WorkspaceUser,
        )
        from modules.base.core.models.user import User
        from modules.base.core.models.organization_user import OrganizationUser
        from system.db.database import db

        with app.app_context():
            _set_g_context(seeded_workspace)
            user = User.create(
                email="terminate-test@test.com", password="pass123",
                first_name="Term", last_name="Test",
            )
            ou = OrganizationUser.create(
                organization_id=seeded_workspace["organization"].id,
                user_id=user.id,
            )
            member = WorkspaceUser(
                user_id=user.id,
                workspace_id=seeded_workspace["workspace"].id,
                organization_user_id=ou.id,
                role="member",
            )
            db.session.add(member)
            db.session.commit()

            member.terminate(TerminationReason.RESIGNATION)
            assert member.status == EmployeeStatus.TERMINATED
            assert member.termination_reason == TerminationReason.RESIGNATION
            assert member.termination_date is not None
            assert user.is_active is False

            member.rehire()
            assert member.status == EmployeeStatus.ACTIVE
            assert member.termination_date is None
            assert member.termination_reason is None
            assert user.is_active is True

    def test_get_by_user_id(self, app, db_session, seeded_workspace):
        """Test get_by_user_id."""
        from modules.base.core.models.workspace_user import WorkspaceUser

        with app.app_context():
            _set_g_context(seeded_workspace)
            ws = seeded_workspace
            found = WorkspaceUser.get_by_user_id(ws["user"].id)
            assert found is not None
            assert found.user_id == ws["user"].id

    def test_is_member(self, app, db_session, seeded_workspace):
        """Test is_member class method."""
        from modules.base.core.models.workspace_user import WorkspaceUser

        with app.app_context():
            _set_g_context(seeded_workspace)
            ws = seeded_workspace
            assert WorkspaceUser.is_member(ws["user"].id, ws["workspace"].id) is True
            assert WorkspaceUser.is_member(99999, ws["workspace"].id) is False

    def test_activate(self, app, db_session, seeded_workspace):
        """Test activate method on an INACTIVE member."""
        from modules.base.core.models.workspace_user import (
            EmployeeStatus, WorkspaceUser,
        )
        from modules.base.core.models.user import User
        from modules.base.core.models.organization_user import OrganizationUser
        from system.db.database import db

        with app.app_context():
            _set_g_context(seeded_workspace)
            user = User.create(
                email="activate-test@test.com", password="pass123",
                first_name="Act", last_name="Test",
            )
            ou = OrganizationUser.create(
                organization_id=seeded_workspace["organization"].id,
                user_id=user.id,
            )
            member = WorkspaceUser(
                user_id=user.id,
                workspace_id=seeded_workspace["workspace"].id,
                organization_user_id=ou.id,
                role="member",
                status=EmployeeStatus.INACTIVE,
            )
            db.session.add(member)
            db.session.commit()

            assert member.status == EmployeeStatus.INACTIVE
            member.activate()
            assert member.status == EmployeeStatus.ACTIVE

    def test_door_is_open(self, app, db_session, seeded_workspace):
        """Test door_is_open and door_minutes_remaining."""
        from system.db.database import db

        with app.app_context():
            _set_g_context(seeded_workspace)
            member = seeded_workspace["membership"]

            # Not open
            member.open_door_until = None
            assert member.door_is_open is False
            assert member.door_minutes_remaining == 0

            # Open for 30 minutes from now
            member.open_door_until = datetime.utcnow() + timedelta(minutes=30)
            db.session.commit()
            assert member.door_is_open is True
            assert member.door_minutes_remaining > 0

    def test_get_member_counts(self, app, db_session, seeded_workspace):
        """Test get_member_counts aggregation."""
        from modules.base.core.models.workspace_user import WorkspaceUser

        with app.app_context():
            _set_g_context(seeded_workspace)
            counts = WorkspaceUser.get_member_counts()
            assert isinstance(counts, dict)
            assert seeded_workspace["workspace"].id in counts


# =========================================================================
# 6. WorkspaceSettings
# =========================================================================

@pytest.mark.integration
class TestWorkspaceSettings:
    """Tests for WorkspaceSettings model."""

    def test_get_instance_creates_singleton(self, app, db_session, seeded_workspace):
        """Test get_instance creates settings if not exists."""
        from modules.base.core.models.workspace_settings import WorkspaceSettings

        with app.app_context():
            _set_g_context(seeded_workspace)
            settings = WorkspaceSettings.get_instance()
            assert settings is not None
            assert settings.id is not None

    def test_get_instance_returns_same_row(self, app, db_session, seeded_workspace):
        """Test get_instance returns the same singleton."""
        from modules.base.core.models.workspace_settings import WorkspaceSettings

        with app.app_context():
            _set_g_context(seeded_workspace)
            s1 = WorkspaceSettings.get_instance()
            # Clear cache to force re-query
            g._workspace_settings_cache = {}
            s2 = WorkspaceSettings.get_instance()
            assert s1.id == s2.id

    def test_update_settings(self, app, db_session, seeded_workspace):
        """Test updating settings fields."""
        from modules.base.core.models.workspace_settings import WorkspaceSettings

        with app.app_context():
            _set_g_context(seeded_workspace)
            settings = WorkspaceSettings.get_instance()
            settings.update(
                company_name="Updated Corp",
                timezone="America/New_York",
                currency="EUR",
            )
            assert settings.company_name == "Updated Corp"
            assert settings.timezone == "America/New_York"
            assert settings.currency == "EUR"

    def test_complete_setup(self, app, db_session, seeded_workspace):
        """Test complete_setup method."""
        from modules.base.core.models.workspace_settings import WorkspaceSettings

        with app.app_context():
            _set_g_context(seeded_workspace)
            settings = WorkspaceSettings.get_instance()
            settings.complete_setup(timezone="Europe/London")
            assert settings.setup_completed is True
            assert settings.timezone == "Europe/London"

    def test_sidebar_config(self, app, db_session, seeded_workspace):
        """Test sidebar config get/set."""
        from modules.base.core.models.workspace_settings import WorkspaceSettings

        with app.app_context():
            _set_g_context(seeded_workspace)
            settings = WorkspaceSettings.get_instance()

            # Initially None
            assert settings.get_sidebar_config() is None

            # Set config
            config = {"pinned_modules": ["sales", "service"]}
            settings.set_sidebar_config(config)
            result = settings.get_sidebar_config()
            assert result["pinned_modules"] == ["sales", "service"]

    def test_sync_labels(self, app, db_session, seeded_workspace):
        """Test sync label customization."""
        from modules.base.core.models.workspace_settings import WorkspaceSettings

        with app.app_context():
            _set_g_context(seeded_workspace)
            settings = WorkspaceSettings.get_instance()

            # Default labels
            assert settings.get_area_label() == "Area"
            assert settings.get_weekly_plan_label() == "Weekly Plan"

            # Custom labels
            settings.update_sync_labels(area_label="Zone", weekly_plan_label="Sprint")
            assert settings.get_area_label() == "Zone"
            assert settings.get_weekly_plan_label() == "Sprint"

    def test_default_values(self, app, db_session, seeded_workspace):
        """Test default setting values."""
        from modules.base.core.models.workspace_settings import WorkspaceSettings

        with app.app_context():
            _set_g_context(seeded_workspace)
            settings = WorkspaceSettings.get_instance()
            assert settings.default_language == "en"
            assert settings.date_format == "MM/DD/YYYY"
            assert settings.time_format == "12-hour"
            assert settings.currency == "USD"
            assert settings.stale_days == 3


# =========================================================================
# 7. AuthSettings
# =========================================================================

@pytest.mark.integration
class TestAuthSettings:
    """Tests for AuthSettings model."""

    def test_get_instance_creates_singleton(self, app, db_session, seeded_workspace):
        """Test get_instance creates auth settings if not exists."""
        from modules.base.core.models.auth_settings import AuthSettings

        with app.app_context():
            _set_g_context(seeded_workspace)
            auth = AuthSettings.get_instance()
            assert auth is not None
            assert auth.id is not None

    def test_update_auth_settings(self, app, db_session, seeded_workspace):
        """Test updating auth settings."""
        from modules.base.core.models.auth_settings import AuthSettings

        with app.app_context():
            _set_g_context(seeded_workspace)
            auth = AuthSettings.get_instance()
            auth.update(magic_link_enabled=False, sms_enabled=True)
            assert auth.magic_link_enabled is False
            assert auth.sms_enabled is True

    def test_is_provider_enabled(self, app, db_session, seeded_workspace):
        """Test is_provider_enabled for each OAuth provider."""
        from modules.base.core.models.auth_settings import AuthSettings

        with app.app_context():
            _set_g_context(seeded_workspace)
            auth = AuthSettings.get_instance()

            # All providers disabled by default
            assert auth.is_provider_enabled("google") is False
            assert auth.is_provider_enabled("microsoft") is False
            assert auth.is_provider_enabled("github") is False
            assert auth.is_provider_enabled("linkedin") is False

            auth.update(google_enabled=True)
            assert auth.is_provider_enabled("google") is True

    def test_get_enabled_providers(self, app, db_session, seeded_workspace):
        """Test get_enabled_providers returns list of enabled providers."""
        from modules.base.core.models.auth_settings import AuthSettings

        with app.app_context():
            _set_g_context(seeded_workspace)
            auth = AuthSettings.get_instance()
            auth.update(google_enabled=True, github_enabled=True)

            enabled = auth.get_enabled_providers()
            assert "google" in enabled
            assert "github" in enabled
            assert "microsoft" not in enabled

    def test_has_any_oauth_enabled(self, app, db_session, seeded_workspace):
        """Test has_any_oauth_enabled flag."""
        from modules.base.core.models.auth_settings import AuthSettings

        with app.app_context():
            _set_g_context(seeded_workspace)
            auth = AuthSettings.get_instance()
            auth.update(
                google_enabled=False, microsoft_enabled=False,
                github_enabled=False, linkedin_enabled=False,
            )
            assert auth.has_any_oauth_enabled() is False

            auth.update(google_enabled=True)
            assert auth.has_any_oauth_enabled() is True

    def test_is_any_auth_enabled(self, app, db_session, seeded_workspace):
        """Test is_any_auth_enabled flag."""
        from modules.base.core.models.auth_settings import AuthSettings

        with app.app_context():
            _set_g_context(seeded_workspace)
            auth = AuthSettings.get_instance()
            # local_auth_enabled is True from seeded workspace bootstrap
            assert auth.is_any_auth_enabled() is True

    def test_get_and_set_provider_credentials(self, app, db_session, seeded_workspace):
        """Test setting and getting provider credentials."""
        from modules.base.core.models.auth_settings import AuthSettings

        with app.app_context():
            _set_g_context(seeded_workspace)
            auth = AuthSettings.get_instance()
            auth.set_provider_credentials(
                "google", "client-id-123", "encrypted-secret-456",
            )
            client_id, client_secret = auth.get_provider_credentials("google")
            assert client_id == "client-id-123"
            assert client_secret == "encrypted-secret-456"


# =========================================================================
# 8. Contact
# =========================================================================

@pytest.mark.integration
class TestContact:
    """Tests for Contact model."""

    def test_create_person_contact(self, app, db_session, seeded_workspace):
        """Test creating a person contact."""
        from modules.base.core.models.contact import Contact

        with app.app_context():
            _set_g_context(seeded_workspace)
            # Mock current_user for audit mixin
            with patch("modules.base.core.models.contact.current_user") as mock_user:
                mock_user.is_authenticated = False
                contact = Contact.create(
                    first_name="Jane",
                    last_name="Doe",
                    email="jane.doe@example.com",
                    phone="555-0001",
                )
            assert contact.id is not None
            assert contact.display_name == "Jane Doe"
            assert contact.portal_access_token is not None

    def test_create_company_contact(self, app, db_session, seeded_workspace):
        """Test creating a company contact."""
        from modules.base.core.models.contact import Contact

        with app.app_context():
            _set_g_context(seeded_workspace)
            with patch("modules.base.core.models.contact.current_user") as mock_user:
                mock_user.is_authenticated = False
                contact = Contact.create(
                    is_company=True,
                    company_name="Acme Inc",
                    email="info@acme.com",
                )
            assert contact.display_name == "Acme Inc"

    def test_create_company_without_name_raises(self, app, db_session, seeded_workspace):
        """Test that company contact without company_name raises ValidationError."""
        from modules.base.core.models.contact import Contact
        from system.exceptions import ValidationError

        with app.app_context():
            _set_g_context(seeded_workspace)
            with patch("modules.base.core.models.contact.current_user") as mock_user:
                mock_user.is_authenticated = False
                with pytest.raises(ValidationError):
                    Contact.create(is_company=True, company_name="")

    def test_create_person_without_name_raises(self, app, db_session, seeded_workspace):
        """Test that person contact without names raises ValidationError."""
        from modules.base.core.models.contact import Contact
        from system.exceptions import ValidationError

        with app.app_context():
            _set_g_context(seeded_workspace)
            with patch("modules.base.core.models.contact.current_user") as mock_user:
                mock_user.is_authenticated = False
                with pytest.raises(ValidationError):
                    Contact.create(first_name="", last_name="")

    def test_create_invalid_email_raises(self, app, db_session, seeded_workspace):
        """Test that invalid email raises ValidationError."""
        from modules.base.core.models.contact import Contact
        from system.exceptions import ValidationError

        with app.app_context():
            _set_g_context(seeded_workspace)
            with patch("modules.base.core.models.contact.current_user") as mock_user:
                mock_user.is_authenticated = False
                with pytest.raises(ValidationError):
                    Contact.create(
                        first_name="Bad", last_name="Email",
                        email="not-an-email",
                    )

    def test_upgrade_to_customer(self, app, db_session, seeded_workspace):
        """Test upgrading a prospect to customer."""
        from modules.base.core.models.contact import Contact, ContactType

        with app.app_context():
            _set_g_context(seeded_workspace)
            with patch("modules.base.core.models.contact.current_user") as mock_user:
                mock_user.is_authenticated = False
                contact = Contact.create(
                    first_name="Prospect", last_name="Person",
                )
            assert contact.contact_type == ContactType.PROSPECT

            contact.upgrade_to_customer()
            assert contact.contact_type == ContactType.CUSTOMER
            assert contact.converted_to_customer_at is not None

    def test_get_by_email(self, app, db_session, seeded_workspace):
        """Test get_by_email lookup."""
        from modules.base.core.models.contact import Contact

        with app.app_context():
            _set_g_context(seeded_workspace)
            with patch("modules.base.core.models.contact.current_user") as mock_user:
                mock_user.is_authenticated = False
                Contact.create(
                    first_name="Find", last_name="Me",
                    email="findme@example.com",
                )
            found = Contact.get_by_email("findme@example.com")
            assert found is not None
            assert found.first_name == "Find"

    def test_full_address_property(self, app, db_session, seeded_workspace):
        """Test full_address property."""
        from modules.base.core.models.contact import Contact

        with app.app_context():
            _set_g_context(seeded_workspace)
            with patch("modules.base.core.models.contact.current_user") as mock_user:
                mock_user.is_authenticated = False
                contact = Contact.create(
                    first_name="Addr", last_name="Test",
                    billing_address="123 Main St",
                    city="Austin",
                    state="TX",
                    zip_code="78701",
                )
            assert "123 Main St" in contact.full_address
            assert "Austin" in contact.full_address

    def test_soft_delete(self, app, db_session, seeded_workspace):
        """Test soft-deleting a contact."""
        from modules.base.core.models.contact import Contact

        with app.app_context():
            _set_g_context(seeded_workspace)
            with patch("modules.base.core.models.contact.current_user") as mock_user:
                mock_user.is_authenticated = False
                contact = Contact.create(
                    first_name="Delete", last_name="Me",
                )
            contact.delete()
            assert contact.is_deleted is True

    def test_get_all_by_type(self, app, db_session, seeded_workspace):
        """Test get_all with type filter."""
        from modules.base.core.models.contact import Contact, ContactType

        with app.app_context():
            _set_g_context(seeded_workspace)
            with patch("modules.base.core.models.contact.current_user") as mock_user:
                mock_user.is_authenticated = False
                Contact.create(
                    first_name="Vendor", last_name="One",
                    contact_type=ContactType.VENDOR,
                )
            vendors = Contact.get_all(contact_type=ContactType.VENDOR)
            assert len(vendors) >= 1

    def test_portal_token_operations(self, app, db_session, seeded_workspace):
        """Test portal token ensure and regenerate."""
        from modules.base.core.models.contact import Contact

        with app.app_context():
            _set_g_context(seeded_workspace)
            with patch("modules.base.core.models.contact.current_user") as mock_user:
                mock_user.is_authenticated = False
                contact = Contact.create(
                    first_name="Portal", last_name="Token",
                )
            original_token = contact.portal_access_token
            assert original_token is not None

            # Ensure returns existing
            token = contact.ensure_portal_token()
            assert token == original_token

            # Regenerate creates new token
            new_token = contact.regenerate_portal_token()
            assert new_token != original_token

    def test_get_stats(self, app, db_session, seeded_workspace):
        """Test get_stats returns expected keys."""
        from modules.base.core.models.contact import Contact

        with app.app_context():
            _set_g_context(seeded_workspace)
            stats = Contact.get_stats()
            assert "total" in stats
            assert "prospects" in stats
            assert "customers" in stats
            assert "vendors" in stats


# =========================================================================
# 9. SystemNotification
# =========================================================================

@pytest.mark.integration
class TestSystemNotification:
    """Tests for SystemNotification model."""

    def test_create_notification(self, app, db_session, seeded_workspace):
        """Test creating a notification."""
        from modules.base.core.models.notification import SystemNotification

        with app.app_context():
            _set_g_context(seeded_workspace)
            notif = SystemNotification.create(
                title="Test Alert",
                message="Something happened",
                type="info",
            )
            assert notif.id is not None
            assert notif.title == "Test Alert"
            assert notif.is_read is False
            assert notif.is_dismissed is False

    def test_create_sets_default_icon_and_color(self, app, db_session, seeded_workspace):
        """Test that defaults for icon and color are set by type."""
        from modules.base.core.models.notification import SystemNotification

        with app.app_context():
            _set_g_context(seeded_workspace)
            error = SystemNotification.create(title="Error!", type="error")
            assert error.icon == "fa-exclamation-triangle"
            assert error.color == "#dc3545"

            success = SystemNotification.create(title="OK!", type="success")
            assert success.icon == "fa-check-circle"
            assert success.color == "#28a745"

    def test_mark_read(self, app, db_session, seeded_workspace):
        """Test marking a notification as read."""
        from modules.base.core.models.notification import SystemNotification

        with app.app_context():
            _set_g_context(seeded_workspace)
            notif = SystemNotification.create(title="Read Me")
            assert notif.is_read is False
            notif.mark_read()
            assert notif.is_read is True

    def test_dismiss(self, app, db_session, seeded_workspace):
        """Test dismissing a notification."""
        from modules.base.core.models.notification import SystemNotification

        with app.app_context():
            _set_g_context(seeded_workspace)
            notif = SystemNotification.create(title="Dismiss Me")
            notif.dismiss()
            assert notif.is_dismissed is True

    def test_time_ago(self, app, db_session, seeded_workspace):
        """Test time_ago returns human-readable string."""
        from modules.base.core.models.notification import SystemNotification

        with app.app_context():
            _set_g_context(seeded_workspace)
            notif = SystemNotification.create(title="Time Test")
            result = notif.time_ago()
            assert result == "just now"

    def test_compute_time_ago_static(self, app, db_session):
        """Test _compute_time_ago for various time deltas."""
        from modules.base.core.models.notification import SystemNotification

        now = datetime.utcnow()
        assert SystemNotification._compute_time_ago(now, now) == "just now"
        assert SystemNotification._compute_time_ago(
            now, now - timedelta(minutes=5),
        ) == "5 minutes ago"
        assert SystemNotification._compute_time_ago(
            now, now - timedelta(minutes=1),
        ) == "1 minute ago"
        assert SystemNotification._compute_time_ago(
            now, now - timedelta(hours=2),
        ) == "2 hours ago"
        assert SystemNotification._compute_time_ago(
            now, now - timedelta(hours=1),
        ) == "1 hour ago"
        assert SystemNotification._compute_time_ago(
            now, now - timedelta(days=3),
        ) == "3 days ago"
        assert SystemNotification._compute_time_ago(
            now, now - timedelta(days=1),
        ) == "1 day ago"

    def test_get_for_user_targeted(self, app, db_session, seeded_workspace):
        """Test get_for_user returns user-targeted notifications."""
        from modules.base.core.models.notification import SystemNotification

        with app.app_context():
            _set_g_context(seeded_workspace)
            user = seeded_workspace["user"]
            SystemNotification.create(
                title="For You",
                user_id=user.id,
                target_role="all",
            )
            notifs = SystemNotification.get_for_user(user, limit=50)
            assert any(n.title == "For You" for n in notifs)

    def test_dismiss_by_url(self, app, db_session, seeded_workspace):
        """Test dismiss_by_url dismisses matching notifications."""
        from modules.base.core.models.notification import SystemNotification

        with app.app_context():
            _set_g_context(seeded_workspace)
            user = seeded_workspace["user"]
            SystemNotification.create(
                title="URL Dismiss",
                user_id=user.id,
                action_url="/settings/test?foo=bar",
            )
            SystemNotification.dismiss_by_url("/settings/test", user.id)
            # Re-fetch to verify
            remaining = SystemNotification.scoped().filter(
                SystemNotification.user_id == user.id,
                SystemNotification.title == "URL Dismiss",
                SystemNotification.is_dismissed == False,
            ).count()
            assert remaining == 0

    def test_category_constants(self, app):
        """Test NotificationCategory constants exist."""
        from modules.base.core.models.notification import NotificationCategory

        assert NotificationCategory.TASK_ASSIGNED == "task_assigned"
        assert NotificationCategory.MENTION == "mention"
        assert NotificationCategory.SYSTEM == "system"


# =========================================================================
# 10. OAuthConnection
# =========================================================================

@pytest.mark.integration
class TestOAuthConnection:
    """Tests for OAuthConnection model."""

    def test_create_or_update_new(self, app, db_session, seeded_workspace):
        """Test creating a new OAuth connection."""
        from modules.base.core.models.oauth_connection import OAuthConnection

        with app.app_context():
            _set_g_context(seeded_workspace)
            conn = OAuthConnection.create_or_update(
                user_id=seeded_workspace["user"].id,
                provider="google",
                provider_user_id="google-123",
                email="user@gmail.com",
                access_token="access-tok",
                refresh_token="refresh-tok",
            )
            assert conn.id is not None
            assert conn.provider == "google"
            assert conn.provider_user_id == "google-123"
            assert conn.access_token == "access-tok"

    def test_create_or_update_existing(self, app, db_session, seeded_workspace):
        """Test updating an existing OAuth connection."""
        from modules.base.core.models.oauth_connection import OAuthConnection

        with app.app_context():
            _set_g_context(seeded_workspace)
            user_id = seeded_workspace["user"].id
            conn1 = OAuthConnection.create_or_update(
                user_id=user_id, provider="github",
                provider_user_id="gh-1", access_token="old-token",
            )
            conn2 = OAuthConnection.create_or_update(
                user_id=user_id, provider="github",
                provider_user_id="gh-1", access_token="new-token",
            )
            assert conn2.id == conn1.id
            assert conn2.access_token == "new-token"

    def test_get_by_provider_user(self, app, db_session, seeded_workspace):
        """Test get_by_provider_user lookup."""
        from modules.base.core.models.oauth_connection import OAuthConnection

        with app.app_context():
            _set_g_context(seeded_workspace)
            OAuthConnection.create_or_update(
                user_id=seeded_workspace["user"].id,
                provider="microsoft",
                provider_user_id="ms-456",
            )
            found = OAuthConnection.get_by_provider_user("microsoft", "ms-456")
            assert found is not None

    def test_get_by_user_and_provider(self, app, db_session, seeded_workspace):
        """Test get_by_user_and_provider lookup."""
        from modules.base.core.models.oauth_connection import OAuthConnection

        with app.app_context():
            _set_g_context(seeded_workspace)
            user_id = seeded_workspace["user"].id
            OAuthConnection.create_or_update(
                user_id=user_id, provider="linkedin",
                provider_user_id="li-789",
            )
            found = OAuthConnection.get_by_user_and_provider(user_id, "linkedin")
            assert found is not None

    def test_get_user_connections(self, app, db_session, seeded_workspace):
        """Test get_user_connections returns all connections for a user."""
        from modules.base.core.models.oauth_connection import OAuthConnection

        with app.app_context():
            _set_g_context(seeded_workspace)
            user_id = seeded_workspace["user"].id
            OAuthConnection.create_or_update(
                user_id=user_id, provider="google",
                provider_user_id="g-conn-1",
            )
            conns = OAuthConnection.get_user_connections(user_id)
            assert len(conns) >= 1

    def test_update_tokens(self, app, db_session, seeded_workspace):
        """Test update_tokens method."""
        from modules.base.core.models.oauth_connection import OAuthConnection

        with app.app_context():
            _set_g_context(seeded_workspace)
            conn = OAuthConnection.create_or_update(
                user_id=seeded_workspace["user"].id,
                provider="google",
                provider_user_id="g-tok-1",
                access_token="old",
            )
            conn.update_tokens(access_token="new-access", refresh_token="new-refresh")
            assert conn.access_token == "new-access"
            assert conn.refresh_token == "new-refresh"

    def test_is_token_expired(self, app, db_session, seeded_workspace):
        """Test is_token_expired method."""
        from modules.base.core.models.oauth_connection import OAuthConnection

        with app.app_context():
            _set_g_context(seeded_workspace)
            conn = OAuthConnection.create_or_update(
                user_id=seeded_workspace["user"].id,
                provider="google",
                provider_user_id="g-exp-1",
            )
            # No expiry — not expired
            assert conn.is_token_expired() is False

            # Set expiry in the past
            conn.token_expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
            assert conn.is_token_expired() is True

            # Set expiry far in the future
            conn.token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
            assert conn.is_token_expired() is False

    def test_delete_connection(self, app, db_session, seeded_workspace):
        """Test deleting an OAuth connection."""
        from modules.base.core.models.oauth_connection import OAuthConnection

        with app.app_context():
            _set_g_context(seeded_workspace)
            conn = OAuthConnection.create_or_update(
                user_id=seeded_workspace["user"].id,
                provider="github",
                provider_user_id="gh-del-1",
            )
            conn_id = conn.id
            conn.delete()
            assert OAuthConnection.query.get(conn_id) is None

    def test_count_by_provider(self, app, db_session, seeded_workspace):
        """Test count_by_provider."""
        from modules.base.core.models.oauth_connection import OAuthConnection

        with app.app_context():
            _set_g_context(seeded_workspace)
            OAuthConnection.create_or_update(
                user_id=seeded_workspace["user"].id,
                provider="google",
                provider_user_id="g-count-1",
            )
            count = OAuthConnection.count_by_provider("google")
            assert count >= 1


# =========================================================================
# 11. PendingSignup
# =========================================================================

@pytest.mark.integration
class TestPendingSignup:
    """Tests for PendingSignup model."""

    def test_create_or_update_new(self, app, db_session):
        """Test creating a new pending signup."""
        from modules.base.core.models.pending_signup import PendingSignup

        with app.app_context():
            ps = PendingSignup.create_or_update(
                email="pending@example.com",
                password="SecurePass!",
                first_name="Pending",
                last_name="User",
            )
            assert ps.id is not None
            assert ps.email == "pending@example.com"
            assert ps.token is not None
            assert ps.password_hash is not None
            assert ps.password_hash != "SecurePass!"

    def test_create_or_update_refreshes_existing(self, app, db_session):
        """Test that create_or_update refreshes token for existing email."""
        from modules.base.core.models.pending_signup import PendingSignup

        with app.app_context():
            ps1 = PendingSignup.create_or_update(
                email="refresh@example.com", password="pass1",
                first_name="First", last_name="Try",
            )
            old_token = ps1.token

            ps2 = PendingSignup.create_or_update(
                email="refresh@example.com", password="pass2",
                first_name="Second", last_name="Try",
            )
            assert ps2.id == ps1.id
            assert ps2.token != old_token
            assert ps2.first_name == "Second"

    def test_get_by_token_valid(self, app, db_session):
        """Test get_by_token with valid token."""
        from modules.base.core.models.pending_signup import PendingSignup

        with app.app_context():
            ps = PendingSignup.create_or_update(
                email="token-valid@example.com", password="pass",
            )
            found = PendingSignup.get_by_token(ps.token)
            assert found is not None
            assert found.id == ps.id

    def test_get_by_token_expired(self, app, db_session):
        """Test get_by_token returns None for expired token."""
        from modules.base.core.models.pending_signup import PendingSignup
        from system.db.database import db

        with app.app_context():
            ps = PendingSignup.create_or_update(
                email="token-expired@example.com", password="pass",
            )
            ps.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
            db.session.commit()

            found = PendingSignup.get_by_token(ps.token)
            assert found is None

    def test_get_by_token_invalid(self, app, db_session):
        """Test get_by_token returns None for invalid token."""
        from modules.base.core.models.pending_signup import PendingSignup

        with app.app_context():
            found = PendingSignup.get_by_token("not-a-real-token")
            assert found is None

    def test_cleanup_expired(self, app, db_session):
        """Test cleanup_expired removes old rows."""
        from modules.base.core.models.pending_signup import PendingSignup
        from system.db.database import db

        with app.app_context():
            ps = PendingSignup.create_or_update(
                email="cleanup@example.com", password="pass",
            )
            ps.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
            db.session.commit()

            PendingSignup.cleanup_expired()
            found = PendingSignup.query.filter_by(email="cleanup@example.com").first()
            assert found is None


# =========================================================================
# 12. PushSubscription
# =========================================================================

@pytest.mark.integration
class TestPushSubscription:
    """Tests for PushSubscription model."""

    def test_create_subscription(self, app, db_session, seeded_workspace):
        """Test creating a push subscription."""
        from modules.base.core.models.push_subscription import PushSubscription

        with app.app_context():
            _set_g_context(seeded_workspace)
            sub = PushSubscription.create(
                user_id=seeded_workspace["user"].id,
                endpoint="https://push.example.com/sub1",
                auth_key="auth-key-123",
                p256dh_key="p256dh-key-456",
            )
            assert sub.id is not None
            assert sub.is_active is True

    def test_create_updates_existing_endpoint(self, app, db_session, seeded_workspace):
        """Test that creating with existing endpoint updates the record."""
        from modules.base.core.models.push_subscription import PushSubscription

        with app.app_context():
            _set_g_context(seeded_workspace)
            user_id = seeded_workspace["user"].id
            sub1 = PushSubscription.create(
                user_id=user_id,
                endpoint="https://push.example.com/dup-endpoint",
                auth_key="old-auth",
                p256dh_key="old-p256",
            )
            sub2 = PushSubscription.create(
                user_id=user_id,
                endpoint="https://push.example.com/dup-endpoint",
                auth_key="new-auth",
                p256dh_key="new-p256",
            )
            assert sub2.id == sub1.id
            assert sub2.auth_key == "new-auth"

    def test_get_active_for_user(self, app, db_session, seeded_workspace):
        """Test get_active_for_user returns active subscriptions."""
        from modules.base.core.models.push_subscription import PushSubscription

        with app.app_context():
            _set_g_context(seeded_workspace)
            user_id = seeded_workspace["user"].id
            PushSubscription.create(
                user_id=user_id,
                endpoint="https://push.example.com/active1",
                auth_key="a1", p256dh_key="p1",
            )
            active = PushSubscription.get_active_for_user(user_id)
            assert len(active) >= 1

    def test_deactivate_by_endpoint(self, app, db_session, seeded_workspace):
        """Test deactivating by endpoint."""
        from modules.base.core.models.push_subscription import PushSubscription

        with app.app_context():
            _set_g_context(seeded_workspace)
            PushSubscription.create(
                user_id=seeded_workspace["user"].id,
                endpoint="https://push.example.com/deactivate",
                auth_key="a", p256dh_key="p",
            )
            result = PushSubscription.deactivate_by_endpoint(
                "https://push.example.com/deactivate",
            )
            assert result is True

            # Verify deactivated
            sub = PushSubscription.query.filter_by(
                endpoint="https://push.example.com/deactivate",
            ).first()
            assert sub.is_active is False

    def test_deactivate_by_endpoint_nonexistent(self, app, db_session, seeded_workspace):
        """Test deactivating nonexistent endpoint returns False."""
        from modules.base.core.models.push_subscription import PushSubscription

        with app.app_context():
            result = PushSubscription.deactivate_by_endpoint("https://no.such.endpoint")
            assert result is False

    def test_delete_by_endpoint(self, app, db_session, seeded_workspace):
        """Test deleting by endpoint."""
        from modules.base.core.models.push_subscription import PushSubscription

        with app.app_context():
            _set_g_context(seeded_workspace)
            PushSubscription.create(
                user_id=seeded_workspace["user"].id,
                endpoint="https://push.example.com/delete-me",
                auth_key="a", p256dh_key="p",
            )
            result = PushSubscription.delete_by_endpoint(
                "https://push.example.com/delete-me",
            )
            assert result is True
            assert PushSubscription.query.filter_by(
                endpoint="https://push.example.com/delete-me",
            ).first() is None

    def test_deactivate_instance(self, app, db_session, seeded_workspace):
        """Test instance deactivate method."""
        from modules.base.core.models.push_subscription import PushSubscription

        with app.app_context():
            _set_g_context(seeded_workspace)
            sub = PushSubscription.create(
                user_id=seeded_workspace["user"].id,
                endpoint="https://push.example.com/deact-inst",
                auth_key="a", p256dh_key="p",
            )
            sub.deactivate()
            assert sub.is_active is False

    def test_to_subscription_info(self, app, db_session, seeded_workspace):
        """Test to_subscription_info returns correct dict structure."""
        from modules.base.core.models.push_subscription import PushSubscription

        with app.app_context():
            _set_g_context(seeded_workspace)
            sub = PushSubscription.create(
                user_id=seeded_workspace["user"].id,
                endpoint="https://push.example.com/info",
                auth_key="auth-x", p256dh_key="p256-y",
            )
            info = sub.to_subscription_info()
            assert info["endpoint"] == "https://push.example.com/info"
            assert info["keys"]["auth"] == "auth-x"
            assert info["keys"]["p256dh"] == "p256-y"

    def test_deactivate_by_id(self, app, db_session, seeded_workspace):
        """Test deactivate_by_id class method."""
        from modules.base.core.models.push_subscription import PushSubscription

        with app.app_context():
            _set_g_context(seeded_workspace)
            sub = PushSubscription.create(
                user_id=seeded_workspace["user"].id,
                endpoint="https://push.example.com/by-id",
                auth_key="a", p256dh_key="p",
            )
            result = PushSubscription.deactivate_by_id(sub.id)
            assert result is True

            refreshed = PushSubscription.query.get(sub.id)
            assert refreshed.is_active is False


# =========================================================================
# 13. ServiceLocation
# =========================================================================

@pytest.mark.integration
class TestServiceLocation:
    """Tests for ServiceLocation model."""

    def _create_contact(self, app, seeded_workspace):
        """Helper to create a contact for service location tests."""
        from modules.base.core.models.contact import Contact

        with patch("modules.base.core.models.contact.current_user") as mock_user:
            mock_user.is_authenticated = False
            return Contact.create(
                first_name="Loc", last_name="Contact",
                email="loc@example.com",
            )

    def test_create_service_location(self, app, db_session, seeded_workspace):
        """Test creating a service location."""
        from modules.base.core.models.service_location import ServiceLocation

        with app.app_context():
            _set_g_context(seeded_workspace)
            contact = self._create_contact(app, seeded_workspace)
            loc = ServiceLocation.create(
                contact_id=contact.id,
                name="Main Office",
                address="100 Oak Street",
                city="Austin",
                state="TX",
                zip_code="78701",
            )
            assert loc.id is not None
            assert loc.name == "Main Office"
            assert loc.address == "100 Oak Street"

    def test_create_without_name_raises(self, app, db_session, seeded_workspace):
        """Test that creating without name raises ValidationError."""
        from modules.base.core.models.service_location import ServiceLocation
        from system.exceptions import ValidationError

        with app.app_context():
            _set_g_context(seeded_workspace)
            contact = self._create_contact(app, seeded_workspace)
            with pytest.raises(ValidationError):
                ServiceLocation.create(contact_id=contact.id, name="")

    def test_full_address_property(self, app, db_session, seeded_workspace):
        """Test full_address property."""
        from modules.base.core.models.service_location import ServiceLocation

        with app.app_context():
            _set_g_context(seeded_workspace)
            contact = self._create_contact(app, seeded_workspace)
            loc = ServiceLocation.create(
                contact_id=contact.id,
                name="Test",
                address="456 Elm",
                city="Dallas",
                state="TX",
                zip_code="75001",
            )
            assert "456 Elm" in loc.full_address
            assert "Dallas" in loc.full_address

    def test_display_name_with_address(self, app, db_session, seeded_workspace):
        """Test display_name includes address when present."""
        from modules.base.core.models.service_location import ServiceLocation

        with app.app_context():
            _set_g_context(seeded_workspace)
            contact = self._create_contact(app, seeded_workspace)
            loc = ServiceLocation.create(
                contact_id=contact.id,
                name="Branch",
                address="789 Pine",
            )
            assert "Branch - 789 Pine" == loc.display_name

    def test_display_name_without_address(self, app, db_session, seeded_workspace):
        """Test display_name falls back to name only."""
        from modules.base.core.models.service_location import ServiceLocation

        with app.app_context():
            _set_g_context(seeded_workspace)
            contact = self._create_contact(app, seeded_workspace)
            loc = ServiceLocation.create(
                contact_id=contact.id, name="No Address Loc",
            )
            assert loc.display_name == "No Address Loc"

    def test_set_as_default(self, app, db_session, seeded_workspace):
        """Test set_as_default clears other defaults."""
        from modules.base.core.models.service_location import ServiceLocation

        with app.app_context():
            _set_g_context(seeded_workspace)
            contact = self._create_contact(app, seeded_workspace)
            loc1 = ServiceLocation.create(
                contact_id=contact.id, name="First", is_default=True,
            )
            loc2 = ServiceLocation.create(
                contact_id=contact.id, name="Second", is_default=False,
            )
            loc2.set_as_default()

            # Refresh loc1 from DB
            from system.db.database import db
            db.session.refresh(loc1)
            assert loc1.is_default is False
            assert loc2.is_default is True

    def test_get_for_contact(self, app, db_session, seeded_workspace):
        """Test get_for_contact returns ordered locations."""
        from modules.base.core.models.service_location import ServiceLocation

        with app.app_context():
            _set_g_context(seeded_workspace)
            contact = self._create_contact(app, seeded_workspace)
            ServiceLocation.create(contact_id=contact.id, name="A Location")
            ServiceLocation.create(contact_id=contact.id, name="B Location")

            locations = ServiceLocation.get_for_contact(contact.id)
            assert len(locations) >= 2

    def test_update_location(self, app, db_session, seeded_workspace):
        """Test updating a service location."""
        from modules.base.core.models.service_location import ServiceLocation

        with app.app_context():
            _set_g_context(seeded_workspace)
            contact = self._create_contact(app, seeded_workspace)
            loc = ServiceLocation.create(
                contact_id=contact.id, name="Original",
            )
            loc.update(name="Updated", city="Houston")
            assert loc.name == "Updated"
            assert loc.city == "Houston"

    def test_delete_location(self, app, db_session, seeded_workspace):
        """Test deleting a service location."""
        from modules.base.core.models.service_location import ServiceLocation

        with app.app_context():
            _set_g_context(seeded_workspace)
            contact = self._create_contact(app, seeded_workspace)
            loc = ServiceLocation.create(
                contact_id=contact.id, name="Delete Me",
            )
            loc_id = loc.id
            loc.delete()
            assert ServiceLocation.query.get(loc_id) is None


# =========================================================================
# 14. UserSetting
# =========================================================================

@pytest.mark.integration
class TestUserSetting:
    """Tests for UserSetting model."""

    def test_set_and_get(self, app, db_session, seeded_workspace):
        """Test setting and getting a user setting."""
        from modules.base.core.models.user_setting import UserSetting

        with app.app_context():
            _set_g_context(seeded_workspace)
            user_id = seeded_workspace["user"].id

            UserSetting.set(user_id, "theme", "dark")
            value = UserSetting.get(user_id, "theme")
            assert value == "dark"

    def test_get_default(self, app, db_session, seeded_workspace):
        """Test get returns default when key does not exist."""
        from modules.base.core.models.user_setting import UserSetting

        with app.app_context():
            _set_g_context(seeded_workspace)
            user_id = seeded_workspace["user"].id

            value = UserSetting.get(user_id, "nonexistent_key", default="fallback")
            assert value == "fallback"

    def test_set_overwrites(self, app, db_session, seeded_workspace):
        """Test that set overwrites an existing value."""
        from modules.base.core.models.user_setting import UserSetting

        with app.app_context():
            _set_g_context(seeded_workspace)
            user_id = seeded_workspace["user"].id

            UserSetting.set(user_id, "color", "blue")
            UserSetting.set(user_id, "color", "red")
            # Clear cache to force re-query
            g._user_setting_cache = {}
            value = UserSetting.get(user_id, "color")
            assert value == "red"

    def test_get_bulk(self, app, db_session, seeded_workspace):
        """Test get_bulk retrieves settings for multiple users."""
        from modules.base.core.models.user_setting import UserSetting
        from modules.base.core.models.user import User

        with app.app_context():
            _set_g_context(seeded_workspace)

            user1 = seeded_workspace["user"]
            user2 = User.create(
                email="bulk-settings@test.com", password="pass123",
                first_name="Bulk", last_name="User",
            )

            UserSetting.set(user1.id, "lang", "en")
            UserSetting.set(user2.id, "lang", "fr")

            result = UserSetting.get_bulk([user1.id, user2.id], "lang")
            assert result[user1.id] == "en"
            assert result[user2.id] == "fr"

    def test_get_bulk_with_default(self, app, db_session, seeded_workspace):
        """Test get_bulk returns default for users without the setting."""
        from modules.base.core.models.user_setting import UserSetting

        with app.app_context():
            _set_g_context(seeded_workspace)
            result = UserSetting.get_bulk([99999], "missing_key", default="none")
            assert result[99999] == "none"

    def test_get_bulk_empty(self, app, db_session, seeded_workspace):
        """Test get_bulk with empty user list."""
        from modules.base.core.models.user_setting import UserSetting

        with app.app_context():
            _set_g_context(seeded_workspace)
            result = UserSetting.get_bulk([], "key")
            assert result == {}


# =========================================================================
# 15. AuditLog
# =========================================================================

@pytest.mark.integration
class TestAuditLog:
    """Tests for AuditLog model."""

    def test_record_audit_entry(self, app, db_session, seeded_workspace):
        """Test recording an audit log entry."""
        from modules.base.core.models.audit_log import AuditLog

        with app.app_context():
            _set_g_context(seeded_workspace)
            entry = AuditLog.record(
                action="test_action",
                target_type="workspace",
                target_id=str(seeded_workspace["workspace"].id),
                actor_user_id=seeded_workspace["user"].id,
                workspace_id=seeded_workspace["workspace"].id,
                metadata={"key": "value"},
            )
            assert entry.id is not None
            assert entry.action == "test_action"
            assert entry.target_type == "workspace"
            assert entry.metadata_json == {"key": "value"}

    def test_record_sets_organization_id(self, app, db_session, seeded_workspace):
        """Test that record automatically uses g.organization_id."""
        from modules.base.core.models.audit_log import AuditLog

        with app.app_context():
            _set_g_context(seeded_workspace)
            entry = AuditLog.record(
                action="auto_org",
                target_type="test",
                actor_user_id=seeded_workspace["user"].id,
            )
            assert entry.organization_id == seeded_workspace["organization"].id

    def test_record_resolves_actor_org_user(self, app, db_session, seeded_workspace):
        """Test that record resolves the actor's OrganizationUser ID."""
        from modules.base.core.models.audit_log import AuditLog

        with app.app_context():
            _set_g_context(seeded_workspace)
            entry = AuditLog.record(
                action="resolve_actor",
                target_type="test",
                actor_user_id=seeded_workspace["user"].id,
            )
            assert entry.actor_organization_user_id is not None

    def test_list_for_organization(self, app, db_session, seeded_workspace):
        """Test list_for_organization returns entries newest first."""
        from modules.base.core.models.audit_log import AuditLog

        with app.app_context():
            _set_g_context(seeded_workspace)
            AuditLog.record(
                action="list_test_1",
                target_type="test",
                actor_user_id=seeded_workspace["user"].id,
            )
            AuditLog.record(
                action="list_test_2",
                target_type="test",
                actor_user_id=seeded_workspace["user"].id,
            )
            entries = AuditLog.list_for_organization(
                seeded_workspace["organization"].id,
            )
            assert len(entries) >= 2
            # Newest first
            assert entries[0].created_at >= entries[1].created_at

    def test_list_for_organization_with_action_filter(self, app, db_session, seeded_workspace):
        """Test list_for_organization with action filter."""
        from modules.base.core.models.audit_log import AuditLog

        with app.app_context():
            _set_g_context(seeded_workspace)
            AuditLog.record(
                action="specific_action",
                target_type="test",
                actor_user_id=seeded_workspace["user"].id,
            )
            AuditLog.record(
                action="other_action",
                target_type="test",
                actor_user_id=seeded_workspace["user"].id,
            )
            entries = AuditLog.list_for_organization(
                seeded_workspace["organization"].id,
                action="specific_action",
            )
            assert all(e.action == "specific_action" for e in entries)

    def test_record_without_metadata(self, app, db_session, seeded_workspace):
        """Test recording an entry without metadata."""
        from modules.base.core.models.audit_log import AuditLog

        with app.app_context():
            _set_g_context(seeded_workspace)
            entry = AuditLog.record(
                action="no_meta",
                target_type="test",
                actor_user_id=seeded_workspace["user"].id,
            )
            assert entry.metadata_json is None
