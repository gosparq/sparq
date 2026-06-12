# -----------------------------------------------------------------------------
# sparQ - Document Model
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

import uuid as uuid_lib
from datetime import datetime

from flask_login import current_user

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.mixins import AuditMixin
from system.db.workspace import WorkspaceMixin
from system.db.raise_on_lazy import LAZY


@ModelRegistry.register
class Document(db.Model, WorkspaceMixin, AuditMixin):
    """Document file in the library.

    Org-scoped (organization_id NOT NULL); workspace_id is a nullable filter
    (set = belongs to a workspace, NULL = org-wide).
    """

    __tablename__ = "document"

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    folder_id = db.Column(
        db.Integer,
        db.ForeignKey("folder.id", ondelete="CASCADE"),
        nullable=True,
    )
    mime_type = db.Column(db.String(100))
    size_bytes = db.Column(db.BigInteger)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    folder = db.relationship("Folder", backref=db.backref("documents", lazy="dynamic"), lazy=LAZY)

    __table_args__ = (
        db.UniqueConstraint("folder_id", "filename", name="uq_document_folder_filename"),
    )

    @property
    def extension(self) -> str:
        """Lowercased file extension, or '' if the filename has no dot."""
        if "." in self.filename:
            return self.filename.rsplit(".", 1)[1].lower()
        return ""

    @property
    def size_display(self) -> str:
        """Human-readable file size (B / KB / MB / GB / TB)."""
        if not self.size_bytes:
            return "0 B"
        size = self.size_bytes
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.0f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    @classmethod
    def get_by_id(cls, doc_id: int) -> "Document | None":
        """Get a document by integer ID within the active scope."""
        return cls.scoped().filter_by(id=doc_id).first()

    @classmethod
    def get_by_uuid(cls, uuid: str) -> "Document | None":
        """Get a document by its public UUID within the active scope."""
        return cls.scoped().filter_by(uuid=uuid).first()

    @classmethod
    def get_by_folder(cls, folder_id: int | None) -> list["Document"]:
        """All documents in a folder (None = root), sorted by filename."""
        return cls.scoped().filter(cls.folder_id == folder_id).order_by(cls.filename).all()

    @classmethod
    def exists_in_folder(cls, filename: str, folder_id: int | None) -> bool:
        """True if a file with this name already exists in the given folder."""
        return cls.scoped().filter(
            cls.filename == filename,
            cls.folder_id == folder_id,
        ).first() is not None

    @classmethod
    def create(
        cls,
        filename: str,
        folder_id: int | None = None,
        mime_type: str | None = None,
        size_bytes: int | None = None,
    ) -> "Document":
        """Create a document in the active scope.

        workspace_id / organization_id are stamped by before_flush listeners.
        """
        doc = cls(
            uuid=str(uuid_lib.uuid4()),
            filename=filename,
            folder_id=folder_id,
            mime_type=mime_type,
            size_bytes=size_bytes,
        )
        if current_user and hasattr(current_user, "id") and current_user.is_authenticated:
            doc.created_by_id = current_user.id
        db.session.add(doc)
        db.session.commit()
        return doc

    def rename(self, new_filename: str) -> "Document":
        """Rename this document; stamps updated_by_id from current_user."""
        self.filename = new_filename
        if current_user and hasattr(current_user, "id") and current_user.is_authenticated:
            self.updated_by_id = current_user.id
        db.session.commit()
        return self

    def move(self, new_folder_id: int | None) -> "Document":
        """Move this document to a different folder (None = root)."""
        self.folder_id = new_folder_id
        if current_user and hasattr(current_user, "id") and current_user.is_authenticated:
            self.updated_by_id = current_user.id
        db.session.commit()
        return self

    def delete(self) -> None:
        """Delete the DB record (physical file removal is the caller's concern)."""
        db.session.delete(self)
        db.session.commit()
