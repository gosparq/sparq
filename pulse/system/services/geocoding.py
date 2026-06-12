# -----------------------------------------------------------------------------
# sparQ - Geocoding Service
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""Reverse geocoding service using OpenStreetMap Nominatim API (free, no registration)."""

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
TIMEOUT = 5  # seconds


def _format_short_address(data: dict) -> str | None:
    """Build a short address from Nominatim structured address components.

    Format: "{house_number} {road}, {city}, {state} {postcode}, {country}"
    Falls back to None if no usable components are found.
    """
    addr = data.get("address", {})
    if not addr:
        return None

    parts: list[str] = []

    # House number + street
    house_number = addr.get("house_number")
    road = addr.get("road") or addr.get("street")
    if house_number and road:
        parts.append(f"{house_number} {road}")
    elif road:
        parts.append(road)

    # City/town/village (multiple Nominatim keys by settlement size)
    city = (
        addr.get("city")
        or addr.get("town")
        or addr.get("village")
        or addr.get("municipality")
        or addr.get("hamlet")
        or addr.get("suburb")
        or addr.get("county")
    )
    if city:
        parts.append(city)

    # State/province
    state = addr.get("state") or addr.get("province")
    if state:
        parts.append(state)

    # Postal code appended to last part
    postcode = addr.get("postcode")
    if postcode and parts:
        parts[-1] = f"{parts[-1]} {postcode}"

    # Country
    country = addr.get("country")
    if country:
        parts.append(country)

    return ", ".join(parts) if parts else None


def reverse_geocode(latitude: float, longitude: float, host: str | None = None) -> str | None:
    """Convert latitude/longitude coordinates to a human-readable address.

    Uses OpenStreetMap's Nominatim API which is free and requires no registration.

    Args:
        latitude: Latitude coordinate.
        longitude: Longitude coordinate.
        host: Instance domain for the User-Agent header.

    Returns:
        Human-readable address string, or None if geocoding fails.
    """
    try:
        user_agent = host or "unknown-instance"

        # Build request URL - zoom 18 gives street-level detail
        params = urllib.parse.urlencode({
            "lat": latitude,
            "lon": longitude,
            "format": "json",
            "addressdetails": 1,
            "zoom": 18,
        })
        url = f"{NOMINATIM_URL}?{params}"

        req = urllib.request.Request(url, headers={"User-Agent": user_agent})

        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            data = json.loads(response.read().decode("utf-8"))

        # Try structured address first, fall back to display_name
        address = _format_short_address(data)
        if address:
            return address

        display_name = data.get("display_name")
        if display_name:
            if len(display_name) > 150:
                return display_name[:147] + "..."
            return display_name

        return None

    except urllib.error.URLError as e:
        logger.warning(f"Geocoding network error: {e}")
        return None
    except json.JSONDecodeError as e:
        logger.warning(f"Geocoding JSON parse error: {e}")
        return None
    except Exception as e:
        logger.warning(f"Geocoding failed: {e}")
        return None


def reverse_geocode_async(
    latitude: float,
    longitude: float,
    callback: Callable[[str | None], None],
    host: str | None = None,
) -> None:
    """Reverse geocode coordinates asynchronously.

    Args:
        latitude: Latitude coordinate.
        longitude: Longitude coordinate.
        callback: Function to call with the result (address string or None).
        host: Instance domain for the User-Agent header.
    """
    from system.background import submit_task

    def do_geocode() -> None:
        result = reverse_geocode(latitude, longitude, host=host)
        callback(result)

    submit_task(do_geocode)
