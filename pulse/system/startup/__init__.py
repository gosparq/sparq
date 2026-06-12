# -----------------------------------------------------------------------------
# sparQ - Startup Package
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# Startup Module
#
# Consolidated Flask application initialization and configuration.
# -----------------------------------------------------------------------------

from .config import configure_app
from .database import init_database, init_realtime, init_logging_capture
from .error_handlers import register_error_handlers
from .extensions import init_extensions
from .request_hooks import register_request_hooks
from .templates import register_context_processors, register_template_filters

__all__ = [
    "configure_app",
    "init_database",
    "init_extensions",
    "init_logging_capture",
    "init_realtime",
    "register_context_processors",
    "register_error_handlers",
    "register_request_hooks",
    "register_template_filters",
]
