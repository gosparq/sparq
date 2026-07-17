# Frontend Patterns

> Bootstrap 5 + Alpine.js + HTMX for modern server-rendered UIs.

---

## Table of Contents

- [Philosophy](#philosophy)
- [Tech Stack](#tech-stack)
- [Alpine.js Patterns](#alpinejs-patterns)
- [HTMX Patterns](#htmx-patterns)
- [Combining Alpine.js and HTMX](#combining-alpinejs-and-htmx)
- [Bootstrap Integration](#bootstrap-integration)
- [CSS](#css)
- [Template Structure](#template-structure)
- [Accessibility](#accessibility)

---

## Philosophy

**No build pipeline. No npm. No webpack.**

- Server-rendered HTML with progressive enhancement
- Alpine.js for reactive client-side state
- HTMX for server-driven updates without page reloads
- Bootstrap 5 for consistent styling
- Self-hosted (vendored) libraries under `/assets/vendor` — no bundling, no CDN dependency

---

## Tech Stack

| Library | Version | Purpose |
|---------|---------|---------|
| Bootstrap | 5.3.2 | CSS framework, components |
| Alpine.js | 3.x | Reactive state, DOM manipulation |
| HTMX | 1.9.10 | Server-driven updates, AJAX |
| FontAwesome | 6.5.1 | Icons |

These libraries are **vendored** into `modules/base/core/views/assets/vendor/`
(`css/`, `js/`, `webfonts/`) and served locally from `/assets/vendor/…` — no
CDN is used. Reference them with `url_for('static', ...)` so they inherit the
app's long-lived caching and `?v=<version>` cache-busting (see
[Deployment](deployment.md#static-asset-caching)).

### Loading in base.html

```html
<!-- In modules/core/views/templates/core/desktop/base.html -->
<head>
    <!-- Bootstrap CSS -->
    <link href="{{ url_for('static', filename='vendor/css/bootstrap.min.css') }}" rel="stylesheet">

    <!-- FontAwesome (CSS references ../webfonts/*.woff2, also vendored) -->
    <link href="{{ url_for('static', filename='vendor/css/fontawesome.min.css') }}" rel="stylesheet">

    <!-- Module CSS -->
    <link href="{{ url_for('static', filename='css/base.css') }}" rel="stylesheet">
</head>
<body>
    <!-- Content -->

    <!-- Bootstrap JS -->
    <script nonce="{{ csp_nonce }}" src="{{ url_for('static', filename='vendor/js/bootstrap.bundle.min.js') }}"></script>

    <!-- Alpine.js -->
    <script nonce="{{ csp_nonce }}" defer src="{{ url_for('static', filename='vendor/js/alpine.min.js') }}"></script>

    <!-- HTMX -->
    <script nonce="{{ csp_nonce }}" src="{{ url_for('static', filename='vendor/js/htmx.min.js') }}"></script>
</body>
```

> **Updating a vendored library:** download the new version into
> `assets/vendor/`, keeping the same filename (Font Awesome also needs its
> `webfonts/` directory). No CDN URL or CSP change required.

---

## Alpine.js Patterns

Alpine.js handles reactive client-side state without a build step.

### Basic Component

```html
<div x-data="{ open: false }">
    <button @click="open = !open">Toggle</button>
    <div x-show="open">
        Content here
    </div>
</div>
```

### State Management

```html
<div x-data="{
    state: 'loading',
    items: [],
    error: null,

    async fetchItems() {
        this.state = 'loading';
        try {
            const response = await fetch('/api/items');
            this.items = await response.json();
            this.state = 'loaded';
        } catch (e) {
            this.error = e.message;
            this.state = 'error';
        }
    }
}" x-init="fetchItems()">

    <!-- Loading state -->
    <div x-show="state === 'loading'">
        <i class="fas fa-spinner fa-spin"></i> Loading...
    </div>

    <!-- Loaded state -->
    <div x-show="state === 'loaded'">
        <template x-for="item in items" :key="item.id">
            <div x-text="item.name"></div>
        </template>
    </div>

    <!-- Error state -->
    <div x-show="state === 'error'" class="alert alert-danger" x-text="error"></div>
</div>
```

### Common Directives

| Directive | Purpose | Example |
|-----------|---------|---------|
| `x-data` | Define component state | `x-data="{ open: false }"` |
| `x-show` | Toggle visibility (CSS) | `x-show="open"` |
| `x-if` | Conditional rendering (DOM) | `x-if="items.length > 0"` |
| `x-text` | Set text content | `x-text="message"` |
| `x-model` | Two-way binding | `x-model="search"` |
| `x-bind` or `:` | Bind attribute | `:class="{ active: isActive }"` |
| `x-on` or `@` | Event listener | `@click="handleClick"` |
| `x-for` | Loop | `x-for="item in items"` |
| `x-init` | Run on init | `x-init="fetchData()"` |

### Form Handling

```html
<form x-data="{
    name: '',
    email: '',
    submitting: false,

    async submit() {
        this.submitting = true;
        await fetch('/api/submit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: this.name, email: this.email })
        });
        this.submitting = false;
    }
}" @submit.prevent="submit">

    <input type="text" x-model="name" class="form-control" placeholder="Name">
    <input type="email" x-model="email" class="form-control" placeholder="Email">

    <button type="submit" class="btn btn-primary" :disabled="submitting">
        <span x-show="!submitting">Submit</span>
        <span x-show="submitting"><i class="fas fa-spinner fa-spin"></i></span>
    </button>
</form>
```

### Computed Properties

```html
<div x-data="{
    items: [],
    search: '',

    get filteredItems() {
        return this.items.filter(i =>
            i.name.toLowerCase().includes(this.search.toLowerCase())
        );
    },

    get itemCount() {
        return this.filteredItems.length;
    }
}">
    <input type="text" x-model="search" placeholder="Search...">
    <p>Showing <span x-text="itemCount"></span> items</p>
    <template x-for="item in filteredItems">
        <div x-text="item.name"></div>
    </template>
</div>
```

### Real Example: Weather Component

From the weather module:

```html
<div class="weather-card"
     x-data="{
         state: 'loading',
         city: 'Minneapolis',
         weather: {},
         errorMessage: '',

         async lookupWeather() {
             this.state = 'loading';
             try {
                 const response = await fetch('/weather/lookup', {
                     method: 'POST',
                     headers: { 'Content-Type': 'application/json' },
                     body: JSON.stringify({ city: this.city })
                 });
                 const data = await response.json();
                 if (data.error) {
                     this.errorMessage = data.error;
                     this.state = 'error';
                 } else {
                     this.weather = data;
                     this.state = 'data';
                 }
             } catch (e) {
                 this.errorMessage = 'Failed to fetch weather';
                 this.state = 'error';
             }
         },

         get weatherIconClass() {
             const iconMap = {
                 '01d': 'sun', '01n': 'moon',
                 '02d': 'cloud-sun', '02n': 'cloud-moon',
                 '03d': 'cloud', '04d': 'cloud',
                 '09d': 'cloud-showers-heavy',
                 '10d': 'cloud-rain',
                 '11d': 'bolt',
                 '13d': 'snowflake',
                 '50d': 'smog'
             };
             return `fas fa-${iconMap[this.weather.icon] || 'question'}`;
         }
     }"
     x-init="lookupWeather()">

    <div class="search-box">
        <input type="text"
               x-model="city"
               @keyup.enter="lookupWeather()"
               placeholder="Enter city name">
        <button @click="lookupWeather()" class="btn btn-primary">
            <i class="fas fa-search"></i>
        </button>
    </div>

    <!-- Loading -->
    <div x-show="state === 'loading'" class="text-center">
        <i class="fas fa-spinner fa-spin fa-2x"></i>
    </div>

    <!-- Data -->
    <div x-show="state === 'data'">
        <i :class="weatherIconClass" class="weather-icon"></i>
        <div class="temperature" x-text="`${Math.round(weather.temp)}°F`"></div>
        <div class="description" x-text="weather.description"></div>
    </div>

    <!-- Error -->
    <div x-show="state === 'error'" class="alert alert-danger" x-text="errorMessage"></div>
</div>
```

---

## HTMX Patterns

HTMX enables server-driven updates without full page reloads.

### Basic Patterns

```html
<!-- GET request, replace target -->
<button hx-get="/items/list"
        hx-target="#item-list"
        hx-swap="innerHTML">
    Load Items
</button>
<div id="item-list"></div>

<!-- POST form -->
<form hx-post="/items/add"
      hx-target="#item-list"
      hx-swap="beforeend">
    <input type="text" name="name">
    <button type="submit">Add</button>
</form>

<!-- DELETE with confirmation -->
<button hx-delete="/items/1"
        hx-confirm="Are you sure?"
        hx-target="closest .item"
        hx-swap="outerHTML">
    Delete
</button>
```

### Common Attributes

| Attribute | Purpose | Example |
|-----------|---------|---------|
| `hx-get` | GET request | `hx-get="/items"` |
| `hx-post` | POST request | `hx-post="/items/add"` |
| `hx-put` | PUT request | `hx-put="/items/1"` |
| `hx-delete` | DELETE request | `hx-delete="/items/1"` |
| `hx-target` | Response target | `hx-target="#container"` |
| `hx-swap` | How to swap content | `hx-swap="innerHTML"` |
| `hx-trigger` | Event trigger | `hx-trigger="click"` |
| `hx-confirm` | Confirmation dialog | `hx-confirm="Delete?"` |
| `hx-indicator` | Loading indicator | `hx-indicator="#spinner"` |

### Swap Options

| Value | Description |
|-------|-------------|
| `innerHTML` | Replace inner HTML (default) |
| `outerHTML` | Replace entire element |
| `beforeend` | Append inside element |
| `afterend` | Insert after element |
| `beforebegin` | Insert before element |
| `none` | Don't swap (for side effects) |

### Modal Pattern

```html
<!-- Trigger button -->
<button hx-get="{{ url_for('yourmodule_bp.modal_new') }}"
        hx-target="#modals"
        hx-swap="innerHTML"
        class="btn btn-primary">
    New Item
</button>

<!-- Modal container -->
<div id="modals"></div>
```

**Controller:**

```python
@blueprint.route("/modal/new")
@login_required
def modal_new():
    """Return modal HTML fragment."""
    return render_template("yourmodule/desktop/partials/_modal.html")
```

**Modal template:**

```html
<!-- partials/_modal.html -->
<div class="modal fade show" style="display: block;" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">{{ _("New Item") }}</h5>
                <button type="button"
                        hx-get="{{ url_for('yourmodule_bp.clear_modal') }}"
                        hx-target="#modals"
                        class="btn-close"></button>
            </div>
            <form hx-post="{{ url_for('yourmodule_bp.create') }}"
                  hx-target="body"
                  hx-swap="none">
                <div class="modal-body">
                    <input type="text" name="name" class="form-control" required>
                </div>
                <div class="modal-footer">
                    <button type="submit" class="btn btn-primary">
                        {{ _("Save") }}
                    </button>
                </div>
            </form>
        </div>
    </div>
</div>
<div class="modal-backdrop fade show"></div>
```

**Clear modal route:**

```python
@blueprint.route("/modal/clear")
def clear_modal():
    """Clear modal container."""
    return ""
```

### HTMX Redirect Pattern

For redirecting after form submission:

```python
from flask import make_response, url_for

@blueprint.route("/create", methods=["POST"])
@login_required
def create():
    """Create item and redirect."""
    name = request.form.get("name")
    Item.create(name)

    # Return HX-Redirect header
    response = make_response()
    response.headers["HX-Redirect"] = url_for("yourmodule_bp.index")
    return response
```

### Inline Editing Pattern

```html
<!-- View mode -->
<div id="item-{{ item.id }}" class="item-row">
    <span>{{ item.name }}</span>
    <button hx-get="{{ url_for('yourmodule_bp.edit_form', id=item.id) }}"
            hx-target="#item-{{ item.id }}"
            hx-swap="outerHTML"
            class="btn btn-sm btn-outline-primary">
        Edit
    </button>
</div>
```

**Edit form partial:**

```html
<!-- partials/_edit_form.html -->
<form id="item-{{ item.id }}"
      hx-put="{{ url_for('yourmodule_bp.update', id=item.id) }}"
      hx-target="#item-{{ item.id }}"
      hx-swap="outerHTML"
      class="item-row">
    <input type="text" name="name" value="{{ item.name }}" class="form-control">
    <button type="submit" class="btn btn-sm btn-success">Save</button>
    <button type="button"
            hx-get="{{ url_for('yourmodule_bp.item_row', id=item.id) }}"
            hx-target="#item-{{ item.id }}"
            hx-swap="outerHTML"
            class="btn btn-sm btn-outline-secondary">
        Cancel
    </button>
</form>
```

---

## Combining Alpine.js and HTMX

Use Alpine.js for client-side state, HTMX for server communication.

### Search with Debounce

```html
<div x-data="{ search: '' }">
    <input type="text"
           x-model="search"
           hx-get="/items/search"
           hx-trigger="input changed delay:300ms"
           hx-target="#results"
           :hx-vals="JSON.stringify({ q: search })"
           placeholder="Search...">

    <div id="results"></div>
</div>
```

### Toggle with Server Sync

```html
<div x-data="{ expanded: false }">
    <button @click="expanded = !expanded"
            :hx-get="expanded ? '/details/collapse' : '/details/expand'"
            hx-target="#details"
            hx-swap="innerHTML">
        <span x-show="!expanded">Show Details</span>
        <span x-show="expanded">Hide Details</span>
    </button>

    <div id="details" x-show="expanded"></div>
</div>
```

---

## Bootstrap Integration

### Standard Components

```html
<!-- Card -->
<div class="card">
    <div class="card-header">Header</div>
    <div class="card-body">
        <h5 class="card-title">Title</h5>
        <p class="card-text">Content</p>
    </div>
</div>

<!-- List Group -->
<ul class="list-group">
    {% for item in items %}
    <li class="list-group-item d-flex justify-content-between align-items-center">
        {{ item.name }}
        <span class="badge bg-primary">{{ item.count }}</span>
    </li>
    {% endfor %}
</ul>

<!-- Alert -->
<div class="alert alert-success alert-dismissible fade show">
    {{ message }}
    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
</div>
```

### Flash Messages

```html
<!-- In base.html -->
{% with messages = get_flashed_messages(with_categories=true) %}
    {% if messages %}
        {% for category, message in messages %}
        <div class="alert alert-{{ 'danger' if category == 'error' else category }} alert-dismissible fade show">
            {{ message }}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
        {% endfor %}
    {% endif %}
{% endwith %}
```

### Button Standards

Buttons follow a consistent style across the application: **small, outline style with color on hover**.

#### Core Apps (modules/base/)

Core apps use purple (`--color-primary`) for primary actions:

```html
<!-- Primary action (Save, Create, Submit) -->
<button type="submit" class="btn btn-sm btn-outline-primary">
    {{ _("Save") }}
</button>

<!-- Secondary action (Cancel, Back) -->
<a href="{{ url_for('module_bp.index') }}" class="btn btn-sm btn-outline-secondary">
    {{ _("Cancel") }}
</a>

<!-- Danger action (Delete) - use sparingly -->
<button type="button" class="btn btn-sm btn-outline-danger">
    {{ _("Delete") }}
</button>
```

**Key rules for core apps:**
- Always use `btn-sm` for compact, clean appearance
- Use `btn-outline-primary` for main actions (purple hover)
- Use `btn-outline-secondary` for cancel/back (gray hover)
- Use `btn-outline-danger` only for delete/destructive actions (red hover)
- Buttons appear gray by default, color shows on hover

#### Installed Apps (data/modules/apps/)

Installed apps use their module color for theming. The module color is set via `--module-color` CSS variable and can be used for button styling if needed.

#### Form Button Pattern

```html
<!-- Standard form footer -->
<div class="d-flex gap-2">
    <button type="submit" class="btn btn-sm btn-outline-primary">
        {{ _("Save Changes") }}
    </button>
    <a href="{{ url_for('module_bp.index') }}" class="btn btn-sm btn-outline-secondary">
        {{ _("Cancel") }}
    </a>
</div>
```

#### Table Action Buttons

```html
<!-- Row actions in tables -->
<div class="btn-group btn-group-sm">
    <a href="{{ url_for('module_bp.edit', id=item.id) }}"
       class="btn btn-outline-primary">
        <i class="fas fa-edit"></i>
    </a>
    <button type="button" class="btn btn-outline-danger"
            hx-delete="{{ url_for('module_bp.delete', id=item.id) }}"
            hx-confirm="{{ _('Delete this item?') }}">
        <i class="fas fa-trash"></i>
    </button>
</div>
```

#### Styling (from base.css)

The button styles are defined globally in base.css:
- Default state: gray text (`--color-gray-500`), gray border (`--color-gray-300`)
- Hover state: white text, colored background based on variant

---

## CSS

For CSS architecture, file organization, variables, and available components, see **[CSS Architecture](css.md)**.

For the color system and variable reference, see **[Color System](colors.md)**.

---

## Template Structure

### Base Template Blocks

```html
<!-- modules/core/views/templates/core/desktop/base.html -->
<!DOCTYPE html>
<html lang="{{ g.lang }}">
<head>
    <title>{% block title %}sparQ{% endblock %}</title>
    {% block head %}{% endblock %}
</head>
<body style="--module-color: {{ g.current_module.color|default('#6c757d') }}">
    {% include "header.html" %}

    <main>
        {% block content %}{% endblock %}
    </main>

    {% block scripts %}{% endblock %}
</body>
</html>
```

### Module Template

```html
<!-- data/modules/apps/yourapp/views/templates/yourapp/desktop/index.html -->
{% extends "core/desktop/base.html" %}

{% block title %}{{ _("Your Module") }} - sparQ{% endblock %}

{% block content %}
<div class="container mt-4">
    <h1>{{ _("Your Module") }}</h1>
    <!-- Content here -->
</div>
{% endblock %}

{% block scripts %}
<script nonce="{{ csp_nonce }}">
    // Module-specific JavaScript if needed
</script>
{% endblock %}
```

> **CSP requirement:** All `<script>` tags (inline and external) must include `nonce="{{ csp_nonce }}"`. Inline event handlers (`onclick`, `onchange`) are not allowed — use `addEventListener` or Alpine.js directives (`@click`) instead.

### Partials Naming Convention

- Prefix with underscore: `_modal.html`, `_list.html`
- Place in `partials/` subfolder
- Keep partials focused on single responsibility

```
views/templates/
├── desktop/
│   ├── index.html
│   ├── detail.html
│   └── partials/
│       ├── _list.html
│       ├── _modal.html
│       └── _form.html
└── mobile/
```

---

## Accessibility

### Semantic HTML

```html
<nav>...</nav>
<main>...</main>
<footer>...</footer>

<h1>Page Title</h1>
<h2>Section</h2>
```

### ARIA Labels

```html
<button class="btn btn-danger" aria-label="Delete item">
    <i class="fas fa-trash"></i>
</button>

<button class="btn btn-primary" disabled aria-busy="true">
    <span class="spinner-border spinner-border-sm" aria-hidden="true"></span>
    Loading...
</button>
```

### Focus Management

```html
<a href="#main-content" class="visually-hidden-focusable">
    Skip to main content
</a>

<main id="main-content">...</main>
```

---

**Next:** [Module System](module-system.md) | [i18n](i18n.md) | [Auth](auth.md)
