# Testing Patterns

> pytest, fixtures, transaction rollback, and test organization

---

## Table of Contents

- [Philosophy](#philosophy)
- [Test Structure](#test-structure)
- [pytest Configuration](#pytest-configuration)
- [Fixtures](#fixtures)
- [Model Tests](#model-tests)
- [Controller Tests](#controller-tests)
- [Test Utilities](#test-utilities)
- [Coverage](#coverage)
- [CI/CD](#cicd)

---

## Philosophy

### Fast, Isolated Tests

- **Transaction rollback**: Each test runs in a transaction that's rolled back
- **In-memory SQLite**: Fast, no external database needed for unit tests
- **Fixtures**: Reusable test setup via pytest fixtures
- **Isolation**: Tests don't affect each other

### Test Types

| Type | Purpose | Database | Speed |
|------|---------|----------|-------|
| Unit | Model logic, validation | In-memory | Fast |
| Integration | Full request/response | In-memory | Medium |
| E2E | Browser testing | Real DB | Slow |

Focus on **unit** and **integration** tests for this blueprint.

---

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures
├── test_models/
│   ├── __init__.py
│   ├── test_user.py
│   └── test_setting.py
├── test_controllers/
│   ├── __init__.py
│   ├── test_auth.py
│   ├── test_users.py
│   └── test_settings.py
└── test_platform/
    ├── test_i18n.py
    └── test_errors.py
```

---

## pytest Configuration

### pyproject.toml

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
addopts = "-v --tb=short"

# Coverage
[tool.coverage.run]
source = ["app"]
omit = ["app/config.py", "*/migrations/*"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "if __name__ == .__main__.:",
]
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=term-missing

# Run specific file
pytest tests/test_models/test_user.py

# Run specific test
pytest tests/test_models/test_user.py::test_user_create

# Run with verbose output
pytest -v

# Stop on first failure
pytest -x
```

---

## Fixtures

### Core Fixtures

```python
# tests/conftest.py
"""Shared test fixtures."""

import pytest
from app import create_app
from app.extensions import db
from app.models import User, Setting


@pytest.fixture
def app():
    """Create application for testing."""
    app = create_app()
    app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'WTF_CSRF_ENABLED': False,
        'SERVER_NAME': 'localhost',
    })

    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    """Test client for making requests."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """CLI test runner."""
    return app.test_cli_runner()


@pytest.fixture
def db_session(app):
    """Database session with automatic rollback."""
    with app.app_context():
        yield db.session
        db.session.rollback()
```

### User Fixtures

```python
# tests/conftest.py (continued)

@pytest.fixture
def user(app):
    """Create a test user."""
    with app.app_context():
        user = User(
            email='test@example.com',
            name='Test User',
        )
        user.save()
        yield user


@pytest.fixture
def authenticated_client(client, user):
    """Client with logged-in user."""
    with client.session_transaction() as session:
        session['_user_id'] = user.id
    return client


@pytest.fixture
def users(app):
    """Create multiple test users."""
    with app.app_context():
        alice = User.create(email='alice@example.com', name='Alice')
        bob = User.create(email='bob@example.com', name='Bob')
        yield {'alice': alice, 'bob': bob}
```

---

## Model Tests

### Basic Model Test

```python
# tests/test_models/test_user.py
"""User model tests."""

import pytest
from app.models import User
from app.platform.errors import ValidationError


class TestUserModel:
    """Tests for User model."""

    def test_create_user(self, app):
        """Test creating a new user."""
        with app.app_context():
            user = User.create(
                email='new@example.com',
                name='New User'
            )

            assert user.id is not None
            assert user.email == 'new@example.com'
            assert user.name == 'New User'
            assert user.created_at is not None

    def test_email_normalized(self, app):
        """Test email is normalized to lowercase."""
        with app.app_context():
            user = User.create(
                email='  TEST@EXAMPLE.COM  ',
                name='Test'
            )
            assert user.email == 'test@example.com'

    def test_email_required(self, app):
        """Test validation rejects empty email."""
        with app.app_context():
            with pytest.raises(ValidationError) as exc:
                User.create(email='', name='Test')
            assert 'Email is required' in str(exc.value)

    def test_invalid_email_format(self, app):
        """Test validation rejects invalid email."""
        with app.app_context():
            with pytest.raises(ValidationError) as exc:
                User.create(email='not-an-email', name='Test')
            assert 'Invalid email' in str(exc.value)

    def test_duplicate_email(self, app, user):
        """Test duplicate email is rejected."""
        with app.app_context():
            with pytest.raises(ValidationError) as exc:
                User.create(email=user.email, name='Another')
            assert 'already registered' in str(exc.value)

    def test_get_by_email(self, app, user):
        """Test finding user by email."""
        with app.app_context():
            found = User.get_by_email(user.email)
            assert found is not None
            assert found.id == user.id

    def test_get_by_email_not_found(self, app):
        """Test get_by_email returns None for unknown email."""
        with app.app_context():
            found = User.get_by_email('unknown@example.com')
            assert found is None

    def test_update_user(self, app, user):
        """Test updating user profile."""
        with app.app_context():
            user.update(name='Updated Name')

            # Refresh from database
            refreshed = User.get_by_id(user.id)
            assert refreshed.name == 'Updated Name'

    def test_get_initials(self, app):
        """Test initials generation."""
        with app.app_context():
            user = User.create(email='test@example.com', name='Alice')
            assert user.get_initials() == 'A'
```

### Setting Model Test

```python
# tests/test_models/test_setting.py
"""Setting model tests."""

import pytest
from app.models import Setting


class TestSettingModel:
    """Tests for Setting model."""

    def test_set_creates_new(self, app, user):
        """Test set() creates new setting."""
        with app.app_context():
            setting = Setting.set(user.id, 'theme', 'dark')

            assert setting.id is not None
            assert setting.key == 'theme'
            assert setting.value == 'dark'

    def test_set_updates_existing(self, app, user):
        """Test set() updates existing setting."""
        with app.app_context():
            Setting.set(user.id, 'theme', 'light')
            Setting.set(user.id, 'theme', 'dark')

            # Should only be one setting
            settings = Setting.query.filter_by(user_id=user.id, key='theme').all()
            assert len(settings) == 1
            assert settings[0].value == 'dark'

    def test_get_value_with_default(self, app, user):
        """Test get_value returns default for missing key."""
        with app.app_context():
            value = Setting.get_value(user.id, 'missing', default='default')
            assert value == 'default'

    def test_get_map(self, app, user):
        """Test get_map returns all settings as dict."""
        with app.app_context():
            Setting.set(user.id, 'theme', 'dark')
            Setting.set(user.id, 'language', 'en')

            settings = Setting.get_map(user.id)
            assert settings == {'theme': 'dark', 'language': 'en'}
```

---

## Controller Tests

### Auth Controller Tests

```python
# tests/test_controllers/test_auth.py
"""Auth controller tests."""

import pytest


class TestAuthController:
    """Tests for auth endpoints."""

    def test_login_page_renders(self, client):
        """Test login page loads."""
        response = client.get('/login')
        assert response.status_code == 200
        assert b'Login' in response.data

    def test_login_with_email(self, client, app):
        """Test login sends magic link."""
        app.config['DEV_MAGIC'] = True

        response = client.post('/login', data={
            'email': 'test@example.com'
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'Magic link' in response.data or b'Check your email' in response.data

    def test_login_empty_email(self, client):
        """Test login rejects empty email."""
        response = client.post('/login', data={
            'email': ''
        }, follow_redirects=True)

        assert b'required' in response.data.lower()

    def test_logout(self, authenticated_client):
        """Test logout clears session."""
        response = authenticated_client.post('/logout', follow_redirects=True)

        assert response.status_code == 200
        # Should be redirected to home
        assert b'logged out' in response.data.lower() or response.request.path == '/'

    def test_protected_route_redirects(self, client):
        """Test protected route redirects to login."""
        response = client.get('/profile')
        assert response.status_code == 302
        assert '/login' in response.location
```

### Users Controller Tests

```python
# tests/test_controllers/test_users.py
"""Users controller tests."""

import pytest


class TestUsersController:
    """Tests for user endpoints."""

    def test_profile_requires_auth(self, client):
        """Test profile page requires authentication."""
        response = client.get('/profile')
        assert response.status_code == 302

    def test_profile_shows_user(self, authenticated_client, user):
        """Test profile page shows user info."""
        response = authenticated_client.get('/profile')
        assert response.status_code == 200
        assert user.name.encode() in response.data

    def test_edit_profile_form(self, authenticated_client):
        """Test edit profile form renders."""
        response = authenticated_client.get('/profile/edit')
        assert response.status_code == 200
        assert b'form' in response.data.lower()

    def test_update_profile(self, authenticated_client, user, app):
        """Test profile update."""
        response = authenticated_client.post('/profile/edit', data={
            'name': 'Updated Name',
            'avatar_url': '',
        }, follow_redirects=True)

        assert response.status_code == 200

        # Verify in database
        with app.app_context():
            from app.models import User
            updated = User.get_by_id(user.id)
            assert updated.name == 'Updated Name'
```

### HTMX Tests

```python
# tests/test_controllers/test_settings.py
"""Settings controller tests with HTMX."""

import pytest


class TestSettingsController:
    """Tests for settings endpoints."""

    def test_settings_page(self, authenticated_client):
        """Test settings page renders."""
        response = authenticated_client.get('/settings')
        assert response.status_code == 200

    def test_update_setting_htmx(self, authenticated_client, user, app):
        """Test HTMX setting update."""
        response = authenticated_client.post(
            '/settings',
            data={'key': 'theme', 'value': 'dark'},
            headers={'HX-Request': 'true'}
        )

        assert response.status_code == 200
        assert b'Saved' in response.data

        # Verify in database
        with app.app_context():
            from app.models import Setting
            value = Setting.get_value(user.id, 'theme')
            assert value == 'dark'

    def test_update_setting_redirect(self, authenticated_client):
        """Test non-HTMX setting update redirects."""
        response = authenticated_client.post(
            '/settings',
            data={'key': 'theme', 'value': 'light'}
        )

        assert response.status_code == 302
        assert '/settings' in response.location
```

---

## Test Utilities

### Factory Functions

```python
# tests/factories.py
"""Test data factories."""

from app.models import User, Setting


def create_user(email='test@example.com', name='Test User', **kwargs):
    """Create a user with defaults."""
    return User.create(email=email, name=name, **kwargs)


def create_setting(user_id, key='theme', value='light'):
    """Create a setting with defaults."""
    return Setting.set(user_id, key, value)
```

### Assertions

```python
# tests/assertions.py
"""Custom test assertions."""


def assert_redirects_to(response, endpoint):
    """Assert response redirects to endpoint."""
    assert response.status_code == 302
    assert endpoint in response.location


def assert_flashes(client, message, category='success'):
    """Assert flash message was set."""
    with client.session_transaction() as session:
        flashes = session.get('_flashes', [])
        assert any(
            cat == category and msg == message
            for cat, msg in flashes
        ), f"Expected flash ({category}, {message}), got {flashes}"
```

---

## Coverage

### Running with Coverage

```bash
# Terminal report
pytest --cov=app --cov-report=term-missing

# HTML report
pytest --cov=app --cov-report=html
open htmlcov/index.html

# XML report (for CI)
pytest --cov=app --cov-report=xml
```

### Coverage Targets

- **Models**: 90%+ (core business logic)
- **Controllers**: 80%+ (main paths)
- **Platform**: 70%+ (utilities)
- **Overall**: 80%+

---

## CI/CD

### GitHub Actions

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-cov

    - name: Run tests
      run: pytest --cov=app --cov-report=xml

    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
```

### Pre-commit Hook

```bash
#!/bin/sh
# .git/hooks/pre-commit

pytest tests/ -x -q
```

---

**Next:** [Deployment](deployment.md) | [Security](security.md)
