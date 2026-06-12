# -----------------------------------------------------------------------------
# sparQ - Member Schedule Models
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""MemberSchedule and MemberScheduleOverride models.

MemberSchedule holds the recurring weekly schedule (one row per day of week).
MemberScheduleOverride holds single-day overrides that replace the default
for that date only.
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import TYPE_CHECKING

from flask import g

from system.db.database import db
from system.db.decorators import ModelRegistry

from system.db.workspace import WorkspaceMixin

if TYPE_CHECKING:
    from uuid import UUID


@ModelRegistry.register
class MemberScheduleOverride(db.Model, WorkspaceMixin):
    """A single-day schedule override for a member.

    Attributes:
        member_id: The WorkspaceUser this override belongs to.
        override_date: The date being overridden.
        start_time: Work start time for this day.
        end_time: Work end time for this day.
        created_by_id: User who created the override.
    """

    __tablename__ = "member_schedule_override"

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(
        db.Integer,
        db.ForeignKey("workspace_user.id", ondelete="CASCADE"),
        nullable=False,
    )
    override_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    created_by_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=True
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint(
            "workspace_id", "member_id", "override_date",
            name="uq_schedule_override_date",
        ),
        db.Index(
            "ix_schedule_override_org_ws_date",
            "organization_id", "workspace_id", "override_date",
        ),
    )

    @classmethod
    def set_override(
        cls,
        member_id: int,
        override_date: date,
        start_time: time,
        end_time: time,
    ) -> "MemberScheduleOverride":
        """Upsert a schedule override for a member on a given date.

        Args:
            member_id: WorkspaceUser id.
            override_date: The date to override.
            start_time: Override start time.
            end_time: Override end time.

        Returns:
            The created or updated override.
        """
        from flask_login import current_user

        existing = cls.scoped().filter_by(
            member_id=member_id, override_date=override_date
        ).first()

        if existing:
            existing.start_time = start_time
            existing.end_time = end_time
            existing.created_by_id = getattr(current_user, "id", None)
            db.session.commit()
            return existing

        override = cls(
            member_id=member_id,
            override_date=override_date,
            start_time=start_time,
            end_time=end_time,
            created_by_id=getattr(current_user, "id", None),
        )
        db.session.add(override)
        db.session.commit()
        return override

    @classmethod
    def clear_override(cls, member_id: int, override_date: date) -> None:
        """Delete the schedule override for a member on a given date.

        Args:
            member_id: WorkspaceUser id.
            override_date: The date to clear.
        """
        cls.scoped().filter_by(
            member_id=member_id, override_date=override_date
        ).delete()
        db.session.commit()

    @classmethod
    def get_overrides_for_range(
        cls,
        member_id: int,
        start_date: date,
        end_date: date,
    ) -> dict[date, "MemberScheduleOverride"]:
        """Get overrides for a member within a date range.

        Args:
            member_id: WorkspaceUser id.
            start_date: Inclusive start.
            end_date: Inclusive end.

        Returns:
            Dict keyed by override_date.
        """
        rows = (
            cls.scoped()
            .filter(
                cls.member_id == member_id,
                cls.override_date >= start_date,
                cls.override_date <= end_date,
            )
            .all()
        )
        return {r.override_date: r for r in rows}


