# -----------------------------------------------------------------------------
# sparQ - OAuth Token Manager
#
# Description:
#     Handles encryption/decryption of OAuth tokens at rest and token refresh
#     logic. Uses Fernet symmetric encryption with a key derived from the
#     Flask SECRET_KEY.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

import base64
import hashlib
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


class TokenManager:
    """Manages OAuth token encryption and refresh."""

    _instance: Optional["TokenManager"] = None
    _fernet: Optional[Fernet] = None

    @classmethod
    def get_instance(cls) -> "TokenManager":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def init_app(cls, app) -> None:
        """Initialize with Flask app to get SECRET_KEY."""
        secret_key = app.config.get("SECRET_KEY", "dev")
        cls._init_fernet(secret_key)

    @classmethod
    def _init_fernet(cls, secret_key: str) -> None:
        """Initialize Fernet with a key derived from SECRET_KEY."""
        # Derive a 32-byte key from SECRET_KEY using SHA256
        key_bytes = hashlib.sha256(secret_key.encode()).digest()
        fernet_key = base64.urlsafe_b64encode(key_bytes)
        cls._fernet = Fernet(fernet_key)

    @classmethod
    def encrypt(cls, plaintext: str) -> str:
        """Encrypt a string (typically an OAuth token).

        Args:
            plaintext: The string to encrypt

        Returns:
            Base64-encoded encrypted string
        """
        if cls._fernet is None:
            # Fallback for testing or when app not initialized
            secret = os.environ.get("SECRET_KEY", "dev")
            cls._init_fernet(secret)

        if not plaintext:
            return ""

        encrypted = cls._fernet.encrypt(plaintext.encode())
        return encrypted.decode()

    @classmethod
    def decrypt(cls, ciphertext: str) -> str:
        """Decrypt a string.

        Args:
            ciphertext: Base64-encoded encrypted string

        Returns:
            Decrypted plaintext string
        """
        if cls._fernet is None:
            secret = os.environ.get("SECRET_KEY", "dev")
            cls._init_fernet(secret)

        if not ciphertext:
            return ""

        try:
            decrypted = cls._fernet.decrypt(ciphertext.encode())
            return decrypted.decode()
        except InvalidToken:
            logger.error("Failed to decrypt token - invalid or corrupted")
            return ""

    @staticmethod
    def is_token_expired(expires_at: Optional[datetime], buffer_minutes: int = 5) -> bool:
        """Check if a token is expired or will expire soon.

        Args:
            expires_at: Token expiration datetime (UTC)
            buffer_minutes: Consider expired if within this many minutes

        Returns:
            True if token is expired or will expire within buffer
        """
        if expires_at is None:
            return False  # No expiry = doesn't expire

        # Ensure we're comparing UTC times
        now = datetime.now(timezone.utc)
        if expires_at.tzinfo is None:
            # Assume naive datetime is UTC
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        buffer = timedelta(minutes=buffer_minutes)
        return now + buffer >= expires_at

    @staticmethod
    def calculate_expiry(expires_in: Optional[int]) -> Optional[datetime]:
        """Calculate expiry datetime from expires_in seconds.

        Args:
            expires_in: Seconds until token expires

        Returns:
            UTC datetime when token expires, or None if no expiry
        """
        if expires_in is None or expires_in <= 0:
            return None

        return datetime.now(timezone.utc) + timedelta(seconds=expires_in)
