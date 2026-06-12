# -----------------------------------------------------------------------------
# sparQ - Resume Parser Service
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# Integrates with the sparQ Resume Parser API to extract candidate information
# from uploaded resume files.
# -----------------------------------------------------------------------------

import os
import requests
from dataclasses import dataclass
from typing import Optional
from werkzeug.datastructures import FileStorage


PARSER_API_URL = os.environ.get("RESUME_PARSER_URL", "")
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".rtf"}


@dataclass
class ParsedField:
    """A parsed field with its value and confidence score."""
    value: Optional[str]
    confidence: float = 0.0


@dataclass
class ParsedResume:
    """Structured data extracted from a resume."""
    first_name: ParsedField
    last_name: ParsedField
    email: ParsedField
    phone: ParsedField
    city: ParsedField
    state: ParsedField
    current_title: ParsedField
    current_company: ParsedField
    linkedin_url: ParsedField

    # Metadata
    success: bool = True
    error_message: Optional[str] = None

    def to_form_data(self) -> dict:
        """Convert to dictionary for form pre-population.

        Only includes fields with values.
        """
        data = {}

        if self.first_name.value:
            data["first_name"] = self.first_name.value
        if self.last_name.value:
            data["last_name"] = self.last_name.value
        if self.email.value:
            data["email"] = self.email.value
        if self.phone.value:
            data["phone"] = self.phone.value
        if self.city.value:
            data["city"] = self.city.value
        if self.state.value:
            data["state"] = self.state.value
        if self.current_title.value:
            data["current_title"] = self.current_title.value
        if self.current_company.value:
            data["current_company"] = self.current_company.value
        if self.linkedin_url.value:
            data["linkedin_url"] = self.linkedin_url.value

        return data

    @classmethod
    def empty(cls, error_message: Optional[str] = None) -> "ParsedResume":
        """Create an empty ParsedResume (for errors or unsupported files)."""
        empty_field = ParsedField(value=None, confidence=0.0)
        return cls(
            first_name=empty_field,
            last_name=empty_field,
            email=empty_field,
            phone=empty_field,
            city=empty_field,
            state=empty_field,
            current_title=empty_field,
            current_company=empty_field,
            linkedin_url=empty_field,
            success=False,
            error_message=error_message,
        )


def is_supported_file(filename: str) -> bool:
    """Check if the file extension is supported for parsing."""
    if not filename or "." not in filename:
        return False
    ext = "." + filename.rsplit(".", 1)[1].lower()
    return ext in SUPPORTED_EXTENSIONS


def parse_resume(file: FileStorage, timeout: int = 30) -> ParsedResume:
    """Parse a resume file and extract candidate information.

    Args:
        file: The uploaded resume file
        timeout: Request timeout in seconds

    Returns:
        ParsedResume with extracted fields and confidence scores
    """
    if not file or not file.filename:
        return ParsedResume.empty("No file provided")

    if not is_supported_file(file.filename):
        return ParsedResume.empty("Unsupported file format. Supported: PDF, DOCX, DOC, TXT, RTF")

    try:
        # Reset file position to beginning
        file.seek(0)

        # Send to parser API
        response = requests.post(
            PARSER_API_URL,
            files={"file": (file.filename, file.stream, file.content_type or "application/octet-stream")},
            timeout=timeout,
        )

        # Reset file position for subsequent saves
        file.seek(0)

        if response.status_code == 429:
            return ParsedResume.empty("Rate limit exceeded. Please try again later.")

        if response.status_code == 400:
            return ParsedResume.empty("Invalid or unsupported file format")

        if response.status_code != 200:
            return ParsedResume.empty(f"Parser service error (status {response.status_code})")

        try:
            data = response.json()
        except Exception as e:
            return ParsedResume.empty(f"Invalid JSON response: {str(e)}")

        import logging
        logging.info(f"Resume parser API response: {data}")

        # API returns "success": true, not "status": "success"
        if not data.get("success"):
            error_msg = data.get("error") or data.get("message") or "Unknown parsing error"
            return ParsedResume.empty(error_msg)

        parsed_data = data.get("data", {})

        def extract_field(field_name: str, parent: dict = None) -> ParsedField:
            """Extract a field from the parsed data."""
            source = parent if parent is not None else parsed_data
            field = source.get(field_name, {})
            if isinstance(field, dict) and "value" in field:
                return ParsedField(
                    value=field.get("value"),
                    confidence=field.get("confidence", 0.0),
                )
            return ParsedField(value=None, confidence=0.0)

        # Address fields are nested under "address"
        address_data = parsed_data.get("address", {})
        # Social fields are nested under "social"
        social_data = parsed_data.get("social", {})

        return ParsedResume(
            first_name=extract_field("first_name"),
            last_name=extract_field("last_name"),
            email=extract_field("email"),
            phone=extract_field("phone"),
            city=extract_field("city", address_data),
            state=extract_field("state", address_data),
            current_title=extract_field("current_title"),
            current_company=extract_field("current_company"),
            linkedin_url=extract_field("linkedin", social_data),
            success=True,
        )

    except requests.Timeout:
        return ParsedResume.empty("Parser service timeout. Please try again.")
    except requests.RequestException as e:
        return ParsedResume.empty(f"Failed to connect to parser service: {str(e)}")
    except Exception as e:
        return ParsedResume.empty(f"Unexpected error: {str(e)}")
