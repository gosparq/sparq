# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - Integration Test Configuration
#
# Fixtures specific to integration tests (database, API, services).
# -----------------------------------------------------------------------------

import json
import os
import pytest

# Get testdata directory
_tests_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_fixtures_dir = os.path.join(_tests_dir, "testdata", "fixtures")


def load_fixture(name: str) -> dict | list:
    """Load a JSON fixture file from testdata/fixtures/."""
    path = os.path.join(_fixtures_dir, f"{name}.json")
    with open(path) as f:
        return json.load(f)


@pytest.fixture
def user_data():
    """Sample user data for testing."""
    return {
        "email": "testuser@example.com",
        "password": "SecurePass123!",
        "first_name": "Test",
        "last_name": "User",
    }


@pytest.fixture
def admin_data():
    """Sample admin user data for testing."""
    return {
        "email": "testadmin@example.com",
        "password": "AdminPass123!",
        "first_name": "Test",
        "last_name": "Admin",
    }


@pytest.fixture
def multiple_users(app, db_session):
    """Create multiple test users."""
    from modules.base.core.models.user import User

    users = []
    with app.app_context():
        for i in range(3):
            user = User.create(
                email=f"user{i}@example.com",
                password="testpass123",
                first_name=f"User{i}",
                last_name="Test",
                is_admin=False,
            )
            users.append(user)
    return users


@pytest.fixture
def quote_data():
    """Sample quote data for testing."""
    return {
        "title": "Test Quote",
        "description": "A test quote for integration testing",
        "amount": "1000.00",
        "status": "draft",
    }


@pytest.fixture
def contact_data():
    """Sample contact data for testing."""
    return {
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@example.com",
        "phone": "555-123-4567",
        "company": "Test Company",
    }
