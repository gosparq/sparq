# sparQ Test Suite

## Quick Start

```bash
# First thing to run - verifies system health (~3 seconds)
make sanity

# All integration tests
make integration
```

## Test Commands

| Command | Description | Server? | Time |
|---------|-------------|---------|------|
| `make sanity` | Quick health check | No | ~3s |
| `make integration` | All integration tests | No | ~4s |
| `make coverage` | Integration + coverage report | No | ~5s |
| `make smoke` | E2E browser smoke tests | Yes | ~12s |
| `make journeys` | E2E user flow tests | Yes | varies |
| `make e2e` | All E2E tests | Yes | varies |
| `make all` | Everything (integration + E2E) | Yes | varies |
| `make lint` | Run ruff linter | No | ~2s |
| `make lint-fix` | Auto-fix lint issues | No | ~2s |
| `make type-check` | Run mypy type checking | No | ~5s |
| `make check` | Lint + type-check (pre-commit) | No | ~7s |

## What Each Test Type Covers

### Sanity Tests (`make sanity`)
Quick verification that the system bootstraps correctly:
- App starts
- Core modules loaded
- Demo data loads
- Login works
- Dashboard accessible

**Run this first** after pulling changes or before commits.

### Unit Tests (`make unit`)
Pure Python tests with no database:
- Utility functions
- Validators
- Business logic calculations

### Integration Tests (`make integration`)
Tests with database access:
- Model CRUD operations
- API endpoint responses
- Authentication flows
- Service layer functions

### E2E Smoke Tests (`make smoke`)
Browser-based sanity checks (requires running server):
- Login page renders
- Authentication works
- Critical pages load

### E2E Journey Tests (`make journeys`)
Full user workflows (requires running server + demo data):
- Quote lifecycle (create → send → accept)
- Contact management
- Job scheduling

## Running E2E Tests

E2E tests require a running server:

```bash
# Terminal 1: Start the server
cd /path/to/sparq
make run

# Terminal 2: Run E2E tests
cd tests
make smoke
```

Or with demo data:
```bash
# Terminal 1
make demo  # Seed demo data
make run   # Start server

# Terminal 2
make smoke
```

## Directory Structure

```
tests/
├── Makefile                 # Test commands
├── pytest.ini               # Pytest configuration
├── conftest.py              # Root fixtures (app, db, client)
├── README.md                # This file
│
├── testdata/
│   └── fixtures/            # JSON fixture data
│       └── users.json
│
├── unit/                    # Unit tests (no db)
│
├── integration/             # Integration tests
│   ├── conftest.py          # Integration fixtures
│   ├── test_sanity.py       # Sanity checks
│   ├── models/
│   │   └── test_user.py     # User model tests
│   └── api/
│       └── test_auth.py     # Auth endpoint tests
│
└── e2e/                     # End-to-end browser tests
    ├── conftest.py          # Playwright fixtures
    ├── smoke/
    │   └── test_critical_paths.py
    └── journeys/
        └── sales/
            └── test_quote_lifecycle.py
```

## Available Fixtures

### Root Fixtures (conftest.py)
- `app` - Flask test app with in-memory SQLite
- `db_session` - Database session (auto-cleanup)
- `client` - Flask test client
- `test_user` - Basic test user
- `admin_user` - Admin test user
- `authenticated_client` - Logged-in test client
- `admin_client` - Admin logged-in client
- `app_with_demo_data` - App with seeded demo data

### E2E Fixtures (e2e/conftest.py)
- `page` - Fresh Playwright page
- `authenticated_page` - Page with logged-in session
- `base_url` - Application base URL

## Writing Tests

### Integration Test Example

```python
def test_create_quote(self, app, db_session):
    """Test creating a new quote."""
    from modules.base.sales.models.quote import Quote

    with app.app_context():
        quote = Quote.create(
            title="Test Quote",
            amount=1000.00,
        )
        assert quote.id is not None
```

### E2E Test Example

```python
def test_login_flow(self, page, base_url):
    """Test login with valid credentials."""
    page.goto(f"{base_url}/login")
    page.fill('input[name="email"]', "sysadmin")
    page.fill('input[name="password"]', "password")
    page.click('button[type="submit"]')

    assert "/login" not in page.url
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///:memory:` | Test database |
| `TEST_BASE_URL` | `http://localhost:8000` | E2E test target |
| `E2E_USER_EMAIL` | `sysadmin` | E2E login email |
| `E2E_USER_PASSWORD` | `password` | E2E login password |

## Troubleshooting

### E2E tests fail with "browser not found"
```bash
python -m playwright install chromium
```

### Tests hang on app creation
Ensure you're running from the tests directory:
```bash
cd tests
make sanity
```

### "Module not found" errors
The test conftest.py changes to project root. If running pytest directly:
```bash
cd /path/to/sparq/tests
pytest integration/test_sanity.py -v
```
