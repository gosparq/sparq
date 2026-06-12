# -----------------------------------------------------------------------------
# sparQ - Input Validation Utilities
#
# Description:
#     Helper functions and decorators for input validation.
#     Provides guard clauses and common validation patterns.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

"""Input validation utilities and guard clauses.

This module provides validation functions that raise ValidationError
when input doesn't meet requirements. Use these as guard clauses
at the start of route handlers.

Required Field Validation:
    require_fields: Validate form fields are present.
    require_json_fields: Validate JSON request fields.

Format Validation:
    validate_email: Check email format.

Range/Length Validation:
    validate_range: Check numeric value is within bounds.
    validate_length: Check string length is within bounds.
    validate_choice: Check value is in allowed list.

All functions raise `ValidationError` from `system.exceptions` which
can be caught by error handlers to return appropriate error responses.

Example:
    Guard clause pattern in a route::

        from system.utils.validation import require_fields, validate_email
        from system.exceptions import ValidationError

        @route("/register", methods=["POST"])
        def register():
            try:
                require_fields("email", "password", "name")
                validate_email(request.form["email"])
                validate_length(request.form["password"], min_length=8)
            except ValidationError as e:
                flash(str(e), "error")
                return redirect(url_for("auth.register"))

            # Continue with valid data...
"""

from typing import Any
from flask import request
from system.exceptions import ValidationError


def require_fields(*field_names: str) -> None:
    """Validate that required fields are present in request.form.

    Guard clause that raises ValidationError if any required field is missing.

    Args:
        *field_names: Names of required form fields

    Raises:
        ValidationError: If any required field is missing

    Example:
        @app.route("/user", methods=["POST"])
        def create_user():
            require_fields("email", "name")
            email = request.form["email"]
            ...
    """
    missing_fields = [field for field in field_names if not request.form.get(field)]

    if missing_fields:
        if len(missing_fields) == 1:
            raise ValidationError(
                f"Field '{missing_fields[0]}' is required", field=missing_fields[0]
            )
        else:
            raise ValidationError(
                f"Required fields missing: {', '.join(missing_fields)}", fields=missing_fields
            )


def require_json_fields(data: dict[str, Any], *field_names: str) -> None:
    """Validate that required fields are present in JSON request data.

    Guard clause that raises ValidationError if any required field is missing.

    Args:
        data: JSON request data (typically request.get_json())
        *field_names: Names of required fields

    Raises:
        ValidationError: If any required field is missing

    Example:
        @app.route("/api/user", methods=["POST"])
        def create_user():
            data = request.get_json() or {}
            require_json_fields(data, "email", "name")
            ...
    """
    missing_fields = [field for field in field_names if field not in data]

    if missing_fields:
        if len(missing_fields) == 1:
            raise ValidationError(
                f"Field '{missing_fields[0]}' is required", field=missing_fields[0]
            )
        else:
            raise ValidationError(
                f"Required fields missing: {', '.join(missing_fields)}", fields=missing_fields
            )


def validate_email(email: str) -> None:
    """Validate email format.

    Args:
        email: Email address to validate

    Raises:
        ValidationError: If email format is invalid
    """
    import re

    email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(email_pattern, email):
        raise ValidationError("Invalid email format", field="email")


def validate_range(
    value: int | float,
    min_value: int | float | None = None,
    max_value: int | float | None = None,
    field_name: str = "value",
) -> None:
    """Validate that a value is within a specified range.

    Args:
        value: Value to validate
        min_value: Minimum allowed value (inclusive)
        max_value: Maximum allowed value (inclusive)
        field_name: Name of the field for error messages

    Raises:
        ValidationError: If value is out of range
    """
    if min_value is not None and value < min_value:
        raise ValidationError(f"{field_name} must be at least {min_value}", field=field_name)

    if max_value is not None and value > max_value:
        raise ValidationError(f"{field_name} must be at most {max_value}", field=field_name)


def validate_length(
    value: str,
    min_length: int | None = None,
    max_length: int | None = None,
    field_name: str = "value",
) -> None:
    """Validate string length.

    Args:
        value: String to validate
        min_length: Minimum allowed length
        max_length: Maximum allowed length
        field_name: Name of the field for error messages

    Raises:
        ValidationError: If string length is invalid
    """
    length = len(value)

    if min_length is not None and length < min_length:
        raise ValidationError(
            f"{field_name} must be at least {min_length} characters", field=field_name
        )

    if max_length is not None and length > max_length:
        raise ValidationError(
            f"{field_name} must be at most {max_length} characters", field=field_name
        )


def validate_choice(value: Any, choices: list[Any], field_name: str = "value") -> None:
    """Validate that a value is one of the allowed choices.

    Args:
        value: Value to validate
        choices: List of allowed values
        field_name: Name of the field for error messages

    Raises:
        ValidationError: If value is not in choices
    """
    if value not in choices:
        raise ValidationError(
            f"{field_name} must be one of: {', '.join(str(c) for c in choices)}", field=field_name
        )
