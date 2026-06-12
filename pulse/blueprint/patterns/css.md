# CSS Architecture

> File organization, template loading, available components, and module CSS rules.

---

## File Architecture

All core CSS lives in `modules/base/core/views/assets/css/`:

| File | Loaded By | Purpose |
|------|-----------|---------|
| `base.css` | Both desktop & mobile templates | Color variables, typography, shared components (badges, buttons, stat cards, alerts, etc.) |
| `desktop.css` | Desktop template only | Header, sidebar navigation, content layout, print styles |
| `mobile.css` | Mobile template only | Mobile header, bottom nav, safe areas, touch interactions |
| `calendar.css` | Modules that need calendar views | Shared calendar system with `cal-` prefix (month, week, day, schedule views) |
| `auth.css` | Login route only | Login page split layout, OAuth buttons |

Module-specific CSS files live inside each module:

```
modules/base/{module}/views/assets/css/{module}.css
data/modules/apps/{app}/views/assets/css/{app}.css
```

---

## Template Loading Flow

```
core/desktop/base.html          core/mobile/base.html
├── base.css                    ├── base.css
├── desktop.css                 ├── mobile.css
└── {% block additional_styles %}
    └── Module layout adds:
        └── <link module.css>
```

### How modules load CSS

```html
{% extends "core/desktop/base.html" %}
{% block app_class %}yourmodule-app{% endblock %}
{% block additional_styles %}
<link rel="stylesheet" href="{{ url_for('yourmodule_bp.static', filename='css/yourmodule.css') }}">
{% endblock %}
```

### Workspace accent cascade

`--workspace-color` is set on `<body>` from the current workspace's chosen palette color:

```html
<body style="--workspace-color: {{ g.workspace_color|default('#E8431A') }}">
```

This drives: header border accent, navigation active states (`color-mix(in srgb, var(--workspace-color) 12%, transparent)`), accent-colored icon/link highlights, and `--color-primary*` variants.

**Modules do not define their own accent.** All modules share one accent via `--workspace-color`. The old `--module-color` alias has been fully removed — do not use it.

See [Color System](colors.md) for the palette and dark-mode architecture.

---

## CSS Variables

### Colors

See **[Color System](colors.md)** for the complete color variable reference (primary purple, gray scale, semantic colors, Bootstrap overrides).

### Typography

```css
--font-family-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
--font-size-base: 0.875rem;   /* 14px */
--font-size-sm: 0.8125rem;    /* 13px */
--font-size-lg: 1rem;         /* 16px */
```

### Layout

```css
--breakpoint-mobile: 768px;
--sidebar-width: 240px;
--workspace-color: var(--color-primary);  /* set on <body> from workspace palette */
```

### Mobile Safe Areas

```css
--safe-area-top: env(safe-area-inset-top, 0px);
--safe-area-bottom: env(safe-area-inset-bottom, 0px);
--safe-area-left: env(safe-area-inset-left, 0px);
--safe-area-right: env(safe-area-inset-right, 0px);
```

---

## Available Components (base.css)

These are already built — use them, don't recreate them.

### Stat Cards

```html
<div class="stats-row">
    <div class="stat-card">
        <div class="stat-content">
            <div class="stat-value">42</div>
            <div class="stat-label">Open Tasks</div>
        </div>
    </div>
</div>
```

- `.stats-row` — 4-column grid
- `.stat-card` — White card with shadow
- `.stat-value` — Large number (1.5rem, bold)
- `.stat-label` — Muted description

### Schedule Items

```html
<a href="#" class="schedule-item">
    <div class="schedule-date">
        <span class="schedule-date-num">15</span>
    </div>
    <span>Meeting with client</span>
</a>
```

- `.schedule-item` — Row with date box + title, hover slides right
- `.schedule-date` — Small date box with border

### Quick Actions

```html
<a href="#" class="quick-action" style="--action-color: var(--color-primary)">
    <i class="fas fa-plus"></i> New Item
</a>
```

- `.quick-action` — Clickable action button, uses `--action-color` for hover tint

### Section Titles

```html
<h2 class="section-title"><i class="fas fa-chart-bar"></i> Overview</h2>
```

