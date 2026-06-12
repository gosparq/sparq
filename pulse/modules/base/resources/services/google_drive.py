# -----------------------------------------------------------------------------
# sparQ - Google Drive Service
#
# Description:
#     Wrapper for Google Drive API v3. Handles listing folders/files, uploading,
#     downloading, and token refresh. Files are streamed/proxied - never copied
#     to local storage.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

import logging
from datetime import datetime, timezone, timedelta
from io import BytesIO
from typing import Iterator

import requests

from system.oauth.token_manager import TokenManager


logger = logging.getLogger(__name__)

DRIVE_API_BASE = "https://www.googleapis.com/drive/v3"
UPLOAD_API_BASE = "https://www.googleapis.com/upload/drive/v3"


class GoogleDriveError(Exception):
    """Exception for Google Drive API errors."""

    pass


class GoogleDriveService:
    """Google Drive API wrapper."""

    def __init__(self, access_token: str):
        """Initialize with access token.

        Args:
            access_token: Decrypted OAuth access token
        """
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

    def _request(
        self,
        method: str,
        url: str,
        params: dict | None = None,
        json_data: dict | None = None,
        files: dict | None = None,
        stream: bool = False,
    ) -> requests.Response:
        """Make an authenticated request to Google Drive API."""
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                params=params,
                json=json_data,
                files=files,
                stream=stream,
                timeout=30,
            )
            if response.status_code == 401:
                raise GoogleDriveError("Token expired or invalid")
            if response.status_code >= 400:
                error_msg = response.json().get("error", {}).get("message", response.text)
                raise GoogleDriveError(f"API error: {error_msg}")
            return response
        except requests.RequestException as e:
            raise GoogleDriveError(f"Request failed: {e}") from e

    def list_folders(self, parent_id: str | None = None) -> list[dict]:
        """List folders in Drive.

        Args:
            parent_id: Parent folder ID, or None for root

        Returns:
            List of folder dicts with id, name, modifiedTime
        """
        query = "mimeType='application/vnd.google-apps.folder' and trashed=false"
        if parent_id:
            query += f" and '{parent_id}' in parents"

        params = {
            "q": query,
            "fields": "files(id,name,modifiedTime,parents)",
            "orderBy": "name",
            "pageSize": 100,
        }

        response = self._request("GET", f"{DRIVE_API_BASE}/files", params=params)
        return response.json().get("files", [])

    def list_files(self, folder_id: str) -> list[dict]:
        """List files and folders in a folder.

        Args:
            folder_id: Folder ID to list contents of

        Returns:
            List of file/folder dicts with id, name, mimeType, size, modifiedTime
        """
        query = f"'{folder_id}' in parents and trashed=false"
        params = {
            "q": query,
            "fields": "files(id,name,mimeType,size,modifiedTime,webViewLink)",
            "orderBy": "folder,name",
            "pageSize": 100,
        }

        response = self._request("GET", f"{DRIVE_API_BASE}/files", params=params)
        files = response.json().get("files", [])

        # Add is_folder flag for convenience
        for f in files:
            f["is_folder"] = f.get("mimeType") == "application/vnd.google-apps.folder"
            # Format size
            if "size" in f:
                f["size_display"] = format_size(int(f["size"]))
            else:
                f["size_display"] = "-"

        return files

    def get_file_metadata(self, file_id: str) -> dict:
        """Get metadata for a file.

        Args:
            file_id: File ID

        Returns:
            File metadata dict
        """
        params = {"fields": "id,name,mimeType,size,modifiedTime,webViewLink"}
        response = self._request("GET", f"{DRIVE_API_BASE}/files/{file_id}", params=params)
        return response.json()

    def download_file(self, file_id: str) -> tuple[bytes, str, str]:
        """Download file content.

        Args:
            file_id: File ID to download

        Returns:
            Tuple of (content_bytes, filename, mime_type)
        """
        # First get metadata for filename and mime type
        metadata = self.get_file_metadata(file_id)
        filename = metadata.get("name", "file")
        mime_type = metadata.get("mimeType", "application/octet-stream")

        # Handle Google Docs formats - export to standard formats
        export_mime = None
        if mime_type == "application/vnd.google-apps.document":
            export_mime = "application/pdf"
            filename += ".pdf"
        elif mime_type == "application/vnd.google-apps.spreadsheet":
            export_mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            filename += ".xlsx"
        elif mime_type == "application/vnd.google-apps.presentation":
            export_mime = "application/pdf"
            filename += ".pdf"

        if export_mime:
            # Export Google Docs format
            params = {"mimeType": export_mime}
            response = self._request(
                "GET", f"{DRIVE_API_BASE}/files/{file_id}/export", params=params
            )
            return response.content, filename, export_mime
        else:
            # Download regular file
            params = {"alt": "media"}
            response = self._request(
                "GET", f"{DRIVE_API_BASE}/files/{file_id}", params=params
            )
            return response.content, filename, mime_type

    def stream_file(self, file_id: str) -> Iterator[bytes]:
        """Stream file content in chunks.

        Args:
            file_id: File ID to stream

        Yields:
            Chunks of file content
        """
        params = {"alt": "media"}
        response = self._request(
            "GET", f"{DRIVE_API_BASE}/files/{file_id}", params=params, stream=True
        )
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                yield chunk

    def upload_file(
        self,
        filename: str,
        content: bytes,
        mime_type: str,
        folder_id: str,
    ) -> dict:
        """Upload a file to Google Drive.

        Args:
            filename: Name for the file
            content: File content as bytes
            mime_type: MIME type of the file
            folder_id: Parent folder ID

        Returns:
            Created file metadata
        """
        # Use simple upload for small files
        params = {"uploadType": "multipart", "fields": "id,name,mimeType,size"}

        # Need special headers for multipart
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = requests.post(
            f"{UPLOAD_API_BASE}/files",
            headers=headers,
            params=params,
            files={  # type: ignore[arg-type]
                "metadata": (None, '{"name": "' + filename + '", "parents": ["' + folder_id + '"]}', "application/json"),
                "file": (filename, BytesIO(content), mime_type),
            },
            timeout=60,
        )

        if response.status_code >= 400:
            error_msg = response.json().get("error", {}).get("message", response.text)
            raise GoogleDriveError(f"Upload failed: {error_msg}")

        return response.json()

    def create_folder(self, name: str, parent_id: str) -> dict:
        """Create a new folder.

        Args:
            name: Folder name
            parent_id: Parent folder ID

        Returns:
            Created folder metadata
        """
        metadata = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id],
        }
        params = {"fields": "id,name,mimeType"}
        response = self._request(
            "POST", f"{DRIVE_API_BASE}/files", params=params, json_data=metadata
        )
        return response.json()


