# -----------------------------------------------------------------------------
# sparQ - Resources Module - Documents Controller
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

import mimetypes
import os

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask.typing import ResponseReturnValue
from flask_login import current_user, login_required

from system.device.template import render_device_template
from system.i18n.translation import translate as _

from system.auth.decorators import admin_required

from ..models.folder import Folder
from ..models.document import Document
from ..models.attachment import Attachment
from ..models.attachment_link import AttachmentLink
from ..services import storage

# Allowed file types (matches chat attachments)
ALLOWED_EXTENSIONS = {
    # Images
    "jpg", "jpeg", "png", "gif", "webp",
    # Documents
    "pdf", "doc", "docx", "xls", "xlsx", "txt", "csv", "rtf",
    # Text and code files
    "json", "xml", "html", "css", "js", "py", "yaml", "yml",
    "md", "log", "sql", "sh", "ini", "toml", "cfg", "env",
}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB


def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


docs_blueprint = Blueprint(
    "docs_blueprint",
    __name__,
    template_folder="../views/templates",
    static_folder="../views/assets",
    static_url_path="/assets",
)


def is_htmx_request() -> bool:
    """Check if request is from HTMX."""
    return request.headers.get("HX-Request") == "true"


# -----------------------------------------------------------------------------
# Document Library Routes
# -----------------------------------------------------------------------------


@docs_blueprint.route("/")
@login_required
def index():
    """List root folder contents (workspace scope)."""
    return render_folder_contents(None)


@docs_blueprint.route("/organization/")
@docs_blueprint.route("/organization")
@login_required
def index_organization():
    """List root folder contents at organization scope (Phase 6 §5)."""
    return render_folder_contents(None)


@docs_blueprint.route("/folder/<int:folder_id>")
@login_required
def view_folder(folder_id: int):
    """List folder contents (workspace scope)."""
    folder = Folder.get_by_id(folder_id)
    if not folder:
        flash(_("Folder not found"), "error")
        return redirect(url_for("docs_blueprint.index"))
    return render_folder_contents(folder_id, folder)


@docs_blueprint.route("/organization/folder/<int:folder_id>")
@login_required
def view_folder_organization(folder_id: int):
    """List folder contents at organization scope."""
    folder = Folder.get_by_id(folder_id)
    if not folder:
        flash(_("Folder not found"), "error")
        return redirect(url_for("docs_blueprint.index_organization"))
    return render_folder_contents(folder_id, folder)


def render_folder_contents(folder_id: int | None, current_folder: Folder | None = None):
    """Render folder contents view."""
    from modules.base.core.models.auth_settings import AuthSettings
    from ..models.drive_connection import DriveConnection

    # Get subfolders
    if folder_id:
        folders = Folder.scoped().filter(Folder.parent_id == folder_id).order_by(Folder.name).all()
    else:
        folders = Folder.get_root_folders()

    # Get documents
    documents = Document.get_by_folder(folder_id)

    # Get recent attachments (root view only — attachments aren't in folders)
    attachments = []
    attachment_sources = {}
    if not folder_id:
        attachments, attachment_sources = Attachment.get_recent_with_sources()

    # Build breadcrumbs
    breadcrumbs = []
    if current_folder:
        breadcrumbs = current_folder.breadcrumbs

    # Check for Google Drive connection — workspace-scoped. Org-scope views
    # (and org-only members with no workspace context) skip this block.
    google_drive_connected = False
    from flask import g as _g
    if getattr(_g, "scope", "workspace") != "organization" and getattr(_g, "workspace_id", None):
        auth_settings = AuthSettings.get_instance()
        google_drive_enabled = auth_settings.google_drive_enabled
        drive_connection = DriveConnection.get_google() if google_drive_enabled else None
        google_drive_connected = drive_connection is not None and len(drive_connection.get_selected_folders()) > 0

    context = {
        "active_page": "resources",
        "current_folder": current_folder,
        "folders": folders,
        "documents": documents,
        "attachments": attachments,
        "attachment_sources": attachment_sources,
        "breadcrumbs": breadcrumbs,
        "module_home": "dashboard_bp.index",
        "google_drive_connected": google_drive_connected,
    }

    # HTMX requests get the desktop partial
    if is_htmx_request():
        return render_template("resources/desktop/docs/_file_list.html", **context)

    # Regular requests use device-aware template
    return render_device_template("resources/desktop/docs/index.html", **context)


