# -----------------------------------------------------------------------------
# sparQ - Offboarding Models
#
# Description:
#     Models for employee offboarding workflow including OffboardingTask
#     templates and OffboardingAssignment for tracking termination checklists.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

from datetime import datetime

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.workspace import WorkspaceMixin
from system.db.raise_on_lazy import LAZY


# Default offboarding task templates
DEFAULT_OFFBOARDING_TASKS = [
    {
        "name": "Collect company property",
        "description": "Collect laptop, keys, badge, and any other company-owned equipment.",
        "order": 1,
    },
    {
        "name": "Revoke system access",
        "description": "Disable user accounts and revoke access to all company systems.",
        "order": 2,
    },
    {
        "name": "Remove from email distribution lists",
        "description": "Remove employee from all email groups and mailing lists.",
        "order": 3,
    },
    {
        "name": "Process final paycheck",
        "description": "Calculate and process final paycheck including accrued PTO.",
        "order": 4,
    },
    {
        "name": "Provide benefits/COBRA information",
        "description": "Send COBRA and benefits continuation information.",
        "order": 5,
    },
    {
        "name": "Conduct exit interview",
        "description": "Schedule and conduct exit interview to gather feedback.",
        "order": 6,
    },
    {
        "name": "Transfer knowledge/handoff tasks",
        "description": "Ensure knowledge transfer and task handoff to remaining team members.",
        "order": 7,
    },
    {
        "name": "Update org chart",
        "description": "Update organizational chart and reporting structures.",
        "order": 8,
    },
]


@ModelRegistry.register
class OffboardingTask(db.Model, WorkspaceMixin):
    """Company-wide offboarding checklist template items.

    These are the template tasks that get assigned to each terminated employee.
    Admins can customize the list of tasks via the offboarding settings.
    """

    __tablename__ = "offboarding_task"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship to assignments
    assignments = db.relationship(
        "OffboardingAssignment",
        backref=db.backref("task", lazy=LAZY),
        cascade="all, delete-orphan",
        lazy=LAZY,
    )

    @classmethod
    def get_active_tasks(cls):
        """Get all active offboarding tasks ordered by order."""
        return cls.scoped().filter_by(is_active=True).order_by(cls.order).all()

    @classmethod
    def get_all_tasks(cls, include_inactive=False):
        """Get all offboarding tasks."""
        query = cls.scoped().order_by(cls.order)
        if not include_inactive:
            query = query.filter_by(is_active=True)
        return query.all()

    @classmethod
    def initialize_defaults(cls):
        """Initialize default offboarding tasks if none exist.

        Returns:
            bool: True if defaults were created, False if tasks already exist.
        """
        if cls.scoped().first() is not None:
            return False

        for task_data in DEFAULT_OFFBOARDING_TASKS:
            task = cls(
                name=task_data["name"],
                description=task_data["description"],
                order=task_data["order"],
            )
            db.session.add(task)

        db.session.commit()
        return True

    @classmethod
    def create(cls, name, description=None, order=None):
        """Create a new offboarding task template."""
        if order is None:
            # Get max order and add 1
            max_order = db.session.query(db.func.max(cls.order)).scalar() or 0
            order = max_order + 1

        task = cls(name=name, description=description, order=order)
        db.session.add(task)
        db.session.commit()
        return task

    def update(self, **kwargs):
        """Update task fields."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        db.session.commit()

    def delete(self):
        """Delete this task template."""
        db.session.delete(self)
        db.session.commit()

    @classmethod
    def get_next_order(cls) -> int:
        """Get the next sequential order value for a new task.

        Returns:
            Integer one greater than the current maximum order, or 1 if no tasks exist.
        """
        return (db.session.query(db.func.max(cls.order)).scalar() or 0) + 1


@ModelRegistry.register
class OffboardingAssignment(db.Model, WorkspaceMixin):
    """Task assigned to a specific terminated employee.

    When an employee is terminated, OffboardingAssignment records are created
    from all active OffboardingTask templates.
    """

    __tablename__ = "offboarding_assignment"

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey("workspace_user.id"), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey("offboarding_task.id"), nullable=False)

    completed = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    completed_by_id = db.Column(db.Integer, db.ForeignKey("workspace_user.id"), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    member = db.relationship(
        "WorkspaceUser",
        foreign_keys=[member_id],
        backref=db.backref("offboarding_assignments", lazy="dynamic"),
        lazy=LAZY,
    )
    completed_by = db.relationship("WorkspaceUser", foreign_keys=[completed_by_id], lazy=LAZY)

    @classmethod
    def create_for_member(cls, member_id):
        """Create offboarding assignments from all active task templates.

        Args:
            member_id: ID of the terminated member.

        Returns:
            list: Created OffboardingAssignment instances.
        """
        active_tasks = OffboardingTask.get_active_tasks()
        assignments = []

        for task in active_tasks:
            assignment = cls(
                member_id=member_id,
                task_id=task.id,
            )
            db.session.add(assignment)
            assignments.append(assignment)

        db.session.commit()
        return assignments

    @classmethod
    def get_for_member(cls, member_id):
        """Get all offboarding assignments for a member.

        Returns assignments ordered by task order.
        """
        return (
            cls.scoped()
            .filter_by(member_id=member_id)
            .join(OffboardingTask)
            .order_by(OffboardingTask.order)
            .all()
        )

    @classmethod
    def get_progress(cls, member_id):
        """Get offboarding progress for a member.

        Returns:
            dict: Progress stats with total, completed, percent.
        """
        assignments = cls.scoped().filter_by(member_id=member_id).all()
        total = len(assignments)
        completed = sum(1 for a in assignments if a.completed)
        percent = int((completed / total) * 100) if total > 0 else 100

        return {
            "total": total,
            "completed": completed,
            "percent": percent,
        }

    def mark_complete(self, user_id):
        """Mark this assignment as completed.

        Args:
            user_id: ID of the user marking it complete.
        """
        self.completed = True
        self.completed_at = datetime.utcnow()
        self.completed_by_id = user_id
        db.session.commit()

    def mark_incomplete(self):
        """Mark this assignment as incomplete."""
        self.completed = False
        self.completed_at = None
        self.completed_by_id = None
        db.session.commit()

    @classmethod
    def delete_for_member(cls, member_id):
        """Delete all offboarding assignments for a member.

        Used when rehiring a member to clear old assignments.
        """
        cls.scoped().filter_by(member_id=member_id).delete()
        db.session.commit()