@ModelRegistry.register
class MemberSchedule(db.Model, WorkspaceMixin):
    """A member's recurring weekly work schedule.

    One row per (workspace_id, member_id, day_of_week). day_of_week uses
    Python weekday convention: 0=Monday, 6=Sunday.

    Attributes:
        member_id: The WorkspaceUser this schedule belongs to.
        day_of_week: 0=Mon through 6=Sun.
        start_time: Default work start time for this day.
        end_time: Default work end time for this day.
    """

    __tablename__ = "member_schedule"

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(
        db.Integer,
        db.ForeignKey("workspace_user.id", ondelete="CASCADE"),
        nullable=False,
    )
    day_of_week = db.Column(db.SmallInteger, nullable=False)
    default_status = db.Column(db.String(10), nullable=True)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        db.UniqueConstraint(
            "workspace_id", "member_id", "day_of_week",
            name="uq_member_schedule_day",
        ),
        db.Index(
            "ix_member_schedule_org_ws_member",
            "organization_id", "workspace_id", "member_id",
        ),
    )

    # --- Query Methods ---

    @classmethod
    def get_weekly_schedule(cls, member_id: int) -> dict[int, "MemberSchedule"]:
        """Get the full weekly schedule for a member.

        Args:
            member_id: WorkspaceUser id.

        Returns:
            Dict keyed by day_of_week (0-6).
        """
        rows = cls.scoped().filter_by(member_id=member_id).all()
        return {r.day_of_week: r for r in rows}

    @classmethod
    def get_effective_schedule(
        cls, member_id: int, target_date: date
    ) -> tuple[time, time] | None:
        """Get the effective (start, end) for a member on a specific date.

        Checks overrides first, then falls back to the weekday default.
        Returns None if no schedule is set for that day.

        Args:
            member_id: WorkspaceUser id.
            target_date: The date to resolve.

        Returns:
            (start_time, end_time) or None.
        """
        override = MemberScheduleOverride.scoped().filter_by(
            member_id=member_id, override_date=target_date
        ).first()
        if override:
            return (override.start_time, override.end_time)

        default = cls.scoped().filter_by(
            member_id=member_id, day_of_week=target_date.weekday()
        ).first()
        if default:
            return (default.start_time, default.end_time)

        return None

    @classmethod
    def get_bulk_effective(
        cls,
        member_ids: list[int],
        target_date: date,
        org_id: "UUID | None" = None,
        ws_id: "UUID | None" = None,
    ) -> dict[int, tuple[time, time] | None]:
        """Batch-fetch effective schedules for multiple members on a date.

        Uses two queries: one for overrides, one for defaults. Override
        wins when present. Designed for the scheduler hot path.

        Args:
            member_ids: List of WorkspaceUser ids.
            target_date: The date to resolve.
            org_id: Organization id (optional, uses g if not provided).
            ws_id: Workspace id (optional, uses g if not provided).

        Returns:
            Dict of {member_id: (start, end) | None}.
        """
        if not member_ids:
            return {}

        _org_id = org_id or getattr(g, "organization_id", None)
        _ws_id = ws_id or getattr(g, "workspace_id", None)

        result: dict[int, tuple[time, time] | None] = {
            mid: None for mid in member_ids
        }

        overrides = (
            MemberScheduleOverride.query.filter(
                MemberScheduleOverride.organization_id == _org_id,
                MemberScheduleOverride.workspace_id == _ws_id,
                MemberScheduleOverride.member_id.in_(member_ids),
                MemberScheduleOverride.override_date == target_date,
            )
            .all()
        )
        overridden = set()
        for o in overrides:
            result[o.member_id] = (o.start_time, o.end_time)
            overridden.add(o.member_id)

        remaining = [mid for mid in member_ids if mid not in overridden]
        if remaining:
            defaults = (
                cls.query.filter(
                    cls.organization_id == _org_id,
                    cls.workspace_id == _ws_id,
                    cls.member_id.in_(remaining),
                    cls.day_of_week == target_date.weekday(),
                )
                .all()
            )
            for d in defaults:
                result[d.member_id] = (d.start_time, d.end_time)

        return result

    # --- Mutation Methods ---

    @classmethod
    def set_weekly_schedule(
        cls,
        member_id: int,
        schedule_data: list[dict],
    ) -> list["MemberSchedule"]:
        """Upsert a member's weekly schedule.

        Deletes days not present in schedule_data (member turned them off).

        Args:
            member_id: WorkspaceUser id.
            schedule_data: List of dicts with keys: day (int 0-6),
                start (time), end (time).

        Returns:
            List of MemberSchedule rows.
        """
        active_days = {d["day"] for d in schedule_data}

        cls.scoped().filter(
            cls.member_id == member_id,
            cls.day_of_week.notin_(active_days) if active_days else True,
        ).delete(synchronize_session="fetch")

        results = []
        for entry in schedule_data:
            day = entry["day"]
            start = entry["start"]
            end = entry["end"]
            status = entry.get("default_status")

            existing = cls.scoped().filter_by(
                member_id=member_id, day_of_week=day
            ).first()

            if existing:
                existing.start_time = start
                existing.end_time = end
                existing.default_status = status
                results.append(existing)
            else:
                row = cls(
                    member_id=member_id,
                    day_of_week=day,
                    start_time=start,
                    end_time=end,
                    default_status=status,
                )
                db.session.add(row)
                results.append(row)

        db.session.commit()
        return results

    @classmethod
    def create_sample_data(cls) -> None:
        """No-op — schedules are user-generated."""
        pass
