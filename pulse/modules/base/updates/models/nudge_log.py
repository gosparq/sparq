# -----------------------------------------------------------------------------
# sparQ - UpdateNudgeLog Model
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""UpdateNudgeLog model — dedup tracking for nudge notifications.

Prevents duplicate nudges: one per local date for daily templates,
one per interval for periodic templates.  Also supports AI-generated
pulse nudges (on_track / energy) with pre-filled suggested values.

Tracks nudge lifecycle via ``status``:
    sent → completed (user posted) | expired (2-hr window closed) |
    superseded (next periodic nudge fired while this one was outstanding).

Classes:
    UpdateNudgeLog: Nudge dedup log.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from enum import Enum
from typing import TypedDict

from flask import g
from sqlalchemy import func

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.workspace import WorkspaceMixin


class NudgeStatus(Enum):
    """Lifecycle states for nudge notifications."""

    SENT = "sent"
    COMPLETED = "completed"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"


class TemplateStat(TypedDict):
    pct: int | None
    completed: int
    total: int


class TeamTemplateStat(TypedDict):
    pct: int | None


class PersonSummary(TypedDict):
    templates: dict[int, TemplateStat]
    overall_pct: int | None


class PulseSummary(TypedDict):
    people: dict[int, PersonSummary]
    team_templates: dict[int, TeamTemplateStat]
    team_overall_pct: int | None


class NudgeHistoryRow(TypedDict):
    nudged_at: datetime
    template_name: str
    template_label: str
    status: str
    expired_at: datetime | None
    responded_at: datetime | None


class MemberPulseDetail(TypedDict):
    templates: dict[int, TemplateStat]
    overall_pct: int | None
    rows: list[NudgeHistoryRow]


