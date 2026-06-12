# Copyright (c) 2025-2026 remarQable LLC

"""Integrations settings index — lists all registered providers."""

import logging

from flask import jsonify, request
from flask_login import login_required

from system.auth.decorators import admin_required
from system.device.template import render_device_template
from modules.integrations.registry import all_providers

from . import blueprint
from ..models.integration_connection import IntegrationConnection

logger = logging.getLogger(__name__)


# ── Settings index ────────────────────────────────────────────────────────────


@blueprint.route("/settings")
@blueprint.route("/settings/")
@login_required
@admin_required
def settings_index():
    """Settings > Integrations — list all registered providers with status."""
    provider_classes = all_providers()

    providers = []
    for cls in provider_classes:
        provider = cls()
        connection = IntegrationConnection.get_active(cls.provider_name)
        providers.append(
            {
                "provider": provider,
                "info": provider.get_display_info(),
                "connection": connection,
            }
        )

    return render_device_template(
        "integrations/desktop/index.html",
        providers=providers,
    )


# ── Palette commands ──────────────────────────────────────────────────────────


@blueprint.route("/palette/commands")
@login_required
def palette_commands():
    """Return slash-palette commands aggregated from all active providers.

    Query params:
        task_id (int): Current task PK; 0 for new-task (create modal) context.

    Returns:
        JSON: {"commands": [{id, label, shortcut, icon, action_url}, ...]}
    """
    task_id = request.args.get("task_id", type=int) or 0
    commands = []
    for provider_cls in all_providers():
        connection = IntegrationConnection.get_active(provider_cls.provider_name)
        if connection:
            try:
                commands.extend(provider_cls().get_palette_commands(task_id))
            except Exception:
                logger.exception("palette_commands: provider %s raised", provider_cls.provider_name)
    return jsonify({"commands": commands})
