# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - Language Pack Unit Tests
#
# Tests for system/lang_packs/__init__.py: validate_pack(), install_pack(),
# uninstall_pack(), and list_installed_packs(). Uses tmp_path and patches
# directory helpers to avoid touching real data.
# -----------------------------------------------------------------------------

import json
import os
import zipfile
from unittest.mock import MagicMock, patch

import pytest


def _build_valid_zip(tmp_path, lang_code="de", lang_name="Deutsch", extra_json=True):
    """Create a valid language pack zip file in tmp_path and return its path."""
    zip_path = os.path.join(str(tmp_path), f"{lang_code}.zip")
    manifest = {
        "language_code": lang_code,
        "language_name": lang_name,
        "version": "1.0.0",
        "author": "Test Author",
    }
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        if extra_json:
            zf.writestr("core.json", json.dumps({"Hello": "Hallo"}))
    return zip_path


@pytest.mark.unit
class TestValidatePack:
    """Test language pack ZIP validation."""

    def test_valid_pack_passes(self, tmp_path):
        from system.lang_packs import validate_pack

        zip_path = _build_valid_zip(tmp_path)
        is_valid, error, manifest = validate_pack(zip_path)
        assert is_valid is True
        assert manifest is not None
        assert manifest["language_code"] == "de"

    def test_missing_manifest_fails(self, tmp_path):
        from system.lang_packs import validate_pack

        zip_path = os.path.join(str(tmp_path), "bad.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("core.json", json.dumps({"Hello": "Hallo"}))

        is_valid, error, manifest = validate_pack(zip_path)
        assert is_valid is False
        assert "manifest" in error.lower()
        assert manifest is None

    def test_missing_translation_files_fails(self, tmp_path):
        from system.lang_packs import validate_pack

        zip_path = os.path.join(str(tmp_path), "no_trans.zip")
        manifest = {
            "language_code": "de",
            "language_name": "Deutsch",
            "version": "1.0.0",
        }
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("manifest.json", json.dumps(manifest))

        is_valid, error, manifest = validate_pack(zip_path)
        assert is_valid is False
        assert "translation" in error.lower() or "no" in error.lower()
        assert manifest is None

    def test_invalid_zip_fails(self, tmp_path):
        from system.lang_packs import validate_pack

        bad_path = os.path.join(str(tmp_path), "corrupt.zip")
        with open(bad_path, "w") as f:
            f.write("this is not a zip file")

        is_valid, error, manifest = validate_pack(bad_path)
        assert is_valid is False
        assert manifest is None

    def test_invalid_language_code_fails(self, tmp_path):
        from system.lang_packs import validate_pack

        zip_path = os.path.join(str(tmp_path), "bad_code.zip")
        manifest = {
            "language_code": "INVALID",
            "language_name": "Bad Code",
            "version": "1.0.0",
        }
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("manifest.json", json.dumps(manifest))
            zf.writestr("core.json", json.dumps({"Hello": "Hi"}))

        is_valid, error, manifest = validate_pack(zip_path)
        assert is_valid is False
        assert "language code" in error.lower() or "invalid" in error.lower()

    def test_missing_required_field_fails(self, tmp_path):
        from system.lang_packs import validate_pack

        zip_path = os.path.join(str(tmp_path), "missing_field.zip")
        manifest = {"language_code": "de"}
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("manifest.json", json.dumps(manifest))
            zf.writestr("core.json", json.dumps({"Hello": "Hallo"}))

        is_valid, error, manifest = validate_pack(zip_path)
        assert is_valid is False
        assert "required" in error.lower() or "missing" in error.lower()


@pytest.mark.unit
class TestInstallPack:
    """Test language pack installation."""

    @patch("system.lang_packs.get_lang_packs_dir")
    @patch("system.lang_packs.get_data_dir")
    def test_install_creates_directory(self, mock_data_dir, mock_packs_dir, tmp_path):
        from system.lang_packs import install_pack

        packs_dir = os.path.join(str(tmp_path), "lang_packs")
        os.makedirs(packs_dir, exist_ok=True)
        mock_packs_dir.return_value = packs_dir
        mock_data_dir.return_value = str(tmp_path)

        zip_path = _build_valid_zip(tmp_path, lang_code="fr", lang_name="Francais")

        mock_file = MagicMock()
        mock_file.save = lambda path: _copy_file(zip_path, path)

        with patch("system.lang_packs.ensure_lang_packs_dir", return_value=packs_dir):
            success, message = install_pack(mock_file)

        assert success is True
        assert os.path.isdir(os.path.join(packs_dir, "fr"))

    @patch("system.lang_packs.get_lang_packs_dir")
    @patch("system.lang_packs.get_data_dir")
    def test_install_replaces_existing(self, mock_data_dir, mock_packs_dir, tmp_path):
        from system.lang_packs import install_pack

        packs_dir = os.path.join(str(tmp_path), "lang_packs")
        os.makedirs(packs_dir, exist_ok=True)
        mock_packs_dir.return_value = packs_dir
        mock_data_dir.return_value = str(tmp_path)

        existing = os.path.join(packs_dir, "fr")
        os.makedirs(existing, exist_ok=True)
        with open(os.path.join(existing, "old.json"), "w") as f:
            f.write("{}")

        zip_path = _build_valid_zip(tmp_path, lang_code="fr", lang_name="Francais")
        mock_file = MagicMock()
        mock_file.save = lambda path: _copy_file(zip_path, path)

        with patch("system.lang_packs.ensure_lang_packs_dir", return_value=packs_dir):
            success, message = install_pack(mock_file)

        assert success is True
        assert not os.path.exists(os.path.join(existing, "old.json"))


@pytest.mark.unit
class TestUninstallPack:
    """Test language pack uninstallation."""

    @patch("system.lang_packs.get_lang_packs_dir")
    def test_uninstall_removes_directory(self, mock_packs_dir, tmp_path):
        from system.lang_packs import uninstall_pack

        packs_dir = os.path.join(str(tmp_path), "lang_packs")
        pack_path = os.path.join(packs_dir, "de")
        os.makedirs(pack_path, exist_ok=True)
        with open(os.path.join(pack_path, "manifest.json"), "w") as f:
            json.dump({"language_name": "Deutsch"}, f)
        mock_packs_dir.return_value = packs_dir

        success, message = uninstall_pack("de")
        assert success is True
        assert not os.path.exists(pack_path)

    @patch("system.lang_packs.get_lang_packs_dir")
    def test_uninstall_nonexistent_returns_false(self, mock_packs_dir, tmp_path):
        from system.lang_packs import uninstall_pack

        packs_dir = os.path.join(str(tmp_path), "lang_packs")
        os.makedirs(packs_dir, exist_ok=True)
        mock_packs_dir.return_value = packs_dir

        success, message = uninstall_pack("zz")
        assert success is False

    def test_uninstall_english_blocked(self):
        from system.lang_packs import uninstall_pack

        success, message = uninstall_pack("en")
        assert success is False
        assert "english" in message.lower() or "built-in" in message.lower()


@pytest.mark.unit
class TestListInstalledPacks:
    """Test listing installed language packs."""

    @patch("system.lang_packs.get_lang_packs_dir")
    def test_lists_installed_packs(self, mock_packs_dir, tmp_path):
        from system.lang_packs import list_installed_packs

        packs_dir = os.path.join(str(tmp_path), "lang_packs")
        pack_path = os.path.join(packs_dir, "de")
        os.makedirs(pack_path, exist_ok=True)
        manifest = {
            "language_code": "de",
            "language_name": "Deutsch",
            "version": "1.0.0",
        }
        with open(os.path.join(pack_path, "manifest.json"), "w") as f:
            json.dump(manifest, f)
        mock_packs_dir.return_value = packs_dir

        packs = list_installed_packs()
        assert len(packs) == 1
        assert packs[0]["code"] == "de"
        assert packs[0]["name"] == "Deutsch"

    @patch("system.lang_packs.get_lang_packs_dir")
    def test_empty_when_none_installed(self, mock_packs_dir, tmp_path):
        from system.lang_packs import list_installed_packs

        packs_dir = os.path.join(str(tmp_path), "lang_packs")
        os.makedirs(packs_dir, exist_ok=True)
        mock_packs_dir.return_value = packs_dir

        packs = list_installed_packs()
        assert packs == []

    @patch("system.lang_packs.get_lang_packs_dir")
    def test_empty_when_dir_missing(self, mock_packs_dir, tmp_path):
        from system.lang_packs import list_installed_packs

        mock_packs_dir.return_value = os.path.join(str(tmp_path), "nonexistent")

        packs = list_installed_packs()
        assert packs == []


def _copy_file(src: str, dst: str) -> None:
    """Copy a file from src to dst (used as a mock for file.save())."""
    import shutil
    shutil.copy2(src, dst)
