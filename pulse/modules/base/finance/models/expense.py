# -----------------------------------------------------------------------------
# sparQ - Expense Model
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""Expense tracking models for employee expense management.

This module provides models for tracking employee expenses, approval workflows,
and reimbursement processing.

Classes:
    ExpenseStatus: Enum for expense approval workflow states.
    ExpenseCategory: Enum for categorizing expenses.
    PaidBy: Enum for tracking payment source.
    ReimbursementStatus: Enum for reimbursement workflow states.
    Expense: Main expense record model.

Example:
    Creating an expense::

        expense = Expense(
            submitted_by_id=user.id,
            description="Client dinner",
            category=ExpenseCategory.MEALS,
            amount=Decimal("75.50"),
            paid_by=PaidBy.PERSONAL
        )
        db.session.add(expense)
        db.session.commit()

    Getting pending approvals::

        pending = Expense.get_pending_for_approval()
"""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.workspace import WorkspaceMixin


class ExpenseStatus(Enum):
    """Expense approval workflow states.

    Attributes:
        PENDING: Awaiting manager review.
        APPROVED: Approved by manager.
        REJECTED: Rejected by manager.
    """

    PENDING = "Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"


class ExpenseCategory(Enum):
    # Project-related expenses
    MATERIALS = "Materials"
    FUEL = "Fuel & Mileage"
    TOOLS = "Tools & Equipment"
    SUBCONTRACTOR = "Subcontractor"
    PERMITS = "Permits & Fees"
    SUPPLIES = "Office Supplies"
    # Business expenses
    SOFTWARE = "Software & Subscriptions"
    MEALS = "Meals & Entertainment"
    TRAVEL = "Travel & Lodging"
    PROFESSIONAL = "Professional Services"
    INSURANCE = "Insurance"
    UTILITIES = "Utilities"
    MARKETING = "Marketing & Advertising"
    RENT = "Rent & Lease"
    TRAINING = "Training & Education"
    OTHER = "Other"


class PaidBy(Enum):
    """Who paid for the expense."""

    COMPANY = "Company Card/Account"
    PERSONAL = "Personal (Needs Reimbursement)"


class ReimbursementStatus(Enum):
    """Status of reimbursement for personal expenses."""

    NOT_APPLICABLE = "N/A"  # Paid by company, no reimbursement needed
    PENDING = "Pending"  # Awaiting reimbursement
    REIMBURSED = "Reimbursed"  # Paid back
    WAIVED = "Waived"  # Employee waived reimbursement


@ModelRegistry.register
class Expense(db.Model, WorkspaceMixin):
    """Expense report submitted by employees or owners.

    Attributes:
        id: Primary key.
        submitted_by_id: FK to User who submitted the expense.
        description: Description of the expense.
        category: ExpenseCategory enum value.
        amount: Expense amount as decimal.
        expense_date: Date the expense was incurred.
        receipt_path: Path to uploaded receipt file.
        notes: Additional notes about the expense.
        job_id: Optional link to a Service module Job.
        billable_to_client: Whether expense can be invoiced to client.
        paid_by: PaidBy enum - company card or personal.
        status: ExpenseStatus approval state.
        reviewed_by_id: FK to User who reviewed the expense.
        reviewed_at: Timestamp of review.
        rejection_reason: Reason if rejected.
        reimbursement_status: ReimbursementStatus for personal expenses.
        reimbursed_at: Timestamp when reimbursed.
        reimbursement_method: Payment method used (Check, ACH, Cash, Payroll).
        reimbursement_reference: Reference number (check #, transaction ID).

    Properties:
        job: Related Job record (if Service module enabled).
        needs_reimbursement: Whether expense awaits reimbursement.
        is_business_expense: Whether expense is not billable to client.
    """

    __tablename__ = "expense"

    id = db.Column(db.Integer, primary_key=True)

    # Who submitted
    submitted_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    submitted_by = db.relationship("User", foreign_keys=[submitted_by_id], lazy="select")

    # Expense details
    description = db.Column(db.String(255), nullable=False)
    category = db.Column(db.Enum(ExpenseCategory), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    expense_date = db.Column(db.Date, nullable=False, default=date.today)
    receipt_path = db.Column(db.String(500), nullable=True)  # Future: file upload
    notes = db.Column(db.Text, nullable=True)

    # Optional job link (no FK constraint for loose coupling with Service module)
    job_id = db.Column(db.Integer, nullable=True)

    # Billing: Can this expense be invoiced to a client?
    billable_to_client = db.Column(db.Boolean, default=False)

    # Payment tracking
    paid_by = db.Column(db.Enum(PaidBy), default=PaidBy.PERSONAL)

    # Approval workflow
    status = db.Column(db.Enum(ExpenseStatus), default=ExpenseStatus.PENDING)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    reviewed_by = db.relationship("User", foreign_keys=[reviewed_by_id], lazy="select")
    reviewed_at = db.Column(db.DateTime, nullable=True)
    rejection_reason = db.Column(db.Text, nullable=True)

    # Reimbursement tracking
    reimbursement_status = db.Column(
        db.Enum(ReimbursementStatus), default=ReimbursementStatus.NOT_APPLICABLE
    )
    reimbursed_at = db.Column(db.DateTime, nullable=True)
    reimbursement_method = db.Column(db.String(50), nullable=True)  # Check, ACH, Cash, Payroll
    reimbursement_reference = db.Column(db.String(100), nullable=True)  # Check #, txn ID
    reimbursed_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    reimbursed_by = db.relationship("User", foreign_keys=[reimbursed_by_id], lazy="select")

    # Invoice tracking (for client-billable expenses)
    invoiced = db.Column(db.Boolean, default=False)
    invoice_line_item_id = db.Column(db.Integer, nullable=True)

    # Accounting sync
    synced_to_accounting = db.Column(db.Boolean, default=False)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def job(self):
        """Get related job if Service module enabled."""
        if not self.job_id:
            return None
        from system.module.registry import module_enabled

        if not module_enabled("Service"):
            return None
        from modules.base.service.models.job import Job

        return Job.query.get(self.job_id)

    @property
    def needs_reimbursement(self) -> bool:
        """Check if expense needs reimbursement."""
        return (
            self.paid_by == PaidBy.PERSONAL
            and self.reimbursement_status == ReimbursementStatus.PENDING
        )

    @property
    def is_business_expense(self) -> bool:
        """Check if this is a business expense (not billable to client)."""
        return not self.billable_to_client

    # -------------------------------------------------------------------------
    # Instance Methods
    # -------------------------------------------------------------------------

    def mark_reimbursed(self, method: str, reference: str = None, user_id: int = None):
        """Mark expense as reimbursed."""
        self.reimbursement_status = ReimbursementStatus.REIMBURSED
        self.reimbursed_at = datetime.utcnow()
        self.reimbursement_method = method
        self.reimbursement_reference = reference
        self.reimbursed_by_id = user_id
        db.session.commit()

    def waive_reimbursement(self, user_id: int = None):
        """Mark reimbursement as waived."""
        self.reimbursement_status = ReimbursementStatus.WAIVED
        self.reimbursed_by_id = user_id
        db.session.commit()

    # -------------------------------------------------------------------------
    # Class Methods - Queries
    # -------------------------------------------------------------------------

    @classmethod
    def get_pending_for_approval(cls):
        """Get all expenses pending approval."""
        return (
            cls.scoped().filter_by(status=ExpenseStatus.PENDING)
            .order_by(cls.created_at.desc())
            .all()
        )

    @classmethod
    def get_approved_for_job(cls, job_id, uninvoiced_only=True):
        """Get approved expenses for a job, optionally only uninvoiced ones."""
        query = cls.scoped().filter_by(job_id=job_id, status=ExpenseStatus.APPROVED)
        if uninvoiced_only:
            query = query.filter_by(invoiced=False)
        return query.order_by(cls.expense_date).all()

    @classmethod
    def get_by_user(cls, user_id):
        """Get all expenses submitted by a user."""
        return (
            cls.scoped().filter_by(submitted_by_id=user_id)
            .order_by(cls.created_at.desc())
            .all()
        )

    @classmethod
    def get_pending_reimbursement(cls):
        """Get all approved expenses awaiting reimbursement."""
        return (
            cls.scoped().filter(
                cls.status == ExpenseStatus.APPROVED,
                cls.paid_by == PaidBy.PERSONAL,
                cls.reimbursement_status == ReimbursementStatus.PENDING,
            )
            .order_by(cls.expense_date.desc())
            .all()
        )

    @classmethod
    def get_business_expenses(cls, year: int = None):
        """Get approved business expenses (not billable to client)."""
        query = cls.scoped().filter(
            cls.status == ExpenseStatus.APPROVED,
            cls.billable_to_client == False,
        )
        if year:
            from sqlalchemy import extract

            query = query.filter(extract("year", cls.expense_date) == year)
        return query.order_by(cls.expense_date.desc()).all()

    @classmethod
    def get_unsynced_business_expenses(cls):
        """Get approved business expenses not yet synced to accounting."""
        return (
            cls.scoped().filter(
                cls.status == ExpenseStatus.APPROVED,
                cls.billable_to_client == False,
                cls.synced_to_accounting == False,
            )
            .order_by(cls.expense_date)
            .all()
        )

    @classmethod
    def get_reimbursement_stats(cls):
        """Get reimbursement statistics."""
        pending = cls.scoped().filter(
            cls.status == ExpenseStatus.APPROVED,
            cls.paid_by == PaidBy.PERSONAL,
            cls.reimbursement_status == ReimbursementStatus.PENDING,
        )
        pending_count = pending.count()
        pending_amount = (
            db.session.query(db.func.sum(cls.amount))
            .filter(
                cls.status == ExpenseStatus.APPROVED,
                cls.paid_by == PaidBy.PERSONAL,
                cls.reimbursement_status == ReimbursementStatus.PENDING,
            )
            .scalar()
            or Decimal("0.00")
        )

        return {
            "pending_count": pending_count,
            "pending_amount": pending_amount,
        }

    @classmethod
    def get_reimbursable_totals(cls, start_date: date, end_date: date) -> dict[int, float]:
        """Get total reimbursable amounts per user for a date range.

        Args:
            start_date: Start of the date range (inclusive).
            end_date: End of the date range (inclusive).

        Returns:
            Dict mapping user_id (int) to total reimbursable amount (float).
        """
        expenses = cls.scoped().filter(
            cls.status == ExpenseStatus.APPROVED,
            cls.paid_by == PaidBy.PERSONAL,
            cls.reimbursement_status == ReimbursementStatus.PENDING,
            cls.expense_date >= start_date,
            cls.expense_date <= end_date,
        ).all()
        totals = {}
        for exp in expenses:
            uid = exp.submitted_by_id
            totals[uid] = totals.get(uid, 0) + float(exp.amount)
        return totals

    @classmethod
    def get_reimbursable_line_items(
        cls, user_id: int, start_date: date, end_date: date
    ) -> list["Expense"]:
        """Get individual reimbursable expenses for a user in a date range.

        Args:
            user_id: ID of the user who submitted the expenses.
            start_date: Start of the date range (inclusive).
            end_date: End of the date range (inclusive).

        Returns:
            List of Expense objects, ordered by expense_date.
        """
        return (
            cls.scoped().filter(
                cls.submitted_by_id == user_id,
                cls.status == ExpenseStatus.APPROVED,
                cls.paid_by == PaidBy.PERSONAL,
                cls.reimbursement_status == ReimbursementStatus.PENDING,
                cls.expense_date >= start_date,
                cls.expense_date <= end_date,
            )
            .order_by(cls.expense_date)
            .all()
        )
