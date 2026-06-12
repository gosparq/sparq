# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - Validation Utils Unit Tests
#
# Tests for system/utils/validation.py. Verifies guard clauses for form
# fields, JSON fields, email format, range, length, and choice validation.
# -----------------------------------------------------------------------------

import pytest

from system.exceptions import ValidationError
from system.utils.validation import (
    require_fields,
    require_json_fields,
    validate_choice,
    validate_email,
    validate_length,
    validate_range,
)


# ---------------------------------------------------------------------------
# 1. require_fields — form field presence (needs Flask request context)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRequireFields:
    """Test form field presence validation."""

    def test_all_fields_present(self, app):
        """No error when all required fields are present."""
        with app.test_request_context(
            "/test", method="POST", data={"email": "a@b.com", "name": "Joe"}
        ):
            require_fields("email", "name")  # should not raise

    def test_single_missing_field(self, app):
        """Single missing field raises ValidationError with field name."""
        with app.test_request_context("/test", method="POST", data={"name": "Joe"}):
            with pytest.raises(ValidationError, match="email"):
                require_fields("email", "name")

    def test_multiple_missing_fields(self, app):
        """Multiple missing fields lists them all."""
        with app.test_request_context("/test", method="POST", data={}):
            with pytest.raises(ValidationError, match="Required fields missing"):
                require_fields("email", "name")

    def test_empty_string_treated_as_missing(self, app):
        """An empty string value should be treated as missing."""
        with app.test_request_context(
            "/test", method="POST", data={"email": "", "name": "Joe"}
        ):
            with pytest.raises(ValidationError, match="email"):
                require_fields("email", "name")


# ---------------------------------------------------------------------------
# 2. require_json_fields — JSON dict field presence
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRequireJsonFields:
    """Test JSON field presence validation."""

    def test_all_fields_present(self):
        """No error when all fields are present."""
        data = {"email": "a@b.com", "name": "Joe"}
        require_json_fields(data, "email", "name")  # should not raise

    def test_single_missing_field(self):
        """Single missing field raises ValidationError."""
        data = {"name": "Joe"}
        with pytest.raises(ValidationError, match="email"):
            require_json_fields(data, "email", "name")

    def test_multiple_missing_fields(self):
        """Multiple missing fields lists them all."""
        with pytest.raises(ValidationError, match="Required fields missing"):
            require_json_fields({}, "email", "name")

    def test_empty_dict(self):
        """Empty dict with required fields should raise."""
        with pytest.raises(ValidationError):
            require_json_fields({}, "id")

    def test_none_value_counts_as_present(self):
        """A key with None value is still considered present (key exists)."""
        data = {"email": None}
        require_json_fields(data, "email")  # should not raise


# ---------------------------------------------------------------------------
# 3. validate_email — format checking
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestValidateEmail:
    """Test email format validation."""

    def test_valid_email(self):
        """Standard email should pass."""
        validate_email("user@example.com")

    def test_valid_email_with_dots(self):
        """Email with dots in local part should pass."""
        validate_email("first.last@example.com")

    def test_valid_email_with_plus(self):
        """Email with plus addressing should pass."""
        validate_email("user+tag@example.com")

    def test_missing_at_sign(self):
        """Email without @ should fail."""
        with pytest.raises(ValidationError, match="Invalid email"):
            validate_email("userexample.com")

    def test_missing_domain(self):
        """Email without domain should fail."""
        with pytest.raises(ValidationError, match="Invalid email"):
            validate_email("user@")

    def test_missing_tld(self):
        """Email without TLD should fail."""
        with pytest.raises(ValidationError, match="Invalid email"):
            validate_email("user@example")

    def test_empty_string(self):
        """Empty string should fail."""
        with pytest.raises(ValidationError, match="Invalid email"):
            validate_email("")

    def test_double_at(self):
        """Double @ should fail."""
        with pytest.raises(ValidationError, match="Invalid email"):
            validate_email("user@@example.com")

    def test_spaces_invalid(self):
        """Email with spaces should fail."""
        with pytest.raises(ValidationError, match="Invalid email"):
            validate_email("user @example.com")


# ---------------------------------------------------------------------------
# 4. validate_range — numeric bounds
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestValidateRange:
    """Test numeric range validation."""

    def test_within_range(self):
        """Value within range should pass."""
        validate_range(5, min_value=1, max_value=10)

    def test_at_min_boundary(self):
        """Value at minimum boundary should pass."""
        validate_range(1, min_value=1, max_value=10)

    def test_at_max_boundary(self):
        """Value at maximum boundary should pass."""
        validate_range(10, min_value=1, max_value=10)

    def test_below_min(self):
        """Value below minimum should raise."""
        with pytest.raises(ValidationError, match="at least"):
            validate_range(0, min_value=1, max_value=10)

    def test_above_max(self):
        """Value above maximum should raise."""
        with pytest.raises(ValidationError, match="at most"):
            validate_range(11, min_value=1, max_value=10)

    def test_min_only(self):
        """Only min_value constraint should work."""
        validate_range(100, min_value=1)  # no max, should pass

    def test_max_only(self):
        """Only max_value constraint should work."""
        validate_range(-5, max_value=10)  # no min, should pass

    def test_no_bounds(self):
        """No constraints should always pass."""
        validate_range(999)

    def test_float_values(self):
        """Float values should work."""
        validate_range(3.14, min_value=3.0, max_value=4.0)

    def test_custom_field_name_in_error(self):
        """Custom field name should appear in error message."""
        with pytest.raises(ValidationError, match="age"):
            validate_range(200, max_value=150, field_name="age")


# ---------------------------------------------------------------------------
# 5. validate_length — string length bounds
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestValidateLength:
    """Test string length validation."""

    def test_within_length(self):
        """String within bounds should pass."""
        validate_length("hello", min_length=1, max_length=10)

    def test_at_min_length(self):
        """String exactly at min length should pass."""
        validate_length("a", min_length=1)

    def test_at_max_length(self):
        """String exactly at max length should pass."""
        validate_length("12345", max_length=5)

    def test_too_short(self):
        """String below min length should raise."""
        with pytest.raises(ValidationError, match="at least"):
            validate_length("hi", min_length=5)

    def test_too_long(self):
        """String above max length should raise."""
        with pytest.raises(ValidationError, match="at most"):
            validate_length("hello world", max_length=5)

    def test_empty_string_with_min(self):
        """Empty string with min_length > 0 should raise."""
        with pytest.raises(ValidationError):
            validate_length("", min_length=1)

    def test_no_bounds(self):
        """No length constraints should always pass."""
        validate_length("anything goes")


# ---------------------------------------------------------------------------
# 6. validate_choice — allowed values
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestValidateChoice:
    """Test choice validation."""

    def test_valid_choice(self):
        """Value in allowed list should pass."""
        validate_choice("admin", ["user", "admin", "moderator"])

    def test_invalid_choice(self):
        """Value not in allowed list should raise."""
        with pytest.raises(ValidationError, match="must be one of"):
            validate_choice("superadmin", ["user", "admin", "moderator"])

    def test_integer_choices(self):
        """Integer choices should work."""
        validate_choice(2, [1, 2, 3])

    def test_none_not_in_choices(self):
        """None should fail if not in choices list."""
        with pytest.raises(ValidationError):
            validate_choice(None, ["a", "b"])

    def test_custom_field_name(self):
        """Custom field name should appear in error message."""
        with pytest.raises(ValidationError, match="role"):
            validate_choice("x", ["a", "b"], field_name="role")
