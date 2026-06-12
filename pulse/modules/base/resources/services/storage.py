# -----------------------------------------------------------------------------
# sparQ - Document Storage Service
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

import os
import shutil
from werkzeug.datastructures import FileStorage

from ..models.document import Document
from ..models.attachment import Attachment


def get_data_dir() -> str:
    """Get the data directory from environment or default to project_root/data."""
    if "SPARQ_DATA_DIR" in os.environ:
        return os.environ["SPARQ_DATA_DIR"]
    # Default: project_root/data
    # Path: storage.py -> services -> resources -> base -> modules -> sparq
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
    return os.path.join(project_root, "data")


def get_docs_dir() -> str:
    """Get the documents library directory."""
    return os.path.join(get_data_dir(), "documents")


def get_attachments_dir() -> str:
    """Get the attachments archive directory."""
    return os.path.join(get_data_dir(), "attachments")


def get_resumes_dir() -> str:
    """Get the resumes directory for candidate resume storage."""
    return os.path.join(get_data_dir(), "resumes")


def ensure_directories() -> None:
    """Create docs, attachments, and resumes directories if they don't exist."""
    os.makedirs(get_docs_dir(), exist_ok=True)
    os.makedirs(get_attachments_dir(), exist_ok=True)
    os.makedirs(get_resumes_dir(), exist_ok=True)


def get_storage_filename(uuid: str, original_filename: str) -> str:
    """Generate storage filename from UUID and original filename extension."""
    ext = ""
    if "." in original_filename:
        ext = "." + original_filename.rsplit(".", 1)[1].lower()
    return uuid + ext


def save_to_library(file: FileStorage, document: Document) -> str:
    """Save uploaded file to the library directory.

    Args:
        file: The uploaded file from request.files
        document: The Document model instance (must have uuid set)

    Returns:
        The full path to the saved file
    """
    storage_name = get_storage_filename(document.uuid, document.filename)
    file_path = os.path.join(get_docs_dir(), storage_name)
    file.save(file_path)
    return file_path


def get_library_path(document: Document) -> str:
    """Get the full filesystem path for a library document."""
    storage_name = get_storage_filename(document.uuid, document.filename)
    return os.path.join(get_docs_dir(), storage_name)


def get_attachment_path(attachment: Attachment) -> str:
    """Get the full filesystem path for an attachment."""
    storage_name = get_storage_filename(attachment.uuid, attachment.filename)
    return os.path.join(get_attachments_dir(), storage_name)


def delete_from_library(document: Document) -> bool:
    """Delete a file from the library directory.

    Args:
        document: The Document model instance

    Returns:
        True if file was deleted, False if it didn't exist
    """
    file_path = get_library_path(document)
    if os.path.exists(file_path):
        os.remove(file_path)
        return True
    return False


def copy_to_attachments(document: Document) -> Attachment:
    """Copy a file from library to attachments archive.

    The original document remains in the library. A new attachment is created
    with its own UUID and the file is copied to the attachments folder.

    Args:
        document: The Document model instance to copy

    Returns:
        New Attachment model instance
    """
    # Get source path
    source_path = get_library_path(document)

    # Create attachment record (new UUID for the attachment copy)
    attachment = Attachment.create(
        filename=document.filename,
        mime_type=document.mime_type,
        size_bytes=document.size_bytes,
    )

    # Get destination path
    dest_path = get_attachment_path(attachment)

    # Copy the file (original stays in library)
    if os.path.exists(source_path):
        shutil.copy2(source_path, dest_path)

    return attachment


def save_to_attachments(file: FileStorage, attachment: Attachment) -> str:
    """Save uploaded file directly to the attachments directory.

    Used when uploading and attaching in one step (skipping library).

    Args:
        file: The uploaded file from request.files
        attachment: The Attachment model instance (must have uuid set)

    Returns:
        The full path to the saved file
    """
    storage_name = get_storage_filename(attachment.uuid, attachment.filename)
    file_path = os.path.join(get_attachments_dir(), storage_name)
    file.save(file_path)
    return file_path


def save_to_resumes(file: FileStorage, attachment: Attachment) -> str:
    """Save uploaded resume file to the resumes directory.

    Args:
        file: The uploaded file from request.files
        attachment: The Attachment model instance (must have uuid set)

    Returns:
        The full path to the saved file
    """
    os.makedirs(get_resumes_dir(), exist_ok=True)
    storage_name = get_storage_filename(attachment.uuid, attachment.filename)
    file_path = os.path.join(get_resumes_dir(), storage_name)
    file.save(file_path)
    return file_path


def get_resume_path(attachment: Attachment) -> str:
    """Get the full filesystem path for a resume attachment."""
    storage_name = get_storage_filename(attachment.uuid, attachment.filename)
    return os.path.join(get_resumes_dir(), storage_name)
