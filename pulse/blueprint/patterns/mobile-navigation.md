# Mobile Navigation Patterns

> Hybrid: hamburger drawer for global nav, bottom tabs for within-module sub-nav.

---

## Table of Contents

- [Philosophy](#philosophy)
- [Navigation Architecture](#navigation-architecture)
- [Implementation](#implementation)
- [Primary Drawer](#primary-drawer)
- [Bottom Tabs (Module Sub-Nav)](#bottom-tabs-module-sub-nav)
- [More Menu (Bottom Sheet)](#more-menu-bottom-sheet)
- [Active State](#active-state)
- [CSS Variables](#css-variables)
- [Template Reference](#template-reference)

---

## Philosophy

Mobile navigation follows a **hybrid pattern**:

1. **Hamburger drawer** (top-left) for global module-to-module navigation — mirrors the desktop sidebar (`core/desktop/nav_primary.html`)
2. **Bottom tabs** for within-module sub-nav (e.g., Sync's Updates/Board) — thumb-friendly access to a module's features

**Key rules:**

- Never go deeper than 2 levels (Module → Feature → Screen)
- The drawer is always reachable — hamburger is in the header on every page
- Module name is owned by the page template (not a header back-arrow)
- Bottom tabs are reserved for *within* a module — never global navigation
- Maximum 4-5 bottom tabs (including "More") per module

---

## Navigation Architecture

```
┌─────────────────────────────────┐
│ [☰]    Workspace ▾    [🔔][👤] │   ← global header: drawer + workspace + actions
├─────────────────────────────────┤
│                                 │
│         Page Content            │
│                                 │
├─────────────────────────────────┤
│ Tab 1 │ Tab 2 │ Tab 3 │  More   │   ← module's own sub-nav (optional)
└─────────────────────────────────┘
```

Opening the hamburger reveals the global drawer:

```
┌──────────────┐
│ sparQ    [×] │
├──────────────┤
│ 🏠 Home      │
│ 💬 Chat      │
│ 🔄 Sync      │
│ 📁 Projects  │
│ ⚡ Actions   │
│ ⏰ Time      │
│ 📄 Docs      │
│ 📅 Calendar  │
│ 👥 Team      │
├──────────────┤
│ ⚙  Settings │   ← admin-only
└──────────────┘
```

**Two navigation layers:**

| Layer | Purpose | Location |
|-------|---------|----------|
| Global (primary) | Switch between modules | Hamburger drawer (top-left) |
| Module features | Navigate within a module | Bottom tabs |

---

## Implementation

### 1. Base Template Structure

`core/mobile/base.html` provides:
- A hamburger button (top-left) wired to Alpine state `drawerOpen`
- The centered workspace switcher (top-middle)
- Bell + user avatar (top-right)
- `{% include "core/mobile/_drawer.html" %}` — renders the primary nav drawer **at body root** (not inside the header — see stacking-context rule below)
- An **empty** `{% block mobile_bottom_nav %}{% endblock %}` — modules override to add their own sub-nav

```html
<!-- core/mobile/base.html (abridged) -->
<body x-data="{ drawerOpen: false, alertsOpen: false, tsOpen: false }">
    <header class="mobile-header">
        <div class="mobile-header-left">
            <button class="mobile-hamburger" @click="drawerOpen = true" aria-label="{{ _('Menu') }}">
                <i class="fas fa-bars"></i>
            </button>
        </div>
        <div class="mobile-header-center">
            <!-- workspace name + switcher (tap to switch) -->
        </div>
        <div class="mobile-header-actions">
            <!-- bell + user avatar -->
        </div>
    </header>

    <!-- ... main content ... -->

    {% block mobile_bottom_nav %}{% endblock mobile_bottom_nav %}

    <!-- Overlay surfaces live at body root, NOT inside <header> -->
    {% include "core/mobile/_drawer.html" %}
    <!-- alerts sheet, workspace picker sheet, etc. -->
</body>
```

> **Stacking-context rule.** `.mobile-header` uses `position: fixed; z-index: 1020`, which creates a new stacking context. Any overlay nested inside it is trapped in that context and cannot paint above `.mobile-bottom-nav` (`z-index: 1030`) regardless of its own z-index. Mount the drawer, bottom sheets, and modal overlays as **siblings** of the header and bottom nav — under a single `x-data` scope on `<body>` so Alpine state stays shared. This mirrors the `#modal-container` placement.

### 2. Adding a Destination to the Drawer

Edit `core/mobile/_drawer.html` — add an entry to `primary_items`:

```jinja
{% set primary_items = [
    {"id": "home",   "label": "Home",   "icon": "fas fa-house", "url": "/dashboard/", "prefix": "/dashboard"},
    ...
    {"id": "myapp",  "label": "MyApp",  "icon": "fas fa-star",  "url": "/myapp/",     "prefix": "/myapp"},
] %}
```

The drawer mirrors `core/desktop/nav_primary.html` — keep the two lists in sync when adding top-level destinations. The active-state exclusion rules (e.g., sync ≠ chat/calendar/projects) must match exactly in both files.

### 3. Module Bottom Tab Override (Optional)

### Module Layout Override

Modules that have multiple features create a layout that extends base and overrides the bottom nav for within-module sub-tabs:

```
modules/base/yourmodule/views/templates/yourmodule/mobile/
├── layout.html          # Extends core/mobile/base.html
├── index.html           # Landing page
├── feature1/
│   └── index.html       # Feature page
└── settings.html        # Settings page
```

**layout.html structure:**

```html
{% extends "core/mobile/base.html" %}

{% block mobile_bottom_nav %}
<!-- Module-specific bottom tabs -->
<nav class="mobile-bottom-nav" x-data="{ moreOpen: false }">
    <!-- Feature tabs — wrap each in .mobile-nav-btn for active-state + badge styling -->
    <div class="mobile-nav-btn {% if request.path.startswith('/yourmodule/feature1') %}active{% endif %}">
        <a href="{{ url_for('yourmodule_bp.feature1') }}" aria-label="{{ _('Feature 1') }}">
            <i class="fas fa-icon1"></i>
            <span>{{ _("Feature 1") }}</span>
        </a>
    </div>

    <div class="mobile-nav-btn {% if request.path.startswith('/yourmodule/feature2') %}active{% endif %}">
        <a href="{{ url_for('yourmodule_bp.feature2') }}" aria-label="{{ _('Feature 2') }}">
            <i class="fas fa-icon2"></i>
            <span>{{ _("Feature 2") }}</span>
        </a>
    </div>

    <!-- More button (opens bottom sheet) -->
    <div class="mobile-nav-btn">
        <button @click="moreOpen = true">
            <i class="fas fa-ellipsis-h"></i>
            <span>{{ _("More") }}</span>
        </button>
    </div>

    <!-- Bottom sheet overlay -->
    <div class="bottom-sheet-overlay"
         x-show="moreOpen"
         x-transition:enter="..."
         @click="moreOpen = false">
    </div>

    <!-- Bottom sheet -->
    <div class="bottom-sheet" x-show="moreOpen" x-transition:enter="...">
        <div class="bottom-sheet-handle"></div>
        <div class="bottom-sheet-content">
            <!-- Overflow items here -->
        </div>
    </div>
</nav>
{% endblock mobile_bottom_nav %}
```

---

## Bottom Tabs

### Tab Structure

```html
<div class="mobile-nav-btn {% if request.path.startswith('/module/feature') %}active{% endif %}">
    <a href="{{ url_for('module_bp.feature') }}" aria-label="{{ _('Label') }}">
        <i class="fas fa-icon"></i>
        <span>{{ _("Label") }}</span>
    </a>
</div>
```

### Tab Rules

| Rule | Guideline |
|------|-----------|
| Max tabs | 4-5 (including More) |
| Icons | FontAwesome, single meaning |
| Labels | 1-2 words max |
| Touch target | Minimum 44px height |
| Active state | Uses `--module-color` |

### Recommended Tab Sets

**Connect module:**
```
Chat | Calendar | Board | More
```

**CRM module:**
```
Pipeline | Contacts | Tasks | More
```

**Team module:**
```
Directory | Schedule | Time | More
```

---

## More Menu (Bottom Sheet)

The "More" tab opens a bottom sheet with overflow items.

### Standard Structure

```html
<div class="bottom-sheet" x-show="moreOpen">
    <div class="bottom-sheet-handle"></div>
    <div class="bottom-sheet-content">
        <!-- Back to dashboard -->
        <a href="{{ url_for('dashboard_bp.index') }}" class="bottom-sheet-item">
            <i class="fas fa-arrow-left"></i>
            <span>{{ _("Dashboard") }}</span>
        </a>

        <!-- Settings (admin only) -->
        {% if current_user.is_admin %}
        <a href="{{ url_for('module_bp.settings') }}" class="bottom-sheet-item">
            <i class="fas fa-cog"></i>
            <span>{{ _("Settings") }}</span>
        </a>
        {% endif %}

        <!-- Back to home -->
        <a href="{{ url_for('dashboard_bp.index') }}" class="bottom-sheet-item">
            <i class="fas fa-house"></i>
            <span>{{ _("Home") }}</span>
        </a>
    </div>
</div>
```

### Bottom Sheet CSS

```css
.bottom-sheet-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.3);
    z-index: 200;
}

.bottom-sheet {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: var(--color-white);
    border-radius: 1rem 1rem 0 0;
    padding: 0.5rem 1rem calc(1rem + var(--safe-area-bottom));
    z-index: 201;
    box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.15);
}

.bottom-sheet-handle {
    width: 36px;
    height: 4px;
    background: var(--color-gray-300);
    border-radius: 2px;
    margin: 0 auto 1rem;
}

.bottom-sheet-item {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 0.875rem 0.5rem;
    color: var(--color-gray-700);
    text-decoration: none;
    border-radius: 0.5rem;
}

.bottom-sheet-item:active {
    background: var(--color-gray-100);
}

.bottom-sheet-item i {
    width: 24px;
    text-align: center;
    color: var(--color-gray-500);
}
```

---

## Floating Action Button (FAB)

Use a FAB for the primary creation action on a mobile page. Styles are defined in `mobile.css` — do not redefine `.fab` in module layouts.

### Usage

```html
<!-- Link-based (navigates to form) -->
<a href="{{ url_for('module_bp.create') }}" class="fab" aria-label="{{ _('Create') }}">
    <i class="fas fa-plus"></i>
</a>

<!-- Button-based (triggers HTMX or Alpine action) -->
<button class="fab"
        hx-get="{{ url_for('module_bp.create_modal') }}"
        hx-target="#modals"
        hx-swap="innerHTML"
        aria-label="{{ _('Create') }}">
    <i class="fas fa-plus"></i>
</button>
```

### Rules

| Rule | Guideline |
|------|-----------|
| Class | Always use `.fab` — no module-prefixed variants |
| Color | Always `--color-primary` (brand blue, not module color) |
| CSS | Defined in `mobile.css` — never inline or redefine |
| Per page | Maximum 1 FAB |
| Placement | In the page template, not the module layout |
| Icon | Usually `fa-plus`; any single FontAwesome icon |
| aria-label | Required for accessibility |

---

## Active State

Use URL path matching for active state (works across page refreshes):

```html
{% if request.path.startswith('/module/feature') %}active{% endif %}
```

### Active Tab CSS

Active-state styles are defined globally in `core/views/assets/css/mobile.css` — do not redefine them per module. Override `--module-color` on the module body class to theme them.

```css
.mobile-nav-btn.active a,
.mobile-nav-btn.active button {
    color: var(--color-primary);
}

.mobile-nav-btn.active a::after,
.mobile-nav-btn.active button::after {
    content: '';
    position: absolute;
    top: 0;
    left: 50%;
    transform: translateX(-50%);
    width: 24px;
    height: 3px;
    background: var(--color-primary);
    border-radius: 0 0 3px 3px;
}
```

---

## CSS Variables

Mobile navigation uses these CSS variables:

```css
:root {
    /* Module theming */
    --module-color: #10b981;        /* Set per module */

    /* Safe areas (iOS) */
    --safe-area-top: env(safe-area-inset-top, 0px);
    --safe-area-bottom: env(safe-area-inset-bottom, 0px);

    /* Nav dimensions */
    --mobile-nav-height: 56px;
    --mobile-header-height: 56px;
}

/* Module colors */
.connect-app { --module-color: #10b981; }  /* Green */
.crm-app { --module-color: #3b82f6; }      /* Blue */
.team-app { --module-color: #8b5cf6; }     /* Purple */
```

---

## Template Reference

### Complete Layout Example

See `modules/base/connect/views/templates/connect/mobile/layout.html` for a full implementation.

### Page Template

```html
{% extends "yourmodule/mobile/layout.html" %}

{% block title %}{{ _("Feature") }} - {{ _("Module") }}{% endblock %}

{% block app_class %}yourmodule-app{% endblock %}

{% block module_content %}
<div class="mobile-page-container">
    <!-- Page content -->
</div>
{% endblock %}
```

### Device-Aware Rendering

Controllers should use `render_device_template()` for automatic mobile/desktop switching:

```python
from system.device.template import render_device_template

@blueprint.route("/feature")
@login_required
def feature():
    return render_device_template(
        "yourmodule/desktop/feature/index.html",  # Desktop path
        data=data,
        active_page="feature",
    )
```

This automatically serves `yourmodule/mobile/feature/index.html` on mobile devices if it exists.

---

## Checklist for New Modules

1. [ ] If the module is a top-level destination, add it to `core/mobile/_drawer.html` `primary_items` AND to `core/desktop/nav_primary.html` (keep both in sync)
2. [ ] Create `mobile/layout.html` extending `core/mobile/base.html`
3. [ ] If module has multiple features, override `{% block mobile_bottom_nav %}` with 2–5 within-module tabs
4. [ ] If module is single-section (like Projects), leave the default (empty) bottom nav
5. [ ] Use `request.path.startswith()` for active state on both drawer and bottom tabs
6. [ ] Set `--module-color` in module CSS
7. [ ] Create mobile templates for each user-facing feature (admin-only screens stay desktop)
8. [ ] Update controllers to use `render_device_template()`
9. [ ] Test with `?device=mobile` query param
10. [ ] Add FAB for primary creation action (if applicable)

---

**Next:** [Frontend Patterns](frontend.md) | [Module System](module-system.md)
