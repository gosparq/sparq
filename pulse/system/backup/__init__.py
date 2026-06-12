# -----------------------------------------------------------------------------
# sparQ - Backup Service
#
# Description:
#     Provides backup and restore functionality using SQLite Backup API
#     for safe hot backups while the database is in use.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

import json
import logging
import os
import shutil
import sqlite3
import zipfile
from datetime import datetime

logger = logging.getLogger(__name__)

# Configuration
MAX_BACKUPS = 10  # Retention: keep last N backups


def get_data_dir() -> str:
    """Get the data directory path."""
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.environ.get("SPARQ_DATA_DIR", os.path.join(project_root, "data"))


def get_backup_dir() -> str:
    """Get the backup directory path."""
    return os.path.join(get_data_dir(), "backups")


def get_db_path() -> str:
    """Get the database file path."""
    return os.path.join(get_data_dir(), "sparq.db")


def get_app_version() -> str:
    """Get computed version (e.g., 0.5.173) from version module."""
    try:
        from system.version import get_version
        return get_version()
    except ImportError:
        return "unknown"


def backup_database(src_path: str, dst_path: str) -> None:
    """
    Safe hot backup using SQLite Backup API.

    This allows backing up the database while it's in use without
    corrupting the backup or blocking the application.
    """
    src = sqlite3.connect(src_path)
    dst = sqlite3.connect(dst_path)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def create_backup(reason: str = "manual") -> str:
    """
    Create a backup zip file.

    Args:
        reason: Why the backup was created (manual, scheduled, pre-upgrade)

    Returns:
        The filename of the created backup
    """
    backup_dir = get_backup_dir()
    data_dir = get_data_dir()
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    version = get_app_version()
    filename = f"sparq-backup-{timestamp}-v{version}.zip"
    zip_path = os.path.join(backup_dir, filename)
    temp_db = os.path.join(backup_dir, f"temp_backup_{timestamp}.db")

    logger.info(f"Creating backup: {filename} (reason: {reason})")

    try:
        # 1. Backup database using SQLite API (safe while in use)
        db_path = get_db_path()

        if os.path.exists(db_path):
            backup_database(db_path, temp_db)

        # 2. Create manifest
        manifest: dict = {
            "version": get_app_version(),
            "schema_version": 1,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "reason": reason,
            "files": {
                "database": "sparq.db" if os.path.exists(db_path) else None,
                "documents": [],
                "attachments": []
            }
        }

        # 3. Create zip with manifest + db + all data files
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Add database
            if os.path.exists(temp_db):
                zf.write(temp_db, "sparq.db")

            # Add all files from data directory except backups/ and sparq.db
            for root, dirs, files in os.walk(data_dir):
                # Skip backups directory to prevent recursion
                if 'backups' in dirs:
                    dirs.remove('backups')

                for file in files:
                    # Skip the database file (already backed up via SQLite API)
                    if file == "sparq.db" and root == data_dir:
                        continue

                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, data_dir)
                    zf.write(file_path, arcname)

                    # Track files by folder for manifest
                    folder_name = arcname.split(os.sep)[0] if os.sep in arcname else ""
                    if folder_name == "documents":
                        manifest["files"]["documents"].append(arcname)
                    elif folder_name == "attachments":
                        manifest["files"]["attachments"].append(arcname)

            # Add manifest
            zf.writestr("manifest.json", json.dumps(manifest, indent=2))

        # Enforce retention policy
        enforce_retention()

        logger.info(f"Backup created successfully: {filename}")
        return filename

    except Exception as e:
        logger.error(f"Backup creation failed: {e}")
        # Clean up partial zip file if it exists
        if os.path.exists(zip_path):
            try:
                os.remove(zip_path)
            except OSError:
                pass
        raise

    finally:
        # Always clean up temp database
        if os.path.exists(temp_db):
            try:
                os.remove(temp_db)
            except OSError:
                pass


