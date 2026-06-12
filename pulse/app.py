# -----------------------------------------------------------------------------
# sparQ - Application Entry Point
#
# Main application factory that orchestrates Flask initialization.
# Most implementation details are delegated to system/startup/ modules.
#
# Structure:
#   create_app()         - Application factory (main entry point)
#   _register_plugins()  - Plugin discovery and registration
#   _start_schedulers()       - Background scheduler daemons
#   _parse_args()        - CLI argument handling
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

# Load environment variables from .env file (before other imports)
from dotenv import load_dotenv
import shutil as _shutil
import os as _os

_base_dir = _os.path.dirname(__file__)
_env_file = _os.path.join(_base_dir, ".env")
_env_example = _os.path.join(_base_dir, ".env.example")
_legacy_env = _os.path.join(_base_dir, "data", ".env")

# Fallback: use data/.env if root .env doesn't exist (backward compatibility)
if not _os.path.exists(_env_file) and _os.path.exists(_legacy_env):
    _env_file = _legacy_env

# Create .env from .env.example if it doesn't exist
if not _os.path.exists(_env_file) and _os.path.exists(_env_example):
    _shutil.copy(_env_example, _os.path.join(_base_dir, ".env"))
    _env_file = _os.path.join(_base_dir, ".env")
    print("\n" + "=" * 60)
    print("Created .env from .env.example")
    print("=" * 60 + "\n")

# Replace placeholder SECRET_KEY if still present in .env
if _os.path.exists(_env_file):
    with open(_env_file, "r") as _f:
        _env_content = _f.read()
    if "SECRET_KEY=change-me-to-a-random-string" in _env_content:
        import secrets as _secrets
        _generated_key = _secrets.token_hex(32)
        _env_content = _env_content.replace(
            "SECRET_KEY=change-me-to-a-random-string",
            f"SECRET_KEY={_generated_key}",
        )
        with open(_env_file, "w") as _f:
            _f.write(_env_content)
        print("Generated secure SECRET_KEY automatically.")

load_dotenv(_env_file, override=False)

import os

from flask import Flask

from system.startup import (
    configure_app,
    init_database,
    init_extensions,
    init_logging_capture,
    init_realtime,
    register_context_processors,
    register_error_handlers,
    register_request_hooks,
    register_template_filters,
)


def create_app() -> Flask:
    """Create and configure the Flask application.

    This is the application factory that initializes all components:
    1. Configuration (logging, SQLAlchemy, security settings)
    2. Extensions (database, login manager, WebSocket support)
    3. Module system (discovers and loads all sparQ modules)
    4. Database (schema creation/migration, default data seeding)
    5. Templates (Jinja filters, context processors)
    6. Request handling (before_request hooks, error handlers)
    7. Background services (backup scheduler, translations)

    Returns:
        Configured Flask application instance.
    """
    app = Flask(
        __name__,
        template_folder="modules/base/core/views/templates",
        static_folder="modules/base/core/views/assets",
        static_url_path="/assets",
    )

    # 1. Configure app (logging, SQLAlchemy, security, etc.)
    debug_mode, verbose = configure_app(app)

    # 2. Initialize extensions (db, login_manager, socketio, sock)
    _, socketio, sock = init_extensions(app)

    # 3. Load modules and initialize database
    with app.app_context():
        # Initialize and validate modules
        from system.module.utils import initialize_modules
        module_loader = initialize_modules()
        app.module_loader = module_loader  # type: ignore[attr-defined]

        # Store manifests in app config
        app.config["INSTALLED_MODULES"] = module_loader.manifests

        # Add plugins discovered by the plugins host module
        _register_plugins(app, module_loader)

        # Initialize module registry for conditional features
        # MUST be before register_routes() so module_enabled() works during import
        from system.module.registry import ModuleRegistry
        ModuleRegistry.init_app(app)

        # Register routes
        module_loader.register_routes(app)

        # Ensure API models are in SQLAlchemy metadata before create_all()
        import system.api.models  # noqa: F401
        import system.api.push  # noqa: F401

        # Initialize database schema and seed default data
        init_database(app, module_loader)

        # Initialize OAuth system
        from system.oauth import init_oauth
        init_oauth(app)
        if verbose:
            app.logger.info("OAuth system initialized")

        # Initialize mobile API (/api/v1/)
        from system.api import register_api
        register_api(app)
        if verbose:
            app.logger.info("Mobile API registered")

        # Initialize real-time handlers (SocketIO, WebSocket)
        init_realtime(app, socketio, sock)

        # Initialize logging capture for web console
        init_logging_capture(app)

    # 4. Register template filters and context processors
    register_template_filters(app)
    register_context_processors(app)

    # 5. Register request hooks and error handlers
    register_request_hooks(app)

    # 5b. Scope middleware — must run AFTER set_workspace_context (which
    #     populates g.organization_id / g.workspace_id) and BEFORE any
    #     module-context setup that reads g.scope.
    from system.scope import register_scope_hook
    register_scope_hook(app)

    register_error_handlers(app)

    # 6. CSRF protection (after request hooks so CSRF runs on all routes)
    from system.middleware.csrf import init_csrf
    init_csrf(app)

    # 7. Post-app setup
    with app.app_context():
        # Load translations
        from system.i18n.translation import preload_translations
        preload_translations()

    # Register database CLI commands
    from system.db.cli import register_commands
    register_commands(app)

    # Start background schedulers
    _start_schedulers(app, debug_mode, verbose)

    return app