@ModelRegistry.register
class UpdateNudgeLog(db.Model, WorkspaceMixin):
    """Log of nudge notifications sent, used for deduplication.

    Attributes:
        template_id: FK to UpdateTemplate.
        user_id: FK to User who was nudged.
        nudged_at: UTC timestamp when the nudge was sent.
        status: Lifecycle state — sent, completed, expired, superseded.
        expired_at: UTC timestamp when the nudge was auto-dismissed.
        nudge_type: 'on_track' or 'energy' for AI pulse nudges.
        suggested_value: Pre-filled guess value for the nudge.
        responded_at: When the user responded to the nudge.
        response_value: What the user actually submitted.
        dismissed: Whether the user dismissed the nudge without responding.
    """

    __tablename__ = "update_nudge_log"

    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(
        db.Integer, db.ForeignKey("update_template.id", ondelete="CASCADE"), nullable=False
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    nudged_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Nudge lifecycle
    status = db.Column(db.String(20), nullable=False, default=NudgeStatus.SENT.value)
    expired_at = db.Column(db.DateTime, nullable=True)

    # Adaptive schedule metrics
    schedule_status = db.Column(db.String(20), nullable=True)
    scheduled_at = db.Column(db.Time, nullable=True)

    # AI pulse nudge fields
    nudge_type = db.Column(db.String(20), nullable=True)
    suggested_value = db.Column(db.String(20), nullable=True)
    responded_at = db.Column(db.DateTime, nullable=True)
    response_value = db.Column(db.String(20), nullable=True)
    dismissed = db.Column(db.Boolean, default=False)

    template = db.relationship("UpdateTemplate", lazy="raise")

    @classmethod
    def was_nudged_today(cls, template_id, user_id, local_date_start_utc):
        """Check if user was already nudged today for this template.

        Args:
            template_id: The template ID.
            user_id: The user ID.
            local_date_start_utc: Start of the user's local date in UTC.

        Returns:
            True if a nudge log exists since local_date_start_utc.
        """
        return cls.scoped().filter(
            cls.template_id == template_id,
            cls.user_id == user_id,
            cls.nudged_at >= local_date_start_utc,
        ).first() is not None

    @classmethod
    def was_nudged_within(cls, template_id, user_id, minutes):
        """Check if user was nudged within the last N minutes.

        Args:
            template_id: The template ID.
            user_id: The user ID.
            minutes: Lookback window in minutes.

        Returns:
            True if a nudge log exists within the window.
        """
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        return cls.scoped().filter(
            cls.template_id == template_id,
            cls.user_id == user_id,
            cls.nudged_at >= cutoff,
        ).first() is not None

    @classmethod
    def log_nudge(
        cls,
        template_id: int,
        user_id: int,
        scheduled_at: time | None = None,
    ) -> UpdateNudgeLog:
        """Record that a nudge was sent.

        Args:
            template_id: The template ID.
            user_id: The user ID.
            scheduled_at: The member's effective schedule time for this nudge.

        Returns:
            The created UpdateNudgeLog instance.
        """
        log = cls(
            template_id=template_id,
            user_id=user_id,
            nudged_at=datetime.utcnow(),
            status=NudgeStatus.SENT.value,
            scheduled_at=scheduled_at,
        )
        db.session.add(log)
        db.session.flush()
        return log

    @classmethod
    def log_completed(
        cls,
        template_id: int,
        user_id: int,
        scheduled_at: time | None = None,
    ) -> UpdateNudgeLog:
        """Record a nudge that was already satisfied (user posted before nudge fired).

        Args:
            template_id: The template ID.
            user_id: The user ID.
            scheduled_at: The member's effective schedule time for this nudge.

        Returns:
            The created UpdateNudgeLog instance.
        """
        now = datetime.utcnow()
        log = cls(
            template_id=template_id,
            user_id=user_id,
            nudged_at=now,
            status=NudgeStatus.COMPLETED.value,
            responded_at=now,
            scheduled_at=scheduled_at,
            schedule_status="on_time",
        )
        db.session.add(log)
        db.session.flush()
        return log

    @classmethod
    def mark_completed(cls, template_id: int, user_id: int) -> None:
        """Mark the most recent 'sent' nudge for this template+user as completed.

        Args:
            template_id: The template ID.
            user_id: The user ID.
        """
        workspace_id = getattr(g, "workspace_id", None)
        query = cls.query.filter(
            cls.template_id == template_id,
            cls.user_id == user_id,
            cls.status == NudgeStatus.SENT.value,
            cls.nudge_type.is_(None),
        )
        if workspace_id is not None:
            query = query.filter(cls.workspace_id == workspace_id)
        nudge = query.order_by(cls.nudged_at.desc()).first()
        if nudge:
            nudge.status = NudgeStatus.COMPLETED.value
            nudge.responded_at = datetime.utcnow()
            nudge.schedule_status = cls._compute_schedule_status(
                nudge.scheduled_at, nudge.responded_at
            )
            db.session.flush()

    @staticmethod
    def _compute_schedule_status(
        scheduled_at: time | None, responded_at: datetime | None
    ) -> str | None:
        """Compute on_time/tardy based on response time vs scheduled time + 1hr grace."""
        if scheduled_at is None or responded_at is None:
            return None
        grace_end = (
            datetime.combine(responded_at.date(), scheduled_at)
            + timedelta(hours=1)
        )
        return "on_time" if responded_at <= grace_end else "tardy"

    @classmethod
    def record_daily_completion(cls, template_id: int, user_id: int) -> None:
        """Record a completed daily-template post for pulse tracking.

        Marks a pending SENT nudge as completed if one exists; otherwise creates
        a COMPLETED entry directly so proactive posts (submitted before the nudge
        fires) still count in the pulse calculation.

        Args:
            template_id: The template ID.
            user_id: The user ID.
        """
        workspace_id = getattr(g, "workspace_id", None)

        sent_query = cls.query.filter(
            cls.template_id == template_id,
            cls.user_id == user_id,
            cls.status == NudgeStatus.SENT.value,
            cls.nudge_type.is_(None),
        )
        if workspace_id is not None:
            sent_query = sent_query.filter(cls.workspace_id == workspace_id)
        nudge = sent_query.order_by(cls.nudged_at.desc()).first()
        if nudge:
            nudge.status = NudgeStatus.COMPLETED.value
            nudge.responded_at = datetime.utcnow()
            nudge.schedule_status = cls._compute_schedule_status(
                nudge.scheduled_at, nudge.responded_at
            )
            db.session.flush()
            return

        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        exists_query = cls.query.filter(
            cls.template_id == template_id,
            cls.user_id == user_id,
            cls.nudge_type.is_(None),
            cls.nudged_at >= today_start,
        )
        if workspace_id is not None:
            exists_query = exists_query.filter(cls.workspace_id == workspace_id)
        if not exists_query.first():
            cls.log_completed(template_id, user_id)

    @classmethod
    def supersede_periodic_nudge(cls, template_id: int, user_id: int) -> None:
        """Mark outstanding periodic nudge as superseded when a new one fires.

        Args:
            template_id: The template ID.
            user_id: The user ID.
        """
        workspace_id = getattr(g, "workspace_id", None)
        query = cls.query.filter(
            cls.template_id == template_id,
            cls.user_id == user_id,
            cls.status == NudgeStatus.SENT.value,
            cls.nudge_type.is_(None),
        )
        if workspace_id is not None:
            query = query.filter(cls.workspace_id == workspace_id)
        nudge = query.order_by(cls.nudged_at.desc()).first()
        if nudge:
            nudge.status = NudgeStatus.SUPERSEDED.value
            nudge.expired_at = datetime.utcnow()
            db.session.flush()

    @classmethod
    def expire_standup_nudges(
        cls, user_expiry_pairs: list[tuple[int, datetime]]
    ) -> int:
        """Bulk-expire daily nudges that have passed their 2-hour window.

        Args:
            user_expiry_pairs: List of (user_id, expiry_cutoff_utc) tuples.

        Returns:
            Number of nudges expired.
        """
        if not user_expiry_pairs:
            return 0
        now_utc = datetime.utcnow()
        workspace_id = getattr(g, "workspace_id", None)
        count = 0
        for uid, cutoff_utc in user_expiry_pairs:
            query = cls.query.filter(
                cls.user_id == uid,
                cls.status == NudgeStatus.SENT.value,
                cls.nudge_type.is_(None),
                cls.nudged_at <= cutoff_utc,
            )
            if workspace_id is not None:
                query = query.filter(cls.workspace_id == workspace_id)
            updated = query.update(
                {
                    cls.status: NudgeStatus.EXPIRED.value,
                    cls.expired_at: now_utc,
                    cls.schedule_status: "missed",
                },
                synchronize_session=False,
            )
            count += updated
        if count:
            db.session.flush()
        return count

    @classmethod
    def get_completion_stats(
        cls,
        user_ids: list[int],
        template_ids: list[int],
        start_date: datetime,
        end_date: datetime,
    ) -> dict[tuple[int, int], dict[str, int]]:
        """Get nudge completion stats grouped by (user_id, template_id).

        Args:
            user_ids: List of user IDs to include.
            template_ids: List of template IDs to include.
            start_date: Start of date range (UTC).
            end_date: End of date range (UTC).

        Returns:
            Dict mapping (user_id, template_id) to {status: count}.
        """
        if not user_ids or not template_ids:
            return {}

        terminal = (NudgeStatus.COMPLETED.value, NudgeStatus.EXPIRED.value, NudgeStatus.SUPERSEDED.value)

        workspace_id = getattr(g, "workspace_id", None)
        query = cls.query.filter(
            cls.user_id.in_(user_ids),
            cls.template_id.in_(template_ids),
            cls.nudged_at >= start_date,
            cls.nudged_at < end_date,
            cls.nudge_type.is_(None),
            cls.status.in_(terminal),
        )
        if workspace_id is not None:
            query = query.filter(cls.workspace_id == workspace_id)

        rows = (
            query.with_entities(
                cls.user_id,
                cls.template_id,
                cls.status,
                func.count(cls.id),
            )
            .group_by(cls.user_id, cls.template_id, cls.status)
            .all()
        )

        result: dict[tuple[int, int], dict[str, int]] = {}
        for uid, tid, status, cnt in rows:
            key = (uid, tid)
            if key not in result:
                result[key] = {}
            result[key][status] = cnt
        return result

    @classmethod
    def get_schedule_status_stats(
        cls,
        user_ids: list[int],
        template_ids: list[int],
        start_date: datetime,
        end_date: datetime,
    ) -> dict[tuple[int, int], dict[str, int]]:
        """Get schedule_status counts grouped by (user_id, template_id).

        Args:
            user_ids: List of user IDs to include.
            template_ids: List of template IDs to include.
            start_date: Start of date range (UTC).
            end_date: End of date range (UTC).

        Returns:
            Dict mapping (user_id, template_id) to {schedule_status: count}.
        """
        if not user_ids or not template_ids:
            return {}

        workspace_id = getattr(g, "workspace_id", None)
        query = cls.query.filter(
            cls.user_id.in_(user_ids),
            cls.template_id.in_(template_ids),
            cls.nudged_at >= start_date,
            cls.nudged_at < end_date,
            cls.nudge_type.is_(None),
            cls.schedule_status.isnot(None),
        )
        if workspace_id is not None:
            query = query.filter(cls.workspace_id == workspace_id)

        rows = (
            query.with_entities(
                cls.user_id,
                cls.template_id,
                cls.schedule_status,
                func.count(cls.id),
            )
            .group_by(cls.user_id, cls.template_id, cls.schedule_status)
            .all()
        )

        result: dict[tuple[int, int], dict[str, int]] = {}
        for uid, tid, ss, cnt in rows:
            key = (uid, tid)
            if key not in result:
                result[key] = {}
            result[key][ss] = cnt
        return result

    @classmethod
    def get_pulse_summary(
        cls,
        user_ids: list[int],
        template_ids: list[int],
        template_groups: list[dict],
        start_date: datetime,
        end_date: datetime,
    ) -> PulseSummary:
        """Aggregate nudge completion stats for the team pulse report.

        Args:
            user_ids: Active user IDs to include.
            template_ids: All nudge-enabled template IDs.
            template_groups: Per-template info, each {"id": int, "label": str}.
            start_date: Start of date range (UTC).
            end_date: End of date range (UTC).

        Returns:
            Dict with keys:
                people: {user_id: {"templates": {tid: {"pct", "completed", "total",
                         "on_time", "tardy", "missed"}},
                         "overall_pct": int | None}}
                team_templates: {tid: {"pct": int | None}}
                team_overall_pct: int | None
                team_on_time_pct: int | None
        """
        stats = cls.get_completion_stats(user_ids, template_ids, start_date, end_date)
        schedule_stats = cls.get_schedule_status_stats(user_ids, template_ids, start_date, end_date)

        people: dict[int, dict] = {}
        team_per_template: dict[int, dict[str, int]] = {
            grp["id"]: {"completed": 0, "total": 0} for grp in template_groups
        }
        team_schedule_totals = {"on_time": 0, "tardy": 0, "missed": 0}

        for uid in user_ids:
            user_templates: dict[int, dict] = {}
            user_overall_completed = 0
            user_overall_total = 0

            for grp in template_groups:
                tid = grp["id"]
                s = stats.get((uid, tid), {})
                ss = schedule_stats.get((uid, tid), {})
                completed = s.get(NudgeStatus.COMPLETED.value, 0)
                total = completed + s.get(NudgeStatus.EXPIRED.value, 0) + s.get(NudgeStatus.SUPERSEDED.value, 0)

                on_time = ss.get("on_time", 0)
                tardy = ss.get("tardy", 0)
                missed = ss.get("missed", 0)

                user_templates[tid] = {
                    "pct": round(completed / total * 100) if total else None,
                    "completed": completed,
                    "total": total,
                    "on_time": on_time,
                    "tardy": tardy,
                    "missed": missed,
                }
                user_overall_completed += completed
                user_overall_total += total

                team_per_template[tid]["completed"] += completed
                team_per_template[tid]["total"] += total

                team_schedule_totals["on_time"] += on_time
                team_schedule_totals["tardy"] += tardy
                team_schedule_totals["missed"] += missed

            people[uid] = {
                "templates": user_templates,
                "overall_pct": round(user_overall_completed / user_overall_total * 100) if user_overall_total else None,
            }

        team_overall_completed = sum(t["completed"] for t in team_per_template.values())
        team_overall_total = sum(t["total"] for t in team_per_template.values())

        team_templates = {
            tid: {"pct": round(t["completed"] / t["total"] * 100) if t["total"] else None}
            for tid, t in team_per_template.items()
        }

        schedule_total = team_schedule_totals["on_time"] + team_schedule_totals["tardy"] + team_schedule_totals["missed"]

        return {
            "people": people,
            "team_templates": team_templates,
            "team_overall_pct": round(team_overall_completed / team_overall_total * 100) if team_overall_total else None,
            "team_on_time_pct": round(team_schedule_totals["on_time"] / schedule_total * 100) if schedule_total else None,
            "team_schedule_totals": team_schedule_totals,
        }

    @classmethod
    def get_member_pulse_detail(
        cls,
        user_id: int,
        template_ids: list[int],
        template_groups: list[dict],
        start_date: datetime,
        end_date: datetime,
        template_map: dict,
    ) -> MemberPulseDetail:
        """Get per-person pulse drilldown with stats and nudge history rows.

        Args:
            user_id: The user to query.
            template_ids: All nudge-enabled template IDs.
            template_groups: Per-template info, each {"id": int, "label": str}.
            start_date: Start of date range (UTC).
            end_date: End of date range (UTC).
            template_map: {template_id: UpdateTemplate} for name/type lookup.

        Returns:
            Dict with keys:
                templates: {tid: {"pct", "completed", "total"}}
                overall_pct: int | None
                rows: list of nudge history dicts
        """
        stats = cls.get_completion_stats([user_id], template_ids, start_date, end_date)
        history = cls.get_nudge_history(user_id, template_ids, start_date, end_date)

        label_by_tid = {grp["id"]: grp["label"] for grp in template_groups}
        templates: dict[int, dict] = {}
        overall_completed = 0
        overall_total = 0

        for grp in template_groups:
            tid = grp["id"]
            s = stats.get((user_id, tid), {})
            completed = s.get(NudgeStatus.COMPLETED.value, 0)
            total = completed + s.get(NudgeStatus.EXPIRED.value, 0) + s.get(NudgeStatus.SUPERSEDED.value, 0)
            templates[tid] = {
                "pct": round(completed / total * 100) if total else None,
                "completed": completed,
                "total": total,
            }
            overall_completed += completed
            overall_total += total

        rows = []
        for log in history:
            tmpl = template_map.get(log.template_id)
            rows.append({
                "nudged_at": log.nudged_at,
                "template_name": tmpl.name if tmpl else "Unknown",
                "template_label": label_by_tid.get(log.template_id, "Unknown"),
                "status": log.status,
                "schedule_status": log.schedule_status,
                "expired_at": log.expired_at,
                "responded_at": log.responded_at,
            })

        return {
            "templates": templates,
            "overall_pct": round(overall_completed / overall_total * 100) if overall_total else None,
            "rows": rows,
        }

    @classmethod
    def get_nudge_history(
        cls,
        user_id: int,
        template_ids: list[int],
        start_date: datetime,
        end_date: datetime,
    ) -> list[UpdateNudgeLog]:
        """Get individual nudge log rows for a user in a date range.

        Args:
            user_id: The user to query.
            template_ids: Template IDs to include.
            start_date: Start of date range (UTC).
            end_date: End of date range (UTC).

        Returns:
            List of UpdateNudgeLog rows ordered by nudged_at descending.
        """
        if not template_ids:
            return []

        terminal = (NudgeStatus.COMPLETED.value, NudgeStatus.EXPIRED.value, NudgeStatus.SUPERSEDED.value)
        today_start = start_date

        workspace_id = getattr(g, "workspace_id", None)
        query = cls.query.filter(
            cls.user_id == user_id,
            cls.template_id.in_(template_ids),
            cls.nudged_at >= start_date,
            cls.nudged_at < end_date,
            cls.nudge_type.is_(None),
            db.or_(
                cls.status.in_(terminal),
                db.and_(cls.status == NudgeStatus.SENT.value, cls.nudged_at >= today_start),
            ),
        )
        if workspace_id is not None:
            query = query.filter(cls.workspace_id == workspace_id)

        return query.order_by(cls.nudged_at.desc()).all()

    @classmethod
    def create_nudge(cls, user_id, nudge_type, suggested_value, template_id=None):
        """Create an AI pulse nudge and send a SystemNotification.

        Args:
            user_id: The user ID to nudge.
            nudge_type: 'on_track' or 'energy'.
            suggested_value: Pre-filled guess value.
            template_id: Optional FK to UpdateTemplate.

        Returns:
            The created UpdateNudgeLog instance.
        """
        from modules.base.core.models.notification import NotificationCategory, SystemNotification
        from modules.base.core.services.push_notification import send_push

        log = cls(
            template_id=template_id or 0,
            user_id=user_id,
            nudged_at=datetime.utcnow(),
            nudge_type=nudge_type,
            suggested_value=str(suggested_value),
        )
        db.session.add(log)
        db.session.flush()  # Get the log.id for action_url

        # Build notification
        title = "How are things going?"
        message = "Quick check-in: are you on track today?"
        icon = "fa-road"

        action_url = f"/presence/flow/pulse/new/{template_id}?prefill_value={suggested_value}&nudge_id={log.id}" if template_id else None

        SystemNotification.create(
            title=title,
            message=message,
            type="info",
            target_role="all",
            user_id=user_id,
            icon=icon,
            action_url=action_url,
            category=NotificationCategory.MISSED_CHECKIN,
        )
        send_push(
            user_id=user_id,
            title=title,
            body=message,
            url=action_url,
        )

        return log

    @classmethod
    def should_nudge(cls, user_id):
        """Check whether a user should receive a pulse nudge now.

        Returns True if:
        - Not nudged (any AI pulse nudge) in the last 4 hours.
        - Not dismissed a nudge in the last 3 hours.

        Args:
            user_id: The user ID.

        Returns:
            True if the user is eligible for an AI pulse nudge.
        """
        four_hours_ago = datetime.utcnow() - timedelta(hours=4)
        recent = cls.scoped().filter(
            cls.user_id == user_id,
            cls.nudge_type.isnot(None),
            cls.nudged_at >= four_hours_ago,
        ).first()
        if recent:
            return False

        three_hours_ago = datetime.utcnow() - timedelta(hours=3)
        dismissed_recent = cls.scoped().filter(
            cls.user_id == user_id,
            cls.nudge_type.isnot(None),
            cls.dismissed.is_(True),
            cls.nudged_at >= three_hours_ago,
        ).first()
        if dismissed_recent:
            return False

        return True

    @classmethod
    def get_pending(cls, user_id):
        """Get undismissed, unresponded nudge for today.

        Args:
            user_id: The user ID.

        Returns:
            UpdateNudgeLog instance or None.
        """
        from sqlalchemy.orm import joinedload

        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        return (
            cls.scoped()
            .options(joinedload(cls.template))
            .filter(
                cls.user_id == user_id,
                cls.status == NudgeStatus.SENT.value,
                cls.dismissed.is_(False),
                cls.responded_at.is_(None),
                cls.nudged_at >= today_start,
            )
            .order_by(cls.nudged_at.desc())
            .first()
        )

    @classmethod
    def get_expired_today(cls, user_id: int) -> list[UpdateNudgeLog]:
        """Get nudges that expired or were superseded today for a user.

        Args:
            user_id: The user ID.

        Returns:
            List of expired/superseded nudge logs from today, most recent first.
        """
        from sqlalchemy.orm import joinedload

        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        return (
            cls.scoped()
            .options(joinedload(cls.template))
            .filter(
                cls.user_id == user_id,
                cls.status.in_([NudgeStatus.EXPIRED.value, NudgeStatus.SUPERSEDED.value]),
                cls.nudged_at >= today_start,
                cls.nudge_type.is_(None),
            )
            .order_by(cls.nudged_at.desc())
            .all()
        )

    def dismiss(self):
        """Mark this nudge as dismissed."""
        self.dismissed = True
        db.session.commit()

    def respond(self, value):
        """Record the user's response to this nudge.

        Args:
            value: The response value submitted by the user.
        """
        self.responded_at = datetime.utcnow()
        self.response_value = str(value)
        db.session.commit()