@docs_blueprint.route("/folder/create", methods=["POST"])
@login_required
@admin_required
def create_folder():
    """Create a new folder."""
    name = request.form.get("name", "").strip()
    parent_id = request.form.get("parent_id")
    parent_id = int(parent_id) if parent_id else None

    if not name:
        flash(_("Folder name is required"), "error")
        return redirect(request.referrer or url_for("docs_blueprint.index"))

    try:
        Folder.create(name=name, parent_id=parent_id)
        flash(_("Folder '%(name)s' created") % {"name": name}, "success")
    except Exception as e:
        flash(_("Error creating folder: %(error)s") % {"error": str(e)}, "error")

    if parent_id:
        return redirect(url_for("docs_blueprint.view_folder", folder_id=parent_id))
    return redirect(url_for("docs_blueprint.index"))


@docs_blueprint.route("/folder/<int:folder_id>/rename", methods=["POST"])
@login_required
@admin_required
def rename_folder(folder_id: int):
    """Rename a folder."""
    folder = Folder.get_by_id(folder_id)
    if not folder:
        flash(_("Folder not found"), "error")
        return redirect(url_for("docs_blueprint.index"))

    new_name = request.form.get("name", "").strip()
    if not new_name:
        flash(_("Folder name is required"), "error")
        return redirect(request.referrer or url_for("docs_blueprint.index"))

    folder.rename(new_name)
    flash(_("Folder renamed to '%(name)s'") % {"name": new_name}, "success")

    if folder.parent_id:
        return redirect(url_for("docs_blueprint.view_folder", folder_id=folder.parent_id))
    return redirect(url_for("docs_blueprint.index"))


