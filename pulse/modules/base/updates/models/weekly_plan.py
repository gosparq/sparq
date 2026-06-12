# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

"""WeeklyPlan and WeeklyPlanGoal models — lightweight weekly containers with loose goals.

Weekly Plans give teams a weekly heartbeat. Each plan covers a Mon-Fri week,
identified by ISO week number. Goals are plain text intentions, not tickets.

Classes:
    WeeklyPlan: Weekly container with metadata.
    WeeklyPlanGoal: Individual text-based goal within a plan.
"""

from datetime import date, datetime, timedelta

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.workspace import WorkspaceMixin
from system.db.raise_on_lazy import LAZY


@ModelRegistry.register
class WeeklyPlan(db.Model, WorkspaceMixin):
    """Lightweight weekly plan container.

    Attributes:
        week_number: ISO week number (1-53).
        year: Year (e.g., 2026).
        start_date: Monday of the week.
        end_date: Friday of the week.
        title: Optional short title (e.g., "Launch Prep").
        description: Optional one-sentence description.
        created_by_id: FK to workspace_user who created the plan.
    """

    __tablename__ = "weekly_plan"
    __table_args__ = (
        db.UniqueConstraint("workspace_id", "year", "week_number", name="uq_weekly_plan_week"),
        db.Index("ix_weekly_plan_lookup", "workspace_id", "year", "week_number"),
    )

    id = db.Column(db.Integer, primary_key=True)
    week_number = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    title = db.Column(db.String(200), nullable=True)
    description = db.Column(db.String(500), nullable=True)

    created_by_id = db.Column(
        db.Integer, db.ForeignKey("workspace_user.id"), nullable=True
    )

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    created_by = db.relationship("WorkspaceUser", foreign_keys=[created_by_id], lazy=LAZY)
    goals = db.relationship(
        "WeeklyPlanGoal",
        backref=db.backref("plan", lazy=LAZY),
        lazy="dynamic",
        cascade="all, delete-orphan",
        order_by="WeeklyPlanGoal.sort_order",
    )

    @classmethod
    def get_current_week(cls):
        """Get the plan for the current ISO week (without creating).

        Returns:
            WeeklyPlan instance or None.
        """
        today = date.today()
        iso = today.isocalendar()
        return (
            cls.scoped()
            .filter(cls.year == iso[0], cls.week_number == iso[1])
            .first()
        )

    @classmethod
    def get_or_create_current_week(cls):
        """Get or auto-create the plan for the current ISO week.

        Weekly plans are automatic — they exist for every week. No manual
        creation needed. Users can optionally add a title and goals.

        Returns:
            WeeklyPlan instance (existing or newly created).
        """
        today = date.today()
        iso = today.isocalendar()
        plan = (
            cls.scoped()
            .filter(cls.year == iso[0], cls.week_number == iso[1])
            .first()
        )
        if plan:
            return plan

        monday = date.fromisocalendar(iso[0], iso[1], 1)
        friday = monday + timedelta(days=4)

        plan = cls(
            week_number=iso[1],
            year=iso[0],
            start_date=monday,
            end_date=friday,
        )
        db.session.add(plan)
        db.session.commit()
        return plan

    @classmethod
    def get_by_week(cls, year, week_number):
        """Get a plan by year and week number.

        Args:
            year: The year.
            week_number: ISO week number.

        Returns:
            WeeklyPlan instance or None.
        """
        return (
            cls.scoped()
            .filter(cls.year == year, cls.week_number == week_number)
            .first()
        )

    @classmethod
    def get_by_id(cls, plan_id):
        """Get a plan by ID within current workspace.

        Args:
            plan_id: The plan ID.

        Returns:
            WeeklyPlan instance or None.
        """
        return cls.scoped().filter_by(id=plan_id).first()

    @classmethod
    def get_recent(cls, limit=8):
        """Get recent plans ordered by date descending.

        Args:
            limit: Max results.

        Returns:
            List of WeeklyPlan instances.
        """
        return (
            cls.scoped()
            .order_by(cls.year.desc(), cls.week_number.desc())
            .limit(limit)
            .all()
        )

    @classmethod
    def get_all_since_launch(cls):
        """Get all weekly plans since the workspace was created, newest first.

        Auto-creates plans for any missing weeks between the earliest plan
        and the current week, so the nav always shows a complete timeline.

        Returns:
            List of WeeklyPlan instances ordered newest first.
        """
        return (
            cls.scoped()
            .order_by(cls.year.desc(), cls.week_number.desc())
            .all()
        )

    @classmethod
    def create(cls, week_number, year, title=None, description=None, created_by_id=None):
        """Create a new weekly plan.

        Computes start_date (Monday) and end_date (Friday) from week number.

        Args:
            week_number: ISO week number.
            year: Year.
            title: Optional short title.
            description: Optional description.
            created_by_id: WorkspaceUser.id of creator.

        Returns:
            Created WeeklyPlan instance.

        Raises:
            ValueError: If a plan for this week already exists.
        """
        existing = cls.get_by_week(year, week_number)
        if existing:
            raise ValueError(f"A plan for Week {week_number}, {year} already exists.")

        # Compute Monday of ISO week
        monday = date.fromisocalendar(year, week_number, 1)
        friday = monday + timedelta(days=4)

        plan = cls(
            week_number=week_number,
            year=year,
            start_date=monday,
            end_date=friday,
            title=title.strip() if title else None,
            description=description.strip() if description else None,
            created_by_id=created_by_id,
        )
        db.session.add(plan)
        db.session.commit()
        return plan

    def update(self, title=None, description=None):
        """Update plan title and/or description.

        Args:
            title: New title (pass empty string to clear).
            description: New description (pass empty string to clear).
        """
        if title is not None:
            self.title = title.strip() if title else None
        if description is not None:
            self.description = description.strip() if description else None
        db.session.commit()

    @property
    def display_name(self):
        """Human-readable plan name: 'Week N' or 'Week N — Title'."""
        base = f"Week {self.week_number}"
        if self.title:
            return f"{base} — {self.title}"
        return base

    @property
    def date_range_display(self):
        """Human-readable date range: 'Apr 7 – 11' or 'Apr 7 – Apr 11'."""
        if self.start_date.month == self.end_date.month:
            return f"{self.start_date.strftime('%b %-d')} – {self.end_date.strftime('%-d')}"
        return f"{self.start_date.strftime('%b %-d')} – {self.end_date.strftime('%b %-d')}"

    @property
    def is_current_week(self):
        """Check if this plan is for the current ISO week."""
        today = date.today()
        iso = today.isocalendar()
        return self.year == iso[0] and self.week_number == iso[1]

    def goal_list(self):
        """Get goals as a list (materializes the dynamic relationship).

        Returns:
            List of WeeklyPlanGoal instances.
        """
        return self.goals.order_by(WeeklyPlanGoal.sort_order).all()

    @property
    def goals_complete_count(self):
        """Count of completed goals."""
        return self.goals.filter(WeeklyPlanGoal.is_complete == True).count()  # noqa: E712

    @property
    def goals_total_count(self):
        """Total count of goals."""
        return self.goals.count()


