# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     AI module manifest. Provides the sparQy agent system for natural
#     language actions via the DM interface.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

manifest = {
    "name": "AI",
    "version": "1.0",
    "main_route": "/ai",
    "icon_class": "fas fa-robot",
    "type": "System",
    "color": "#8b5cf6",  # purple
    "depends": ["core", "updates"],
    "description": "AI agent for natural language actions",
    "long_description": "AI provides sparQy, a DM-based assistant where users can type natural language to capture and manage information.",
}