def format_size(size_bytes: int) -> str:
    """Format bytes as human-readable size."""
    if not size_bytes:
        return "0 B"
    size: float = size_bytes
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.0f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def get_drive_service(connection) -> GoogleDriveService | None:  # connection: DriveConnection
    """Get GoogleDriveService with valid token, refreshing if needed.

    Args:
        connection: DriveConnection model instance

    Returns:
        GoogleDriveService instance, or None if token refresh fails
    """
    from modules.base.core.models.auth_settings import AuthSettings

    if not connection:
        return None

    # Check if token needs refresh
    if connection.is_token_expired():
        # Refresh the token
        if not connection.refresh_token:
            logger.error("Cannot refresh token: no refresh token stored")
            return None

        try:
            # Get credentials
            auth_settings = AuthSettings.get_instance()
            client_id, client_secret_encrypted = auth_settings.get_provider_credentials("google")

            if not client_id or not client_secret_encrypted:
                logger.error("Cannot refresh token: no Google credentials configured")
                return None

            client_secret = TokenManager.decrypt(client_secret_encrypted)
            refresh_token = TokenManager.decrypt(connection.refresh_token)

            # Request new tokens
            response = requests.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
                timeout=10,
            )

            if response.status_code != 200:
                logger.error(f"Token refresh failed: {response.text}")
                return None

            token_data = response.json()

            # Calculate expiry
            expires_in = token_data.get("expires_in", 3600)
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

            # Update stored tokens
            new_access_token = TokenManager.encrypt(token_data["access_token"])
            connection.update_tokens(
                access_token=new_access_token,
                token_expires_at=expires_at,
            )

            access_token = token_data["access_token"]
        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            return None
    else:
        # Decrypt existing token
        access_token = TokenManager.decrypt(connection.access_token)

    return GoogleDriveService(access_token)
