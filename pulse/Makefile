# sparQ Makefile
# Core commands for running and managing the development environment

.PHONY: help venv run kill reset clean \
        db-start db-stop db-reset db-status

# Detect OS and set paths
ifeq ($(OS),Windows_NT)
    PYTHON := ./venv/Scripts/python.exe
    PIP := ./venv/Scripts/pip.exe
    PYTHON_CMD := python
    VENV_BIN := ./venv/Scripts
    ACTIVATE_PATH := venv/Scripts/activate
else
    PYTHON := ./venv/bin/python
    PIP := ./venv/bin/pip
    PYTHON_CMD := python3
    VENV_BIN := ./venv/bin
    ACTIVATE_PATH := venv/bin/activate
endif

PORT ?= 8000

help:
	@echo "+-------------------+----------------------------------------------------------+"
	@echo "| sparQ                                                                        |"
	@echo "+-------------------+----------------------------------------------------------+"
	@echo "| Command           | Description                                              |"
	@echo "+-------------------+----------------------------------------------------------+"
	@echo "| make venv         | Create Python venv and install dependencies              |"
	@echo "| make run          | Start dev server (SQLite default, PG if configured)     |"
	@echo "| make kill         | Stop the Flask development server                        |"
	@echo "| make reset        | Reset database (drop, recreate, run migrations)          |"
	@echo "| make clean        | Remove Python cache files (__pycache__, .pyc)            |"
	@echo "+-------------------+----------------------------------------------------------+"
	@echo "| Database (PostgreSQL only — SQLite needs no setup)                            |"
	@echo "+-------------------+----------------------------------------------------------+"
	@echo "| make db-start     | Start PostgreSQL Docker container                        |"
	@echo "| make db-stop      | Stop PostgreSQL Docker container                         |"
	@echo "| make db-reset     | Drop and recreate database in container                  |"
	@echo "| make db-status    | Check if PostgreSQL is running                           |"
	@echo "+-------------------+----------------------------------------------------------+"
	@echo ""
	@echo "Quick start: make venv && source $(ACTIVATE_PATH)"
	@echo "Then:        make run"

# Create virtual environment (auto-detects OS)
venv:
	@if [ -d venv ]; then echo "Removing old venv..." && rm -rf venv; fi
	uv venv venv
	VIRTUAL_ENV=venv uv pip compile requirements.in -o requirements.txt
	VIRTUAL_ENV=venv uv pip install -r requirements.txt
	@echo ""
	@echo "Setup complete! Now run:"
	@echo "  source $(ACTIVATE_PATH)"
	@echo ""
	@echo "Then start the server with: make run"

# --- Database targets ---

PG_CONTAINER := sparq-postgres
PG_IMAGE     := postgres:16
PG_PORT      := 5432
PG_USER      := sparq
PG_PASS      := sparq
PG_DB        := sparq

db-start:
	@if docker ps --format '{{.Names}}' | grep -q '^$(PG_CONTAINER)$$'; then \
		echo "PostgreSQL already running"; \
	elif docker ps -a --format '{{.Names}}' | grep -q '^$(PG_CONTAINER)$$'; then \
		docker start $(PG_CONTAINER) && echo "PostgreSQL started"; \
	else \
		docker run -d --name $(PG_CONTAINER) \
			-e POSTGRES_USER=$(PG_USER) -e POSTGRES_PASSWORD=$(PG_PASS) -e POSTGRES_DB=$(PG_DB) \
			-p $(PG_PORT):5432 $(PG_IMAGE) && echo "PostgreSQL created and started"; \
	fi
	@until docker exec $(PG_CONTAINER) pg_isready -U $(PG_USER) -q 2>/dev/null; do sleep 0.5; done

db-stop:
	@docker stop $(PG_CONTAINER) 2>/dev/null && echo "PostgreSQL stopped" || echo "Not running"

db-reset:
	@docker exec $(PG_CONTAINER) psql -U $(PG_USER) -d postgres -c "DROP DATABASE IF EXISTS $(PG_DB);" -c "CREATE DATABASE $(PG_DB) OWNER $(PG_USER);"
	@echo "Database reset"

db-status:
	@docker exec $(PG_CONTAINER) pg_isready -U $(PG_USER) 2>/dev/null && echo "PostgreSQL is running" || echo "PostgreSQL is not running"

# --- Application targets ---

run:
	@if echo "$${DATABASE_URL:-$$(grep -s '^DATABASE_URL=' .env | cut -d= -f2-)}" | grep -q '^postgresql'; then \
		$(MAKE) db-start; \
	fi
	@export FLASK_DEBUG=True && $(PYTHON) system/db/dev_setup.py
	export FLASK_DEBUG=True && export PORT=$(PORT) && \
	$(if $(V),export SPARQ_VERBOSE=1 &&) $(PYTHON) app.py

kill:
	@lsof -ti:$(PORT) | xargs kill 2>/dev/null && echo "Server stopped on port $(PORT)" || echo "No server running on port $(PORT)"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; \
	find . -type f -name "*.pyc" -delete 2>/dev/null; \
	find . -type f -name "*.pyo" -delete 2>/dev/null; \
	echo "Cleaned Python cache files"
