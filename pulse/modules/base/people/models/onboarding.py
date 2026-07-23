# -----------------------------------------------------------------------------
# sparQ - Onboarding Models
#
# Description:
#     Models for employee onboarding workflow including OnboardingRecord
#     and OnboardingTask for tracking new hire progress.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

import secrets
from datetime import datetime
from enum import Enum

from flask import g

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.mixins import AuditMixin
from system.db.workspace import WorkspaceMixin

from modules.base.core.models.workspace_user import SalaryType
from system.db.raise_on_lazy import LAZY


class OnboardingStatus(Enum):
    """Status of an onboarding record."""

    DRAFT = "Draft"
    SENT = "Sent"
    IN_PROGRESS = "In Progress"
    PENDING_REVIEW = "Pending Review"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"


class OnboardingType(Enum):
    """Type of employee being onboarded."""

    W2 = "W-2 Employee"
    CONTRACTOR = "1099 Contractor"


class TaskAssignee(Enum):
    """Who is responsible for completing a task."""

    EMPLOYEE = "Employee"
    ADMIN = "Admin"


class TaskStatus(Enum):
    """Status of an onboarding task."""

    PENDING = "Pending"
    COMPLETED = "Completed"
    SKIPPED = "Skipped"


# Default task templates by onboarding type
W2_TASK_TEMPLATES = [
    {
        "task_key": "offer_letter",
        "label": "Sign Offer Letter",
        "description": "Review and sign your offer letter.",
        "assignee": TaskAssignee.EMPLOYEE,
        "required": True,
        "order": 1,
    },
    {
        "task_key": "contract",
        "label": "Sign Employment Agreement",
        "description": "Review and sign your employment agreement.",
        "assignee": TaskAssignee.EMPLOYEE,
        "required": False,
        "order": 2,
    },
    {
        "task_key": "personal_info",
        "label": "Personal Information",
        "description": "Provide your personal information and contact details.",
        "assignee": TaskAssignee.EMPLOYEE,
        "required": True,
        "order": 3,
    },
    {
        "task_key": "emergency_contact",
        "label": "Emergency Contact",
        "description": "Provide emergency contact information.",
        "assignee": TaskAssignee.EMPLOYEE,
        "required": False,
        "order": 4,
    },
    {
        "task_key": "w4",
        "label": "W-4 Tax Form",
        "description": "Download, complete, and upload your W-4 form.",
        "assignee": TaskAssignee.EMPLOYEE,
        "required": True,
        "order": 5,
    },
    {
        "task_key": "direct_deposit",
        "label": "Direct Deposit Info",
        "description": "Provide your bank account information for direct deposit.",
        "assignee": TaskAssignee.EMPLOYEE,
        "required": False,
        "order": 6,
    },
    {
        "task_key": "create_accounts",
        "label": "Create Email/System Accounts",
        "description": "Set up company email and system access for the new employee.",
        "assignee": TaskAssignee.ADMIN,
        "required": False,
        "order": 7,
    },
    {
        "task_key": "verify_documents",
        "label": "Verify I-9 Documents",
        "description": "Verify employee identity and work authorization documents.",
        "assignee": TaskAssignee.ADMIN,
        "required": False,
        "order": 8,
    },
]

CONTRACTOR_TASK_TEMPLATES = [
    {
        "task_key": "contract",
        "label": "Sign Contractor Agreement",
        "description": "Review and sign your contractor agreement.",
        "assignee": TaskAssignee.EMPLOYEE,
        "required": True,
        "order": 1,
    },
    {
        "task_key": "personal_info",
        "label": "Personal/Business Information",
        "description": "Provide your personal or business information.",
        "assignee": TaskAssignee.EMPLOYEE,
        "required": True,
        "order": 2,
    },
    {
        "task_key": "w9",
        "label": "W-9 Tax Form",
        "description": "Download, complete, and upload your W-9 form.",
        "assignee": TaskAssignee.EMPLOYEE,
        "required": True,
        "order": 3,
    },
    {
        "task_key": "verify_w9",
        "label": "Verify W-9 Information",
        "description": "Verify contractor W-9 information.",
        "assignee": TaskAssignee.ADMIN,
        "required": False,
        "order": 4,
    },
]


def generate_token():
    """Generate a secure token for onboarding access."""
    return secrets.token_urlsafe(32)


