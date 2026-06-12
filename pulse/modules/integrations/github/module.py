# Copyright (c) 2025-2026 remarQable LLC

"""GitHubModule — lifecycle hooks and route registration for the GitHub integration."""


class GitHubModule:
    """sparQ integration module for GitHub."""

    def get_routes(self):
        """Return blueprint registrations for the GitHub integration module.

        Returns:
            List of (blueprint, url_prefix) tuples.
        """
        from .routes import github_bp
        from . import api   # noqa: F401 — registers routes on github_bp
        from . import webhook  # noqa: F401 — registers webhook route on github_bp
        return [
            (github_bp, "/integrations"),
        ]
