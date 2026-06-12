# Copyright (c) 2025-2026 remarQable LLC

"""IntegrationProvider — abstract base class for all external integration adapters.

Each provider implements this interface; the framework calls only these methods,
keeping all provider-specific logic inside the adapter.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from modules.integrations.models.integration_connection import IntegrationConnection


class IntegrationProvider(ABC):
    """Abstract base for integration adapters (GitHub, Jira, Linear, …).

    Subclasses implement the four abstract methods. Everything else —
    OAuth flows, webhook ingestion, chip rendering — delegates here.

    Class Attributes:
        provider_name: Unique slug for this provider (e.g. "github").
    """

    provider_name: str = ""
    palette_shortcut: str = ""  # 2–3 char prefix for the slash palette (e.g. "gh")

    # ── Display ──────────────────────────────────────────────────────────────

    def get_display_info(self) -> dict:
        """Return display metadata shown in Settings > Integrations.

        Returns:
            Dict with keys: name, icon_class, color, description.
        """
        return {
            "name": self.provider_name.title(),
            "icon_class": "fa-solid fa-plug",
            "color": "#6366f1",
            "description": "",
        }

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    @abstractmethod
    def connect(self, workspace_id: int, credentials: dict) -> "IntegrationConnection":
        """Persist a new connection for a workspace.

        Args:
            workspace_id: The workspace being connected.
            credentials: Provider-specific data (e.g. installation_id, repo).

        Returns:
            The newly created or updated IntegrationConnection.
        """

    @abstractmethod
    def disconnect(self, connection: "IntegrationConnection") -> None:
        """Revoke the connection and clean up remote resources.

        Args:
            connection: The active IntegrationConnection to disconnect.
        """

    # ── Webhook ───────────────────────────────────────────────────────────────

    @abstractmethod
    def handle_webhook(
        self,
        connection: "IntegrationConnection",
        event_type: str,
        payload: dict,
    ) -> None:
        """Process an inbound webhook event.

        Called from a background thread — do not access Flask request context.

        Args:
            connection: The IntegrationConnection the event belongs to.
            event_type: Provider-specific event name (e.g. "issues").
            payload: Parsed JSON payload from the webhook body.
        """

    # ── Status ────────────────────────────────────────────────────────────────

    @abstractmethod
    def get_status(self, connection: "IntegrationConnection") -> dict:
        """Return a summary of the current connection state.

        Args:
            connection: The IntegrationConnection to inspect.

        Returns:
            Dict with at least: connected (bool), repo (str|None),
            last_synced_at (datetime|None).
        """

    # ── Deferred actions ─────────────────────────────────────────────────────

    def handle_deferred_action(self, task, action: dict) -> None:
        """Execute an integration action that was deferred until after task creation.

        Called by the task creation route after the task exists, so the action
        can use the task's real urgency_tier, ID, and other properties.

        The default is a no-op.  Providers override this to create tickets,
        link issues, etc.

        Args:
            task: The newly created Task instance.
            action: Provider-specific dict written by the palette panel
                    (e.g. {"action": "create", "title": "...", "body": "..."}).
        """

    # ── Palette ───────────────────────────────────────────────────────────────

    def get_palette_commands(self, task_id: int) -> list[dict]:
        """Return slash-palette commands contributed by this provider.

        Called for each active connection when the palette commands endpoint
        is hit. The default returns an empty list; providers override this to
        add their own commands.

        Each command dict must contain:
            id (str): Unique command identifier (e.g. "github-create").
            label (str): Display label shown in the palette list.
            shortcut (str): Short keyboard hint shown in the palette.
            icon (str): FontAwesome icon class.
            action_url (str): URL that the palette will HTMX-load as the
                              action subpanel when the command is selected.

        Args:
            task_id: The current task PK (0 for new-task context).

        Returns:
            List of command dicts, possibly empty.
        """
        return []
