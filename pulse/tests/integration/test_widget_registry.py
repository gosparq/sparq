# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - Widget Registry Integration Tests
#
# Tests for system/widgets/registry.py: get_widget_by_id(),
# get_available_widgets(), get_default_widgets(), get_user_widgets(),
# and save_user_widgets(). Requires app context for module_enabled checks
# and DB for UserSetting persistence.
# -----------------------------------------------------------------------------

from unittest.mock import patch

import pytest

from flask import g


def _set_scope(ws):
    """Set g.organization_id and g.workspace_id from a seeded_workspace dict."""
    g.organization_id = ws["organization"].id
    g.workspace_id = ws["workspace"].id


@pytest.mark.integration
class TestGetWidgetById:
    """Test looking up widgets by ID."""

    def test_finds_existing_widget(self, app):
        with app.app_context():
            from system.widgets.registry import get_widget_by_id

            widget = get_widget_by_id("chat")
            assert widget is not None
            assert widget["id"] == "chat"

    def test_returns_none_for_unknown(self, app):
        with app.app_context():
            from system.widgets.registry import get_widget_by_id

            widget = get_widget_by_id("nonexistent_widget_xyz")
            assert widget is None

    def test_finds_admin_widget_when_included(self, app):
        with app.app_context():
            from system.widgets.registry import get_widget_by_id

            widget = get_widget_by_id("settings", include_admin=True)
            assert widget is not None
            assert widget["id"] == "settings"

    def test_does_not_find_admin_widget_by_default(self, app):
        with app.app_context():
            from system.widgets.registry import get_widget_by_id

            widget = get_widget_by_id("settings", include_admin=False)
            assert widget is None


@pytest.mark.integration
class TestGetAvailableWidgets:
    """Test retrieving available widgets filtered by module."""

    def test_returns_dict_with_module_keys(self, app):
        with app.app_context():
            from system.widgets.registry import get_available_widgets

            result = get_available_widgets()
            assert isinstance(result, dict)

    def test_widgets_have_required_keys(self, app):
        with app.app_context():
            from system.widgets.registry import get_available_widgets

            result = get_available_widgets()
            required_keys = {"id", "route", "label", "icon", "color"}
            for module_key, module_data in result.items():
                assert "widgets" in module_data
                for widget in module_data["widgets"]:
                    assert required_keys.issubset(widget.keys()), (
                        f"Widget {widget.get('id', '?')} missing keys: "
                        f"{required_keys - widget.keys()}"
                    )


@pytest.mark.integration
class TestDefaultWidgets:
    """Test default widget lists."""

    def test_returns_a_list(self, app):
        with app.app_context():
            from system.widgets.registry import get_default_widgets

            result = get_default_widgets()
            assert isinstance(result, list)

    def test_widgets_have_required_keys(self, app):
        with app.app_context():
            from system.widgets.registry import get_default_widgets

            required_keys = {"id", "route", "label", "icon", "color"}
            for widget in get_default_widgets():
                assert required_keys.issubset(widget.keys())

    def test_fsm_mode_returns_list(self, app):
        with app.app_context():
            from system.widgets.registry import get_default_widgets

            result = get_default_widgets(is_fsm_mode=True)
            assert isinstance(result, list)


@pytest.mark.integration
class TestUserWidgets:
    """Test per-user widget loading and saving."""

    def test_returns_defaults_when_no_saved_settings(self, app, seeded_workspace):
        with app.app_context():
            _set_scope(seeded_workspace)
            from system.widgets.registry import get_default_widgets, get_user_widgets

            user_id = seeded_workspace["user"].id
            result = get_user_widgets(user_id)
            defaults = get_default_widgets()
            assert isinstance(result, list)
            assert len(result) == len(defaults)

    @patch("system.widgets.registry.module_enabled", return_value=True)
    def test_save_and_load_roundtrip(self, _mock_enabled, app, seeded_workspace):
        with app.app_context():
            _set_scope(seeded_workspace)
            from system.widgets.registry import (
                get_user_widgets,
                get_widget_by_id,
                save_user_widgets,
            )

            user_id = seeded_workspace["user"].id
            chat_widget = get_widget_by_id("chat")
            assert chat_widget is not None

            save_user_widgets(user_id, [chat_widget])
            loaded = get_user_widgets(user_id)
            assert len(loaded) == 1
            assert loaded[0]["id"] == "chat"
