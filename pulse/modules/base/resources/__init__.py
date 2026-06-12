# -----------------------------------------------------------------------------
# sparQ - Resources Module
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""Resources module for document management and e-signatures.

This module provides file storage, document organization, and electronic
signature workflows for contracts and agreements.

Key Models:
    Folder: Hierarchical folder structure for organizing documents.
    Document: File metadata and storage references.
    Attachment: Generic file attachments linkable to any model.
    AttachmentLink: Polymorphic links between attachments and records.
    SignatureRequest: E-signature workflow requests.
    SignatureRecipient: Recipients in a signature workflow.
    SignatureAuditLog: Audit trail for signature actions.

Key Features:
    - Folder-based document organization
    - File upload and storage
    - Attachment system for any model
    - E-signature workflows with audit logging
    - Document templates

Routes:
    /resources - Document browser
    /resources/folders - Folder management
    /resources/esign - E-signature dashboard
"""

from .module import ResourcesModule

# Import all models to ensure they're registered with SQLAlchemy
# This is required even if the module is disabled, as other modules may reference them
from .models.folder import Folder
from .models.document import Document
from .models.attachment import Attachment
from .models.attachment_link import AttachmentLink

# E-Sign models
from .models.settings import ResourcesSettings
from .models.signature_request import SignatureRequest
from .models.signature_recipient import SignatureRecipient
from .models.signature_audit_log import SignatureAuditLog

module_instance = ResourcesModule()

__all__ = [
    "module_instance",
    "Folder",
    "Document",
    "Attachment",
    "AttachmentLink",
    "ResourcesSettings",
    "SignatureRequest",
    "SignatureRecipient",
    "SignatureAuditLog",
]
