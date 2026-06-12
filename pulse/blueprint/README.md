# Blueprint

> Documentation blueprint for building sparQ modules using Flask, HTMX, and SQLite.

## What is a sparQ Module?

> **Important:** A sparQ module is NOT a Python module.

A **sparQ module** is a self-contained feature unit — a folder with a specific structure containing models, views, controllers, and a manifest. It's a standalone, loosely-coupled building block that can function independently or integrate with other modules.

## What is This?

This is a **documentation-only blueprint** that guides developers and AI agents in building sparQ modules following best practices. It contains no application code - just comprehensive guides on architecture, patterns, and implementation.

## Quick Start

When starting a new module, have Claude read:

1. `CLAUDE.md` - Master blueprint with Quick Start section
2. `patterns/*.md` - Detailed implementation guides (as needed)

## Structure

```
blueprint/
├── CLAUDE.md                    # Master blueprint - read this first
├── patterns/
│   ├── module-system.md         # Module architecture, hooks, lifecycle
│   ├── database.md              # SQLAlchemy, migrations, queries
│   ├── mvc.md                   # Models, Views, Controllers
│   ├── auth.md                  # Authentication, groups, permissions
│   ├── frontend.md              # Bootstrap + Alpine.js + HTMX
│   ├── htmx.md                  # HTMX patterns
│   ├── i18n.md                  # Internationalization
│   ├── colors.md                # Design system, CSS variables
│   ├── typing.md                # Type hints, mypy --strict
│   ├── security.md              # CSRF, rate limiting
│   ├── testing.md               # pytest patterns
│   ├── deployment.md            # Docker, Gunicorn
│   └── audit.md                 # Code review checklist
└── README.md                    # This file
```

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.11+ / Flask 3.x |
| Database | SQLite (default) or PostgreSQL |
| ORM | SQLAlchemy 2.0 |
| Templates | Jinja2 |
| Frontend | Bootstrap 5 + Alpine.js + HTMX |
| Plugin System | pluggy |
| Testing | pytest |
| Server | Gunicorn |

## Philosophy

- **Modular by design** - Features are self-contained modules
- **MVC Pattern** - Fat models, thin controllers
- **Server-rendered HTML** - HTMX + Alpine.js for interactivity
- **No build pipeline** - No npm, webpack, etc.
- **i18n from day 1** - Module-scoped translations
- **Convention over configuration** - Standard patterns reduce decisions

## Usage as Submodule

```bash
# Add to your project
git submodule add <repository-url> blueprint

# Point Claude to it
# In your project's CLAUDE.md:
# "See blueprint/CLAUDE.md for architecture patterns"
```

Copyright (c) 2025-2026 sparQ Software LLC
