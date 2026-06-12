# -----------------------------------------------------------------------------
# sparQ - SMS Service
#
# Description:
#     SMS sending service.
#     Supports sparQ SMS provider via environment variables.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

import logging
import os

import requests

logger = logging.getLogger(__name__)

SPARQSMS_API_URL = os.environ.get("SPARQSMS_API_URL", "")


def is_configured() -> bool:
    """Check if SMS service is configured.

    Returns:
        True if SMS API URL and API key are configured via environment variables
    """
    return bool(SPARQSMS_API_URL) and bool(os.environ.get("SPARQSMS_API_KEY"))


def send_sms(to: str, body: str, timeout: int = 30) -> bool:
    """Send SMS via sparQ SMS API.

    Args:
        to: Phone number (E.164 format preferred, e.g., +15551234567)
        body: SMS text content
        timeout: Request timeout in seconds

    Returns:
        True if sent successfully, False otherwise
    """
    api_key = os.environ.get("SPARQSMS_API_KEY")
    if not SPARQSMS_API_URL or not api_key:
        logger.warning("[SPARQSMS] SMS not configured (set SPARQSMS_API_URL and SPARQSMS_API_KEY)")
        return False

    logger.info("[SPARQSMS] Sending SMS to %s", _mask_phone(to))

    try:
        response = requests.post(
            SPARQSMS_API_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            json={
                "to": to,
                "body": body,
            },
            timeout=timeout,
        )

        if response.status_code in (200, 202):
            logger.info("[SPARQSMS] SMS sent successfully to %s", _mask_phone(to))
            return True
        else:
            logger.error("[SPARQSMS] Failed to send SMS: %s - %s", response.status_code, response.text)
            return False

    except requests.Timeout:
        logger.error("[SPARQSMS] Request timed out after %ds", timeout)
        return False
    except requests.RequestException as e:
        logger.exception("[SPARQSMS] Error sending SMS: %s", str(e))
        return False


def _mask_phone(phone: str) -> str:
    """Mask phone number for logging (show last 4 digits).

    Args:
        phone: Phone number

    Returns:
        Masked phone number like ***1234
    """
    digits = "".join(filter(str.isdigit, phone))
    if len(digits) <= 4:
        return "***" + digits
    return "***" + digits[-4:]