### Content Layout (desktop.css)

- `.content-wrapper` — Flex container next to sidebar
- `.content-card` — White card with border, padding, min-width 1100px

### Badges

Bootstrap badges are overridden to be subtle (light backgrounds, gray text):

```html
<span class="badge bg-success">Active</span>   <!-- light green bg, gray text -->
<span class="badge bg-danger">Overdue</span>    <!-- light red bg, gray text -->
<span class="badge bg-primary">New</span>       <!-- light purple bg, gray text -->
```

Status workflow badges:
- `.badge-draft` — Gray
- `.badge-submitted` — Amber
- `.badge-approved` — Green
- `.badge-rejected` — Red
- `.badge-invoiced` — Blue

### Buttons

Outline buttons are gray by default, colored on hover:

```html
<button class="btn btn-sm btn-outline-primary">Save</button>      <!-- purple on hover -->
<button class="btn btn-sm btn-outline-secondary">Cancel</button>  <!-- gray on hover -->
<button class="btn btn-sm btn-outline-danger">Delete</button>     <!-- red on hover -->
```

Always use `btn-sm` for compact appearance. See [Frontend Patterns](frontend.md) for button standards.

### Other Components

| Pattern | Classes | Notes |
|---------|---------|-------|
| Alerts/flash messages | `.flash-messages-container`, `.alert` | Fixed top-right, colored left border |
| Search box | `.search-box` | Icon-prefixed input |
| Coming soon placeholder | `.coming-soon` | Centered icon + message |
| Modal overlay | `.modal-overlay`, `.modal-form` | Centered fixed modal |
| App launcher | `.app-launcher-*` | Full-page app grid overlay |
| Chart bars | `.chart-bar` | Vertical bars with hover labels |
| HTMX indicators | `.htmx-indicator` | Hidden by default, shown during requests |
| Soft delete | `.deleted-indicator`, `.deleted-row`, `.deleted-name` | Rose-tinted deleted item styling |
| Visibility | `.mobile-only`, `.desktop-only` | Platform visibility toggles |
| Alpine.js | `[x-cloak]` | Hidden until Alpine initializes |

---

## Desktop Layout (desktop.css)

### Header

- `.app-header` — Sticky white header with `--workspace-color` bottom border
- `.header-content` — Flexbox row (app title left, user nav right)
- `.app-name-btn` — Clickable module name that opens app launcher
- `.user-nav` — Right-side user info and controls

### Sidebar Navigation

- `.side-nav` — 240px fixed-width sidebar with border and shadow
- `.nav-menu` — Unstyled list container
- `.nav-link` — Nav item with icon + label, active state uses `color-mix()` with `--workspace-color`
- `.nav-section` — Grouped nav items with `.nav-section-header` title
- `.nav-section-collapsible` — Collapsible section with chevron toggle
- `.nav-divider` — Horizontal separator line

### Drag & Drop

- `.drag-handle` — Grab cursor icon
- `.sortable-ghost` — Transparent during drag
- `.sortable-chosen` — Light purple highlight on picked item

---

## Mobile Layout (mobile.css)

### Fixed Layout

```
┌─────────────────────────┐
│  .mobile-header (56px)  │  ← fixed top, safe-area-top padding
├─────────────────────────┤
│                         │
│  .mobile-main-content   │  ← fixed between header and nav, scrollable
│                         │
├─────────────────────────┤
│  .mobile-bottom-nav     │  ← fixed bottom, safe-area-bottom padding
└─────────────────────────┘
```

- `.mobile-header` — Fixed top bar with logo and module label
- `.mobile-main-content` — Scrollable content area between header and nav
- `.mobile-bottom-nav` — Fixed bottom tab bar (within-module sub-nav)
- `.mobile-nav-btn` — Tab with icon + label, min 44px touch target
- `.mobile-nav-badge` — Red dot badge on a tab (unread/open count indicator)
- `.mobile-drawer` / `.mobile-drawer-item` — Hamburger drawer for global nav
- `.alerts-sheet` — Bottom slide-up sheet for notifications
- `.bottom-nav-popup` — Popup menu from bottom nav items
- `.fab` — Floating action button above bottom nav, always `--color-primary`

