# -----------------------------------------------------------------------------
# sparQ - Resources Module - Cloud Drive Controller
#
# Description:
#     OAuth and file management routes for Google Drive integration.
#     Business admins connect their Drive account, select folders to share,
#     and all users can browse/upload/download files.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

import os
import secrets
from datetime import datetime, timezone, timedelta

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    Response,
    session,
    url_for,
)
from flask_login import current_user, login_required

from system.i18n.translation import translate as _

from modules.base.core.models.auth_settings import AuthSettings
from system.oauth.token_manager import TokenManager

from ..models.drive_connection import DriveConnection
from ..services.google_drive import GoogleDriveError, get_drive_service


def get_google_credentials() -> tuple[str | None, str | None]:
    """Get Google OAuth credentials from environment variables."""
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    return client_id, client_secret


drive_blueprint = Blueprint(
    "drive_blueprint",
    __name__,
    template_folder="../views/templates",
)

# Google OAuth endpoints
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

# Scopes for Google Drive R/W access
GOOGLE_DRIVE_SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/userinfo.email",
]


def is_htmx_request() -> bool:
    """Check if request is from HTMX."""
    return request.headers.get("HX-Request") == "true"


def can_manage_drive() -> bool:
    """Check if current user can manage Drive connection (admin)."""
    if not current_user.is_authenticated:
        return False
    return current_user.is_admin


# -----------------------------------------------------------------------------
# OAuth Flow
# -----------------------------------------------------------------------------


@drive_blueprint.route("/connect/google")
@login_required
def connect_google():
    """Start Google Drive OAuth flow."""
    if not can_manage_drive():
        flash(_("You don't have permission to connect cloud storage."), "error")
        return redirect(url_for("resources_settings_bp.index"))

    # Check if Google Drive is enabled
    auth_settings = AuthSettings.get_instance()
    if not auth_settings.google_drive_enabled:
        flash(_("Google Drive integration is not enabled."), "error")
        return redirect(url_for("resources_settings_bp.index"))

    # Get credentials from environment variables
    client_id, client_secret = get_google_credentials()
    if not client_id or not client_secret:
        flash(_("Google OAuth is not configured. Contact your system administrator."), "error")
        return redirect(url_for("resources_settings_bp.index"))

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    session["drive_oauth_state"] = state

    # Build authorization URL
    callback_url = url_for("drive_blueprint.callback_google", _external=True)
    params = {
        "client_id": client_id,
        "redirect_uri": callback_url,
        "response_type": "code",
        "scope": " ".join(GOOGLE_DRIVE_SCOPES),
        "access_type": "offline",  # Request refresh token
        "prompt": "consent",  # Always show consent to get refresh token
        "state": state,
    }

    auth_url = GOOGLE_AUTH_URL + "?" + "&".join(f"{k}={v}" for k, v in params.items())
    return redirect(auth_url)


