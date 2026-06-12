# -----------------------------------------------------------------------------
# sparQ - Sync Module Event Model
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""Event model for internal calendar management.

This module provides the Event model for managing company-wide
calendar events visible to all employees.

Classes:
    Event: Company-wide calendar event model.

Example:
    Creating a company event::

        event = Event.create(
            title="Company All-Hands",
            scheduled_date=date(2025, 1, 20),
            scheduled_start_time=time(14, 0),
            scheduled_end_time=time(15, 0),
            is_all_day=False,
            location="Conference Room A"
        )

    Getting upcoming events::

        events = Event.get_upcoming(limit=10)
"""

from datetime import date, datetime, time

from flask_login import current_user

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.mixins import AuditMixin
from system.db.workspace import WorkspaceMixin


@ModelRegistry.register
class Event(db.Model, WorkspaceMixin, AuditMixin):
    """Company-wide calendar event visible to all employees."""

    __tablename__ = "event"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)

    # Scheduling
    scheduled_date = db.Column(db.Date, nullable=False, index=True)
    scheduled_start_time = db.Column(db.Time, nullable=True)
    scheduled_end_time = db.Column(db.Time, nullable=True)
    is_all_day = db.Column(db.Boolean, default=True)

    # Location (optional)
    location = db.Column(db.String(255))

    # Holiday flag
    is_holiday = db.Column(db.Boolean, default=False, nullable=False)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # --- Properties ---

    @property
    def display_name(self) -> str:
        """Return display name."""
        return self.title

    @property
    def display_time(self) -> str:
        """Return formatted time display."""
        if self.is_all_day or not self.scheduled_start_time:
            return "All day"
        start = self.scheduled_start_time.strftime("%I:%M %p").lstrip("0")
        if self.scheduled_end_time:
            end = self.scheduled_end_time.strftime("%I:%M %p").lstrip("0")
            return f"{start} - {end}"
        return start

    @property
    def is_upcoming(self) -> bool:
        """Check if event is in the future."""
        return self.scheduled_date >= date.today()

    @property
    def is_today(self) -> bool:
        """Check if event is today."""
        return self.scheduled_date == date.today()

    # --- Class Methods ---

    @classmethod
    def create(
        cls,
        title: str,
        scheduled_date: date,
        description: str | None = None,
        scheduled_start_time: time | None = None,
        scheduled_end_time: time | None = None,
        is_all_day: bool = True,
        location: str | None = None,
    ) -> "Event":
        """Create a new company event."""
        event = cls(
            title=title,
            description=description,
            scheduled_date=scheduled_date,
            scheduled_start_time=scheduled_start_time,
            scheduled_end_time=scheduled_end_time,
            is_all_day=is_all_day,
            location=location,
        )

        # Set audit fields
        if current_user and hasattr(current_user, "id") and current_user.is_authenticated:
            event.created_by_id = current_user.id

        db.session.add(event)
        db.session.commit()
        return event

    @classmethod
    def get_by_id(cls, event_id: int) -> "Event | None":
        """Get event by ID."""
        return cls.scoped().filter_by(id=event_id).first()

    @classmethod
    def get_for_date_range(cls, start_date: date, end_date: date) -> list["Event"]:
        """Get events within a date range."""
        return cls.scoped().filter(
            cls.scheduled_date >= start_date,
            cls.scheduled_date <= end_date,
        ).order_by(cls.scheduled_date, cls.scheduled_start_time).all()

    @classmethod
    def get_for_date(cls, target_date: date) -> list["Event"]:
        """Get events for a specific date."""
        return cls.get_for_date_range(target_date, target_date)

    @classmethod
    def get_upcoming(cls, limit: int = 5) -> list["Event"]:
        """Get upcoming events from today onwards."""
        return cls.scoped().filter(
            cls.scheduled_date >= date.today(),
        ).order_by(cls.scheduled_date, cls.scheduled_start_time).limit(limit).all()

    @classmethod
    def get_all(cls) -> list["Event"]:
        """Get all events ordered by date."""
        return cls.scoped().order_by(cls.scheduled_date.desc(), cls.scheduled_start_time).all()

    # --- Instance Methods ---

    def update(self, **kwargs) -> "Event":
        """Update event fields."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

        # Handle is_all_day clearing times
        if kwargs.get("is_all_day"):
            self.scheduled_start_time = None
            self.scheduled_end_time = None

        # Set audit fields
        if current_user and hasattr(current_user, "id") and current_user.is_authenticated:
            self.updated_by_id = current_user.id

        db.session.commit()
        return self

    def delete(self) -> None:
        """Delete the event."""
        db.session.delete(self)
        db.session.commit()

    # --- Holiday Methods ---

    @classmethod
    def get_holiday_dates_in_range(cls, start_date: date, end_date: date) -> set[date]:
        """Get a set of holiday dates within a date range.

        Args:
            start_date: Start of range (inclusive).
            end_date: End of range (inclusive).

        Returns:
            Set of dates that are holidays in this workspace.
        """
        rows = cls.scoped().filter(
            cls.is_holiday.is_(True),
            cls.scheduled_date >= start_date,
            cls.scheduled_date <= end_date,
        ).with_entities(cls.scheduled_date).all()
        return {r[0] for r in rows}

    @classmethod
    def populate_holidays(cls, holidays: list[tuple[date, str]]) -> int:
        """Create holiday events, skipping dates that already have one.

        Args:
            holidays: List of (date, name) tuples.

        Returns:
            Number of holidays created.
        """
        existing = cls.scoped().filter(
            cls.is_holiday.is_(True),
            cls.scheduled_date.in_([h[0] for h in holidays]),
        ).with_entities(cls.scheduled_date).all()
        existing_dates = {r[0] for r in existing}

        count = 0
        for holiday_date, name in holidays:
            if holiday_date in existing_dates:
                continue
            event = cls(
                title=name,
                scheduled_date=holiday_date,
                is_all_day=True,
                is_holiday=True,
            )
            db.session.add(event)
            count += 1

        if count:
            db.session.commit()
        return count
