# -----------------------------------------------------------------------------
# sparQ - Attachment Model
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""Attachment model for file storage and management.

This module provides the Attachment model for storing file metadata and
references to permanently archived files in the system.

Example:
    Creating an attachment::

        attachment = Attachment.create(
            filename="document.pdf",
            mime_type="application/pdf",
            size_bytes=102400
        )

    Getting an attachment by UUID::

        attachment = Attachment.get_by_uuid("abc-123-def")
"""

from __future__ import annotations

import os
import uuid as uuid_lib
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from werkzeug.datastructures import FileStorage

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.workspace import WorkspaceMixin


@ModelRegistry.register
class Attachment(db.Model, WorkspaceMixin):
    """Attachment model for permanently archived files.

    Attributes:
        id: Primary key.
        uuid: Unique identifier for external references (URL-safe).
        filename: Original filename of the uploaded file.
        mime_type: MIME type of the file (e.g., "application/pdf").
        size_bytes: File size in bytes.
        created_at: Timestamp when the attachment was created.

    Properties:
        extension: File extension extracted from filename.
        size_display: Human-readable file size (e.g., "1.5 MB").
        signature_request: Associated SignatureRequest if this is an e-sign document.
        esign_status: E-signature status (None, pending, completed, expired, cancelled, declined).
    """

    __tablename__ = "attachment"

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    mime_type = db.Column(db.String(100))
    size_bytes = db.Column(db.BigInteger)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def extension(self) -> str:
        """Return file extension."""
        if "." in self.filename:
            return self.filename.rsplit(".", 1)[1].lower()
        return ""

    @property
    def size_display(self) -> str:
        """Return human-readable file size."""
        if not self.size_bytes:
            return "0 B"
        size = self.size_bytes
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.0f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    @classmethod
    def get_by_id(cls, attachment_id: int) -> "Attachment | None":
        """Get attachment by ID."""
        return cls.scoped().filter_by(id=attachment_id).first()

    @classmethod
    def get_by_uuid(cls, uuid: str) -> "Attachment | None":
        """Get attachment by UUID."""
        return cls.scoped().filter_by(uuid=uuid).first()

    @property
    def signature_request(self):
        """Get the signature request for this attachment (if any)."""
        if hasattr(self, "signature_requests_original") and self.signature_requests_original:
            return self.signature_requests_original[0]
        return None

    @property
    def esign_status(self) -> str | None:
        """Get e-sign status for this attachment.

        Returns: None (no e-sign), 'pending', 'completed', 'expired', 'cancelled', 'declined'
        """
        sig_req = self.signature_request
        if not sig_req:
            return None
        # Check if any recipient declined
        for recipient in sig_req.recipients:
            if recipient.status == "declined":
                return "declined"
        return sig_req.status

    @classmethod
    def create(
        cls,
        filename: str,
        mime_type: str | None = None,
        size_bytes: int | None = None,
        uuid: str | None = None,
    ) -> "Attachment":
        """Create a new attachment record."""
        attachment = cls(
            uuid=uuid or str(uuid_lib.uuid4()),
            filename=filename,
            mime_type=mime_type,
            size_bytes=size_bytes,
        )
        db.session.add(attachment)
        db.session.commit()
        return attachment

    @classmethod
    def get_recent_with_sources(cls, limit: int = 20) -> tuple[list["Attachment"], dict[int, str]]:
        """Get recent attachments that have links, with source labels.

        Returns:
            Tuple of (attachments list, dict mapping attachment_id to source label).
        """
        from ..models.attachment_link import AttachmentLink

        entity_type_labels = {
            "task": "Task",
            "project": "Project",
            "chat_message": "Chat Message",
        }

        recent = cls.scoped().order_by(cls.created_at.desc()).limit(limit).all()
        if not recent:
            return [], {}

        att_ids = [a.id for a in recent]
        links = AttachmentLink.scoped().filter(
            AttachmentLink.attachment_id.in_(att_ids)
        ).all()

        sources: dict[int, str] = {}
        linked_ids: set[int] = set()
        for link in links:
            if link.attachment_id not in linked_ids:
                linked_ids.add(link.attachment_id)
                sources[link.attachment_id] = entity_type_labels.get(
                    link.entity_type, link.entity_type.replace("_", " ").title()
                )

        attachments = [a for a in recent if a.id in linked_ids]
        return attachments, sources

    @classmethod
    def create_from_uploads(
        cls,
        files: list,
        entity_type: str,
        entity_ids: list[int],
    ) -> list["Attachment"]:
        """Validate, store, and link uploaded files to entities.

        Args:
            files: List of FileStorage objects from request.files.
            entity_type: The entity type for AttachmentLink (e.g. "task").
            entity_ids: List of entity IDs to link each attachment to.
        """
        import mimetypes as mt

        from ..controllers.docs import ALLOWED_EXTENSIONS, MAX_FILE_SIZE
        from ..models.attachment_link import AttachmentLink
        from ..services import storage

        created = []
        for file in files:
            if not file.filename:
                continue

            ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
            if ext not in ALLOWED_EXTENSIONS:
                continue

            file.seek(0, 2)
            size_bytes = file.tell()
            file.seek(0)

            if size_bytes > MAX_FILE_SIZE or size_bytes == 0:
                continue

            mime_type = mt.guess_type(file.filename)[0]
            attachment = cls.create(
                filename=file.filename,
                mime_type=mime_type,
                size_bytes=size_bytes,
            )
            storage.save_to_attachments(file, attachment)

            for eid in entity_ids:
                AttachmentLink.create(attachment.id, entity_type, eid)

            created.append(attachment)
        return created

    _AUDIO_ALLOWED_TYPES = {"audio/webm", "audio/mp4", "audio/ogg", "audio/mpeg", "audio/wav"}
    _AUDIO_MAX_SIZE = 5 * 1024 * 1024

    @classmethod
    def create_from_audio_upload(cls, file_storage: FileStorage | None) -> Attachment | None:
        """Validate and save an uploaded audio file.

        Returns the saved Attachment, or None if validation fails.
        """
        from werkzeug.utils import secure_filename
        from ..services import storage

        if not file_storage or not file_storage.filename:
            return None
        content_type = file_storage.content_type
        base_type = content_type.split(";")[0].strip() if content_type else ""
        if not base_type or base_type not in cls._AUDIO_ALLOWED_TYPES:
            return None
        file_storage.seek(0, 2)
        size = file_storage.tell()
        file_storage.seek(0)
        if size > cls._AUDIO_MAX_SIZE or size == 0:
            return None
        filename = secure_filename(file_storage.filename) or "audio.webm"
        attachment = cls.create(
            filename=filename,
            mime_type=content_type,
            size_bytes=size,
        )
        storage.save_to_attachments(file_storage, attachment)
        return attachment

    def destroy(self) -> None:
        """Delete this attachment, all its links, and the file on disk."""
        from ..models.attachment_link import AttachmentLink
        from ..services import storage

        file_path = storage.get_attachment_path(self)
        if os.path.exists(file_path):
            os.remove(file_path)

        AttachmentLink.scoped().filter_by(attachment_id=self.id).delete()
        db.session.delete(self)
        db.session.commit()
