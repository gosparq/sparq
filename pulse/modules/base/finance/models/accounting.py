# -----------------------------------------------------------------------------
# sparQ - Accounting Models
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from datetime import datetime
from decimal import Decimal
from enum import Enum

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.workspace import WorkspaceMixin


class AccountType(Enum):
    """Types of accounts in chart of accounts."""

    ASSET = "Asset"
    LIABILITY = "Liability"
    EQUITY = "Equity"
    REVENUE = "Revenue"
    EXPENSE = "Expense"


@ModelRegistry.register
class AccountingAccount(db.Model, WorkspaceMixin):
    """Chart of Accounts - defines account structure for general ledger."""

    __tablename__ = "accounting_account"
    __table_args__ = (
        db.UniqueConstraint("code", "workspace_id", name="uq_accounting_account_code_workspace"),
    )

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), nullable=False)  # e.g., "5100"
    name = db.Column(db.String(100), nullable=False)  # e.g., "Office Supplies"
    account_type = db.Column(db.Enum(AccountType), nullable=False)
    parent_id = db.Column(
        db.Integer, db.ForeignKey("accounting_account.id"), nullable=True
    )
    is_active = db.Column(db.Boolean, default=True)
    description = db.Column(db.String(255), nullable=True)

    # For tax reporting - IRS Schedule C category hint
    tax_category = db.Column(db.String(100), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    parent = db.relationship(
        "AccountingAccount", remote_side=[id], backref=db.backref("children", lazy="select"), lazy="select",
    )
    ledger_entries = db.relationship("AccountingLedger", backref=db.backref("account", lazy="select"), lazy="select")

    @property
    def display_name(self) -> str:
        """Return code and name for display."""
        return f"{self.code} - {self.name}"

    @classmethod
    def get_expense_accounts(cls):
        """Get all active expense accounts (type=EXPENSE, excluding parent)."""
        return (
            cls.scoped().filter(
                cls.account_type == AccountType.EXPENSE,
                cls.is_active == True,
                cls.code != "5000",  # Exclude parent account
            )
            .order_by(cls.code)
            .all()
        )

    @classmethod
    def get_by_code(cls, code: str):
        """Find account by code."""
        return cls.scoped().filter_by(code=code).first()

    @classmethod
    def seed_defaults(cls):
        """Create default chart of accounts if not exists."""
        # Check if already seeded
        if cls.scoped().first():
            return

        DEFAULT_ACCOUNTS = [
            # Parent accounts (code, name, type, parent_code)
            ("1000", "Assets", AccountType.ASSET, None),
            ("2000", "Liabilities", AccountType.LIABILITY, None),
            ("3000", "Equity", AccountType.EQUITY, None),
            ("4000", "Revenue", AccountType.REVENUE, None),
            ("5000", "Expenses", AccountType.EXPENSE, None),
            # Expense sub-accounts (mapped to ExpenseCategory)
            ("5100", "Materials", AccountType.EXPENSE, "5000"),
            ("5200", "Fuel & Mileage", AccountType.EXPENSE, "5000"),
            ("5300", "Tools & Equipment", AccountType.EXPENSE, "5000"),
            ("5400", "Subcontractor", AccountType.EXPENSE, "5000"),
            ("5500", "Permits & Fees", AccountType.EXPENSE, "5000"),
            ("5600", "Office Supplies", AccountType.EXPENSE, "5000"),
            ("5700", "Software & Subscriptions", AccountType.EXPENSE, "5000"),
            ("5800", "Meals & Entertainment", AccountType.EXPENSE, "5000"),
            ("5900", "Travel & Lodging", AccountType.EXPENSE, "5000"),
            ("5910", "Professional Services", AccountType.EXPENSE, "5000"),
            ("5920", "Insurance", AccountType.EXPENSE, "5000"),
            ("5930", "Utilities", AccountType.EXPENSE, "5000"),
            ("5940", "Marketing & Advertising", AccountType.EXPENSE, "5000"),
            ("5950", "Rent & Lease", AccountType.EXPENSE, "5000"),
            ("5960", "Training & Education", AccountType.EXPENSE, "5000"),
            ("5990", "Other Expenses", AccountType.EXPENSE, "5000"),
            # Equity accounts for owner reimbursements
            ("3100", "Owner Draws", AccountType.EQUITY, "3000"),
            # Liability for employee reimbursements owed
            ("2100", "Accounts Payable - Employee", AccountType.LIABILITY, "2000"),
        ]

        # First pass: create all accounts without parent links
        accounts_by_code = {}
        for code, name, acct_type, _ in DEFAULT_ACCOUNTS:
            account = cls(code=code, name=name, account_type=acct_type)
            db.session.add(account)
            accounts_by_code[code] = account

        db.session.flush()  # Get IDs assigned

        # Second pass: set parent links
        for code, _, _, parent_code in DEFAULT_ACCOUNTS:
            if parent_code:
                accounts_by_code[code].parent_id = accounts_by_code[parent_code].id

        db.session.commit()


# Mapping from ExpenseCategory to AccountingAccount code
EXPENSE_CATEGORY_TO_ACCOUNT = {
    "Materials": "5100",
    "Fuel & Mileage": "5200",
    "Tools & Equipment": "5300",
    "Subcontractor": "5400",
    "Permits & Fees": "5500",
    "Office Supplies": "5600",
    "Software & Subscriptions": "5700",
    "Meals & Entertainment": "5800",
    "Travel & Lodging": "5900",
    "Professional Services": "5910",
    "Insurance": "5920",
    "Utilities": "5930",
    "Marketing & Advertising": "5940",
    "Rent & Lease": "5950",
    "Training & Education": "5960",
    "Other": "5990",
}


@ModelRegistry.register
class AccountingLedger(db.Model, WorkspaceMixin):
    """General Ledger - double-entry accounting entries."""

    __tablename__ = "accounting_ledger"

    id = db.Column(db.Integer, primary_key=True)

    # Entry details
    entry_date = db.Column(db.Date, nullable=False, index=True)
    account_id = db.Column(
        db.Integer, db.ForeignKey("accounting_account.id"), nullable=False
    )
    description = db.Column(db.String(255), nullable=False)

    # Double-entry: each entry has either debit OR credit (not both)
    debit = db.Column(db.Numeric(10, 2), default=Decimal("0.00"))
    credit = db.Column(db.Numeric(10, 2), default=Decimal("0.00"))

    # Source reference (polymorphic link back to source record)
    reference_type = db.Column(
        db.String(50), nullable=True
    )  # "expense", "invoice", "payment"
    reference_id = db.Column(db.Integer, nullable=True)

    # For quick filtering
    fiscal_year = db.Column(db.Integer, nullable=False, index=True)
    fiscal_period = db.Column(db.Integer, nullable=False)  # Month 1-12

    # Vendor/payee for expense tracking
    vendor_name = db.Column(db.String(100), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    @classmethod
    def create_from_expense(cls, expense, user_id=None):
        """
        Create ledger entries from an approved business expense.

        Creates two entries (double-entry):
        - Debit: Expense account (increases expense)
        - Credit: Owner Draws (if paid by owner) or AP-Employee (if employee)
        """
        from .expense import PaidBy

        # Get expense account based on category
        category_value = expense.category.value
        account_code = EXPENSE_CATEGORY_TO_ACCOUNT.get(category_value, "5990")
        expense_account = AccountingAccount.get_by_code(account_code)

        if not expense_account:
            raise ValueError(f"Expense account {account_code} not found")

        # Determine credit account based on who paid
        if expense.paid_by == PaidBy.PERSONAL:
            # Check if submitter is owner/admin or employee
            if expense.submitted_by.is_admin:
                credit_account = AccountingAccount.get_by_code("3100")  # Owner Draws
            else:
                credit_account = AccountingAccount.get_by_code("2100")  # AP-Employee
        else:
            # Paid by company - credit a cash/bank account (use Owner Draws for now)
            credit_account = AccountingAccount.get_by_code("3100")

        if not credit_account:
            raise ValueError("Credit account not found")

        fiscal_year = expense.expense_date.year
        fiscal_period = expense.expense_date.month

        # Create debit entry (expense account)
        debit_entry = cls(
            entry_date=expense.expense_date,
            account_id=expense_account.id,
            description=expense.description,
            debit=expense.amount,
            credit=Decimal("0.00"),
            reference_type="expense",
            reference_id=expense.id,
            fiscal_year=fiscal_year,
            fiscal_period=fiscal_period,
            vendor_name=None,  # Could add vendor field to expense later
            created_by_id=user_id,
        )
        db.session.add(debit_entry)

        # Create credit entry (equity/liability account)
        credit_entry = cls(
            entry_date=expense.expense_date,
            account_id=credit_account.id,
            description=f"Expense: {expense.description}",
            debit=Decimal("0.00"),
            credit=expense.amount,
            reference_type="expense",
            reference_id=expense.id,
            fiscal_year=fiscal_year,
            fiscal_period=fiscal_period,
            vendor_name=None,
            created_by_id=user_id,
        )
        db.session.add(credit_entry)

        # Mark expense as synced
        expense.synced_to_accounting = True
        db.session.commit()

        return debit_entry, credit_entry

    @classmethod
    def get_by_year(cls, year: int):
        """Get all ledger entries for a fiscal year."""
        return (
            cls.scoped().filter_by(fiscal_year=year)
            .order_by(cls.entry_date.desc(), cls.id.desc())
            .all()
        )

    @classmethod
    def get_expense_entries(cls, year: int):
        """Get expense-related ledger entries (debit entries to expense accounts)."""
        return (
            cls.scoped().join(AccountingAccount)
            .filter(
                cls.fiscal_year == year,
                AccountingAccount.account_type == AccountType.EXPENSE,
                cls.debit > 0,
            )
            .order_by(cls.entry_date.desc())
            .all()
        )

    @classmethod
    def get_expense_summary(cls, year: int):
        """Get expense totals grouped by account."""
        results = (
            db.session.query(
                AccountingAccount.code,
                AccountingAccount.name,
                db.func.sum(cls.debit).label("total"),
                db.func.count(cls.id).label("count"),
            )
            .join(AccountingAccount)
            .filter(
                cls.fiscal_year == year,
                AccountingAccount.account_type == AccountType.EXPENSE,
                cls.debit > 0,
            )
            .group_by(AccountingAccount.code, AccountingAccount.name)
            .order_by(AccountingAccount.code)
            .all()
        )

        return [
            {"code": r.code, "name": r.name, "total": r.total or Decimal("0.00"), "count": r.count}
            for r in results
        ]

    @classmethod
    def get_monthly_totals(cls, year: int):
        """Get monthly expense totals for charting."""
        results = (
            db.session.query(
                cls.fiscal_period, db.func.sum(cls.debit).label("total")
            )
            .join(AccountingAccount)
            .filter(
                cls.fiscal_year == year,
                AccountingAccount.account_type == AccountType.EXPENSE,
                cls.debit > 0,
            )
            .group_by(cls.fiscal_period)
            .all()
        )

        # Fill in all months with 0 for missing
        monthly = {i: Decimal("0.00") for i in range(1, 13)}
        for r in results:
            monthly[r.fiscal_period] = r.total or Decimal("0.00")

        return monthly

    @classmethod
    def get_grand_total(cls, year: int):
        """Get total expenses for a year."""
        result = (
            db.session.query(db.func.sum(cls.debit))
            .join(AccountingAccount)
            .filter(
                cls.fiscal_year == year,
                AccountingAccount.account_type == AccountType.EXPENSE,
                cls.debit > 0,
            )
            .scalar()
        )
        return result or Decimal("0.00")

    @classmethod
    def get_available_years(cls) -> list[int]:
        """Get all distinct fiscal years with ledger entries, sorted descending.

        Returns:
            List of fiscal year integers in descending order.
        """
        rows = (
            db.session.query(db.func.distinct(cls.fiscal_year))
            .order_by(cls.fiscal_year.desc())
            .all()
        )
        return [y[0] for y in rows if y[0]]
