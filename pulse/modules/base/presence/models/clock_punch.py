# -----------------------------------------------------------------------------
# sparQ - Clock Punch Model
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

import pytz
from flask import g

from system.api.serialization import SerializableMixin
from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.workspace import OrganizationMixin
from system.db.raise_on_lazy import LAZY

if TYPE_CHECKING:
    from modules.base.core.models.user import User


class PunchType(Enum):
    """Type of clock punch"""

    IN = "in"
    OUT = "out"


@ModelRegistry.register
class ClockPunch(db.Model, OrganizationMixin, SerializableMixin):
    """Clock punch for tracking member clock-in/clock-out times."""

    __tablename__ = "clock_punch"

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(
        db.Integer, db.ForeignKey("organization_user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    punch_type = db.Column(db.Enum(PunchType), nullable=False)
    punch_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Link to auto-created TimeEntry (set on clock-out)
    time_entry_id = db.Column(
        db.Integer, db.ForeignKey("time_entry.id", ondelete="SET NULL"), nullable=True
    )

    # Metadata
    source = db.Column(db.String(50), default="web")  # web, mobile, kiosk, api
    ip_address = db.Column(db.String(45), nullable=True)  # IPv4 or IPv6
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Geolocation data
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    location_accuracy = db.Column(db.Float, nullable=True)  # Accuracy in meters
    outside_geofence = db.Column(db.Boolean, default=False)  # Flag for punches outside geofence
    needs_review = db.Column(db.Boolean, default=False)  # Flag for punches requiring admin review
    location_address = db.Column(db.String(500), nullable=True)  # Reverse-geocoded address

    # Relationships
    member = db.relationship("OrganizationUser", backref=db.backref("clock_punches", lazy="dynamic"), lazy=LAZY)
    time_entry = db.relationship("TimeEntry", backref=db.backref("clock_punch", uselist=False, lazy=LAZY), lazy=LAZY)

    __table_args__ = (db.Index("ix_clock_punch_member_time", "member_id", "punch_time"),)

    # --- Class Methods ---

    @classmethod
    def clock_in(
        cls,
        member_id: int,
        source: str = "web",
        ip_address: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        location_accuracy: float | None = None,
        location_denied: bool = False,
    ) -> "ClockPunch":
        """Clock in a member. Raises ValueError if already clocked in."""
        from .settings import TimeTrackingSettings

        # Check if already clocked in
        if cls.is_clocked_in(member_id):
            raise ValueError("Employee is already clocked in")

        # Check geofence
        outside_geofence = False
        needs_review = False
        if latitude is not None and longitude is not None:
            within = TimeTrackingSettings.is_within_geofence(latitude, longitude)
            if within is False:  # Explicitly outside (not None)
                outside_geofence = True
                needs_review = True  # Mark for admin review
        elif location_denied and TimeTrackingSettings.is_geofence_enabled():
            outside_geofence = True
            needs_review = True

        punch = cls(
            member_id=member_id,
            punch_type=PunchType.IN,
            punch_time=datetime.utcnow(),
            source=source,
            ip_address=ip_address,
            latitude=latitude,
            longitude=longitude,
            location_accuracy=location_accuracy,
            outside_geofence=outside_geofence,
            needs_review=needs_review,
        )
        db.session.add(punch)
        db.session.commit()
        return punch

    @classmethod
    def clock_out(
        cls,
        member_id: int,
        source: str = "web",
        ip_address: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        location_accuracy: float | None = None,
        auto_create_timeentry: bool = True,
        location_denied: bool = False,
    ) -> "ClockPunch":
        """Clock out a member. Raises ValueError if not clocked in.
        Optionally auto-creates a TimeEntry based on the clock-in/out times.
        """
        from .settings import TimeTrackingSettings

        # Find the matching clock-in
        clock_in_punch = cls.get_last_clock_in(member_id)
        if not clock_in_punch:
            raise ValueError("Employee is not clocked in")

        # Check geofence
        outside_geofence = False
        needs_review = False
        if latitude is not None and longitude is not None:
            within = TimeTrackingSettings.is_within_geofence(latitude, longitude)
            if within is False:  # Explicitly outside (not None)
                outside_geofence = True
                needs_review = True  # Mark for admin review
        elif location_denied and TimeTrackingSettings.is_geofence_enabled():
            outside_geofence = True
            needs_review = True

        # Also check if the clock-in was outside geofence
        if clock_in_punch.outside_geofence or clock_in_punch.needs_review:
            needs_review = True

        punch_time = datetime.utcnow()
        punch = cls(
            member_id=member_id,
            punch_type=PunchType.OUT,
            punch_time=punch_time,
            source=source,
            ip_address=ip_address,
            latitude=latitude,
            longitude=longitude,
            location_accuracy=location_accuracy,
            outside_geofence=outside_geofence,
            needs_review=needs_review,
        )
        db.session.add(punch)

        # Auto-create TimeEntry if enabled
        if auto_create_timeentry:
            from .time_entry import TimeEntry

            settings = TimeTrackingSettings.get()
            clock_in_time = clock_in_punch.punch_time
            clock_out_time = punch_time

            # Apply rounding if enabled
            if settings.rounding_enabled:
                clock_in_time = cls.round_time(
                    clock_in_time, PunchType.IN, settings.rounding_minutes, settings.rounding_type
                )
                clock_out_time = cls.round_time(
                    clock_out_time, PunchType.OUT, settings.rounding_minutes, settings.rounding_type
                )

            # Calculate hours
            duration = clock_out_time - clock_in_time
            hours = Decimal(str(duration.total_seconds() / 3600)).quantize(Decimal("0.01"))

            # Handle negative or zero hours
            if hours <= 0:
                hours = Decimal("0.25")  # Minimum 15 minutes

            # Convert UTC times to local timezone for display (same as in timeclock)
            company_settings = g.get("company_settings")
            tz_name = company_settings.timezone if company_settings else "America/Chicago"
            local_tz = pytz.timezone(tz_name)
            local_clock_in = clock_in_punch.punch_time.replace(tzinfo=pytz.UTC).astimezone(local_tz)
            local_clock_out = punch_time.replace(tzinfo=pytz.UTC).astimezone(local_tz)

            # Create time entry (use local date, not UTC date)
            time_entry = TimeEntry.create(
                member_id=member_id,
                date=local_clock_in.date(),
                hours=hours,
                description=f"Clock: {local_clock_in.strftime('%I:%M %p')} - {local_clock_out.strftime('%I:%M %p')}",
                category="Clock",
            )
            punch.time_entry_id = time_entry.id

        db.session.commit()
        return punch

    @classmethod
    def is_clocked_in(cls, member_id: int) -> bool:
        """Check if member is currently clocked in."""
        return cls.get_last_clock_in(member_id) is not None

    @classmethod
    def get_last_clock_in(cls, member_id: int) -> "ClockPunch | None":
        """Get the last clock-in punch without a matching clock-out."""
        # Find the most recent punch for this member
        last_punch = (
            cls.scoped().filter_by(member_id=member_id)
            .order_by(cls.punch_time.desc())
            .first()
        )

        # If the last punch is a clock-in, member is clocked in
        if last_punch and last_punch.punch_type == PunchType.IN:
            return last_punch
        return None

    @classmethod
    def get_current_status(cls, member_id: int) -> dict:
        """Get current clock status for a member."""
        clock_in = cls.get_last_clock_in(member_id)
        if clock_in:
            elapsed = datetime.utcnow() - clock_in.punch_time
            return {
                "is_clocked_in": True,
                "clock_in_time": clock_in.punch_time,
                "elapsed": elapsed,
                "elapsed_str": cls._format_elapsed(elapsed),
                "outside_geofence": clock_in.outside_geofence,
            }
        return {
            "is_clocked_in": False,
            "clock_in_time": None,
            "elapsed": None,
            "elapsed_str": None,
            "outside_geofence": False,
        }

    @classmethod
    def get_todays_punches(cls, member_id: int) -> list["ClockPunch"]:
        """Get all punches for today for a member."""
        # Get today's date in company timezone
        company_settings = g.get("company_settings")
        tz_name = company_settings.timezone if company_settings else "America/Chicago"
        local_tz = pytz.timezone(tz_name)
        local_now = datetime.now(pytz.UTC).astimezone(local_tz)
        local_today = local_now.date()

        # Convert local day boundaries to UTC for query
        local_start = local_tz.localize(datetime.combine(local_today, datetime.min.time()))
        local_end = local_tz.localize(datetime.combine(local_today, datetime.max.time()))
        utc_start = local_start.astimezone(pytz.UTC).replace(tzinfo=None)
        utc_end = local_end.astimezone(pytz.UTC).replace(tzinfo=None)

        return (
            cls.scoped().filter(
                cls.member_id == member_id,
                cls.punch_time >= utc_start,
                cls.punch_time <= utc_end,
            )
            .order_by(cls.punch_time)
            .all()
        )

    @classmethod
    def get_todays_total_hours(cls, member_id: int) -> float:
        """Calculate total clocked hours from today's completed punch pairs.

        Iterates today's punches, pairs consecutive IN/OUT punches, and sums
        the duration of each completed pair.

        Args:
            member_id: The member's ID.

        Returns:
            Total hours as a float, rounded to 2 decimal places.
        """
        punches = cls.get_todays_punches(member_id)
        total_seconds = 0
        i = 0
        while i < len(punches) - 1:
            if punches[i].punch_type == PunchType.IN and punches[i + 1].punch_type == PunchType.OUT:
                duration = punches[i + 1].punch_time - punches[i].punch_time
                total_seconds += duration.total_seconds()
                i += 2
            else:
                i += 1
        return round(total_seconds / 3600, 2)

    @classmethod
    def get_employee_by_pin(cls, pin: str):
        """Look up an active org member by clock PIN."""
        from modules.base.core.models.organization_user import OrganizationUser

        return OrganizationUser.get_by_pin(pin, g.organization_id)

    @classmethod
    def get_clocked_in_members(cls) -> list[dict]:
        """Get all members currently clocked in (for In/Out Board).

        Returns org-level clock status for members who belong to the current
        workspace (filtered via WorkspaceUser join).
        """
        ws_id = getattr(g, "workspace_id", None)
        org_id = getattr(g, "organization_id", None)
        try:
            cache = getattr(g, "_clocked_in_members_cache", None)
            if cache is None:
                cache = {}
                g._clocked_in_members_cache = cache
            if ws_id in cache:
                return cache[ws_id]
        except Exception:
            cache = None

        from sqlalchemy import func
        from sqlalchemy.orm import joinedload

        from modules.base.core.models.organization_user import OrganizationUser
        from modules.base.core.models.workspace_user import WorkspaceUser

        members = (
            OrganizationUser.query
            .filter_by(organization_id=org_id, is_active=True, employment_status="ACTIVE")
            .join(WorkspaceUser, WorkspaceUser.organization_user_id == OrganizationUser.id)
            .filter(WorkspaceUser.workspace_id == ws_id, WorkspaceUser.deleted_at.is_(None))
            .options(joinedload(OrganizationUser.user))
            .all()
        )
        member_ids = [m.id for m in members]

        punch_map: dict[int, "ClockPunch"] = {}
        if member_ids:
            subq = (
                db.session.query(
                    cls.member_id,
                    func.max(cls.punch_time).label("max_time"),
                )
                .filter(
                    cls.organization_id == org_id,
                    cls.member_id.in_(member_ids),
                )
                .group_by(cls.member_id)
                .subquery()
            )
            latest_punches = (
                cls.query
                .join(
                    subq,
                    db.and_(
                        cls.member_id == subq.c.member_id,
                        cls.punch_time == subq.c.max_time,
                    ),
                )
                .all()
            )
            for p in latest_punches:
                if p.member_id not in punch_map or p.id > punch_map[p.member_id].id:
                    punch_map[p.member_id] = p

        now = datetime.utcnow()
        result = []
        for emp in members:
            punch = punch_map.get(emp.id)
            is_clocked_in = punch is not None and punch.punch_type == PunchType.IN
            clock_in_time = punch.punch_time if is_clocked_in else None
            elapsed = (now - punch.punch_time) if is_clocked_in else None
            result.append(
                {
                    "member": emp,
                    "is_clocked_in": is_clocked_in,
                    "clock_in_time": clock_in_time,
                    "elapsed_str": cls._format_elapsed(elapsed) if elapsed else None,
                    "outside_geofence": punch.outside_geofence if is_clocked_in else False,
                }
            )

        result.sort(key=lambda x: (not x["is_clocked_in"], x["member"].user.full_name if x["member"].user else ""))

        if cache is not None:
            cache[ws_id] = result
        return result

    @classmethod
    def set_location_address(cls, punch_id: int, address: str) -> None:
        """Set the reverse-geocoded location address for a clock punch.

        Args:
            punch_id: The ID of the punch to update.
            address: The human-readable address string.
        """
        punch = cls.scoped().filter_by(id=punch_id).first()
        if punch:
            punch.location_address = address
            db.session.commit()

    @classmethod
    def split_overnight_punches(cls, member_id: int | None = None) -> list[dict]:
        """Split open clock-in punches that have crossed midnight boundaries.

        Finds all members currently clocked in (open IN punch with no matching
        OUT) where the punch crosses one or more local-timezone midnight
        boundaries. For each midnight crossed, creates:
        - An OUT punch at 23:59:59 local time (source="auto-split")
        - A TimeEntry for the completed day
        - An IN punch at 00:00:00 the next day (source="auto-split")

        The member remains "clocked in" seamlessly — get_last_clock_in()
        will return the auto-created IN punch at midnight.

        Handles multi-day spans (e.g. member forgot to clock out for 3 days).
        Naturally idempotent: only processes IN punches without a matching OUT.

        Args:
            member_id: If provided, only check this member. Otherwise
                      checks all members with open clock-in punches.

        Returns:
            List of dicts with split info: [{"member_id": int, "splits": int}]
        """
        import logging

        from .settings import TimeTrackingSettings
        from .time_entry import TimeEntry

        logger = logging.getLogger(__name__)

        # Get company timezone without depending on Flask g context
        from modules.base.core.models.workspace_settings import WorkspaceSettings

        company_settings = WorkspaceSettings.scoped().first()
        tz_name = company_settings.timezone if company_settings else "America/Chicago"
        local_tz = pytz.timezone(tz_name)
        now_utc = datetime.utcnow()
        now_local = now_utc.replace(tzinfo=pytz.UTC).astimezone(local_tz)
        today_local = now_local.date()

        # Find open IN punches (no matching OUT after them)
        query = cls.scoped().filter(cls.punch_type == PunchType.IN)
        if member_id is not None:
            query = query.filter(cls.member_id == member_id)

        # Get all IN punches, ordered newest first
        in_punches = query.order_by(cls.punch_time.desc()).all()

        # Filter to only truly open IN punches (no OUT punch after them)
        open_punches = []
        for punch in in_punches:
            matching_out = punch.get_matching_out()
            if matching_out is None:
                open_punches.append(punch)

        # Get rounding settings
        settings = TimeTrackingSettings.get()

        results = []

        for in_punch in open_punches:
            # Convert punch time to local timezone
            punch_local = in_punch.punch_time.replace(tzinfo=pytz.UTC).astimezone(local_tz)
            punch_date = punch_local.date()

            # No split needed if same day
            if punch_date >= today_local:
                continue

            splits = 0
            current_in_punch = in_punch
            current_date = punch_date

            while current_date < today_local:
                next_date = current_date + timedelta(days=1)

                # Create OUT punch at 23:59:59 local time
                midnight_out_local = local_tz.localize(
                    datetime.combine(current_date, datetime.max.time().replace(microsecond=0))
                )
                midnight_out_utc = midnight_out_local.astimezone(pytz.UTC).replace(tzinfo=None)

                out_punch = cls(
                    member_id=current_in_punch.member_id,
                    punch_type=PunchType.OUT,
                    punch_time=midnight_out_utc,
                    source="auto-split",
                    created_at=now_utc,
                )
                db.session.add(out_punch)
                db.session.flush()  # Get out_punch.id for time_entry_id link

                # Calculate hours for this day's segment
                clock_in_time = current_in_punch.punch_time
                clock_out_time = midnight_out_utc

                # Apply rounding if enabled
                if settings.rounding_enabled:
                    clock_in_time = cls.round_time(
                        clock_in_time, PunchType.IN, settings.rounding_minutes, settings.rounding_type
                    )
                    clock_out_time = cls.round_time(
                        clock_out_time, PunchType.OUT, settings.rounding_minutes, settings.rounding_type
                    )

                duration = clock_out_time - clock_in_time
                hours = Decimal(str(duration.total_seconds() / 3600)).quantize(Decimal("0.01"))
                if hours <= 0:
                    hours = Decimal("0.25")

                # Convert to local for TimeEntry description
                local_in = current_in_punch.punch_time.replace(tzinfo=pytz.UTC).astimezone(local_tz)
                local_out = midnight_out_local

                time_entry = TimeEntry.create(
                    member_id=current_in_punch.member_id,
                    date=current_date,
                    hours=hours,
                    description=f"Clock: {local_in.strftime('%I:%M %p')} - {local_out.strftime('%I:%M %p')}",
                    category="Clock",
                )
                out_punch.time_entry_id = time_entry.id

                # Create IN punch at 00:00:00 next day local time
                midnight_in_local = local_tz.localize(
                    datetime.combine(next_date, datetime.min.time())
                )
                midnight_in_utc = midnight_in_local.astimezone(pytz.UTC).replace(tzinfo=None)

                new_in_punch = cls(
                    member_id=current_in_punch.member_id,
                    punch_type=PunchType.IN,
                    punch_time=midnight_in_utc,
                    source="auto-split",
                    created_at=now_utc,
                )
                db.session.add(new_in_punch)

                current_in_punch = new_in_punch
                current_date = next_date
                splits += 1

            if splits > 0:
                db.session.commit()
                logger.info(
                    f"Auto-split {splits} midnight boundary(ies) for member {in_punch.member_id}"
                )
                results.append({"member_id": in_punch.member_id, "splits": splits})

        return results

    def update_clock_in_time(self, new_time_str: str, timezone_str: str,
                             adjusted_by_id: int) -> str | None:
        """Parse and update this clock-in punch's time from a form time string.

        Validates the new time, records an audit trail, and commits.

        Args:
            new_time_str: Time string in "HH:MM" format (local timezone).
            timezone_str: Timezone name (e.g., "America/Chicago").
            adjusted_by_id: User ID of the admin making the adjustment.

        Returns:
            Error message string if validation fails, None on success.
        """
        import pytz

        local_tz = pytz.timezone(timezone_str)
        original_local = self.punch_time.replace(tzinfo=pytz.UTC).astimezone(local_tz)

        # Parse the new time
        try:
            new_time_parts = new_time_str.split(":")
            new_hour = int(new_time_parts[0])
            new_minute = int(new_time_parts[1])
        except (ValueError, IndexError):
            return "Invalid time format"

        # Create new local datetime with the new time
        new_local = original_local.replace(hour=new_hour, minute=new_minute, second=0, microsecond=0)

        # Validate: new time cannot be in the future
        now_local = datetime.now(pytz.UTC).astimezone(local_tz)
        if new_local > now_local:
            return "Clock-in time cannot be in the future"

        # Convert back to UTC for storage
        new_utc = new_local.astimezone(pytz.UTC).replace(tzinfo=None)

        # Validate using existing model method
        error = self.validate_new_time(new_utc, timezone_str)
        if error:
            return error

        # Record the audit trail and update
        from .clock_punch_adjustment import ClockPunchAdjustment

        ClockPunchAdjustment.record(
            clock_punch_id=self.id,
            adjusted_by_id=adjusted_by_id,
            original_punch_time=self.punch_time,
            new_punch_time=new_utc,
        )

        self.punch_time = new_utc
        db.session.commit()
        return None

    @staticmethod
    def round_time(
        punch_time: datetime,
        punch_type: PunchType,
        rounding_minutes: int = 15,
        rounding_type: str = "employee_friendly",
    ) -> datetime:
        """Round punch time based on settings.

        Employee-friendly (default):
            - Clock-in: Round DOWN (7:07 -> 7:00)
            - Clock-out: Round UP (4:53 -> 5:00)

        Employer-friendly:
            - Clock-in: Round UP (7:07 -> 7:15)
            - Clock-out: Round DOWN (4:53 -> 4:45)

        Nearest:
            - Round to nearest interval (7:07 -> 7:00, 7:08 -> 7:15)
        """
        minutes = punch_time.minute
        remainder = minutes % rounding_minutes

        if remainder == 0:
            # Already on boundary
            rounded_minutes = minutes
        elif rounding_type == "employee_friendly":
            if punch_type == PunchType.IN:
                rounded_minutes = minutes - remainder  # Round down
            else:
                rounded_minutes = minutes + (rounding_minutes - remainder)  # Round up
        elif rounding_type == "employer_friendly":
            if punch_type == PunchType.IN:
                rounded_minutes = minutes + (rounding_minutes - remainder)  # Round up
            else:
                rounded_minutes = minutes - remainder  # Round down
        else:  # nearest
            if remainder < rounding_minutes / 2:
                rounded_minutes = minutes - remainder
            else:
                rounded_minutes = minutes + (rounding_minutes - remainder)

        # Handle hour overflow
        hour_adjustment = rounded_minutes // 60
        rounded_minutes = rounded_minutes % 60

        return punch_time.replace(
            minute=rounded_minutes, second=0, microsecond=0
        ) + timedelta(hours=hour_adjustment)

    @staticmethod
    def _format_elapsed(elapsed: timedelta) -> str:
        """Format elapsed time as human-readable string."""
        total_seconds = int(elapsed.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, _ = divmod(remainder, 60)

        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"

    # --- Query Methods for Specific Day/Punch Relationships ---

    @classmethod
    def get_for_day(
        cls, member_id: int, view_date: date, timezone: str | None = None
    ) -> list[ClockPunch]:
        """Get all punches for a member on a specific day in local timezone.

        Each punch in the returned list has a `punch_time_local` attribute set
        for convenient template display.

        Args:
            member_id: The member's ID.
            view_date: The date to query (in local timezone).
            timezone: Timezone name (e.g., "America/Chicago"). If not provided,
                     uses company settings.

        Returns:
            List of ClockPunch objects ordered by punch_time.
        """
        # Get timezone
        if timezone is None:
            company_settings = g.get("company_settings")
            timezone = company_settings.timezone if company_settings else "America/Chicago"
        local_tz = pytz.timezone(timezone)

        # Convert local day boundaries to UTC for query
        local_start = local_tz.localize(datetime.combine(view_date, datetime.min.time()))
        local_end = local_tz.localize(datetime.combine(view_date, datetime.max.time()))
        utc_start = local_start.astimezone(pytz.UTC).replace(tzinfo=None)
        utc_end = local_end.astimezone(pytz.UTC).replace(tzinfo=None)

        punches = (
            cls.scoped().filter(
                cls.member_id == member_id,
                cls.punch_time >= utc_start,
                cls.punch_time <= utc_end,
            )
            .order_by(cls.punch_time.asc())
            .all()
        )

        # Add local time attribute to each punch for template display
        for punch in punches:
            punch.punch_time_local = punch.punch_time.replace(tzinfo=pytz.UTC).astimezone(local_tz)

        return punches

    def get_matching_in(self) -> ClockPunch | None:
        """Find the clock-in punch that pairs with this clock-out punch.

        For an OUT punch, finds the most recent IN punch before this punch
        for the same member.

        Returns:
            The matching ClockPunch (IN type) or None if not found or
            if this is not an OUT punch.
        """
        if self.punch_type != PunchType.OUT:
            return None

        return (
            ClockPunch.scoped().filter(
                ClockPunch.member_id == self.member_id,
                ClockPunch.punch_type == PunchType.IN,
                ClockPunch.punch_time < self.punch_time,
            )
            .order_by(ClockPunch.punch_time.desc())
            .first()
        )

    def get_matching_out(self) -> ClockPunch | None:
        """Find the clock-out punch that pairs with this clock-in punch.

        For an IN punch, finds the earliest OUT punch after this punch
        for the same member.

        Returns:
            The matching ClockPunch (OUT type) or None if not found or
            if this is not an IN punch.
        """
        if self.punch_type != PunchType.IN:
            return None

        return (
            ClockPunch.scoped().filter(
                ClockPunch.member_id == self.member_id,
                ClockPunch.punch_type == PunchType.OUT,
                ClockPunch.punch_time > self.punch_time,
            )
            .order_by(ClockPunch.punch_time.asc())
            .first()
        )

    def validate_new_time(self, new_time_utc: datetime, timezone: str | None = None) -> str | None:
        """Validate a proposed new punch time.

        Checks:
        - Time is the same as current punch time
        - Time is not in the future
        - OUT punch time is after matching IN punch
        - IN punch time is before matching OUT punch
        - IN punch time is after previous session's OUT punch
        - OUT punch time is before next session's IN punch

        Args:
            new_time_utc: The proposed new punch time in UTC (naive datetime).
            timezone: Timezone name for future check. Uses company settings if not provided.

        Returns:
            Error message string if validation fails, None if valid.
        """
        # Get timezone for future check
        if timezone is None:
            company_settings = g.get("company_settings")
            timezone = company_settings.timezone if company_settings else "America/Chicago"
        local_tz = pytz.timezone(timezone)

        # Check: not the same as current time
        if new_time_utc.replace(second=0, microsecond=0) == self.punch_time.replace(second=0, microsecond=0):
            return "New time must be different from the current punch time"

        # Check: not in the future
        now_local = datetime.now(pytz.UTC).astimezone(local_tz)
        new_time_local = new_time_utc.replace(tzinfo=pytz.UTC).astimezone(local_tz)
        if new_time_local > now_local:
            return "Punch time cannot be in the future"

        # Check punch relationships
        if self.punch_type == PunchType.OUT:
            # OUT punch: must be after matching IN
            matching_in = (
                ClockPunch.scoped().filter(
                    ClockPunch.member_id == self.member_id,
                    ClockPunch.punch_type == PunchType.IN,
                    ClockPunch.punch_time < self.punch_time,  # Use original time to find pair
                )
                .order_by(ClockPunch.punch_time.desc())
                .first()
            )
            if matching_in and new_time_utc <= matching_in.punch_time:
                return "Clock out time must be after the clock in time"

            # OUT punch: must not overlap with next session
            next_in = (
                ClockPunch.scoped().filter(
                    ClockPunch.member_id == self.member_id,
                    ClockPunch.punch_type == PunchType.IN,
                    ClockPunch.punch_time >= self.punch_time,
                )
                .order_by(ClockPunch.punch_time.asc())
                .first()
            )
            if next_in and new_time_utc >= next_in.punch_time:
                return "Clock out time cannot be after the next clock in time"

        elif self.punch_type == PunchType.IN:
            # IN punch: must be before matching OUT
            matching_out = (
                ClockPunch.scoped().filter(
                    ClockPunch.member_id == self.member_id,
                    ClockPunch.punch_type == PunchType.OUT,
                    ClockPunch.punch_time > self.punch_time,  # Use original time to find pair
                )
                .order_by(ClockPunch.punch_time.asc())
                .first()
            )
            if matching_out and new_time_utc >= matching_out.punch_time:
                return "Clock in time must be before the clock out time"

            # IN punch: must not overlap with previous session
            previous_out = (
                ClockPunch.scoped().filter(
                    ClockPunch.member_id == self.member_id,
                    ClockPunch.punch_type == PunchType.OUT,
                    ClockPunch.punch_time <= self.punch_time,
                )
                .order_by(ClockPunch.punch_time.desc())
                .first()
            )
            if previous_out and new_time_utc <= previous_out.punch_time:
                return "Clock in time cannot be before the previous clock out time"

        return None

    def update_time(
        self,
        new_time_utc: datetime,
        adjusted_by: User,
        reason: str | None = None,
    ) -> None:
        """Update punch time with audit trail and TimeEntry recalculation.

        Records the adjustment for audit purposes, updates the punch time,
        and triggers recalculation of the associated TimeEntry if applicable.

        Args:
            new_time_utc: The new punch time in UTC (naive datetime).
            adjusted_by: The User making the adjustment.
            reason: Optional reason for the adjustment.

        Note:
            Caller should validate with validate_new_time() before calling.
            Commits the database session.
        """
        from .clock_punch_adjustment import ClockPunchAdjustment

        # Record the adjustment for audit trail
        ClockPunchAdjustment.record(
            clock_punch_id=self.id,
            adjusted_by_id=adjusted_by.id,
            original_punch_time=self.punch_time,
            new_punch_time=new_time_utc,
            reason=reason if reason else None,
        )

        # Update the punch time
        self.punch_time = new_time_utc
        db.session.commit()

        # Recalculate TimeEntry
        self._recalculate_related_time_entry()

    def _recalculate_related_time_entry(self) -> None:
        """Recalculate the TimeEntry associated with this punch or its pair."""
        from sqlalchemy.orm import joinedload

        from .time_entry import TimeEntry

        if self.time_entry_id:
            # This is an OUT punch - recalculate directly
            time_entry = (
                TimeEntry.scoped()
                .options(joinedload(TimeEntry.clock_punch))
                .filter_by(id=self.time_entry_id)
                .first()
            )
            if time_entry:
                time_entry.recalculate_from_punches()
        elif self.punch_type == PunchType.IN:
            # This is an IN punch - find the matching OUT punch and recalculate
            matching_out = self.get_matching_out()
            if matching_out and matching_out.time_entry_id:
                time_entry = (
                    TimeEntry.scoped()
                    .options(joinedload(TimeEntry.clock_punch))
                    .filter_by(id=matching_out.time_entry_id)
                    .first()
                )
                if time_entry:
                    time_entry.recalculate_from_punches()
