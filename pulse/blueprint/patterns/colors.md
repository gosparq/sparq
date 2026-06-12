# Color System

> Orange + Gray design system for consistent, professional UI, with per-workspace accent.

---

## Philosophy

The design system uses a **restrained color palette**:
- **Brand Orange** (`#E8431A`) — default workspace accent / primary brand color
- **Gray scale** — everything else (text, borders, backgrounds)
- **Semantic colors** — only when communicating meaning (success, error, warning, info)
- **Workspace accent** — each workspace picks a palette color that cascades as `--workspace-color` on `<body>`; `--color-primary` + variants derive from it via `color-mix()`, so all primary-tinted UI follows automatically

This creates a distinctive, professional look while staying flexible across workspaces and light/dark modes.

---

## CSS Variables

All colors are defined in `modules/base/core/views/assets/css/base.css` as CSS custom properties.

### Primary Colors (derive from workspace accent)

`--color-primary` and its variants track `--workspace-color` (set on `<body>` from `g.workspace_color`) via `color-mix()`. Default workspace color is brand orange `#E8431A`.

| Variable | Derivation | Use |
|----------|-----------|-----|
| `--color-primary` | `var(--workspace-color)` | Main brand color, buttons, links |
| `--color-primary-dark` | `color-mix(workspace 85%, black)` | Hover states |
| `--color-primary-light` | `color-mix(workspace 70%, white)` | Badges, accents |
| `--color-primary-lighter` | `color-mix(workspace 25%, white)` | Light backgrounds |
| `--color-primary-lightest` | `color-mix(workspace 10%, white)` | Very light backgrounds |

In dark mode (`body.dark`), the lighter/lightest variants mix with **black** instead of white to produce dark-tinted surfaces.

### Gray Scale

| Variable | Value | Use |
|----------|-------|-----|
| `--color-gray-900` | `#111827` | Primary text |
| `--color-gray-700` | `#374151` | Secondary text, icons |
| `--color-gray-500` | `#6b7280` | Placeholder text, muted |
| `--color-gray-300` | `#d1d5db` | Borders, dividers |
| `--color-gray-100` | `#f3f4f6` | Backgrounds, hover |
| `--color-gray-50` | `#f9fafb` | Page background |
| `--color-white` | `#ffffff` | Cards, inputs |

### Semantic Colors (Use Sparingly)

| Variable | Value | Use |
|----------|-------|-----|
| `--color-success` | `#10b981` | Success messages, positive actions |
| `--color-success-light` | `#d1fae5` | Success backgrounds |
| `--color-danger` | `#ef4444` | Errors, delete actions |
| `--color-danger-light` | `#fee2e2` | Error backgrounds |
| `--color-warning` | `#f59e0b` | Warnings, caution |
| `--color-warning-light` | `#fef3c7` | Warning backgrounds |
| `--color-info` | `#3b82f6` | Information, links |
| `--color-info-light` | `#dbeafe` | Info backgrounds |

### Workspace Accent

Every workspace picks a palette color (stored in `workspace.color`). The hex is set on `<body>` for each request:

```html
<body style="--workspace-color: {{ g.workspace_color|default('#E8431A') }}; --module-color: {{ g.workspace_color|default('#E8431A') }}">
```

The `--module-color` alias exists for backwards compatibility with existing CSS; both resolve to the same workspace color. **New CSS should use `--workspace-color`.** Modules do not define their own accent.

Palette options (`WORKSPACE_COLORS` in `modules/base/core/models/workspace.py`):

| Key | Hex |
|-----|-----|
| `orange` (default) | `#E8431A` |
| `violet` | `#7C3AED` |
| `indigo` | `#4F46E5` |
| `fuchsia` | `#C026D3` |
| `rose` | `#E11D48` |
| `amber` | `#D97706` |
| `emerald` | `#059669` |
| `teal` | `#0D9488` |
| `sky` | `#0284C7` |
| `slate` | `#475569` |

Drives:
- Header border accent
- Navigation active states (`color-mix(in srgb, var(--workspace-color) 12%, transparent)`)
- Accent-colored icons and highlights
- `--color-primary*` variants (and therefore `.btn-primary`, badges, focus rings, etc.)

---

## Dark Mode