@docs_blueprint.route("/folder/<int:folder_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_folder(folder_id: int):
    """Delete a folder and its contents."""
    folder = Folder.get_by_id(folder_id)
    if not folder:
        flash(_("Folder not found"), "error")
        return redirect(url_for("docs_blueprint.index"))

    parent_id = folder.parent_id

    # Delete all documents in this folder from disk
    for doc in folder.documents:
        storage.delete_from_library(doc)

    folder.delete()
    flash(_("Folder deleted"), "success")

    if parent_id:
        return redirect(url_for("docs_blueprint.view_folder", folder_id=parent_id))
    return redirect(url_for("docs_blueprint.index"))


@docs_blueprint.route("/upload", methods=["POST"])
@login_required
def upload():
    """Upload file(s) to library."""
    folder_id = request.form.get("folder_id")
    folder_id = int(folder_id) if folder_id else None

    if "file" not in request.files:
        flash(_("No file selected"), "error")
        return redirect(request.referrer or url_for("docs_blueprint.index"))

    files = request.files.getlist("file")
    uploaded = 0

    for file in files:
        if file.filename:
            # Validate file extension
            if not allowed_file(file.filename):
                flash(_("'%(filename)s' — file type not allowed") % {"filename": file.filename}, "error")
                continue

            # Get file info
            file.seek(0, 2)  # Seek to end
            size_bytes = file.tell()
            file.seek(0)  # Seek back to start

            # Validate file size
            if size_bytes > MAX_FILE_SIZE:
                flash(_("'%(filename)s' exceeds 100 MB limit") % {"filename": file.filename}, "error")
                continue

            # Check for duplicate
            if Document.exists_in_folder(file.filename, folder_id):
                flash(_("'%(filename)s' already exists in this folder") % {"filename": file.filename}, "error")
                continue

            mime_type = mimetypes.guess_type(file.filename)[0]

            # Create document record
            doc = Document.create(
                filename=file.filename,
                folder_id=folder_id,
                mime_type=mime_type,
                size_bytes=size_bytes,
            )

            # Save file to disk
            storage.save_to_library(file, doc)
            uploaded += 1

    if uploaded:
        flash(_("Uploaded %(count)s file(s)") % {"count": uploaded}, "success")

    if folder_id:
        return redirect(url_for("docs_blueprint.view_folder", folder_id=folder_id))
    return redirect(url_for("docs_blueprint.index"))


@docs_blueprint.route("/download/<int:doc_id>")
@login_required
def download(doc_id: int):
    """Download a document from library."""
    doc = Document.get_by_id(doc_id)
    if not doc:
        flash(_("Document not found"), "error")
        return redirect(url_for("docs_blueprint.index"))

    file_path = storage.get_library_path(doc)
    if not os.path.exists(file_path):
        flash(_("File not found on disk"), "error")
        return redirect(url_for("docs_blueprint.index"))

    return send_file(
        file_path,
        download_name=doc.filename,
        as_attachment=True,
    )


@docs_blueprint.route("/document/<int:doc_id>/rename", methods=["POST"])
@login_required
def rename_document(doc_id: int):
    """Rename a document."""
    doc = Document.get_by_id(doc_id)
    if not doc:
        flash(_("Document not found"), "error")
        return redirect(url_for("docs_blueprint.index"))

    if not current_user.is_admin and doc.created_by_id != current_user.id:
        abort(403)

    new_name = request.form.get("name", "").strip()
    if not new_name:
        flash(_("Filename is required"), "error")
        return redirect(request.referrer or url_for("docs_blueprint.index"))

    # Check for duplicate in same folder
    if Document.exists_in_folder(new_name, doc.folder_id):
        flash(_("'%(filename)s' already exists in this folder") % {"filename": new_name}, "error")
        return redirect(request.referrer or url_for("docs_blueprint.index"))

    doc.rename(new_name)
    flash(_("Document renamed to '%(name)s'") % {"name": new_name}, "success")

    if doc.folder_id:
        return redirect(url_for("docs_blueprint.view_folder", folder_id=doc.folder_id))
    return redirect(url_for("docs_blueprint.index"))


@docs_blueprint.route("/document/<int:doc_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_document(doc_id: int):
    """Delete a document from library."""
    doc = Document.get_by_id(doc_id)
    if not doc:
        flash(_("Document not found"), "error")
        return redirect(url_for("docs_blueprint.index"))

    folder_id = doc.folder_id

    # Delete file from disk
    storage.delete_from_library(doc)

    # Delete database record
    doc.delete()
    flash(_("Document deleted"), "success")

    if folder_id:
        return redirect(url_for("docs_blueprint.view_folder", folder_id=folder_id))
    return redirect(url_for("docs_blueprint.index"))


@docs_blueprint.route("/move", methods=["POST"])
@login_required
def move_item():
    """Move a document or folder to a different location."""
    item_type = request.form.get("item_type")
    item_id = request.form.get("item_id")
    target_folder_id = request.form.get("target_folder_id")

    if not item_type or not item_id:
        flash(_("Invalid request"), "error")
        return redirect(url_for("docs_blueprint.index"))

    item_id = int(item_id)
    target_folder_id = int(target_folder_id) if target_folder_id else None

    if item_type == "folder":
        folder = Folder.get_by_id(item_id)
        if folder:
            if not current_user.is_admin and folder.created_by_id != current_user.id:
                abort(403)
            folder.move(target_folder_id)
            flash(_("Folder '%(name)s' moved") % {"name": folder.name}, "success")
    elif item_type == "document":
        doc = Document.get_by_id(item_id)
        if doc:
            if not current_user.is_admin and doc.created_by_id != current_user.id:
                abort(403)
            # Check for duplicate in target folder
            if Document.exists_in_folder(doc.filename, target_folder_id):
                flash(_("'%(filename)s' already exists in target folder") % {"filename": doc.filename}, "error")
            else:
                doc.move(target_folder_id)
                flash(_("Document '%(filename)s' moved") % {"filename": doc.filename}, "success")

    if target_folder_id:
        return redirect(url_for("docs_blueprint.view_folder", folder_id=target_folder_id))
    return redirect(url_for("docs_blueprint.index"))


# -----------------------------------------------------------------------------
# Attachment Routes
# -----------------------------------------------------------------------------


@docs_blueprint.route("/attachments/<entity_type>/<int:entity_id>")
@login_required
def list_attachments(entity_type: str, entity_id: int):
    """List attachments for an entity (returns list-only partial for HTMX)."""
    if entity_type == "project":
        links = AttachmentLink.get_for_entities(["project", "project_doc"], entity_id)
    else:
        links = AttachmentLink.get_for_entity(entity_type, entity_id)
    attachments = [link.attachment for link in links]

    show_previews = request.args.get("preview") == "1"
    return render_template(
        "resources/desktop/docs/_attachments_list.html",
        attachments=attachments,
        entity_type=entity_type,
        entity_id=entity_id,
        show_previews=show_previews,
    )


@docs_blueprint.route("/attach", methods=["POST"])
@login_required
def attach_document():
    """Attach a document from library to an entity."""
    doc_id = request.form.get("document_id")
    entity_type = request.form.get("entity_type")
    entity_id = request.form.get("entity_id")

    if not all([doc_id, entity_type, entity_id]):
        flash(_("Invalid request"), "error")
        return redirect(request.referrer or url_for("docs_blueprint.index"))

    doc_id = int(doc_id)
    entity_id = int(entity_id)

    # Get the document
    doc = Document.get_by_id(doc_id)
    if not doc:
        flash(_("Document not found"), "error")
        return redirect(request.referrer or url_for("docs_blueprint.index"))

    # Copy to attachments and create link (original stays in library)
    attachment = storage.copy_to_attachments(doc)
    AttachmentLink.create(attachment.id, entity_type, entity_id)

    # Return to the entity page if HTMX, otherwise redirect
    if is_htmx_request():
        links = AttachmentLink.get_for_entity(entity_type, entity_id)
        attachments = [link.attachment for link in links]
        return render_template(
            "resources/desktop/docs/_attachments_list.html",
            attachments=attachments,
            entity_type=entity_type,
            entity_id=entity_id,
        )

    flash(_("'%(filename)s' attached") % {"filename": attachment.filename}, "success")
    return redirect(request.referrer or url_for("docs_blueprint.index"))


@docs_blueprint.route("/attach/upload", methods=["POST"])
@login_required
def upload_and_attach():
    """Upload a file and attach it directly to an entity."""
    entity_type = request.form.get("entity_type")
    entity_id = request.form.get("entity_id")

    if not all([entity_type, entity_id]):
        flash(_("Invalid request"), "error")
        return redirect(request.referrer or url_for("docs_blueprint.index"))

    entity_id = int(entity_id)

    if "file" not in request.files:
        flash(_("No file selected"), "error")
        return redirect(request.referrer or url_for("docs_blueprint.index"))

    file = request.files["file"]
    if not file.filename:
        flash(_("No file selected"), "error")
        return redirect(request.referrer or url_for("docs_blueprint.index"))

    # Validate file extension
    if not allowed_file(file.filename):
        flash(_("'%(filename)s' — file type not allowed") % {"filename": file.filename}, "error")
        return redirect(request.referrer or url_for("docs_blueprint.index"))

    # Get file info
    file.seek(0, 2)
    size_bytes = file.tell()
    file.seek(0)

    # Validate file size
    if size_bytes > MAX_FILE_SIZE:
        flash(_("'%(filename)s' exceeds 100 MB limit") % {"filename": file.filename}, "error")
        return redirect(request.referrer or url_for("docs_blueprint.index"))

    mime_type = mimetypes.guess_type(file.filename)[0]

    # Create attachment record
    attachment = Attachment.create(
        filename=file.filename,
        mime_type=mime_type,
        size_bytes=size_bytes,
    )

    # Save file directly to attachments
    storage.save_to_attachments(file, attachment)

    # Create link
    AttachmentLink.create(attachment.id, entity_type, entity_id)

    flash(_("'%(filename)s' attached") % {"filename": attachment.filename}, "success")

    # Return to the entity page if HTMX
    if is_htmx_request():
        links = AttachmentLink.get_for_entity(entity_type, entity_id)
        attachments = [link.attachment for link in links]
        return render_template(
            "resources/desktop/docs/_attachments_list.html",
            attachments=attachments,
            entity_type=entity_type,
            entity_id=entity_id,
        )

    return redirect(request.referrer or url_for("docs_blueprint.index"))


@docs_blueprint.route("/attachment/<int:attachment_id>/download")
@login_required
def download_attachment(attachment_id: int):
    """Download an attachment."""
    attachment = Attachment.get_by_id(attachment_id)
    if not attachment:
        flash(_("Attachment not found"), "error")
        return redirect(request.referrer or url_for("docs_blueprint.index"))

    file_path = storage.get_attachment_path(attachment)
    if not os.path.exists(file_path):
        flash(_("File not found on disk"), "error")
        return redirect(request.referrer or url_for("docs_blueprint.index"))

    return send_file(
        file_path,
        download_name=attachment.filename,
        as_attachment=True,
    )


@docs_blueprint.route("/attachment/<int:attachment_id>/preview")
@login_required
def preview_attachment(attachment_id: int):
    """Preview an attachment inline in browser."""
    attachment = Attachment.get_by_id(attachment_id)
    if not attachment:
        flash(_("Attachment not found"), "error")
        return redirect(request.referrer or url_for("docs_blueprint.index"))

    file_path = storage.get_attachment_path(attachment)
    if not os.path.exists(file_path):
        flash(_("File not found on disk"), "error")
        return redirect(request.referrer or url_for("docs_blueprint.index"))

    return send_file(
        file_path,
        download_name=attachment.filename,
        as_attachment=False,
        mimetype=attachment.mime_type,
    )


@docs_blueprint.route("/attachment/<int:attachment_id>/detach", methods=["POST"])
@login_required
def detach_attachment(attachment_id: int):
    """Remove an attachment from an entity (unlink, does not delete file)."""
    entity_type = request.form.get("entity_type")
    entity_id = request.form.get("entity_id")

    if not all([entity_type, entity_id]):
        flash(_("Invalid request"), "error")
        return redirect(request.referrer or url_for("docs_blueprint.index"))

    entity_id = int(entity_id)

    # Find and delete the link
    link = AttachmentLink.get_link(attachment_id, entity_type, entity_id)
    if not link:
        if is_htmx_request():
            # Return empty list for HTMX
            return render_template(
                "resources/desktop/docs/_attachments_list.html",
                attachments=[],
                entity_type=entity_type,
                entity_id=entity_id,
            )
        flash(_("Attachment link not found"), "error")
        return redirect(request.referrer or url_for("docs_blueprint.index"))

    link.delete()

    # Return updated list if HTMX
    if is_htmx_request():
        links = AttachmentLink.get_for_entity(entity_type, entity_id)
        attachments = [link.attachment for link in links]
        return render_template(
            "resources/desktop/docs/_attachments_list.html",
            attachments=attachments,
            entity_type=entity_type,
            entity_id=entity_id,
        )

    flash(_("Attachment removed"), "success")
    return redirect(request.referrer or url_for("docs_blueprint.index"))


@docs_blueprint.route("/attachment/<int:attachment_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_attachment(attachment_id: int) -> ResponseReturnValue:
    """Delete an attachment, its links, and the file on disk."""
    attachment = Attachment.get_by_id(attachment_id)
    if not attachment:
        flash(_("Attachment not found"), "error")
        return redirect(url_for("docs_blueprint.index"))

    attachment.destroy()

    flash(_("Attachment deleted"), "success")
    return redirect(url_for("docs_blueprint.index"))


# -----------------------------------------------------------------------------
# Library Browser (for attachment modal)
# -----------------------------------------------------------------------------


@docs_blueprint.route("/browser")
@login_required
def browser():
    """Library browser for attachment modal."""
    folder_id = request.args.get("folder_id")
    folder_id = int(folder_id) if folder_id else None

    entity_type = request.args.get("entity_type")
    entity_id = request.args.get("entity_id")

    current_folder = None
    if folder_id:
        current_folder = Folder.get_by_id(folder_id)

    # Get subfolders
    if folder_id:
        folders = Folder.scoped().filter(Folder.parent_id == folder_id).order_by(Folder.name).all()
    else:
        folders = Folder.get_root_folders()

    # Get documents
    documents = Document.get_by_folder(folder_id)

    # Build breadcrumbs
    breadcrumbs = []
    if current_folder:
        breadcrumbs = current_folder.breadcrumbs

    return render_template(
        "resources/desktop/docs/_browser.html",
        current_folder=current_folder,
        folders=folders,
        documents=documents,
        breadcrumbs=breadcrumbs,
        entity_type=entity_type,
        entity_id=entity_id,
    )