@ModelRegistry.register
class WeeklyPlanGoal(db.Model):
    """Individual text-based goal within a weekly plan.

    Attributes:
        plan_id: FK to WeeklyPlan.
        text: Goal description (plain text).
        sort_order: Display order.
        is_complete: Whether the goal has been marked done.
    """

    __tablename__ = "weekly_plan_goal"
    __table_args__ = (
        db.Index("ix_weekly_plan_goal_plan", "plan_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(
        db.Integer, db.ForeignKey("weekly_plan.id", ondelete="CASCADE"), nullable=False
    )
    text = db.Column(db.String(500), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_complete = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    @classmethod
    def add_to_plan(cls, plan_id, text):
        """Add a goal to a plan.

        Args:
            plan_id: WeeklyPlan ID.
            text: Goal text.

        Returns:
            Created WeeklyPlanGoal instance.
        """
        max_order = (
            db.session.query(db.func.max(cls.sort_order))
            .filter(cls.plan_id == plan_id)
            .scalar()
        ) or 0

        goal = cls(
            plan_id=plan_id,
            text=text.strip(),
            sort_order=max_order + 1,
        )
        db.session.add(goal)
        db.session.commit()
        return goal

    def toggle_complete(self):
        """Toggle the is_complete flag."""
        self.is_complete = not self.is_complete
        db.session.commit()

    def delete(self):
        """Delete this goal."""
        db.session.delete(self)
        db.session.commit()

    def update_text(self, text):
        """Update the goal text.

        Args:
            text: New text.
        """
        self.text = text.strip()
        db.session.commit()