@drive_blueprint.route("/callback/google")
@login_required
def callback_google():
    """Handle Google OAuth callback."""
    import requests

    # Verify state
    state = request.args.get("state")
    stored_state = session.pop("drive_oauth_state", None)
    if not state or state != stored_state:
        flash(_("Invalid OAuth state. Please try again."), "error")
        return redirect(url_for("resources_settings_bp.index"))

    # Check for errors
    error = request.args.get("error")
    if error:
        flash(_("Google authorization failed: %(error)s") % {"error": error}, "error")
        return redirect(url_for("resources_settings_bp.index"))

    # Get authorization code
    code = request.args.get("code")
    if not code:
        flash(_("No authorization code received."), "error")
        return redirect(url_for("resources_settings_bp.index"))

    # Get credentials from environment variables
    client_id, client_secret = get_google_credentials()

    # Exchange code for tokens
    callback_url = url_for("drive_blueprint.callback_google", _external=True)
    try:
        response = requests.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": callback_url,
                "grant_type": "authorization_code",
            },
            timeout=10,
        )

        if response.status_code != 200:
            flash(_("Failed to exchange authorization code."), "error")
            return redirect(url_for("resources_settings_bp.index"))

        token_data = response.json()
    except Exception as e:
        flash(_("Token exchange failed: %(error)s") % {"error": e}, "error")
        return redirect(url_for("resources_settings_bp.index"))

    # Get user info (email)
    try:
        userinfo_response = requests.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {token_data['access_token']}"},
            timeout=10,
        )
        userinfo = userinfo_response.json()
        connected_email = userinfo.get("email")
    except Exception:
        connected_email = None

    # Calculate token expiry
    expires_in = token_data.get("expires_in", 3600)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    # Encrypt tokens
    access_token_encrypted = TokenManager.encrypt(token_data["access_token"])
    refresh_token_encrypted = None
    if "refresh_token" in token_data:
        refresh_token_encrypted = TokenManager.encrypt(token_data["refresh_token"])

    # Create or update connection
    existing = DriveConnection.get_google()
    if existing:
        existing.update_tokens(
            access_token=access_token_encrypted,
            refresh_token=refresh_token_encrypted,
            token_expires_at=expires_at,
        )
        existing.connected_email = connected_email
        existing.connected_by_id = current_user.id
        from system.db.database import db
        db.session.commit()
        flash(_("Google Drive reconnected successfully."), "success")
    else:
        DriveConnection.create(
            provider="google",
            connected_by_id=current_user.id,
            access_token=access_token_encrypted,
            refresh_token=refresh_token_encrypted,
            token_expires_at=expires_at,
            connected_email=connected_email,
        )
        flash(_("Google Drive connected successfully."), "success")

    return redirect(url_for("resources_settings_bp.index"))


@drive_blueprint.route("/disconnect/google", methods=["POST"])
@login_required
def disconnect_google():
    """Disconnect Google Drive."""
    if not can_manage_drive():
        flash(_("You don't have permission to disconnect cloud storage."), "error")
        return redirect(url_for("resources_settings_bp.index"))

    connection = DriveConnection.get_google()
    if connection:
        connection.disconnect()
        flash(_("Google Drive disconnected."), "success")
    else:
        flash(_("No Google Drive connection found."), "warning")

    return redirect(url_for("resources_settings_bp.index"))


# -----------------------------------------------------------------------------
# Folder Management (for Settings)
# -----------------------------------------------------------------------------


@drive_blueprint.route("/folders")
@login_required
def list_folders():
    """List Google Drive folders for selection (HTMX partial)."""
    if not can_manage_drive():
        return "Unauthorized", 403

    connection = DriveConnection.get_google()
    if not connection:
        return render_template("resources/desktop/drive/_no_connection.html")

    service = get_drive_service(connection)
    if not service:
        return render_template("resources/desktop/drive/_token_error.html")

    try:
        folders = service.list_folders()
        selected_ids = connection.get_selected_folder_ids()
        return render_template(
            "resources/desktop/drive/_folder_picker.html",
            folders=folders,
            selected_ids=selected_ids,
        )
    except GoogleDriveError as e:
        return render_template("resources/desktop/drive/_error.html", error=str(e))


@drive_blueprint.route("/folders/save", methods=["POST"])
@login_required
def save_folders():
    """Save selected folders."""
    if not can_manage_drive():
        flash(_("Unauthorized"), "error")
        return redirect(url_for("resources_settings_bp.index"))

    connection = DriveConnection.get_google()
    if not connection:
        flash(_("No Google Drive connection found."), "error")
        return redirect(url_for("resources_settings_bp.index"))

    # Get selected folder IDs and names from form
    folder_ids = request.form.getlist("folders")

    if not folder_ids:
        connection.set_selected_folders([])
        flash(_("Folder selection cleared."), "success")
        return redirect(url_for("resources_settings_bp.index"))

    # Fetch folder names from Drive
    service = get_drive_service(connection)
    if not service:
        flash(_("Could not connect to Google Drive."), "error")
        return redirect(url_for("resources_settings_bp.index"))

    try:
        all_folders = service.list_folders()
        folder_map = {f["id"]: f["name"] for f in all_folders}

        selected = [
            {"id": fid, "name": folder_map.get(fid, "Unknown")}
            for fid in folder_ids
            if fid in folder_map
        ]

        connection.set_selected_folders(selected)
        flash(_("Saved %(count)s folder(s).") % {"count": len(selected)}, "success")
    except GoogleDriveError as e:
        flash(_("Error: %(error)s") % {"error": e}, "error")

    return redirect(url_for("resources_settings_bp.index"))


