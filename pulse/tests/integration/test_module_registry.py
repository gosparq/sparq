# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - Module Registry Integration Tests
#
# Tests for system/module/registry.py. Verifies module scanning, enabled/
# disabled checks, case insensitivity, module info lookups, the convenience
# module_enabled function, and REQUIRED_MODULES enforcement.
# -----------------------------------------------------------------------------

import pytest


# =========================================================================
# 1. ModuleRegistry
# =========================================================================

@pytest.mark.integration
class TestModuleRegistry:
    """Tests for the ModuleRegistry singleton."""

    def test_scan_finds_core_modules(self, app):
        from system.module.registry import ModuleRegistry

        with app.app_context():
            registry = ModuleRegistry.get_instance()
            enabled = registry.get_enabled_modules()
            assert "core" in enabled
            assert "people" in enabled
            assert "home" in enabled

    def test_is_enabled_case_insensitive(self, app):
        from system.module.registry import ModuleRegistry

        with app.app_context():
            registry = ModuleRegistry.get_instance()
            assert registry.is_enabled("Core") is True
            assert registry.is_enabled("CORE") is True
            assert registry.is_enabled("core") is True

    def test_get_enabled_modules_returns_copy(self, app):
        from system.module.registry import ModuleRegistry

        with app.app_context():
            registry = ModuleRegistry.get_instance()
            modules = registry.get_enabled_modules()
            original_len = len(modules)
            modules.add("fake_module_xyz")

            fresh = registry.get_enabled_modules()
            assert len(fresh) == original_len
            assert "fake_module_xyz" not in fresh

    def test_get_module_info_returns_dict_for_known_module(self, app):
        from system.module.registry import ModuleRegistry

        with app.app_context():
            registry = ModuleRegistry.get_instance()
            info = registry.get_module_info("core")
            assert info is not None
            assert isinstance(info, dict)
            assert "name" in info
            assert "enabled" in info

    def test_get_module_info_returns_none_for_unknown(self, app):
        from system.module.registry import ModuleRegistry

        with app.app_context():
            registry = ModuleRegistry.get_instance()
            info = registry.get_module_info("nonexistent_module_xyz")
            assert info is None

    def test_refresh_rescans(self, app):
        from system.module.registry import ModuleRegistry

        with app.app_context():
            registry = ModuleRegistry.get_instance()
            registry.refresh()
            enabled = registry.get_enabled_modules()
            assert "core" in enabled
            assert "people" in enabled


# =========================================================================
# 2. module_enabled convenience function
# =========================================================================

@pytest.mark.integration
class TestModuleEnabledFunction:
    """Tests for the module_enabled() convenience function."""

    def test_returns_true_for_enabled_module(self, app):
        from system.module.registry import module_enabled

        with app.app_context():
            assert module_enabled("core") is True

    def test_returns_false_for_unknown_module(self, app):
        from system.module.registry import module_enabled

        with app.app_context():
            assert module_enabled("nonexistent_module_xyz") is False


# =========================================================================
# 3. REQUIRED_MODULES / is_required_module
# =========================================================================

@pytest.mark.integration
class TestIsRequiredModule:
    """Tests for the is_required_module function and REQUIRED_MODULES set."""

    def test_core_is_required(self):
        from system.module.registry import is_required_module

        assert is_required_module("core") is True

    def test_people_is_required(self):
        from system.module.registry import is_required_module

        assert is_required_module("people") is True

    def test_optional_module_not_required(self):
        from system.module.registry import is_required_module

        assert is_required_module("sales") is False
