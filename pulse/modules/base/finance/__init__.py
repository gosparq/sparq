# -----------------------------------------------------------------------------
# sparQ - Finance Module
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""Finance module for expense tracking and accounting.

This module provides expense management, reimbursement workflows,
and basic accounting ledger functionality.

Key Models:
    Expense: Employee expense records with receipt attachments.
    ExpenseCategory: Categories for organizing expenses.
    ExpenseStatus: Workflow states (Draft, Submitted, Approved, Rejected, Paid).
    PaidBy: Payment method tracking (Company Card, Personal, Cash).
    ReimbursementStatus: Reimbursement workflow states.
    AccountingAccount: Chart of accounts entries.
    AccountingLedger: Double-entry ledger transactions.
    AccountType: Account classifications (Asset, Liability, Equity, Revenue, Expense).

Key Features:
    - Employee expense submission and tracking
    - Manager approval workflows
    - Receipt attachment support
    - Reimbursement processing
    - Basic double-entry accounting

Routes:
    /finance - Finance dashboard
    /finance/expenses - Expense management
    /finance/accounts - Chart of accounts
"""

from .models.expense import (
    Expense,
    ExpenseCategory,
    ExpenseStatus,
    PaidBy,
    ReimbursementStatus,
)
from .models.accounting import (
    AccountingAccount,
    AccountingLedger,
    AccountType,
)
from .module import FinanceModule

module_instance = FinanceModule()

__all__ = [
    "module_instance",
    "Expense",
    "ExpenseCategory",
    "ExpenseStatus",
    "PaidBy",
    "ReimbursementStatus",
    "AccountingAccount",
    "AccountingLedger",
    "AccountType",
]
