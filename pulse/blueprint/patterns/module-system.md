# Module System Pattern Guide

> Complete guide to the sparQ pluggy-based module system for building extensible applications.

---

## What is a sparQ Module?

> **Important:** A sparQ module is NOT a Python module.

A **sparQ module** is a self-contained feature unit — a folder with a specific structure containing models, views, controllers, and a manifest. It's a standalone, loosely-coupled building block that can function independently or integrate with other modules.

When this documentation refers to "module", it means a sparQ module unless explicitly stated otherwise (e.g., "Python module" or `importlib.import_module()`).

---

## Overview

sparQ uses [pluggy](https://pluggy.readthedocs.io/) (the plugin system behind pytest) to enable dynamic module loading. Modules are self-contained units that can be added, removed, or disabled without modifying core application code.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     ModuleLoader                            │
│                  (system/module/loader.py)                  │
├─────────────────────────────────────────────────────────────┤
│  1. discover_modules()  - Scan modules/base/ and data/modules/apps/ │
│  2. load_module()       - Import manifest & module_instance │
│  3. register_routes()   - Register Flask blueprints         │
└─────────────────────────────────────────────────────────────┘
                             │
                             │ uses
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                    pluggy PluginManager                     │
│                     ("sparqone" project)                    │
├─────────────────────────────────────────────────────────────┤
│  - Registers hook specifications (ModuleSpecs)              │
│  - Registers module instances as plugins                    │
│  - Calls hooks on all registered modules                    │
└─────────────────────────────────────────────────────────────┘
```

---

## Directory Structure

Modules are organized into two directories:

```
modules/
└── base/           # Core + optional base modules
    ├── core/       # REQUIRED - auth, base templates, settings
    ├── team/       # REQUIRED - employee management
    ├── dashboard/  # REQUIRED - main dashboard, navigation
    ├── sales/      # Optional - contacts, quotes, requests
    ├── service/    # Optional - jobs, scheduling
    ├── billing/    # Optional - invoices, payments
    ├── timetracking/ # Optional - timesheets
    ├── resources/  # Optional - documents, attachments
    ├── chat/       # Optional - internal messaging
    └── finance/    # Optional - reports, expenses

data/modules/
└── apps/           # Installed apps and plugins (marketplace + custom)
    ├── notes/      # Example app
    ├── weather/    # Example app
    └── nickname/   # Example plugin (type: Plugin)
```

**Required modules** (core, team, dashboard) cannot be disabled.
**Optional base modules** can be toggled via Settings → App Manager.
**Apps** in `data/modules/apps/` can be installed/removed at runtime via marketplace or `cd sdk && make app`.

---

## Module Lifecycle

### 1. Discovery Phase

The `ModuleLoader.discover_modules()` method:

```python
# Scans modules/ directory
modules_dir = "modules"
module_names = [
    d for d in os.listdir(modules_dir)
    if os.path.isdir(os.path.join(modules_dir, d))
    and not d.startswith("_")
]
```

**Loading Order:**
1. `core` module (required - provides base templates, auth)
2. `team` module (required - provides user management)
3. All other modules (alphabetically)

### 2. Loading Phase

For each module, `load_module()`:

1. **Import manifest** from `modules/{name}/__manifest__.py`
2. **Check if disabled** - looks for `__DISABLED__` file
3. **Import module** from `modules/{name}/__init__.py`
4. **Get instance** - expects `module_instance` attribute
5. **Register with pluggy** - makes hooks available

```python
def load_module(self, module_name, folder):
    # Load manifest
    manifest = importlib.import_module(
        f"modules.{folder}.{module_name}.__manifest__"
    ).manifest

    # Check disabled status
    disabled_file = os.path.join("modules", folder, module_name, "__DISABLED__")
    is_enabled = not os.path.exists(disabled_file)
    manifest["enabled"] = is_enabled

    # Always import base modules to register their SQLAlchemy models
    # This ensures cross-module relationships work even when modules are disabled
    if folder == "base":
        importlib.import_module(import_path)

    if is_enabled:
        # Load module and register routes/hooks
        module = importlib.import_module(f"modules.{folder}.{module_name}")
        if hasattr(module, "module_instance"):
            self.pm.register(module.module_instance)
            self.modules.append(module.module_instance)
```

### 3. Route Registration Phase

After all modules load, `register_routes()` is called:

```python
def register_routes(self, app):
    for module in self.modules:
        if hasattr(module, "get_routes"):
            routes = module.get_routes()
            for blueprint, url_prefix in routes:
                app.register_blueprint(blueprint, url_prefix=url_prefix)
```

### 4. Database Initialization Phase

After routes are registered and `db.create_all()` runs:

```python
# In app.py
module_loader.pm.hook.init_database()
```

This calls `init_database()` on every module that implements it.

---

## Creating a Module

### Using the SDK

```bash
cd sdk
make app name=yourmodule
```

This scaffolds a new app with:
- Auto-generated `mappid` (6-character marketplace ID)
- Correct folder structure
- Template files ready to customize

### Required Files

```
data/modules/apps/yourmodule/

├── __init__.py          # REQUIRED: Exports module_instance
├── __manifest__.py      # REQUIRED: Module metadata (includes mappid)
├── module.py            # REQUIRED: Module class
├── controllers/
│   └── routes.py        # REQUIRED: Flask blueprint
├── models/              # Optional: SQLAlchemy models
├── views/
│   ├── templates/
│   │   └── yourmodule/        # Namespaced templates
│   │       ├── desktop/       # Desktop Jinja2 templates
│   │       └── mobile/        # Mobile templates (optional)
│   └── assets/css/            # Module CSS
└── lang/                # Optional: i18n JSON files
```

### __manifest__.py

```python
manifest = {
    # Required fields
    "name": "YourModule",         # Display name (used as dict key)
    "version": "1.0",             # Semantic version
    "mappid": "x7k2m9",           # 6-char marketplace ID (auto-generated by SDK)
    "main_route": "/yourmodule",  # URL slug (accessed at /m/{mappid}/yourmodule)
    "type": "App",                # "App" or "System"
    "depends": ["core"],          # Module dependencies

    # Display fields
    "icon_class": "fa-solid fa-cube",   # FontAwesome icon
    "color": "#007bff",                  # Theme color (hex)
    "description": "Short description",  # One line
    "long_description": "...",           # Detailed (optional)
}
```

**Note:** The `mappid` is a unique identifier for each module. Apps are accessible at `/m/{mappid}/{slug}` where slug is from `main_route`.

**Type Values:**
| Type | Description | Launchpad |
|------|-------------|-----------|
| `"App"` | User-facing feature with full UI | Visible in Apps section |
| `"Plugin"` | Utility/extension with minimal UI | Hidden |
| `"System"` | Infrastructure/admin | Hidden |

### __init__.py

```python
from .module import YourModuleModule

# Import all models to ensure they're registered with SQLAlchemy
# This is required even if the module is disabled, as other modules may reference them
from .models.yourmodel import YourModel  # noqa: F401

# This is what ModuleLoader looks for
module_instance = YourModuleModule()

__all__ = ["module_instance"]
```

**Important:**
- The `module_instance` variable name is required. The loader checks for this exact attribute.
- **Base modules must explicitly import their models** in `__init__.py` to ensure SQLAlchemy registers them even when the module is disabled. This allows cross-module relationships to work correctly.

### module.py

```python
from system.db.database import db
from system.module.hooks import hookimpl


class YourModuleModule:
    """Module class implementing lifecycle hooks."""

    def get_routes(self):
        """Return list of (blueprint, url_prefix) tuples.

        Called by ModuleLoader.register_routes() during app startup.
        """
        from .controllers.routes import blueprint
        return [(blueprint, "/yourmodule")]

    @hookimpl
    def init_database(self):
        """Initialize database tables and sample data.

        Called after all modules are loaded and db.create_all() runs.
        """
        db.create_all()
        # Optional: Create sample data
        from .models.yourmodel import YourModel
        YourModel.create_sample_data()
```

---

## Hook System

### Hook Specifications

Defined in `system/module/hooks.py`:

```python
import pluggy

hookspec = pluggy.HookspecMarker("sparqone")
hookimpl = pluggy.HookimplMarker("sparqone")


class ModuleSpecs:
    @hookspec
    def init_database(self):
        """Initialize database tables and sample data."""
        pass
```

### Implementing Hooks

Use the `@hookimpl` decorator:

```python
from system.module.hooks import hookimpl

class MyModule:
    @hookimpl
    def init_database(self):
        """This will be called during app startup."""
        db.create_all()
```

### Available Hooks

| Hook | When Called | Purpose |
|------|-------------|---------|
| `init_database()` | After `db.create_all()` | Create tables, seed data |

### Adding Custom Hooks

Modules can define their own hook specifications. See the `team` module for an example:

```python
# modules/team/hooks.py
class TeamHookSpecs:
    @hookspec
    def employee_created(self, employee):
        """Called when a new employee is created."""
        pass

# In TeamModule
def register_specs(self, plugin_manager):
    plugin_manager.add_hookspecs(TeamHookSpecs)
```

---

## Disabling Modules

### Via Control Panel (Recommended)

Use **Control Panel → App Manager** to toggle optional modules on/off. This:
- Creates/removes the `__DISABLED__` file
- Triggers automatic server restart
- Works in both dev mode (Flask reloader) and production (Docker restart)

### Manual Toggle

To disable a base module without the UI:

```bash
# Disable a base module (e.g., billing)
touch modules/base/billing/__DISABLED__

# Re-enable
rm modules/base/billing/__DISABLED__

# Restart server for changes to take effect
```

To disable a custom app:

```bash
# Disable a custom app
touch data/modules/apps/yourapp/__DISABLED__

# Re-enable
rm data/modules/apps/yourapp/__DISABLED__
```

### Behavior When Disabled

Disabled modules:
- Are still tracked in manifests (for UI display)
- Have `enabled: false` in their manifest
- **Base modules**: Models are still imported (SQLAlchemy relationships work)
- **Base modules**: Routes and hooks are NOT registered (404 for disabled routes)
- **Custom apps**: Not imported at all
- Data remains in database (preserved for re-enabling)

### Why Base Module Models Always Load

Base modules (in `modules/base/`) always have their models imported, even when disabled. This ensures:

1. **Cross-module relationships work** - e.g., `TimeEntry.job` relationship to `Job` model
2. **No SQLAlchemy errors** - All model classes are registered before relationships resolve
3. **Data integrity** - Existing data with foreign keys remains valid

The loader achieves this by always importing base modules:

```python
# In system/module/loader.py
if folder == "base":
    importlib.import_module(import_path)  # Always import base modules
```

Each base module's `__init__.py` explicitly imports its models:

```python
# modules/base/sales/__init__.py
from .models.quote import Quote, QuoteLineItem  # noqa: F401
from .models.service_request import ServiceRequest  # noqa: F401
```

### Server Restart on Toggle

When modules are toggled via App Manager:
- **Dev mode**: Touches `app.py` to trigger Flask's auto-reloader
- **Production (Docker)**: Calls `os._exit(0)`, container restarts via `--restart unless-stopped`

---

## Module Context

During requests, module information is available via Flask's `g` object:

```python
from flask import g

# In before_request hook (set by app.py):
g.installed_modules  # List of all module manifests
g.current_module     # Current module's manifest (based on URL)
```

### Determining Current Module

The current module is determined by matching the URL path:

```python
path = request.path.split("/")[1] or "core"
current_module = next(
    (m for m in g.installed_modules
     if m.get("main_route", "").strip("/").lower() == path.lower()),
    # Fallback to core
    next((m for m in g.installed_modules if m.get("name") == "Core"), None)
)
```

---

## Conditional UI with module_enabled()

Use the `module_enabled()` template helper to show/hide UI based on module availability.

### In Templates

```html
{% if module_enabled('Billing') %}
<div class="billing-section">
    <a href="/billing/invoices">Invoices</a>
</div>
{% endif %}

{% if module_enabled('Catalog') %}
    <select name="catalog_item"><!-- Catalog dropdown --></select>
{% else %}
    <input type="text" name="description" placeholder="Enter description">
{% endif %}
```

### In Navigation

```html
{% if module_enabled('Sales') %}
<li class="nav-section">
    <span class="nav-section-header">{{ _("Sales") }}</span>
    <ul class="nav-section-items">
        <li><a href="/sales/contacts">Contacts</a></li>
        <li><a href="/sales/quotes">Quotes</a></li>
    </ul>
</li>
{% endif %}
```

### Module Name Matching

Use the **display name** from the module's manifest (with spaces if applicable):

| Module | Manifest Name | Check |
|--------|--------------|-------|
| sales | "Sales" | `module_enabled('Sales')` |
| billing | "Billing" | `module_enabled('Billing')` |
| timetracking | "Time Tracking" | `module_enabled('Time Tracking')` |
| resources | "Resources" | `module_enabled('Resources')` |

### Graceful Degradation

When a module is disabled, design UI to degrade gracefully:

```html
{% if module_enabled('Billing') %}
<div class="invoices-tab">
    <!-- Full invoice list -->
</div>
{% else %}
<div class="text-center py-4 text-muted">
    <i class="fas fa-file-invoice fa-2x mb-2"></i>
    <p class="mb-0">{{ _("Billing module not enabled") }}</p>
</div>
{% endif %}
```

---

## Best Practices

### 1. Import Models in __init__.py (Base Modules Only)

**Note:** This applies to base modules (in `modules/base/`) shipped with sparQ. Custom apps in `data/modules/apps/` don't need this pattern.

For base modules, explicitly import all models in `__init__.py`:

```python
# modules/base/billing/__init__.py
from .module import BillingModule

# Import all models to ensure they're registered with SQLAlchemy
from .models.invoice import Invoice, InvoiceLineItem  # noqa: F401
from .models.payment import Payment  # noqa: F401

module_instance = BillingModule()
```

This ensures SQLAlchemy relationships work even when the module is disabled.

### 2. Keep Modules Independent

- Only depend on `core` unless necessary
- Don't import from other modules directly
- Use hooks for inter-module communication

### 3. Consistent Structure

Use `cd sdk && make app name=yourapp` to scaffold with correct structure:

```
data/modules/apps/yourapp/

├── __init__.py            # Only: module_instance = YourAppModule()
├── __manifest__.py        # manifest = {...} with mappid
├── module.py              # Module class with hooks
├── controllers/
│   ├── __init__.py
│   └── routes.py          # Blueprint definition
├── models/
│   ├── __init__.py
│   └── *.py               # @ModelRegistry.register models
├── views/
│   ├── templates/
│   │   └── yourapp/           # Namespaced templates
│   │       ├── desktop/       # Desktop templates
│   │       │   ├── index.html
│   │       │   └── partials/
│   │       │       └── _*.html
│   │       └── mobile/        # Mobile templates (optional)
│   └── assets/
│       └── css/
│           └── yourapp.css
└── lang/
    ├── en.json
    └── es.json
```

### 4. Route Prefix Convention

Define the URL prefix **only** in `get_routes()`:

```python
# CORRECT - single source of truth
def get_routes(self):
    return [(blueprint, "/yourmodule")]

# WRONG - don't register blueprint in __init__.py
# module_instance.register_blueprint(bp, "/yourmodule")  # Don't do this
```

### 5. Sample Data Pattern

```python
@classmethod
def create_sample_data(cls):
    """Idempotent sample data creation."""
    if not cls.query.first():  # Only if table is empty
        cls.create("Sample 1")
        cls.create("Sample 2")
```

### 6. Error Handling

Wrap sample data creation in try/except:

```python
@hookimpl
def init_database(self):
    db.create_all()
    try:
        MyModel.create_sample_data()
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Sample data error: {e}")
```

---

## Troubleshooting

### Module Not Loading

1. Check `module_instance` is exported from `__init__.py`
2. Check for Python import errors (run `python -c "import modules.yourmodule"`)
3. Check manifest is valid Python dict
4. Look for `__DISABLED__` file

### Routes Not Working

1. Verify `get_routes()` returns correct format: `[(blueprint, "/prefix")]`
2. Check blueprint is properly defined
3. Verify URL prefix matches `main_route` in manifest

### Hooks Not Called

1. Verify `@hookimpl` decorator is imported from correct location
2. Ensure method signature matches hook specification
3. Check module is registered with pluggy (no load errors)

### Console Output

On startup, the loader prints a module registry:

```
Database Model Registry:
--------   ----------   --------------------
Module     Model        Table
--------   ----------   --------------------
core       User         user
core       Group        group
tasks      Task         task
```

Check this output to verify modules loaded correctly.

---

## Example: Complete Module

Here's a complete minimal module. Use `cd sdk && make app name=notes` to scaffold, then customize:

```python
# data/modules/apps/notes/__manifest__.py
manifest = {
    "name": "Notes",
    "version": "1.0",
    "mappid": "n0t3s1",  # Auto-generated by SDK
    "main_route": "/notes",
    "icon_class": "fa-solid fa-sticky-note",
    "type": "App",
    "color": "#ffc107",
    "depends": ["core"],
    "description": "Simple note taking",
}
```

The app will be accessible at `/m/n0t3s1/notes`.

```python
# data/modules/apps/notes/__init__.py
from .module import NotesModule
module_instance = NotesModule()
__all__ = ["module_instance"]
```

```python
# data/modules/apps/notes/module.py
from system.db.database import db
from system.module.hooks import hookimpl

class NotesModule:
    def get_routes(self):
        from .controllers.routes import blueprint
        return [(blueprint, "/notes")]

    @hookimpl
    def init_database(self):
        db.create_all()
        from .models.note import Note
        Note.create_sample_data()
```

```python
# data/modules/apps/notes/models/note.py
from system.db.database import db
from system.db.decorators import ModelRegistry

@ModelRegistry.register
class Note(db.Model):
    __tablename__ = "note"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text)

    @classmethod
    def create_sample_data(cls):
        if not cls.query.first():
            db.session.add(cls(title="Welcome", content="Your first note"))
            db.session.commit()
```

```python
# data/modules/apps/notes/controllers/routes.py
from flask import Blueprint
from flask_login import login_required
from system.device.template import render_device_template
from ..models.note import Note

blueprint = Blueprint(
    "notes_bp", __name__,
    template_folder="../views/templates",
    static_folder="../views/assets",
)

@blueprint.route("/")
@login_required
def index():
    return render_device_template("notes/desktop/index.html", notes=Note.query.all())
```

```html
<!-- data/modules/apps/notes/views/templates/notes/desktop/index.html -->
{% extends "core/desktop/base.html" %}
{% block content %}
<div class="container mt-4">
    <h1>{{ _("Notes") }}</h1>
    {% for note in notes %}
    <div class="card mb-2">
        <div class="card-body">
            <h5>{{ note.title }}</h5>
            <p>{{ note.content }}</p>
        </div>
    </div>
    {% endfor %}
</div>
{% endblock %}
```