# -----------------------------------------------------------------------------
# File Browsing (for Docs UI)
# -----------------------------------------------------------------------------


@drive_blueprint.route("/browse")
@drive_blueprint.route("/browse/<folder_id>")
@login_required
def browse(folder_id: str | None = None):
    """Browse files in a Drive folder (HTMX partial)."""
    connection = DriveConnection.get_google()
    if not connection:
        return render_template("resources/desktop/drive/_no_connection.html")

    service = get_drive_service(connection)
    if not service:
        return render_template("resources/desktop/drive/_token_error.html")

    # If no folder specified, show selected root folders
    if not folder_id:
        selected = connection.get_selected_folders()
        return render_template(
            "resources/desktop/drive/_file_list.html",
            items=selected,
            is_root=True,
            current_folder=None,
            can_manage=can_manage_drive(),
        )

    # Check if folder is within selected folders (security)
    # For now, trust the folder_id (could add validation later)

    try:
        items = service.list_files(folder_id)
        folder_meta = service.get_file_metadata(folder_id)
        return render_template(
            "resources/desktop/drive/_file_list.html",
            items=items,
            is_root=False,
            current_folder=folder_meta,
            can_manage=can_manage_drive(),
        )
    except GoogleDriveError as e:
        return render_template("resources/desktop/drive/_error.html", error=str(e))


@drive_blueprint.route("/download/<file_id>")
@login_required
def download(file_id: str):
    """Download/proxy a file from Google Drive."""
    connection = DriveConnection.get_google()
    if not connection:
        flash(_("Google Drive not connected."), "error")
        return redirect(url_for("docs_blueprint.index"))

    service = get_drive_service(connection)
    if not service:
        flash(_("Could not connect to Google Drive."), "error")
        return redirect(url_for("docs_blueprint.index"))

    try:
        content, filename, mime_type = service.download_file(file_id)
        return Response(
            content,
            mimetype=mime_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(content)),
            },
        )
    except GoogleDriveError as e:
        flash(_("Download failed: %(error)s") % {"error": e}, "error")
        return redirect(url_for("docs_blueprint.index"))


@drive_blueprint.route("/upload/<folder_id>", methods=["POST"])
@login_required
def upload(folder_id: str):
    """Upload a file to Google Drive folder."""
    connection = DriveConnection.get_google()
    if not connection:
        if is_htmx_request():
            return "<div class='alert alert-danger'>Google Drive not connected.</div>"
        flash(_("Google Drive not connected."), "error")
        return redirect(url_for("docs_blueprint.index"))

    service = get_drive_service(connection)
    if not service:
        if is_htmx_request():
            return "<div class='alert alert-danger'>Could not connect to Google Drive.</div>"
        flash(_("Could not connect to Google Drive."), "error")
        return redirect(url_for("docs_blueprint.index"))

    # Get uploaded file
    file = request.files.get("file")
    if not file or not file.filename:
        if is_htmx_request():
            return "<div class='alert alert-warning'>No file selected.</div>"
        flash(_("No file selected."), "warning")
        return redirect(url_for("docs_blueprint.index"))

    try:
        content = file.read()
        mime_type = file.content_type or "application/octet-stream"
        service.upload_file(
            filename=file.filename,
            content=content,
            mime_type=mime_type,
            folder_id=folder_id,
        )

        if is_htmx_request():
            # Return updated file list
            return redirect(url_for("drive_blueprint.browse", folder_id=folder_id))

        flash(_("Uploaded %(filename)s to Google Drive.") % {"filename": file.filename}, "success")
        return redirect(url_for("docs_blueprint.index"))

    except GoogleDriveError as e:
        if is_htmx_request():
            return f"<div class='alert alert-danger'>Upload failed: {e}</div>"
        flash(_("Upload failed: %(error)s") % {"error": e}, "error")
        return redirect(url_for("docs_blueprint.index"))
