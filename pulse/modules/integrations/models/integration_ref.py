# Copyright (c) 2025-2026 sparQ Software LLC.

"""IntegrationRef model — generic external-reference link.

One row per (sparQ object, provider, external issue). Stores the cached
GitHub issue state so chips can render without a live API call on every
page load.

Classes:
    IntegrationRef: Links a sparQ object to an external provider resource.
"""

from datetime import datetime

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.workspace import WorkspaceMixin
from system.db.raise_on_lazy import LAZY


@ModelRegistry.register
class IntegrationRef(db.Model, WorkspaceMixin):
    """Generic external-reference row linking a sparQ object to a provider resource.

    object_type + object_id identify the sparQ entity (task, comment,
    post, blocker). provider + external_id identify the external resource.

    Attributes:
        provider: Provider slug, e.g. "github".
        external_id: External resource identifier, e.g. issue number as string.
        external_repo: Owner/repo slug, e.g. "acme/my-repo".
        object_type: sparQ entity type: "task", "comment", "post", "blocker".
        object_id: Primary key of the sparQ entity.
        cached_state: Last-known issue state dict (title, state, assignee_login, …).
        cached_at: When cached_state was last refreshed.
        linked_task_id: FK to Task for "Open + Linked" chip state.
    """

    __tablename__ = "integration_ref"

    id = db.Column(db.Integer, primary_key=True)

    provider = db.Column(db.String(50), nullable=False)
    external_id = db.Column(db.String(100), nullable=False)
    external_repo = db.Column(db.String(255), nullable=False)

    object_type = db.Column(db.String(50), nullable=False)
    object_id = db.Column(db.Integer, nullable=False)

    # Cached GitHub issue state; refreshed by webhook events.
    # Shape: {title, state, assignee_login, html_url, labels, opened_by, opened_at}
    cached_state = db.Column(db.JSON, nullable=True)
    cached_at = db.Column(db.DateTime, nullable=True)

    # Set when a paired Task exists — drives the "Open + Linked" chip state.
    linked_task_id = db.Column(
        db.Integer,
        db.ForeignKey("task.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    linked_task = db.relationship(
        "Task",
        foreign_keys=[linked_task_id],
        lazy=LAZY,
    )

    __table_args__ = (
        db.UniqueConstraint(
            "workspace_id",
            "provider",
            "external_id",
            name="uq_integration_ref_ts_provider_issue",
        ),
        db.Index(
            "ix_integration_ref_external",
            "workspace_id",
            "provider",
            "external_repo",
            "external_id",
        ),
        db.Index(
            "ix_integration_ref_object",
            "workspace_id",
            "object_type",
            "object_id",
        ),
    )

    # ── Class methods ─────────────────────────────────────────────────────────

    @classmethod
    def get_for_object(
        cls, object_type: str, object_id: int
    ) -> list["IntegrationRef"]:
        """Return all refs for a given sparQ object in the current workspace.

        Args:
            object_type: "task", "comment", "post", or "blocker".
            object_id: Primary key of the sparQ entity.

        Returns:
            List of IntegrationRef rows.
        """
        return (
            cls.scoped()
            .filter_by(object_type=object_type, object_id=object_id)
            .all()
        )

    @classmethod
    def get_by_external(
        cls, provider: str, external_id: str, workspace_id
    ) -> list["IntegrationRef"]:
        """Return all refs for a given external resource in a specific workspace.

        Does NOT use .scoped() because the workspace context may not be set
        in the calling thread (e.g. webhook background task).

        Args:
            provider: Provider slug.
            external_id: External resource identifier.
            workspace_id: UUID of the target workspace.

        Returns:
            List of IntegrationRef rows.
        """
        return cls.query.filter_by(
            provider=provider,
            external_id=str(external_id),
            workspace_id=workspace_id,
        ).all()

    @classmethod
    def get_all_external_ids(cls, provider: str) -> set[str]:
        """Return all external_id values for a provider in the current workspace.

        Used for orphan detection (UC-7): compare against the live issue list.

        Args:
            provider: Provider slug.

        Returns:
            Set of external_id strings.
        """
        rows = (
            cls.scoped()
            .filter_by(provider=provider)
            .with_entities(cls.external_id)
            .all()
        )
        return {r.external_id for r in rows}

    @classmethod
    def get_or_create(
        cls,
        provider: str,
        external_id: str,
        external_repo: str,
        object_type: str,
        object_id: int,
    ) -> "IntegrationRef":
        """Fetch or create a ref for the given provider + sparQ object pair.

        Args:
            provider: Provider slug.
            external_id: External resource identifier.
            external_repo: Owner/repo slug.
            object_type: sparQ entity type.
            object_id: Primary key of the sparQ entity.

        Returns:
            Existing or newly created IntegrationRef.
        """
        existing = (
            cls.scoped()
            .filter_by(
                provider=provider,
                external_id=str(external_id),
            )
            .first()
        )
        if existing:
            return existing
        ref = cls(
            provider=provider,
            external_id=str(external_id),
            external_repo=external_repo,
            object_type=object_type,
            object_id=object_id,
        )
        db.session.add(ref)
        db.session.commit()
        return ref

    def update_cached_state(self, state: dict) -> None:
        """Refresh the cached GitHub issue state and timestamp.

        Args:
            state: Dict with keys matching the cached_state schema.
        """
        self.cached_state = state
        self.cached_at = datetime.utcnow()
        db.session.commit()

    def link_task(self, task_id: int) -> None:
        """Set the linked_task_id and persist.

        Args:
            task_id: Task.id to link this ref to.
        """
        self.linked_task_id = task_id
        db.session.commit()

    def __repr__(self) -> str:
        return (
            f"<IntegrationRef {self.provider}#{self.external_id} "
            f"→ {self.object_type}:{self.object_id}>"
        )