def list_backups() -> list[dict]:
    """
    List all backups with metadata from manifest.

    Returns:
        List of backup info dicts sorted by date (newest first)
    """
    backup_dir = get_backup_dir()
    backups = []

    if not os.path.exists(backup_dir):
        return backups

    for filename in os.listdir(backup_dir):
        if not filename.endswith(".zip"):
            continue

        zip_path = os.path.join(backup_dir, filename)

        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                # Read manifest if available
                if "manifest.json" in zf.namelist():
                    manifest = json.loads(zf.read("manifest.json"))
                    created_at = manifest.get("created_at", "")
                    reason = manifest.get("reason", "unknown")
                    version = manifest.get("version", "unknown")
                else:
                    # Fallback for backups without manifest
                    created_at = ""
                    reason = "unknown"
                    version = "unknown"

                # Get file size
                size = os.path.getsize(zip_path)

                backups.append({
                    "filename": filename,
                    "created_at": created_at,
                    "reason": reason,
                    "version": version,
                    "size": size,
                    "size_formatted": format_size(size)
                })
        except (zipfile.BadZipFile, json.JSONDecodeError) as e:
            logger.warning(f"Could not read backup {filename}: {e}")
            continue

    # Sort by created_at descending (newest first)
    backups.sort(key=lambda x: x["created_at"], reverse=True)
    return backups


def format_size(size_bytes: int) -> str:
    """Format byte size to human readable string."""
    size: float = size_bytes
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def delete_backup(filename: str) -> bool:
    """
    Delete a backup file.

    Args:
        filename: The backup filename to delete

    Returns:
        True if deleted, False if not found
    """
    backup_dir = get_backup_dir()
    zip_path = os.path.join(backup_dir, filename)

    # Security: ensure filename doesn't contain path traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        logger.warning(f"Invalid backup filename: {filename}")
        return False

    if os.path.exists(zip_path):
        os.remove(zip_path)
        logger.info(f"Deleted backup: {filename}")
        return True

    return False


def enforce_retention() -> None:
    """Delete oldest backups if over MAX_BACKUPS."""
    backups = list_backups()

    while len(backups) > MAX_BACKUPS:
        oldest = backups.pop()  # List is sorted newest first, so pop gets oldest
        delete_backup(oldest["filename"])
        logger.info(f"Retention: deleted old backup {oldest['filename']}")


def get_backup_path(filename: str) -> str | None:
    """
    Get full path to a backup file if it exists.

    Args:
        filename: The backup filename

    Returns:
        Full path or None if not found/invalid
    """
    # Security: ensure filename doesn't contain path traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        return None

    backup_dir = get_backup_dir()
    zip_path = os.path.join(backup_dir, filename)

    if os.path.exists(zip_path):
        return zip_path
    return None


def validate_backup(zip_path: str) -> tuple[bool, str, dict | None]:
    """
    Validate a backup zip file.

    Args:
        zip_path: Path to the backup zip file

    Returns:
        Tuple of (is_valid, error_message, manifest)
    """
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            # Check for required files
            if "manifest.json" not in zf.namelist():
                return False, "Missing manifest.json", None

            if "sparq.db" not in zf.namelist():
                return False, "Missing sparq.db", None

            # Parse manifest
            manifest = json.loads(zf.read("manifest.json"))

            # Check schema version compatibility
            schema_version = manifest.get("schema_version", 0)
            if schema_version > 1:  # Current schema version
                return False, f"Backup schema version {schema_version} is newer than supported", None

            return True, "", manifest

    except zipfile.BadZipFile:
        return False, "Invalid zip file", None
    except json.JSONDecodeError:
        return False, "Invalid manifest.json", None
    except Exception as e:
        return False, str(e), None