@ModelRegistry.register
class OnboardingRecord(db.Model, WorkspaceMixin, AuditMixin):
    """Record for tracking employee onboarding process."""

    __tablename__ = "onboarding_record"

    id = db.Column(db.Integer, primary_key=True)

    # Link to member (created when onboarding starts)
    member_id = db.Column(db.Integer, db.ForeignKey("workspace_user.id"), nullable=True)

    # Basic info (set by admin)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    personal_email = db.Column(db.String(255), nullable=False)
    work_email = db.Column(db.String(255), nullable=True)

    # Employment details
    onboarding_type = db.Column(db.Enum(OnboardingType), nullable=False)
    position = db.Column(db.String(100))
    department = db.Column(db.String(100))
    start_date = db.Column(db.Date)
    salary = db.Column(db.Numeric(10, 2))
    salary_type = db.Column(db.Enum(SalaryType), default=SalaryType.YEARLY)
    manager_id = db.Column(db.Integer, db.ForeignKey("workspace_user.id"), nullable=True)

    # Workflow
    status = db.Column(db.Enum(OnboardingStatus), default=OnboardingStatus.DRAFT)
    token = db.Column(db.String(64), unique=True, default=generate_token)
    sent_at = db.Column(db.DateTime)
    started_at = db.Column(db.DateTime)
    submitted_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)

    # Documents (offer letter, contract - via e-sign)
    offer_letter_request_id = db.Column(
        db.Integer, db.ForeignKey("signature_request.id"), nullable=True
    )
    contract_request_id = db.Column(
        db.Integer, db.ForeignKey("signature_request.id"), nullable=True
    )

    # Tax form uploaded by employee
    tax_form_attachment_id = db.Column(
        db.Integer, db.ForeignKey("attachment.id"), nullable=True
    )

    # Admin notes
    admin_notes = db.Column(db.Text)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    member = db.relationship(
        "WorkspaceUser",
        foreign_keys=[member_id],
        backref=db.backref("onboarding_record", uselist=False, lazy=LAZY),
        lazy=LAZY,
    )
    manager = db.relationship("WorkspaceUser", foreign_keys=[manager_id], lazy=LAZY)
    offer_letter_request = db.relationship(
        "SignatureRequest", foreign_keys=[offer_letter_request_id], lazy=LAZY,
    )
    contract_request = db.relationship(
        "SignatureRequest", foreign_keys=[contract_request_id], lazy=LAZY,
    )
    tax_form_attachment = db.relationship("Attachment", foreign_keys=[tax_form_attachment_id], lazy=LAZY)
    tasks = db.relationship(
        "OnboardingTask",
        backref=db.backref("onboarding", lazy=LAZY),
        cascade="all, delete-orphan",
        order_by="OnboardingTask.order",
        lazy=LAZY,
    )

    @property
    def full_name(self):
        """Return full name."""
        return f"{self.first_name} {self.last_name}"

    @property
    def progress_percent(self):
        """Calculate completion percentage based on required employee tasks."""
        employee_tasks = [t for t in self.tasks if t.assignee == TaskAssignee.EMPLOYEE]
        if not employee_tasks:
            return 100
        completed = sum(1 for t in employee_tasks if t.status == TaskStatus.COMPLETED)
        return int((completed / len(employee_tasks)) * 100)

    @property
    def required_tasks_complete(self):
        """Check if all required employee tasks are complete."""
        required = [
            t
            for t in self.tasks
            if t.assignee == TaskAssignee.EMPLOYEE and t.required
        ]
        return all(t.status == TaskStatus.COMPLETED for t in required)

    @classmethod
    def create(cls, **kwargs):
        """Create a new onboarding record with tasks from templates."""
        onboarding_type = kwargs.get("onboarding_type", OnboardingType.W2)
        record = cls(**kwargs)
        db.session.add(record)
        db.session.flush()  # Get ID for task relationships

        # Auto-prepend working agreement task
        agreement_task = OnboardingTask(
            onboarding_id=record.id,
            task_key="working_agreement",
            label="Read the team working agreement",
            description="Read and acknowledge the team working agreement at /resources/working-agreement/",
            assignee=TaskAssignee.EMPLOYEE,
            required=False,
            order=0,
        )
        db.session.add(agreement_task)

        # Create tasks based on type (uses DB templates or defaults)
        templates = get_task_templates_for_type(onboarding_type)
        for template in templates:
            task = OnboardingTask(
                onboarding_id=record.id,
                task_key=template["task_key"],
                label=template["label"],
                description=template["description"],
                assignee=template["assignee"],
                required=template["required"],
                order=template["order"],
            )
            db.session.add(task)

        db.session.commit()
        return record

    @classmethod
    def get_by_id(cls, record_id):
        """Get onboarding record by ID."""
        return cls.scoped().filter_by(id=record_id).first()

    @classmethod
    def get_by_token(cls, token: str) -> "OnboardingRecord | None":
        """Get onboarding record by its globally-unique token.

        Unscoped by design: the token is a cryptographic secret, and the
        onboarding magic-link is a public route where an anonymous new hire
        has no workspace context. Matches OrganizationInvitation/PendingSignup.
        """
        return cls.query.filter_by(token=token).first()

    @classmethod
    def get_by_member_id(cls, member_id):
        """Get onboarding record for a member."""
        return cls.scoped().filter_by(member_id=member_id).first()

    @classmethod
    def get_all(cls, status=None):
        """Get all onboarding records, optionally filtered by status."""
        query = cls.scoped().order_by(cls.created_at.desc())
        if status:
            query = query.filter_by(status=status)
        return query.all()

    @classmethod
    def get_pending_review(cls):
        """Get records awaiting admin review."""
        return cls.get_all(status=OnboardingStatus.PENDING_REVIEW)

    def mark_sent(self):
        """Mark as sent (invite email sent)."""
        self.status = OnboardingStatus.SENT
        self.sent_at = datetime.utcnow()
        db.session.commit()

    def mark_in_progress(self):
        """Mark as in progress (employee started)."""
        if self.status == OnboardingStatus.SENT:
            self.status = OnboardingStatus.IN_PROGRESS
            self.started_at = datetime.utcnow()
            db.session.commit()

    def submit_for_review(self):
        """Submit for admin review."""
        self.status = OnboardingStatus.PENDING_REVIEW
        self.submitted_at = datetime.utcnow()
        db.session.commit()

    def approve(self):
        """Approve and complete onboarding."""
        self.status = OnboardingStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        db.session.commit()

    def cancel(self) -> None:
        """Cancel onboarding and deactivate associated member/user.

        Sets the onboarding status to CANCELLED. If a member was created
        during the invite, marks them as INACTIVE and deactivates their
        user account so they cannot log in.
        """
        from modules.base.core.models.workspace_user import EmployeeStatus

        self.status = OnboardingStatus.CANCELLED

        if self.member:
            self.member.status = EmployeeStatus.INACTIVE
            self.member.user.is_active = False

        db.session.commit()

    def resume(self) -> None:
        """Resume a cancelled onboarding so the member can pick up where they left off.

        Resets the onboarding status to SENT and reactivates the associated
        member's user account. Generates a new magic link token. Completed
        tasks are preserved.
        """
        from modules.base.core.models.workspace_user import EmployeeStatus

        self.status = OnboardingStatus.SENT
        self.token = generate_token()

        if self.member:
            self.member.status = EmployeeStatus.INACTIVE
            self.member.user.is_active = True

        db.session.commit()

    def get_task(self, task_key):
        """Get a specific task by key."""
        for task in self.tasks:
            if task.task_key == task_key:
                return task
        return None

    def transfer_documents_to_member(self) -> int:
        """Transfer onboarding documents to member record.

        Creates AttachmentLink records for tax forms and signed documents
        so they appear in the member's document section.

        Returns:
            int: Number of documents transferred.
        """
        from modules.base.resources.models import AttachmentLink

        if not self.member_id:
            return 0

        transferred = 0

        # Tax form (W4/W9)
        if self.tax_form_attachment_id:
            if not AttachmentLink.exists(
                self.tax_form_attachment_id, "member", self.member_id
            ):
                AttachmentLink.create(
                    attachment_id=self.tax_form_attachment_id,
                    entity_type="member",
                    entity_id=self.member_id,
                )
                transferred += 1

        # Signed offer letter
        if (
            self.offer_letter_request
            and self.offer_letter_request.signed_attachment_id
        ):
            if not AttachmentLink.exists(
                self.offer_letter_request.signed_attachment_id,
                "member",
                self.member_id,
            ):
                AttachmentLink.create(
                    attachment_id=self.offer_letter_request.signed_attachment_id,
                    entity_type="member",
                    entity_id=self.member_id,
                )
                transferred += 1

        # Signed contract
        if self.contract_request and self.contract_request.signed_attachment_id:
            if not AttachmentLink.exists(
                self.contract_request.signed_attachment_id,
                "member",
                self.member_id,
            ):
                AttachmentLink.create(
                    attachment_id=self.contract_request.signed_attachment_id,
                    entity_type="member",
                    entity_id=self.member_id,
                )
                transferred += 1

        return transferred


