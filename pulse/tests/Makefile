.PHONY: unit integration models routes security database api sanity smoke journeys e2e all coverage watch clean help lint lint-fix type-check check

# Run from project root: make -C tests <target>
# Or from tests dir: make <target>

# Detect OS and set Python path (venv is in parent directory)
ifeq ($(OS),Windows_NT)
    PYTHON := ../venv/Scripts/python.exe
else
    PYTHON := ../venv/bin/python
endif

help:
	@echo "+------------------+--------------------------------+---------+--------+"
	@echo "| Command          | Description                    | Server? | Time   |"
	@echo "+------------------+--------------------------------+---------+--------+"
	@echo "| make sanity      | Quick health check             | No      | ~3s    |"
	@echo "| make unit        | Unit tests (pure functions)    | No      | ~2s    |"
	@echo "| make models      | Model integration tests        | No      | ~20s   |"
	@echo "| make routes      | Route smoke tests              | No      | ~30s   |"
	@echo "| make security    | Security middleware tests       | No      | ~15s   |"
	@echo "| make database    | DB/ORM behavior tests          | No      | ~10s   |"
	@echo "| make api         | REST API endpoint tests        | No      | ~15s   |"
	@echo "| make integration | All integration tests          | No      | ~85s   |"
	@echo "| make all         | Everything (unit + integration)| No      | ~85s   |"
	@echo "| make coverage    | Integration + coverage report  | No      | ~90s   |"
	@echo "+------------------+--------------------------------+---------+--------+"
	@echo "| make smoke       | E2E browser smoke tests        | Yes     | ~12s   |"
	@echo "| make journeys    | E2E user flow tests            | Yes     | varies |"
	@echo "| make e2e         | All E2E tests                  | Yes     | varies |"
	@echo "+------------------+--------------------------------+---------+--------+"
	@echo "| make lint        | Run ruff linter                | No      | ~2s    |"
	@echo "| make lint-fix    | Auto-fix lint issues           | No      | ~2s    |"
	@echo "| make type-check  | Run mypy type checking         | No      | ~5s    |"
	@echo "| make check       | Lint + type-check (pre-commit) | No      | ~7s    |"
	@echo "+------------------+--------------------------------+---------+--------+"
	@echo ""
	@echo "Quick start: make sanity"
	@echo "Full suite:  make all"
	@echo "Note: E2E tests require the app running in a separate terminal (make run)"

# Sanity check - quick verification that system works
sanity:
	$(PYTHON) -m pytest integration/test_sanity.py -v

unit:
	$(PYTHON) -m pytest unit/ -v

# Integration test subsets
models:
	$(PYTHON) -m pytest integration/models/ -v

routes:
	$(PYTHON) -m pytest integration/routes/ -v

security:
	$(PYTHON) -m pytest integration/security/ -v

database:
	$(PYTHON) -m pytest integration/database/ -v

api:
	$(PYTHON) -m pytest integration/api/ -v

integration:
	$(PYTHON) -m pytest integration/ -v

# E2E tests - require running server (make run in project root)
smoke:
	@echo "Note: Smoke tests require a running server (make run)"
	$(PYTHON) -m pytest e2e/smoke/ -v

journeys:
	@echo "Note: Journey tests require a running server with demo data"
	$(PYTHON) -m pytest e2e/journeys/ -v

e2e: smoke journeys

all:
	$(PYTHON) -m pytest unit/ integration/ -v

coverage:
	$(PYTHON) -m pytest integration/ -v --cov=../modules --cov=../system --cov-report=term-missing --cov-report=html

# Watch mode (requires pytest-watch)
watch:
	$(PYTHON) -m ptw unit/ integration/

clean:
	rm -rf .pytest_cache __pycache__ .coverage htmlcov
	find . -type d -name "__pycache__" -exec rm -rf {} +

# Code quality (runs on source code in parent directory)
lint:
	$(PYTHON) -m ruff check .. --config pyproject.toml

lint-fix:
	$(PYTHON) -m ruff check --fix .. --config pyproject.toml

type-check:
	$(PYTHON) -m mypy ../app.py ../system/ ../modules/ --config-file mypy.ini --ignore-missing-imports

check: lint type-check
	@echo ""
	@echo "All checks passed (done)"
