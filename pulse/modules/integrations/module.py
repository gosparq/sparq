# Copyright (c) 2025-2026 remarQable LLC

"""IntegrationsModule — framework shell: settings index route only."""


class IntegrationsModule:
    """sparQ module for integration framework (settings index, shared models)."""

    def get_routes(self):
        """Return blueprint registrations for the integrations framework module.

        Returns:
            List of (blueprint, url_prefix) tuples.
        """
        from .controllers import blueprint
        return [
            (blueprint, "/integrations"),
        ]