def restore_backup(zip_file) -> tuple[bool, str]:
    """
    Restore from a backup zip file.

    Args:
        zip_file: File-like object or path to the backup zip

    Returns:
        Tuple of (success, message)
    """
    data_dir = get_data_dir()
    backup_dir = get_backup_dir()

    # Handle both file path and file-like object
    if isinstance(zip_file, str):
        zip_path = zip_file
        cleanup_temp = False
    else:
        # Save uploaded file to temp location
        os.makedirs(backup_dir, exist_ok=True)
        temp_path = os.path.join(backup_dir, f"temp_restore_{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip")
        zip_file.save(temp_path)
        zip_path = temp_path
        cleanup_temp = True

    try:
        # 1. Validate backup
        is_valid, error_msg, manifest = validate_backup(zip_path)
        if not is_valid:
            return False, f"Invalid backup: {error_msg}"

        logger.info(f"Restoring backup from version {manifest.get('version', 'unknown')}")

        # 2. Create pre-restore backup (safety net)
        try:
            pre_restore_backup = create_backup(reason="pre-restore")
            logger.info(f"Created pre-restore backup: {pre_restore_backup}")
        except Exception as e:
            logger.warning(f"Could not create pre-restore backup: {e}")

        # 3. Extract to temp directory
        temp_extract = os.path.join(backup_dir, f"temp_extract_{datetime.now().strftime('%Y%m%d-%H%M%S')}")
        os.makedirs(temp_extract, exist_ok=True)

        with zipfile.ZipFile(zip_path, 'r') as zf:
            # Validate all paths to prevent Zip Slip (path traversal)
            for member in zf.namelist():
                member_path = os.path.realpath(os.path.join(temp_extract, member))
                if not member_path.startswith(os.path.realpath(temp_extract) + os.sep) and member_path != os.path.realpath(temp_extract):
                    raise ValueError(f"Zip contains path traversal entry: {member}")
            zf.extractall(temp_extract)

        # 4. Replace database
        src_db = os.path.join(temp_extract, "sparq.db")
        dst_db = get_db_path()
        if os.path.exists(src_db):
            # Remove old database
            if os.path.exists(dst_db):
                os.remove(dst_db)
            shutil.move(src_db, dst_db)

        # 5. Replace documents folder
        src_docs = os.path.join(temp_extract, "documents")
        dst_docs = os.path.join(data_dir, "documents")
        if os.path.exists(src_docs):
            if os.path.exists(dst_docs):
                shutil.rmtree(dst_docs)
            shutil.move(src_docs, dst_docs)

        # 6. Replace attachments folder
        src_attach = os.path.join(temp_extract, "attachments")
        dst_attach = os.path.join(data_dir, "attachments")
        if os.path.exists(src_attach):
            if os.path.exists(dst_attach):
                shutil.rmtree(dst_attach)
            shutil.move(src_attach, dst_attach)

        # 7. Replace resumes folder
        src_resumes = os.path.join(temp_extract, "resumes")
        dst_resumes = os.path.join(data_dir, "resumes")
        if os.path.exists(src_resumes):
            if os.path.exists(dst_resumes):
                shutil.rmtree(dst_resumes)
            shutil.move(src_resumes, dst_resumes)

        # 8. Replace modules folder (installed apps/plugins)
        src_modules = os.path.join(temp_extract, "modules")
        dst_modules = os.path.join(data_dir, "modules")
        if os.path.exists(src_modules):
            if os.path.exists(dst_modules):
                shutil.rmtree(dst_modules)
            shutil.move(src_modules, dst_modules)

        # 9. Cleanup temp extract directory
        shutil.rmtree(temp_extract, ignore_errors=True)

        logger.info("Backup restored successfully")
        return True, "Backup restored successfully. Please restart the application to apply changes."

    except Exception as e:
        logger.error(f"Restore failed: {e}")
        return False, f"Restore failed: {str(e)}"

    finally:
        if cleanup_temp and os.path.exists(zip_path):
            os.remove(zip_path)


def get_last_backup_time() -> str | None:
    """Get the timestamp of the most recent backup."""
    backups = list_backups()
    if backups:
        return backups[0]["created_at"]
    return None


def get_db_mtime() -> float | None:
    """Get the modification time of the database file."""
    db_path = get_db_path()
    if os.path.exists(db_path):
        return os.path.getmtime(db_path)
    return None


def cleanup_orphaned_files() -> int:
    """
    Clean up orphaned temp files and corrupted backups from previous failed runs.

    Returns:
        Number of files cleaned up
    """
    backup_dir = get_backup_dir()
    if not os.path.exists(backup_dir):
        return 0

    cleaned = 0

    for filename in os.listdir(backup_dir):
        filepath = os.path.join(backup_dir, filename)

        # Clean up temp database files
        if filename.startswith("temp_backup_") and filename.endswith(".db"):
            try:
                os.remove(filepath)
                logger.info(f"Cleaned up orphaned temp file: {filename}")
                cleaned += 1
            except OSError as e:
                logger.warning(f"Could not remove temp file {filename}: {e}")

        # Clean up empty or corrupted zip files
        elif filename.endswith(".zip"):
            try:
                size = os.path.getsize(filepath)
                # Empty files are definitely corrupted
                if size == 0:
                    os.remove(filepath)
                    logger.info(f"Cleaned up empty backup file: {filename}")
                    cleaned += 1
                else:
                    # Verify zip file is valid (catches truncated files)
                    try:
                        with zipfile.ZipFile(filepath, 'r') as zf:
                            zf.namelist()
                    except zipfile.BadZipFile:
                        os.remove(filepath)
                        logger.info(f"Cleaned up corrupted backup file: {filename}")
                        cleaned += 1
            except OSError as e:
                logger.warning(f"Could not check/remove backup {filename}: {e}")

    return cleaned