@ModelRegistry.register
class OnboardingTask(db.Model, WorkspaceMixin):
    """Individual task within an onboarding workflow."""

    __tablename__ = "onboarding_task"

    id = db.Column(db.Integer, primary_key=True)
    onboarding_id = db.Column(
        db.Integer, db.ForeignKey("onboarding_record.id"), nullable=False
    )

    task_key = db.Column(db.String(50), nullable=False)
    label = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    assignee = db.Column(db.Enum(TaskAssignee), nullable=False)
    required = db.Column(db.Boolean, default=True)
    order = db.Column(db.Integer, default=0)

    status = db.Column(db.Enum(TaskStatus), default=TaskStatus.PENDING)
    completed_at = db.Column(db.DateTime)

    # Data storage for completed task (JSON)
    data = db.Column(db.Text)

    def complete(self, data=None):
        """Mark task as completed."""
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        if data:
            import json

            self.data = json.dumps(data)
        db.session.commit()

    def skip(self):
        """Mark task as skipped."""
        if not self.required:
            self.status = TaskStatus.SKIPPED
            db.session.commit()

    def reset(self):
        """Reset task to pending."""
        self.status = TaskStatus.PENDING
        self.completed_at = None
        self.data = None
        db.session.commit()

    @property
    def is_complete(self):
        """Check if task is completed or skipped."""
        return self.status in (TaskStatus.COMPLETED, TaskStatus.SKIPPED)


