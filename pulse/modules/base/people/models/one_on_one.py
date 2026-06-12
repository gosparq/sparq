# -----------------------------------------------------------------------------
# sparQ - 1:1 Tracker Models
#
# Description:
#     Models for tracking 1:1 meetings between leads and reports.
#     Includes pairs, sessions, and agenda items.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""1:1 Tracker models for lead/report meeting management.

Three models track the lifecycle of 1:1 meetings:

- OneOnOnePair: The recurring relationship between a lead and report.
- OneOnOneSession: A logged meeting instance with notes.
- OneOnOneAgendaItem: Talking points and action items tied to a pair or session.

Example:
    Creating a 1:1 pair::

        pair = OneOnOnePair.create(lead_id=1, report_id=2, cadence="weekly")

    Logging a session::

        session = OneOnOneSession.create(
            pair_id=pair.id,
            meeting_date=date.today(),
            notes="Discussed quarterly goals.",
        )
"""

from datetime import date, datetime, timezone


from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.workspace import WorkspaceMixin
from system.db.raise_on_lazy import LAZY


@ModelRegistry.register
class OneOnOnePair(db.Model, WorkspaceMixin):
    """Recurring 1:1 relationship between a lead and a report.

    Attributes:
        id: Primary key.
        lead_id: FK to workspace_user (manager side).
        report_id: FK to workspace_user (report side).
        cadence: Meeting frequency (weekly, biweekly, monthly).
        next_meeting_date: Suggested next meeting date.
        active: Whether this pair is currently active.
        created_at: When the pair was created.
    """

    __tablename__ = "one_on_one_pair"
    __table_args__ = (
        db.UniqueConstraint("lead_id", "report_id", name="uq_one_on_one_pair"),
    )

    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(
        db.Integer, db.ForeignKey("workspace_user.id"), nullable=False, index=True
    )
    report_id = db.Column(
        db.Integer, db.ForeignKey("workspace_user.id"), nullable=False, index=True
    )
    cadence = db.Column(db.String(20), default="biweekly", nullable=False)
    next_meeting_date = db.Column(db.Date, nullable=True)
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    lead = db.relationship(
        "WorkspaceUser", foreign_keys=[lead_id],
        backref=db.backref("one_on_one_as_lead", lazy="dynamic"),
        lazy=LAZY,
    )
    report = db.relationship(
        "WorkspaceUser", foreign_keys=[report_id],
        backref=db.backref("one_on_one_as_report", lazy="dynamic"),
        lazy=LAZY,
    )
    sessions = db.relationship(
        "OneOnOneSession", backref=db.backref("pair", lazy=LAZY), lazy="dynamic",
        order_by="OneOnOneSession.meeting_date.desc()",
    )
    agenda_items = db.relationship(
        "OneOnOneAgendaItem", backref=db.backref("pair", lazy=LAZY), lazy="dynamic",
        foreign_keys="OneOnOneAgendaItem.pair_id",
    )

    # -------------------------------------------------------------------------
    # Class Methods
    # -------------------------------------------------------------------------

    @classmethod
    def get_pairs_for_user(cls, member_id: int) -> list["OneOnOnePair"]:
        """Get all active pairs where user is lead or report.

        Args:
            member_id: WorkspaceUser ID.

        Returns:
            List of active OneOnOnePair instances.
        """
        return (
            cls.scoped()
            .filter(
                cls.active.is_(True),
                db.or_(cls.lead_id == member_id, cls.report_id == member_id),
            )
            .order_by(cls.next_meeting_date.asc().nullslast(), cls.created_at.desc())
            .all()
        )

    @classmethod
    def get_all_pairs(cls) -> list["OneOnOnePair"]:
        """Get all active pairs in the current workspace.

        Returns:
            List of active OneOnOnePair instances.
        """
        return (
            cls.scoped()
            .filter(cls.active.is_(True))
            .order_by(cls.next_meeting_date.asc().nullslast(), cls.created_at.desc())
            .all()
        )

    @classmethod
    def create(cls, lead_id: int, report_id: int, cadence: str = "biweekly") -> "OneOnOnePair":
        """Create a new 1:1 pair.

        Args:
            lead_id: WorkspaceUser ID of the lead.
            report_id: WorkspaceUser ID of the report.
            cadence: Meeting frequency.

        Returns:
            The created OneOnOnePair instance.
        """
        pair = cls(lead_id=lead_id, report_id=report_id, cadence=cadence)
        db.session.add(pair)
        db.session.commit()
        return pair

    def deactivate(self) -> None:
        """Mark this pair as inactive."""
        self.active = False
        db.session.commit()

    def __repr__(self) -> str:
        return f"<OneOnOnePair {self.id} lead={self.lead_id} report={self.report_id}>"


@ModelRegistry.register
class OneOnOneSession(db.Model, WorkspaceMixin):
    """A logged 1:1 meeting session.

    Attributes:
        id: Primary key.
        pair_id: FK to one_on_one_pair.
        meeting_date: Date the meeting took place.
        notes: Free-text notes from the meeting.
        created_at: When the session was recorded.
    """

    __tablename__ = "one_on_one_session"

    id = db.Column(db.Integer, primary_key=True)
    pair_id = db.Column(
        db.Integer, db.ForeignKey("one_on_one_pair.id"), nullable=False, index=True
    )
    meeting_date = db.Column(db.Date, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    @classmethod
    def create(cls, pair_id: int, meeting_date: date, notes: str = "") -> "OneOnOneSession":
        """Log a new 1:1 session.

        Args:
            pair_id: The pair this session belongs to.
            meeting_date: When the meeting happened.
            notes: Meeting notes.

        Returns:
            The created OneOnOneSession instance.
        """
        session = cls(pair_id=pair_id, meeting_date=meeting_date, notes=notes)
        db.session.add(session)
        db.session.commit()
        return session

    def __repr__(self) -> str:
        return f"<OneOnOneSession {self.id} pair={self.pair_id} date={self.meeting_date}>"


@ModelRegistry.register
class OneOnOneAgendaItem(db.Model, WorkspaceMixin):
    """Agenda item or action item for a 1:1 pair.

    Items start unattached to a session (parking lot) and can be linked
    to a session once discussed.

    Attributes:
        id: Primary key.
        pair_id: FK to one_on_one_pair.
        session_id: FK to one_on_one_session (nullable — unlinked = parking lot).
        added_by_id: FK to workspace_user who created the item.
        content: The agenda item text.
        is_task: Whether this is an action item vs. talking point.
        owner_id: FK to workspace_user responsible (for action items).
        completed: Whether the item is done.
        created_at: When the item was created.
    """

    __tablename__ = "one_on_one_agenda_item"

    id = db.Column(db.Integer, primary_key=True)
    pair_id = db.Column(
        db.Integer, db.ForeignKey("one_on_one_pair.id"), nullable=False, index=True
    )
    session_id = db.Column(
        db.Integer, db.ForeignKey("one_on_one_session.id"), nullable=True
    )
    added_by_id = db.Column(
        db.Integer, db.ForeignKey("workspace_user.id"), nullable=False
    )
    content = db.Column(db.Text, nullable=False)
    is_task = db.Column(db.Boolean, default=False, nullable=False)
    owner_id = db.Column(
        db.Integer, db.ForeignKey("workspace_user.id"), nullable=True
    )
    completed = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    session = db.relationship(
        "OneOnOneSession",
        backref=db.backref("agenda_items", lazy="dynamic"),
        lazy=LAZY,
    )
    added_by = db.relationship(
        "WorkspaceUser", foreign_keys=[added_by_id], lazy=LAZY,
    )
    owner = db.relationship(
        "WorkspaceUser", foreign_keys=[owner_id], lazy=LAZY,
    )

    @classmethod
    def create(
        cls,
        pair_id: int,
        added_by_id: int,
        content: str,
        is_task: bool = False,
        owner_id: int | None = None,
        session_id: int | None = None,
    ) -> "OneOnOneAgendaItem":
        """Create a new agenda item.

        Args:
            pair_id: The pair this item belongs to.
            added_by_id: WorkspaceUser who added the item.
            content: Item text.
            is_task: True if action item, False if talking point.
            owner_id: Responsible WorkspaceUser (for action items).
            session_id: Session to link to (optional).

        Returns:
            The created OneOnOneAgendaItem instance.
        """
        item = cls(
            pair_id=pair_id,
            added_by_id=added_by_id,
            content=content,
            is_task=is_task,
            owner_id=owner_id,
            session_id=session_id,
        )
        db.session.add(item)
        db.session.commit()
        return item

    def mark_complete(self) -> None:
        """Mark the agenda item as completed."""
        self.completed = True
        db.session.commit()

    def mark_incomplete(self) -> None:
        """Mark the agenda item as not completed."""
        self.completed = False
        db.session.commit()

    def __repr__(self) -> str:
        return f"<OneOnOneAgendaItem {self.id} pair={self.pair_id}>"
