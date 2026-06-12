# -----------------------------------------------------------------------------
# sparQ - Background Task Processing
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""
Background task processing using fire-and-forget threads.

This module provides a simple way to run tasks in the background without
blocking the HTTP request. Uses Python's ThreadPoolExecutor for simplicity.

Usage:
    from system.background import submit_task

    def my_slow_function(arg1, arg2):
        # Do something slow
        pass

    # Fire and forget
    submit_task(my_slow_function, arg1, arg2)
"""

import logging
from concurrent.futures import ThreadPoolExecutor

from flask import current_app, g

logger = logging.getLogger(__name__)

# Thread pool with 4 workers - sufficient for low-load single-workspace app
executor = ThreadPoolExecutor(max_workers=4)


def submit_task(fn, *args, **kwargs):
    """
    Submit a task to run in a background thread.

    The task runs asynchronously and the function returns immediately.
    Any exceptions are logged but not re-raised.

    Automatically preserves the Flask application context and workspace
    context for the background thread.

    Args:
        fn: The function to execute
        *args: Positional arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function

    Returns:
        Future object (can be ignored for fire-and-forget usage)
    """
    task_name = getattr(fn, "__name__", str(fn))
    logger.info(f"[BACKGROUND] Submitting task: {task_name}")

    # Capture the current Flask app and scope context
    app = current_app._get_current_object()
    workspace_id = getattr(g, "workspace_id", None)
    organization_id = getattr(g, "organization_id", None)

    def wrapped_fn(*a, **kw):
        # Push app context and restore scope context for this thread
        with app.app_context():
            if workspace_id is not None:
                g.workspace_id = workspace_id
            if organization_id is not None:
                g.organization_id = organization_id
            logger.info(f"[BACKGROUND] Starting task: {task_name}")
            try:
                result = fn(*a, **kw)
                logger.info(f"[BACKGROUND] Task completed successfully: {task_name}")
                return result
            except Exception as e:
                logger.error(f"[BACKGROUND] Task failed: {task_name} - {e}", exc_info=True)
                raise

    future = executor.submit(wrapped_fn, *args, **kwargs)
    return future
