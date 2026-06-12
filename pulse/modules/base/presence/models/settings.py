# -----------------------------------------------------------------------------
# sparQ - Time Tracking Settings Model
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

import secrets
from datetime import datetime

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.workspace import OrganizationMixin


# Association table for notification recipients (many-to-many: settings <-> users)
timesheet_notification_recipients = db.Table(
    "timesheet_notification_recipients",
    db.Column("settings_id", db.Integer, db.ForeignKey("presence_settings.id", ondelete="CASCADE"), primary_key=True),
    db.Column("user_id", db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), primary_key=True),
)

# Register the association table with ModelRegistry
ModelRegistry.register_table(timesheet_notification_recipients, "presence")


@ModelRegistry.register
class TimeTrackingSettings(db.Model, OrganizationMixin):
    """Singleton settings for Time Tracking module."""

    __tablename__ = "presence_settings"

    id = db.Column(db.Integer, primary_key=True)

    # Time Clock feature
    time_clock_enabled = db.Column(db.Boolean, default=True)

    # Rounding settings
    rounding_enabled = db.Column(db.Boolean, default=True)
    rounding_minutes = db.Column(db.Integer, default=15)  # 5, 6, 10, 15, 30, 60
    rounding_type = db.Column(
        db.String(20), default="employee_friendly"
    )  # employee_friendly, employer_friendly, nearest

    # In/Out Board settings
    board_enabled = db.Column(db.Boolean, default=True)
    board_visible_to_all = db.Column(db.Boolean, default=True)  # vs admin-only
    public_board_token = db.Column(db.String(64), unique=True, nullable=True)  # Secret token for public TV display

    # Auto-close settings (for missed clock-outs)
    auto_close_enabled = db.Column(db.Boolean, default=False)
    auto_close_after_hours = db.Column(db.Integer, default=12)  # Hours after clock-in

    # Geofencing settings
    geofence_enabled = db.Column(db.Boolean, default=False)
    geofence_enforcement = db.Column(db.String(10), default="soft")  # "soft" or "hard"
    geofence_use_company_address = db.Column(db.Boolean, default=True)  # Use company address vs custom
    geofence_latitude = db.Column(db.Float, nullable=True)  # Geofence latitude
    geofence_longitude = db.Column(db.Float, nullable=True)  # Geofence longitude
    geofence_radius_meters = db.Column(db.Integer, default=100)  # Radius in meters
    # Custom address fields (when not using company address)
    geofence_address = db.Column(db.String(255), nullable=True)
    geofence_city = db.Column(db.String(100), nullable=True)
    geofence_state = db.Column(db.String(100), nullable=True)
    geofence_zip = db.Column(db.String(20), nullable=True)

    # Flow/Free auto-reset time
    flow_reset_time = db.Column(db.String(5), default="18:00")

    # Pulse nudge settings
    pulse_nudge_enabled = db.Column(db.Boolean, default=True)
    pulse_nudge_time = db.Column(db.String(5), default="09:00")

    # End of day nudge settings
    eod_nudge_enabled = db.Column(db.Boolean, default=True)
    eod_nudge_time = db.Column(db.String(5), default="17:00")

    # Timestamps
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Email notification settings
    notify_on_submission = db.Column(db.Boolean, default=False)
    notification_recipients = db.relationship(
        "User",
        secondary=timesheet_notification_recipients,
        backref=db.backref("timesheet_notification_settings", lazy="dynamic"),
        lazy="dynamic",
    )

    # --- Singleton pattern ---

    @classmethod
    def get(cls) -> "TimeTrackingSettings":
        """Get the settings singleton (keyed by organization). Creates one if it doesn't exist."""
        from flask import g
        org_id = getattr(g, "organization_id", None)
        try:
            cache = getattr(g, "_presence_settings_cache", None)
            if cache is None:
                cache = {}
                g._presence_settings_cache = cache
            if org_id in cache:
                return cache[org_id]
        except Exception:
            cache = None

        settings = cls.scoped().first()
        if not settings:
            settings = cls()
            db.session.add(settings)
            db.session.commit()

        if cache is not None:
            cache[org_id] = settings
        return settings

    @classmethod
    def update_settings(
        cls,
        time_clock_enabled: bool | None = None,
        rounding_enabled: bool | None = None,
        rounding_minutes: int | None = None,
        rounding_type: str | None = None,
        board_enabled: bool | None = None,
        board_visible_to_all: bool | None = None,
        auto_close_enabled: bool | None = None,
        auto_close_after_hours: int | None = None,
    ) -> "TimeTrackingSettings":
        """Update settings. Only provided values are changed."""
        settings = cls.get()

        if time_clock_enabled is not None:
            settings.time_clock_enabled = time_clock_enabled
        if rounding_enabled is not None:
            settings.rounding_enabled = rounding_enabled
        if rounding_minutes is not None:
            if rounding_minutes not in [5, 6, 10, 15, 30, 60]:
                raise ValueError("Invalid rounding interval")
            settings.rounding_minutes = rounding_minutes
        if rounding_type is not None:
            if rounding_type not in ["employee_friendly", "employer_friendly", "nearest"]:
                raise ValueError("Invalid rounding type")
            settings.rounding_type = rounding_type
        if board_enabled is not None:
            settings.board_enabled = board_enabled
        if board_visible_to_all is not None:
            settings.board_visible_to_all = board_visible_to_all
        if auto_close_enabled is not None:
            settings.auto_close_enabled = auto_close_enabled
        if auto_close_after_hours is not None:
            if auto_close_after_hours < 1 or auto_close_after_hours > 24:
                raise ValueError("Auto-close hours must be between 1 and 24")
            settings.auto_close_after_hours = auto_close_after_hours

        db.session.commit()
        return settings

    # --- Feature checks ---

    @classmethod
    def is_time_clock_enabled(cls) -> bool:
        """Check if Time Clock feature is enabled."""
        return cls.get().time_clock_enabled

    @classmethod
    def is_board_enabled(cls) -> bool:
        """Check if In/Out Board is enabled."""
        return cls.get().board_enabled

    @classmethod
    def is_board_visible_to_user(cls, user) -> bool:
        """Check if In/Out Board is visible to the given user."""
        settings = cls.get()
        if not settings.board_enabled:
            return False
        if settings.board_visible_to_all:
            return True
        return user.is_admin

    @classmethod
    def get_or_create_public_token(cls) -> str:
        """Get or create the public board token for TV display."""
        settings = cls.get()
        if not settings.public_board_token:
            settings.public_board_token = secrets.token_urlsafe(32)
            db.session.commit()
        return settings.public_board_token

    @classmethod
    def validate_public_token(cls, token: str) -> bool:
        """Validate a public board token."""
        settings = cls.get()
        return settings.public_board_token and settings.public_board_token == token

    # --- Geofencing methods ---

    @classmethod
    def is_geofence_enabled(cls) -> bool:
        """Check if geofencing is enabled."""
        return cls.get().geofence_enabled

    @classmethod
    def get_geofence_coords(cls) -> tuple[float, float] | None:
        """Get geofence center coordinates (lat, lng).

        Coordinates are stored on this model regardless of whether the company
        address or a custom address was geocoded. Returns None if not configured.
        """
        settings = cls.get()
        if not settings.geofence_enabled:
            return None

        if settings.geofence_latitude and settings.geofence_longitude:
            return (settings.geofence_latitude, settings.geofence_longitude)
        return None

    @classmethod
    def is_within_geofence(cls, lat: float | None, lng: float | None) -> bool | None:
        """Check if given coordinates are within the geofence.

        Returns:
            True if within geofence
            False if outside geofence
            None if geofencing disabled or coords not provided
        """
        if lat is None or lng is None:
            return None

        settings = cls.get()
        if not settings.geofence_enabled:
            return None

        geofence_coords = cls.get_geofence_coords()
        if geofence_coords is None:
            return None  # Geofence not configured

        distance = cls._haversine_distance(
            lat, lng, geofence_coords[0], geofence_coords[1]
        )
        return distance <= settings.geofence_radius_meters

    @classmethod
    def check_geofence(
        cls,
        latitude: float | None,
        longitude: float | None,
        location_denied: bool = False,
    ) -> tuple[bool, bool]:
        """Check geofence and return whether the punch should be blocked.

        Args:
            latitude: Client latitude (or None).
            longitude: Client longitude (or None).
            location_denied: Whether the client denied location access.

        Returns:
            Tuple of (blocked, outside_geofence):
            - blocked: True if hard enforcement should block the punch.
            - outside_geofence: True if the punch is outside the geofence.
        """
        settings = cls.get()
        if not settings.geofence_enabled:
            return False, False

        if latitude is not None and longitude is not None:
            within = cls.is_within_geofence(latitude, longitude)
            if within is False:
                blocked = settings.geofence_enforcement == "hard"
                return blocked, True
            return False, False

        if location_denied:
            blocked = settings.geofence_enforcement == "hard"
            return blocked, True

        return False, False

    @staticmethod
    def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points in meters using Haversine formula."""
        from math import atan2, cos, radians, sin, sqrt

        R = 6371000  # Earth radius in meters
        phi1, phi2 = radians(lat1), radians(lat2)
        delta_phi = radians(lat2 - lat1)
        delta_lambda = radians(lon2 - lon1)
        a = sin(delta_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(delta_lambda / 2) ** 2
        return R * 2 * atan2(sqrt(a), sqrt(1 - a))

    @classmethod
    def save_geofence_coords(cls, latitude: float, longitude: float) -> "TimeTrackingSettings":
        """Save geocoded coordinates for the geofence center."""
        settings = cls.get()
        settings.geofence_latitude = latitude
        settings.geofence_longitude = longitude
        db.session.commit()
        return settings

    def update_geofence(self, *, enabled: bool, enforcement: str, use_company_address: bool,
                        radius_meters: int, address: str | None = None, city: str | None = None,
                        state: str | None = None, zip_code: str | None = None,
                        latitude: float | None = None, longitude: float | None = None) -> None:
        """Update geofencing settings."""
        self.geofence_enabled = enabled
        self.geofence_enforcement = enforcement
        self.geofence_use_company_address = use_company_address
        self.geofence_radius_meters = radius_meters
        if not use_company_address:
            self.geofence_address = address
            self.geofence_city = city
            self.geofence_state = state
            self.geofence_zip = zip_code
            self.geofence_latitude = latitude
            self.geofence_longitude = longitude
        db.session.commit()

    # --- Notification settings methods ---

    @classmethod
    def get_notification_recipients(cls) -> list["User"]:  # noqa: F821
        """Get users to notify when timesheets are submitted.

        Returns empty list if notifications are disabled.
        Filters out terminated/inactive members.
        """
        from modules.base.core.models.user import User  # noqa: F401 - for type hint

        settings = cls.get()
        if not settings.notify_on_submission:
            return []

        # Filter to only include active users with contactable member profiles
        recipients = []
        for user in settings.notification_recipients:
            # Check if user is active
            if not user.is_active:
                continue
            # Check if member profile exists and is contactable
            if hasattr(user, "workspace_membership") and user.workspace_membership:
                if not user.workspace_membership.is_contactable:
                    continue
            recipients.append(user)

        return recipients

    @classmethod
    def set_notification_recipients(cls, user_ids: list[int]) -> None:
        """Set the users to notify on timesheet submission."""
        from modules.base.core.models.user import User

        settings = cls.get()
        settings.notification_recipients = User.get_by_ids(user_ids) if user_ids else []
        db.session.commit()
