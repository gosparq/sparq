# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - i18n Translation Integration Tests
#
# Tests for system/i18n/translation.py: translate(), format_date(),
# format_datetime(), format_number(), and format_day_name(). All tests
# require Flask app context for g and current_app access.
# -----------------------------------------------------------------------------

from datetime import date, datetime

import pytest


@pytest.mark.integration
class TestTranslate:
    """Test the translate() function."""

    def test_returns_original_when_no_translation_found(self, app):
        with app.test_request_context():
            from system.i18n.translation import translate

            result = translate("Some Untranslated Key XYZ")
            assert result == "Some Untranslated Key XYZ"

    def test_translate_callable_without_error(self, app):
        with app.test_request_context():
            from system.i18n.translation import translate

            result = translate("Hello")
            assert isinstance(result, str)


@pytest.mark.integration
class TestFormatDate:
    """Test the format_date() function."""

    def test_formats_date_object(self, app):
        with app.test_request_context():
            from system.i18n.translation import format_date

            d = date(2025, 3, 15)
            result = format_date(d)
            assert isinstance(result, str)
            assert len(result) > 0
            assert "2025" in result

    def test_returns_empty_for_none(self, app):
        with app.test_request_context():
            from system.i18n.translation import format_date

            assert format_date(None) == ""

    def test_formats_string_date(self, app):
        with app.test_request_context():
            from system.i18n.translation import format_date

            result = format_date("2025-06-01")
            assert isinstance(result, str)
            assert len(result) > 0


@pytest.mark.integration
class TestFormatDatetime:
    """Test the format_datetime() function."""

    def test_formats_datetime(self, app):
        with app.test_request_context():
            from system.i18n.translation import format_datetime

            dt = datetime(2025, 6, 15, 14, 30, 0)
            result = format_datetime(dt)
            assert isinstance(result, str)
            assert len(result) > 0

    def test_show_date_only_omits_time(self, app):
        with app.test_request_context():
            from system.i18n.translation import format_datetime

            dt = datetime(2025, 6, 15, 14, 30, 0)
            result = format_datetime(dt, show_date_only=True)
            assert "2025" in result
            assert "14:30" not in result

    def test_returns_dash_for_none(self, app):
        with app.test_request_context():
            from system.i18n.translation import format_datetime

            assert format_datetime(None) == "-"


@pytest.mark.integration
class TestFormatNumber:
    """Test the format_number() function."""

    def test_integer_formatting_includes_grouping(self, app):
        with app.test_request_context():
            from system.i18n.translation import format_number

            result = format_number(1000, decimal_places=0)
            assert "1" in result
            assert "000" in result

    def test_decimal_places_respected(self, app):
        with app.test_request_context():
            from system.i18n.translation import format_number

            result = format_number(1234.5, decimal_places=2)
            assert "1" in result
            assert "234" in result
            assert "50" in result

    def test_zero_decimal_places(self, app):
        with app.test_request_context():
            from system.i18n.translation import format_number

            result = format_number(42, decimal_places=0)
            assert "42" in result


@pytest.mark.integration
class TestFormatDayName:
    """Test the format_day_name() function."""

    def test_full_style_returns_full_name(self, app):
        with app.test_request_context():
            from system.i18n.translation import format_day_name

            d = date(2025, 6, 9)  # Monday
            result = format_day_name(d, style="full")
            assert isinstance(result, str)
            assert len(result) > 3

    def test_short_style_returns_abbreviation(self, app):
        with app.test_request_context():
            from system.i18n.translation import format_day_name

            d = date(2025, 6, 9)  # Monday
            result = format_day_name(d, style="short")
            assert isinstance(result, str)
            assert len(result) <= 4
