# CLAUDE.md - sparQ Module Development Guide

> **Single source of truth for sparQ architecture and patterns.**

---

## Terminology: What is a sparQ Module?

> **Important:** A sparQ module is NOT a Python module.

A **sparQ module** is a self-contained feature unit — a folder with a specific structure containing models, views, controllers, and a manifest. It's a standalone, loosely-coupled building block that can function independently or integrate with other modules.

**sparQ module structure:**
```
modulename/
├── __init__.py          # Exports module_instance
├── __manifest__.py      # Metadata (name, version, mappid, dependencies)
├── module.py            # Module class with lifecycle hooks
├── controllers/         # Routes (Flask blueprints)
├── models/              # SQLAlchemy models
├── views/
│   ├── templates/
│   │   └── modulename/  # Namespaced templates (prevents collisions)
│   │       ├── desktop/ # Desktop Jinja2 templates
│   │       └── mobile/  # Mobile templates (future)
│   └── assets/css/      # Module CSS
└── lang/                # i18n translation files
```

**Template path convention:**
- Controllers use: `render_device_template("modulename/desktop/index.html")`
- Import: `from system.device.template import render_device_template`
- Templates extend: `{% extends "core/desktop/base.html" %}`
- Cross-module includes: `{% include "othername/desktop/partial.html" %}`

**Module types (defined in manifest):**
- `type: "System"` — Required modules that cannot be disabled (core, dashboard)
- `type: "App"` — Optional modules that can be toggled on/off
- `type: "Plugin"` — Hidden utility modules

This is distinct from Python's concept of a module (any `.py` file). When this documentation refers to "module", it means a sparQ module unless explicitly stated otherwise.

---

## Project Overview

sparQ is a modular business suite built with Python + Flask + HTMX + PostgreSQL. It uses a plugin-based architecture (pluggy) where modules can be enabled/disabled independently.

**Key characteristics:**
- Modular by design — features are self-contained modules
- Plugin architecture — modules extend via hooks, no core modification needed
- Fat Models, Thin Controllers — business logic lives in models
- Server-rendered HTML + Alpine.js + HTMX — no SPA complexity
- i18n from day 1 — module-scoped translations with fallback
- Convention over configuration — standard patterns reduce decisions

**Base modules (13):**
core, dashboard, sync, people, presence, resources, finance, tasks, projects, ai, msa, plugins

---

## Architecture

```
Flask Application (app.py)
         │
    ┌────┴────┬─────────────┐
    ▼         ▼             ▼
 Module    Database      i18n
 Loader   (SQLAlchemy)  (JSON)
(pluggy)
    │
    ▼
modules/
└── base/                    # Core modules (shipped with sparQ)
    ├── core/                # Auth, base templates, settings
    ├── dashboard/           # Main dashboard, launchpad
    ├── sync/                # Team updates, chat, boards, blockers
    ├── people/              # Employee management, hiring, onboarding
    ├── presence/            # Time tracking, clock in/out
    ├── resources/           # Documents, knowledge base, signatures
    ├── finance/             # Accounting, expenses
    ├── tasks/               # Task management, blocker tracking
    ├── projects/            # Project management
    ├── ai/                  # AI assistant features
    ├── msa/                 # Master service agreements
    └── plugins/             # Hidden utility plugins
```

**Loading order:** Core → all others (alphabetically)

---

## Pattern Reference

For implementation details, see these pattern files:

| Topic | File |
|-------|------|
| **Creating modules** | [patterns/module-system.md](patterns/module-system.md) |
| **Database & models** | [patterns/database.md](patterns/database.md) |
| **MVC pattern** | [patterns/mvc.md](patterns/mvc.md) |
| **Authentication** | [patterns/auth.md](patterns/auth.md) |
| **CSS architecture** | [patterns/css.md](patterns/css.md) |
| **Frontend (Alpine+HTMX)** | [patterns/frontend.md](patterns/frontend.md) |
| **Mobile navigation** | [patterns/mobile-navigation.md](patterns/mobile-navigation.md) |
| **HTMX patterns** | [patterns/htmx.md](patterns/htmx.md) |
| **Internationalization** | [patterns/i18n.md](patterns/i18n.md) |
| **Async processing** | [patterns/async procesing.md](patterns/async%20procesing.md) |
| **Security** | [patterns/security.md](patterns/security.md) |
| **Type safety** | [patterns/typing.md](patterns/typing.md) |
| **Testing** | [patterns/testing.md](patterns/testing.md) |
| **Deployment** | [patterns/deployment.md](patterns/deployment.md) |
| **Code audit checklist** | [patterns/audit.md](patterns/audit.md) |
| **Soft delete** | [patterns/soft-delete.md](patterns/soft-delete.md) |

---

## Development vs Production Mode

Controlled by the presence of a `VERSION` file in the project root.

| Mode | Database | Debug |
|------|----------|-------|
| **Development** (default) | `db.create_all()`, no migrations | Enabled |
| **Production** | Alembic migrations only | Disabled |

→ See [patterns/database.md](patterns/database.md) for details.

---

## AI Agent Instructions

**When modifying existing code:**
1. Read the relevant pattern file first
2. Follow MVC pattern (fat models, thin controllers)
3. Use `{{ _("text") }}` for all user-visible strings

**Documentation requirements:**
When modifying Python code, always maintain docstrings:
- Add/update docstrings for any new or modified classes, methods, functions
- Use Google-style docstrings
- Include: description, Args, Returns, Example (where helpful)
- Keep docstrings in sync with code changes

**When troubleshooting:**
1. Check folder structure matches convention
2. Verify `module_instance` is exported from `__init__.py`
3. Check for `__DISABLED__` file
4. Review console output for loading errors

---

Copyright (c) 2025-2026 sparQ Software LLC
