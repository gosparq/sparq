# -----------------------------------------------------------------------------
# sparQ - Exception Hierarchy
#
# Description:
#     Domain-specific exception classes for the application.
#     Provides structured error handling with clear exception types.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

import uuid
from typing import Any


class AppError(Exception):
    """Base exception for all application errors.

    All custom exceptions should inherit from this class.
    Each exception automatically generates a unique error ID for tracking.
    """

    def __init__(self, message: str, error_id: str | None = None, **kwargs: Any) -> None:
        super().__init__(message)
        self.message = message
        self.error_id = error_id or str(uuid.uuid4())
        self.details = kwargs

    def __str__(self) -> str:
        return f"{self.message} [ID: {self.error_id}]"


class ValidationError(AppError):
    """Raised when input validation fails.

    Use this for:
    - Invalid form data
    - Missing required fields
    - Out-of-range values
    - Type mismatches

    Example:
        raise ValidationError("Email is required", field="email")
    """

    def __init__(
        self, message: str, field: str | None = None, error_id: str | None = None, **kwargs: Any
    ) -> None:
        super().__init__(message, error_id, field=field, **kwargs)
        self.field = field


class NotFoundError(AppError):
    """Raised when a requested resource is not found.

    Use this for:
    - Database queries that return no results
    - Missing files or resources
    - Invalid IDs

    Example:
        raise NotFoundError("User not found", resource="user", id=user_id)
    """

    def __init__(
        self, message: str, resource: str | None = None, error_id: str | None = None, **kwargs: Any
    ) -> None:
        super().__init__(message, error_id, resource=resource, **kwargs)
        self.resource = resource


class ConflictError(AppError):
    """Raised when an operation conflicts with existing state.

    Use this for:
    - Duplicate entries (unique constraint violations)
    - Concurrent modification conflicts
    - State transition violations

    Example:
        raise ConflictError("Email already registered", email=email)
    """

    pass


class AuthenticationError(AppError):
    """Raised when authentication fails.

    Use this for:
    - Invalid credentials
    - Expired tokens
    - Missing authentication

    Example:
        raise AuthenticationError("Invalid username or password")
    """

    pass


class AuthorizationError(AppError):
    """Raised when user lacks permission for an operation.

    Use this for:
    - Insufficient permissions
    - Role-based access denials
    - Resource ownership violations

    Example:
        raise AuthorizationError("Admin access required")
    """

    def __init__(
        self,
        message: str,
        required_permission: str | None = None,
        error_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, error_id, required_permission=required_permission, **kwargs)
        self.required_permission = required_permission


class ConfigurationError(AppError):
    """Raised when application configuration is invalid.

    Use this for:
    - Missing required environment variables
    - Invalid configuration values
    - Startup validation failures

    Example:
        raise ConfigurationError("DATABASE_URL environment variable not set")
    """

    pass


class ExternalServiceError(AppError):
    """Raised when an external service fails.

    Use this for:
    - API call failures
    - Third-party service timeouts
    - Network errors

    Example:
        raise ExternalServiceError("Weather API unavailable", service="OpenMeteo")
    """

    def __init__(
        self, message: str, service: str | None = None, error_id: str | None = None, **kwargs: Any
    ) -> None:
        super().__init__(message, error_id, service=service, **kwargs)
        self.service = service