### Mobile App Launcher

The mobile template overrides desktop app launcher classes:
- 3-column grid (vs desktop 6-column)
- Touch-friendly (no hover effects, `:active` states instead)
- Safe area padding
- Pin menus hidden

---

## Shared Calendar System (calendar.css)

All calendar classes use the `cal-` prefix. Loaded on-demand by modules that need calendar views.

### Views

| Class | Layout |
|-------|--------|
| `.cal-month` | 7-column month grid |
| `.cal-week` | 7-column week view |
| `.cal-schedule` | Hourly grid schedule |
| `.cal-day-schedule` | Single day hourly grid |
| `.cal-day-list` | Day card list |

### Components

- `.cal-header-row` / `.cal-header-cell` — Column headers (days of week)
- `.cal-week-row` / `.cal-day-cell` — Grid cells
- `.cal-day-number` — Day number in cell
- `.cal-day-items` — Container for items within a day
- `.cal-month-item` / `.cal-week-item` / `.cal-schedule-item` — Items per view
- `.cal-more-items` — "+N more" overflow link
- `.cal-view-toggle` — View switcher buttons
- `.cal-legend` — Legend for item types
- `.cal-filter` — Filter dropdown

### Item Type Colors

```css
.cal-schedule-item.visit          /* Green #20c997 */
.cal-schedule-item.task           /* Amber #ffc107 */
.cal-schedule-item.event          /* Blue #0d6efd */
.cal-schedule-item.leave          /* Purple #8b5cf6 */
.cal-schedule-item.company-event  /* Blue */
```

### Item Status Colors

```css
.cal-month-item.status-cancelled   /* Red (danger) */
.cal-month-item.status-completed   /* Gray */
.cal-month-item.status-no_show     /* Amber (warning) */
```

---

## Naming Conventions

| Scope | Prefix/Pattern | Examples |
|-------|---------------|----------|
| App-level (header, launcher) | `.app-*` | `.app-header`, `.app-launcher-grid`, `.app-name-btn` |
| Navigation | `.nav-*` | `.nav-link`, `.nav-section`, `.nav-divider` |
| Stats/dashboard | `.stat-*`, `.section-*` | `.stat-card`, `.stat-value`, `.section-title` |
| Calendar | `.cal-*` | `.cal-month`, `.cal-day-cell`, `.cal-schedule-item` |
| Mobile | `.mobile-*` | `.mobile-header`, `.mobile-nav-btn`, `.mobile-drawer` |
| Module-specific | `.{module}-app`, `.{module}-*` | `.sales-app`, `.service-card` |
| Status badges | `.badge-{status}` | `.badge-draft`, `.badge-approved` |
| Soft delete | `.deleted-*` | `.deleted-indicator`, `.deleted-row` |

---

## Module CSS Rules

### Template

```css
/* modules/base/{module}/views/assets/css/{module}.css */

/* Module-specific styles only — accent via --workspace-color (set on body) */
.yourmodule-special-widget {
    border-left: 4px solid var(--workspace-color);
    background: var(--color-white);
    padding: 1rem;
}
```

### Do

- Use `--workspace-color` for all accent colors (already available from `<body>`)
- Use CSS variables for all colors (see [Color System](colors.md))
- Use gray scale for most UI elements (text, borders, backgrounds)
- Reserve purple for interactive elements (buttons, links, active states)
- Use semantic colors only for meaning (success/error/warning)
- Use Bootstrap utility classes first (`d-flex`, `gap-2`, `text-muted`, etc.)
- Use existing base.css components (stat cards, badges, buttons, etc.)
- Keep module CSS under 50-100 lines

### Don't

- Hardcode hex colors — always use `var(--color-*)`
- Duplicate patterns from base.css
- Create custom badge styles (use Bootstrap badge classes)
- Use multiple brand colors (purple + gray only, no rainbow)
- Overuse semantic colors decoratively (green/red/amber are for meaning, not decoration)
- Add responsive breakpoints (desktop/mobile are separate templates)
- CSS Preprocessors/LESS/SASS

---

**Next:** [Color System](colors.md) | [Frontend Patterns](frontend.md) | [Module System](module-system.md)
