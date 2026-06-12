# -----------------------------------------------------------------------------
# sparQ - PresenceForecast Model
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""PresenceForecast model — per-member daily availability forecast.

One row per (workspace_id, member_id, forecast_date). available_from /
available_until are optional; NULL means all-day / unspecified hours.
"""

from __future__ import annotations

from datetime import date, time
from enum import Enum

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.workspace import WorkspaceMixin


class ForecastStatus(Enum):
    """Availability forecast statuses."""

    IN = "in"
    OUT = "out"
    REMOTE = "remote"
    PTO = "pto"


@ModelRegistry.register
class PresenceForecast(db.Model, WorkspaceMixin):
    """A member's declared availability for a single calendar day.

    Attributes:
        member_id: The WorkspaceUser this forecast belongs to.
        forecast_date: The date being forecasted.
        status: One of ForecastStatus values.
        available_from: Optional start of availability window.
        available_until: Optional end of availability window.
        note: Free-text note (e.g. "OOO 12–2pm").
    """

    __tablename__ = "presence_forecast"

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(
        db.Integer,
        db.ForeignKey("workspace_user.id", ondelete="CASCADE"),
        nullable=False,
    )
    forecast_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False)
    available_from = db.Column(db.Time, nullable=True)
    available_until = db.Column(db.Time, nullable=True)
    note = db.Column(db.Text, nullable=True)

    __table_args__ = (
        db.UniqueConstraint(
            "workspace_id", "member_id", "forecast_date",
            name="uq_forecast_member_date",
        ),
        db.Index(
            "ix_presence_forecast_org_ws_date",
            "organization_id", "workspace_id", "forecast_date",
        ),
    )

    # --- Class Methods ---

    @classmethod
    def set_forecast(
        cls,
        member_id: int,
        forecast_date: date,
        status: str,
        available_from: time | None = None,
        available_until: time | None = None,
        note: str | None = None,
    ) -> "PresenceForecast":
        """Upsert a forecast for a member on a given date.

        Args:
            member_id: WorkspaceUser id.
            forecast_date: The date being forecasted.
            status: One of ForecastStatus values.
            available_from: Optional start of availability window.
            available_until: Optional end of availability window.
            note: Optional free-text note.

        Returns:
            The created or updated PresenceForecast.
        """
        existing = cls.scoped().filter_by(
            member_id=member_id, forecast_date=forecast_date
        ).first()

        if existing:
            existing.status = status
            existing.available_from = available_from
            existing.available_until = available_until
            existing.note = note or None
            db.session.commit()
            return existing

        forecast = cls(
            member_id=member_id,
            forecast_date=forecast_date,
            status=status,
            available_from=available_from,
            available_until=available_until,
            note=note or None,
        )
        db.session.add(forecast)
        db.session.commit()
        return forecast

    @classmethod
    def clear_forecast(cls, member_id: int, forecast_date: date) -> None:
        """Delete the forecast for a member on a given date.

        Args:
            member_id: WorkspaceUser id.
            forecast_date: The date to clear.
        """
        cls.scoped().filter_by(
            member_id=member_id, forecast_date=forecast_date
        ).delete()
        db.session.commit()

    @classmethod
    def get_for_member(
        cls,
        member_id: int,
        start_date: date,
        end_date: date,
    ) -> list["PresenceForecast"]:
        """Get all forecasts for a member within a date range.

        Args:
            member_id: WorkspaceUser id.
            start_date: Inclusive start date.
            end_date: Inclusive end date.

        Returns:
            List of PresenceForecast records ordered by forecast_date.
        """
        return (
            cls.scoped()
            .filter(
                cls.member_id == member_id,
                cls.forecast_date >= start_date,
                cls.forecast_date <= end_date,
            )
            .order_by(cls.forecast_date)
            .all()
        )

    @classmethod
    def create_sample_data(cls) -> None:
        """No-op — forecasts are user-generated."""
        pass
