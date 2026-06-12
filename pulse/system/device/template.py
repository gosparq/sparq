# -----------------------------------------------------------------------------
# sparQ - Device Template Rendering
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# Device-Aware Template Rendering
#
# Provides render_device_template() as a drop-in replacement for render_template
# that automatically selects mobile templates when available.
# -----------------------------------------------------------------------------

from flask import render_template
from jinja2 import TemplateNotFound

from .detection import is_mobile


def render_device_template(template_name: str, **context) -> str:
    """
    Render a template with automatic mobile/desktop selection.

    On mobile devices, attempts to render the mobile version of the template
    first, falling back to desktop if the mobile version doesn't exist.

    Template naming convention:
        - Desktop: module/desktop/page.html
        - Mobile:  module/mobile/page.html

    Args:
        template_name: Template path (e.g., 'sales/desktop/index.html')
        **context: Template context variables

    Returns:
        Rendered template string

    Example:
        # In a route handler:
        return render_device_template('sales/desktop/customers/list.html', customers=customers)

        # On mobile, this will try:
        # 1. sales/mobile/customers/list.html (if exists)
        # 2. sales/desktop/customers/list.html (fallback)
    """
    if is_mobile():
        mobile_template = _get_mobile_template_name(template_name)
        if mobile_template:
            try:
                return render_template(mobile_template, **context)
            except TemplateNotFound:
                # Fall through to desktop template
                pass

    return render_template(template_name, **context)


def _get_mobile_template_name(desktop_template: str) -> str | None:
    """
    Convert a desktop template path to its mobile equivalent.

    Args:
        desktop_template: Template path like 'sales/desktop/index.html'

    Returns:
        Mobile template path like 'sales/mobile/index.html', or None if
        the template doesn't follow the desktop/mobile convention.
    """
    if "/desktop/" in desktop_template:
        return desktop_template.replace("/desktop/", "/mobile/")
    return None