@ModelRegistry.register
class OnboardingTaskTemplate(db.Model, WorkspaceMixin):
    """Reusable task template for onboarding workflows.

    Admins can customize the default task templates per onboarding type.
    If no custom templates exist, the hardcoded defaults are used.
    """

    __tablename__ = "onboarding_task_template"

    id = db.Column(db.Integer, primary_key=True)
    onboarding_type = db.Column(db.Enum(OnboardingType), nullable=False)

    task_key = db.Column(db.String(50), nullable=False)
    label = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    assignee = db.Column(db.Enum(TaskAssignee), nullable=False)
    required = db.Column(db.Boolean, default=True)
    order = db.Column(db.Integer, default=0)
    active = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @classmethod
    def get_templates_for_type(cls, onboarding_type, include_inactive=False):
        """Get templates for a given onboarding type."""
        query = cls.scoped().filter_by(onboarding_type=onboarding_type)
        if not include_inactive:
            query = query.filter_by(active=True)
        return query.order_by(cls.order).all()

    @classmethod
    def get_all_templates(cls):
        """Get all templates grouped by type."""
        return cls.scoped().order_by(cls.onboarding_type, cls.order).all()

    @classmethod
    def has_custom_templates(cls):
        """Check if any custom templates exist in the database."""
        return cls.scoped().first() is not None

    @classmethod
    def initialize_defaults(cls):
        """Initialize default templates from hardcoded values if none exist."""
        # Check if any templates exist
        if cls.scoped().first() is not None:
            return False

        # Create W2 templates
        for template in W2_TASK_TEMPLATES:
            db.session.add(cls(
                onboarding_type=OnboardingType.W2,
                task_key=template["task_key"],
                label=template["label"],
                description=template["description"],
                assignee=template["assignee"],
                required=template["required"],
                order=template["order"],
            ))

        # Create Contractor templates
        for template in CONTRACTOR_TASK_TEMPLATES:
            db.session.add(cls(
                onboarding_type=OnboardingType.CONTRACTOR,
                task_key=template["task_key"],
                label=template["label"],
                description=template["description"],
                assignee=template["assignee"],
                required=template["required"],
                order=template["order"],
            ))

        db.session.commit()
        return True

    @classmethod
    def get_next_order_by_type(cls):
        """Get the next available order number for each onboarding type.

        Returns:
            dict: Mapping of OnboardingType name to next order number.
        """
        result = {}
        for otype in OnboardingType:
            max_order = (
                db.session.query(db.func.max(cls.order))
                .filter(
                    cls.workspace_id == g.workspace_id,
                    cls.onboarding_type == otype,
                )
                .scalar()
            )
            result[otype.name] = (max_order or 0) + 1
        return result

    @classmethod
    def create(cls, **kwargs):
        """Create a new task template."""
        template = cls(**kwargs)
        db.session.add(template)
        db.session.commit()
        return template

    def update(self, **kwargs):
        """Update template fields."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        db.session.commit()

    def delete(self):
        """Delete this template."""
        db.session.delete(self)
        db.session.commit()


def get_task_templates_for_type(onboarding_type):
    """Get task templates for an onboarding type.

    Returns database templates if they exist, otherwise returns hardcoded defaults.
    """
    templates = OnboardingTaskTemplate.get_templates_for_type(onboarding_type)
    if templates:
        return [
            {
                "task_key": t.task_key,
                "label": t.label,
                "description": t.description,
                "assignee": t.assignee,
                "required": t.required,
                "order": t.order,
            }
            for t in templates
        ]

    # Fall back to hardcoded defaults
    if onboarding_type == OnboardingType.W2:
        return W2_TASK_TEMPLATES
    else:
        return CONTRACTOR_TASK_TEMPLATES
