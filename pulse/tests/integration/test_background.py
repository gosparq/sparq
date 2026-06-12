# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - Background Task Processing Integration Tests
#
# Tests for system/background/__init__.py. Verifies that submit_task executes
# functions in background threads with proper Flask app context and workspace/
# organization scope preservation.
# -----------------------------------------------------------------------------

from concurrent.futures import Future

import pytest
from flask import current_app, g


@pytest.mark.integration
class TestSubmitTask:
    """Tests for the submit_task background task dispatcher."""

    def test_task_executes_function(self, app):
        from system.background import submit_task

        with app.app_context():
            future = submit_task(lambda: 42)
            assert future.result(timeout=5) == 42

    def test_task_receives_args_and_kwargs(self, app):
        from system.background import submit_task

        def add(a, b, extra=0):
            return a + b + extra

        with app.app_context():
            future = submit_task(add, 3, 7, extra=10)
            assert future.result(timeout=5) == 20

    def test_task_has_app_context(self, app):
        from system.background import submit_task

        def check_app_context():
            return current_app.config["TESTING"]

        with app.app_context():
            future = submit_task(check_app_context)
            assert future.result(timeout=5) is True

    def test_task_preserves_workspace_id(self, app):
        from system.background import submit_task

        def read_workspace_id():
            return getattr(g, "workspace_id", None)

        with app.app_context():
            g.workspace_id = "ws-test-123"
            future = submit_task(read_workspace_id)
            assert future.result(timeout=5) == "ws-test-123"

    def test_task_preserves_organization_id(self, app):
        from system.background import submit_task

        def read_organization_id():
            return getattr(g, "organization_id", None)

        with app.app_context():
            g.organization_id = "org-test-456"
            future = submit_task(read_organization_id)
            assert future.result(timeout=5) == "org-test-456"

    def test_task_exception_logged_not_raised_to_caller(self, app):
        """submit_task itself does not raise; future.result() surfaces the error."""
        from system.background import submit_task

        def blow_up():
            raise ValueError("kaboom")

        with app.app_context():
            future = submit_task(blow_up)
            assert isinstance(future, Future)

            with pytest.raises(ValueError, match="kaboom"):
                future.result(timeout=5)

    def test_returns_future_object(self, app):
        from system.background import submit_task

        with app.app_context():
            future = submit_task(lambda: None)
            assert isinstance(future, Future)
            future.result(timeout=5)