def _register_plugins(app: Flask, module_loader) -> None:
    """Register plugins discovered by the plugins host module.

    Plugins are user-installable extensions that live in data/plugins/.
    This function adds them to INSTALLED_MODULES and registers their
    hook implementations with the plugin manager.

    Args:
        app: Flask application instance.
        module_loader: Module loader with plugin manager for hook registration.
    """
    try:
        from modules.base.plugins import module_instance as plugins_host

        for plugin in plugins_host.get_discovered_plugins():
            plugin_data = plugin.copy()
            plugin_data["is_plugin"] = True
            plugin_data["folder"] = "plugins"
            app.config["INSTALLED_MODULES"][plugin["name"]] = plugin_data

        # Register plugins with the plugin manager for hook implementations
        plugins_host.register_plugins_with_pm(module_loader.pm)
    except Exception:
        pass  # Plugins module not loaded yet or failed


def _start_schedulers(app: Flask, debug_mode: bool, verbose: bool) -> None:
    """Start background scheduler daemon threads.

    Only starts in production mode, or in the reloader's main process during
    debug mode (to avoid duplicate schedulers from Flask's reloader).

    Args:
        app: Flask application instance (for logging).
        debug_mode: Whether Flask debug mode is enabled.
        verbose: Whether to log scheduler startup.
    """
    if not debug_mode or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        try:
            from system.sync.nudge_scheduler import start_nudge_scheduler
            start_nudge_scheduler(app)
            if verbose:
                app.logger.info("Nudge scheduler started")
        except Exception as e:
            app.logger.warning(f"Failed to start nudge scheduler: {e}")

        try:
            from system.tasks.nudge_scheduler import start_tasks_nudge_scheduler
            start_tasks_nudge_scheduler(app)
            if verbose:
                app.logger.info("Tasks nudge scheduler started")
        except Exception as e:
            app.logger.warning(f"Failed to start action items nudge scheduler: {e}")


def _parse_args() -> None:
    """Parse command line arguments and set environment variables.

    Handles CLI flags like --verbose when running directly via `python app.py`.
    Skipped when running under Gunicorn or other WSGI servers.

    Supported arguments:
        -v, --verbose: Enable verbose startup output (shows all modules/models)
    """
    import argparse
    import sys

    # Only parse args when running directly (not via Gunicorn/WSGI)
    if "gunicorn" in sys.modules or not sys.argv[0].endswith("app.py"):
        return

    parser = argparse.ArgumentParser(description="sparQ Application Server")
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose startup output (shows all modules and models)"
    )
    args, _ = parser.parse_known_args()

    # Set SPARQ_VERBOSE from command line if specified
    if args.verbose:
        os.environ["SPARQ_VERBOSE"] = "1"


# Parse args before creating app
_parse_args()

# Create app instance (used by both Gunicorn and direct run)
app = create_app()


if __name__ == "__main__":
    from system.utils.network import get_local_ip

    # Use environment variable for debug mode (defaults to False for safety)
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() == "true"

    # Startup message - only print in main process (not reloader child)
    host = "0.0.0.0"
    port = os.environ.get("PORT", 8000)
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        local_ip = get_local_ip()
        print("=" * 60)
        print(f"Local:   http://localhost:{port}")
        print(f"Network: http://{local_ip}:{port}")
        print(f"Debug:   {'ON' if debug_mode else 'OFF'}")
        print("=" * 60)

    # Monkey-patch eventlet's wsgi to filter out noisy logs
    try:
        import sys
        import re

        _original_write_output = sys.stderr.write

        # Pattern to match "accepted" connection logs: (12345) accepted ('127.0.0.1', 54321)
        _accepted_pattern = re.compile(r"^\(\d+\) accepted \(")

        def _filtered_write(msg):
            # Filter out console polling requests
            if "/sysadmin/console/logs" in msg:
                return len(msg)
            # Filter out "accepted" connection logs
            if _accepted_pattern.match(msg):
                return len(msg)
            return _original_write_output(msg)

        sys.stderr.write = _filtered_write  # type: ignore[method-assign]

        # Also filter stdout
        _original_stdout_write = sys.stdout.write

        def _filtered_stdout_write(msg):
            if "/sysadmin/console/logs" in msg:
                return len(msg)
            if _accepted_pattern.match(msg):
                return len(msg)
            return _original_stdout_write(msg)

        sys.stdout.write = _filtered_stdout_write  # type: ignore[method-assign]
    except Exception:
        pass

    app.socketio.run(
        app,
        debug=debug_mode,
        host=host,
        port=port,
        allow_unsafe_werkzeug=True,
        log_output=debug_mode,
    )  # type: ignore[attr-defined]
