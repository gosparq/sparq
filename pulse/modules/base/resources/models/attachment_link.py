# -----------------------------------------------------------------------------
# sparQ - AttachmentLink Model
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from datetime import datetime

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.workspace import WorkspaceMixin
from system.db.raise_on_lazy import LAZY


@ModelRegistry.register
class AttachmentLink(db.Model, WorkspaceMixin):
    """Links attachments to entities (jobs, quotes, contacts, invoices)."""

    __tablename__ = "attachment_link"

    id = db.Column(db.Integer, primary_key=True)
    attachment_id = db.Column(
        db.Integer,
        db.ForeignKey("attachment.id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_type = db.Column(db.String(50), nullable=False)
    entity_id = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship
    attachment = db.relationship("Attachment", backref=db.backref("links", lazy="dynamic"), lazy=LAZY)

    # Unique constraint: same attachment can't be linked twice to same entity
    __table_args__ = (
        db.UniqueConstraint(
            "attachment_id", "entity_type", "entity_id",
            name="uq_attachment_link_entity",
        ),
        db.Index("ix_attachment_link_entity", "entity_type", "entity_id"),
    )

    @classmethod
    def get_for_entity(cls, entity_type: str, entity_id: int) -> list["AttachmentLink"]:
        """Get all attachment links for an entity."""
        from sqlalchemy.orm import joinedload

        return cls.scoped().options(
            joinedload(cls.attachment),
        ).filter(
            cls.entity_type == entity_type,
            cls.entity_id == entity_id,
        ).order_by(cls.created_at.desc()).all()

    @classmethod
    def get_for_entities(cls, entity_types: list[str], entity_id: int) -> list["AttachmentLink"]:
        """Get all attachment links matching any of the given entity types."""
        from sqlalchemy.orm import joinedload

        return cls.scoped().options(
            joinedload(cls.attachment),
        ).filter(
            cls.entity_type.in_(entity_types),
            cls.entity_id == entity_id,
        ).order_by(cls.created_at.desc()).all()

    @classmethod
    def create(cls, attachment_id: int, entity_type: str, entity_id: int) -> "AttachmentLink":
        """Create a new attachment link."""
        link = cls(
            attachment_id=attachment_id,
            entity_type=entity_type,
            entity_id=entity_id,
        )
        db.session.add(link)
        db.session.commit()
        return link

    @classmethod
    def exists(cls, attachment_id: int, entity_type: str, entity_id: int) -> bool:
        """Check if this attachment is already linked to this entity."""
        return cls.scoped().filter(
            cls.attachment_id == attachment_id,
            cls.entity_type == entity_type,
            cls.entity_id == entity_id,
        ).first() is not None

    @classmethod
    def get_by_id(cls, link_id: int) -> "AttachmentLink | None":
        """Get an attachment link by ID."""
        return cls.scoped().filter_by(id=link_id).first()

    @classmethod
    def get_link(cls, attachment_id: int, entity_type: str, entity_id: int) -> "AttachmentLink | None":
        """Get a specific attachment link."""
        return cls.scoped().filter(
            cls.attachment_id == attachment_id,
            cls.entity_type == entity_type,
            cls.entity_id == entity_id,
        ).first()

    def delete(self) -> None:
        """Delete this attachment link."""
        db.session.delete(self)
        db.session.commit()
