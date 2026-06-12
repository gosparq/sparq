# -----------------------------------------------------------------------------
# sparQ - Language Pack Service
#
# Description:
#     Provides functionality for managing language packs including installation,
#     uninstallation, listing, and validation. Language packs are stored in
#     data/lang_packs/ and allow users to add translations without modifying
#     the core application.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

import json
import logging
import os
import re
import shutil
import zipfile
from datetime import datetime

logger = logging.getLogger(__name__)


def get_project_root() -> str:
    """Get the project root directory."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_data_dir() -> str:
    """Get the data directory path."""
    return os.environ.get("SPARQ_DATA_DIR", os.path.join(get_project_root(), "data"))


def get_lang_packs_dir() -> str:
    """Get the language packs directory path."""
    return os.path.join(get_data_dir(), "lang_packs")


def ensure_lang_packs_dir() -> str:
    """Ensure the language packs directory exists and return its path."""
    lang_packs_dir = get_lang_packs_dir()
    os.makedirs(lang_packs_dir, exist_ok=True)
    return lang_packs_dir


def list_installed_packs() -> list[dict]:
    """
    List all installed language packs with metadata from manifest.

    Returns:
        List of dicts with language pack info, sorted by language name
    """
    packs = []
    packs_dir = get_lang_packs_dir()

    if not os.path.exists(packs_dir):
        return packs

    for lang_code in os.listdir(packs_dir):
        pack_path = os.path.join(packs_dir, lang_code)
        manifest_path = os.path.join(pack_path, "manifest.json")

        if not os.path.isdir(pack_path):
            continue

        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                    packs.append(
                        {
                            "code": manifest.get("language_code", lang_code),
                            "name": manifest.get("language_name", lang_code),
                            "name_english": manifest.get("language_name_english", ""),
                            "version": manifest.get("version", "1.0.0"),
                            "author": manifest.get("author", ""),
                            "modules": manifest.get("modules", []),
                            "created_at": manifest.get("created_at", ""),
                        }
                    )
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Could not read manifest for {lang_code}: {e}")
                # Include pack without manifest data
                packs.append(
                    {
                        "code": lang_code,
                        "name": lang_code,
                        "name_english": "",
                        "version": "unknown",
                        "author": "",
                        "modules": [],
                        "created_at": "",
                    }
                )
        else:
            # Pack exists but has no manifest
            packs.append(
                {
                    "code": lang_code,
                    "name": lang_code,
                    "name_english": "",
                    "version": "unknown",
                    "author": "",
                    "modules": [],
                    "created_at": "",
                }
            )

    return sorted(packs, key=lambda x: x.get("name", ""))


def get_available_languages() -> list[dict]:
    """
    Get list of all available languages (built-in + installed packs).

    Returns:
        List of dicts with keys: code, name, is_builtin
    """
    # Built-in languages shipped in module lang/ folders
    languages = [
        {"code": "en", "name": "English", "is_builtin": True},
        {"code": "es", "name": "Español", "is_builtin": True},
    ]
    builtin_codes = {lang["code"] for lang in languages}

    # Add installed packs (skip if already built-in)
    for pack in list_installed_packs():
        if pack["code"] not in builtin_codes:
            languages.append(
                {
                    "code": pack["code"],
                    "name": pack["name"],
                    "is_builtin": False,
                }
            )

    return languages


def validate_pack(zip_path: str) -> tuple[bool, str, dict | None]:
    """
    Validate a language pack ZIP file.

    Args:
        zip_path: Path to the ZIP file

    Returns:
        Tuple of (is_valid, error_message, manifest)
    """
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            namelist = zf.namelist()

            # Check for manifest.json (can be at root or in a subdirectory)
            manifest_paths = [n for n in namelist if n.endswith("manifest.json")]
            if not manifest_paths:
                return False, "Missing manifest.json", None

            # Read the first manifest found
            manifest_path = manifest_paths[0]
            manifest = json.loads(zf.read(manifest_path))

            # Check required fields
            required = ["language_code", "language_name", "version"]
            for field in required:
                if field not in manifest:
                    return False, f"Missing required field: {field}", None

            # Validate language code format (2-letter ISO 639-1)
            lang_code = manifest["language_code"]
            if not re.match(r"^[a-z]{2}$", lang_code):
                return False, f"Invalid language code: {lang_code} (must be 2 lowercase letters)", None

            # Check for at least one translation file
            json_files = [n for n in namelist if n.endswith(".json") and "manifest" not in n]
            if not json_files:
                return False, "No translation files found in package", None

            return True, "", manifest

    except zipfile.BadZipFile:
        return False, "Invalid ZIP file", None
    except json.JSONDecodeError:
        return False, "Invalid manifest.json (malformed JSON)", None
    except Exception as e:
        return False, str(e), None


def install_pack(zip_file) -> tuple[bool, str]:
    """
    Install a language pack from an uploaded ZIP file.

    Args:
        zip_file: File-like object from Flask request.files

    Returns:
        Tuple of (success, message)
    """
    packs_dir = ensure_lang_packs_dir()

    # Save to temp location
    temp_path = os.path.join(packs_dir, f"temp_{datetime.now().strftime('%Y%m%d%H%M%S')}.zip")

    try:
        zip_file.save(temp_path)

        # Validate the pack
        is_valid, error, manifest = validate_pack(temp_path)
        if not is_valid:
            return False, f"Invalid language pack: {error}"

        lang_code = manifest["language_code"]
        pack_path = os.path.join(packs_dir, lang_code)

        # Remove existing pack if present (upgrade)
        if os.path.exists(pack_path):
            shutil.rmtree(pack_path)
            logger.info(f"Removed existing language pack: {lang_code}")

        os.makedirs(pack_path)

        # Extract translations
        with zipfile.ZipFile(temp_path, "r") as zf:
            for name in zf.namelist():
                if not name.endswith(".json"):
                    continue

                # Skip directories
                if name.endswith("/"):
                    continue

                # Determine output filename
                # Handle various structures:
                # - manifest.json -> manifest.json
                # - core/de.json -> core.json
                # - de/core.json -> core.json
                basename = os.path.basename(name)
                dirname = os.path.dirname(name)

                if basename == "manifest.json":
                    out_name = "manifest.json"
                elif dirname:
                    # Has a directory component
                    parts = dirname.split("/")
                    if parts[0] == lang_code or parts[-1] == lang_code:
                        # de/core.json structure -> core.json
                        out_name = basename
                    else:
                        # core/de.json structure -> core.json
                        out_name = parts[-1] + ".json" if basename == f"{lang_code}.json" else basename
                else:
                    out_name = basename

                # Write the file
                content = zf.read(name)
                out_path = os.path.join(pack_path, out_name)
                with open(out_path, "wb") as f:
                    f.write(content)

        logger.info(f"Installed language pack: {manifest['language_name']} ({lang_code})")
        return True, f"Language pack '{manifest['language_name']}' installed successfully"

    except Exception as e:
        logger.error(f"Failed to install language pack: {e}")
        return False, f"Installation failed: {str(e)}"

    finally:
        # Clean up temp file
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


def uninstall_pack(lang_code: str) -> tuple[bool, str]:
    """
    Uninstall a language pack.

    Args:
        lang_code: The language code to uninstall (e.g., "es", "de")

    Returns:
        Tuple of (success, message)
    """
    # Prevent uninstalling English (built-in)
    if lang_code == "en":
        return False, "Cannot uninstall built-in English language"

    pack_path = os.path.join(get_lang_packs_dir(), lang_code)

    if not os.path.exists(pack_path):
        return False, f"Language pack '{lang_code}' not found"

    try:
        # Get language name for message
        manifest_path = os.path.join(pack_path, "manifest.json")
        lang_name = lang_code
        if os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
                lang_name = manifest.get("language_name", lang_code)

        shutil.rmtree(pack_path)
        logger.info(f"Uninstalled language pack: {lang_name} ({lang_code})")
        return True, f"Language pack '{lang_name}' uninstalled successfully"

    except Exception as e:
        logger.error(f"Failed to uninstall language pack {lang_code}: {e}")
        return False, f"Uninstallation failed: {str(e)}"