Activation: `body.dark` class, toggled via the user-menu button in `core/desktop/content_header.html`. State persists in `localStorage` under `sparq-dark-mode`. A preload script in `base.html` applies the class before CSS parse to prevent flash.

Architecture: `body.dark` in `base.css` **remaps the raw `--color-*` tokens** to dark equivalents (e.g. `--color-white: #0f172a`, `--color-gray-900: #f9fafb`). Because CSS custom properties resolve at use time, any element that uses `var(--color-*)` automatically adapts.

Bootstrap components that hardcode `--bs-*` vars locally (`.card`, `.form-control`, `.table`, `.table-light`, `.btn-outline-*`, `.btn-dark`) and utility classes (`.bg-light`, `.bg-white`, `.text-dark`, `.badge.bg-light`) have explicit `body.dark` overrides in `base.css` because their own scoping beats our token remap.

Per-shell chrome (header, primary nav, secondary nav, workspace dropdown) has hand-picked dark shades in `desktop.css` under `body.dark .<component>`.

---

## Usage Examples

### Text

```css
/* Primary text */
color: var(--color-gray-900);

/* Secondary/muted text */
color: var(--color-gray-500);

/* Links */
color: var(--color-primary);
```

### Backgrounds

```css
/* Page background */
background-color: var(--color-gray-50);

/* Cards */
background-color: var(--color-white);

/* Hover states */
background-color: var(--color-gray-100);

/* Selected/active */
background-color: var(--color-primary-lightest);
```

### Borders

```css
/* Standard border */
border: 1px solid var(--color-gray-300);

/* Subtle border */
border: 1px solid var(--color-gray-100);

/* Active/focus border */
border-color: var(--color-primary);
```

### Buttons

```css
/* Primary button */
background-color: var(--color-primary);
color: var(--color-white);

/* Primary button hover */
background-color: var(--color-primary-dark);

/* Outline button (default gray, color on hover) */
color: var(--color-gray-500);
border-color: var(--color-gray-300);

/* Outline button hover */
color: var(--color-white);
background-color: var(--color-primary);
```

### Badges

```css
/* Use Bootstrap classes with our colors */
.badge.bg-success  /* Green - positive */
.badge.bg-warning  /* Amber - caution */
.badge.bg-danger   /* Red - negative */
.badge.bg-info     /* Blue - neutral info */
.badge.bg-secondary /* Gray - default */
```

---

## Module CSS Pattern

Every module should have a CSS file that:
1. Defines its `--module-color`
2. Uses CSS variables from base.css
3. Contains only module-specific styles

```css
/* data/modules/apps/yourapp/views/assets/css/yourapp.css */

/* Module color definition */
.yourapp-app { --module-color: var(--color-primary); }

/* Module-specific styles only */
.yourapp-special-card {
    border-left: 4px solid var(--module-color);
    background: var(--color-white);
}

.yourapp-icon {
    color: var(--module-color);
}
```

---

## Do's and Don'ts

### Do

- Use CSS variables for all colors
- Use gray scale for most UI elements
- Reserve purple for interactive elements
- Use semantic colors only for meaning
- Keep module CSS minimal (<100 lines)

### Don't

- Hardcode hex colors in CSS
- Use multiple brand colors (no rainbow)
- Overuse semantic colors decoratively
- Create custom badge styles (use Bootstrap)
- Duplicate base.css patterns in modules

---

## Bootstrap Integration

CSS variables are mapped to Bootstrap for compatibility:

```css
--bs-primary: #7c3aed;
--bs-secondary: #6b7280;
--bs-success: #10b981;
--bs-danger: #ef4444;
--bs-warning: #f59e0b;
--bs-info: #3b82f6;
```

Use Bootstrap utility classes when possible:
- `text-primary`, `text-secondary`, `text-muted`
- `bg-primary`, `bg-light`, `bg-white`
- `border-primary`, `border-secondary`
- `btn-primary`, `btn-outline-primary`

---

## Accessibility

All color combinations meet WCAG AA standards:
- Gray-900 on white: 16.5:1 ratio
- Gray-700 on white: 9.5:1 ratio
- Gray-500 on white: 4.6:1 ratio
- Primary on white: 5.4:1 ratio

For low-contrast text (gray-500), ensure font size is at least 14px.

---

**Next:** [Frontend Patterns](frontend.md) | [Module System](module-system.md)
