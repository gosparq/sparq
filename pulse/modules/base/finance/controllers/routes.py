# -----------------------------------------------------------------------------
# sparQ - Finance Module Routes
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from datetime import datetime
from decimal import Decimal
from io import StringIO
import csv

from flask import Blueprint, flash, g, make_response, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from system.db.database import db
from system.device.template import render_device_template
from system.auth.decorators import admin_required
from system.i18n.translation import translate as _
from system.module.registry import module_enabled

from ..models.expense import (
    Expense,
    ExpenseCategory,
    ExpenseStatus,
    PaidBy,
    ReimbursementStatus,
)
from ..models.accounting import AccountingAccount, AccountingLedger, AccountType

blueprint = Blueprint(
    "finance_bp",
    __name__,
    template_folder="../views/templates",
    static_folder="../views/assets",
    static_url_path="/assets",
)


@blueprint.route("/")  # type: ignore[misc]
@login_required  # type: ignore[misc]
def index() -> str:
    return redirect(url_for("finance_bp.expenses"))


@blueprint.route("/reports")  # type: ignore[misc]
@login_required  # type: ignore[misc]
def reports() -> str:
    return render_template(  # type: ignore[no-any-return]
        "finance/desktop/coming-soon.html",
        active_page="reports",
        title="Reports",
        page_icon="fa-solid fa-chart-line",
        icon_color=g.workspace_color,
        module_home="dashboard_bp.index",
    )


# -----------------------------------------------------------------------------
# Expense Routes
# -----------------------------------------------------------------------------


@blueprint.route("/expenses")  # type: ignore[misc]
@login_required  # type: ignore[misc]
def expenses() -> str:
    """List expenses - admin sees all, users see their own."""
    if current_user.is_admin:
        expense_list = Expense.scoped().order_by(Expense.created_at.desc()).all()
        pending_count = Expense.scoped().filter_by(status=ExpenseStatus.PENDING).count()
    else:
        expense_list = Expense.get_by_user(current_user.id)
        pending_count = 0

    return render_device_template(
        "finance/desktop/expenses/index.html",
        active_page="expenses",
        title="Expenses",
        expenses=expense_list,
        pending_count=pending_count,
        ExpenseStatus=ExpenseStatus,
        module_home="dashboard_bp.index",
    )


@blueprint.route("/expenses/new")  # type: ignore[misc]
@login_required  # type: ignore[misc]
def expense_new() -> str:
    """Show expense submission form."""
    jobs = []
    selected_job_id = request.args.get("job_id", type=int)
    if module_enabled("Service"):
        from modules.base.service.models.job import Job, JobStatus

        jobs = Job.query.filter(
            Job.status.in_([JobStatus.SCHEDULED, JobStatus.IN_PROGRESS])
        ).all()

    return render_device_template(
        "finance/desktop/expenses/form.html",
        active_page="expenses",
        title="New Expense",
        selected_job_id=selected_job_id,
        expense=None,
        jobs=jobs,
        categories=ExpenseCategory,
        PaidBy=PaidBy,
        module_home="dashboard_bp.index",
    )


@blueprint.route("/expenses", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
def expense_create() -> str:
    """Create a new expense."""
    # Determine paid_by from form
    paid_by_value = request.form.get("paid_by", "Personal (Needs Reimbursement)")
    paid_by = PaidBy(paid_by_value)

    # Determine reimbursement status based on paid_by
    if paid_by == PaidBy.PERSONAL:
        reimbursement_status = ReimbursementStatus.PENDING
    else:
        reimbursement_status = ReimbursementStatus.NOT_APPLICABLE

    # Billable to client checkbox
    billable_to_client = request.form.get("billable_to_client") == "on"

    expense = Expense(
        submitted_by_id=current_user.id,
        description=request.form["description"],
        category=ExpenseCategory(request.form["category"]),
        amount=Decimal(request.form["amount"]),
        expense_date=datetime.strptime(request.form["expense_date"], "%Y-%m-%d").date(),
        job_id=request.form.get("job_id") or None,
        notes=request.form.get("notes"),
        paid_by=paid_by,
        reimbursement_status=reimbursement_status,
        billable_to_client=billable_to_client,
    )
    db.session.add(expense)
    db.session.commit()
    flash(_("Expense submitted for approval"), "success")
    return redirect(url_for("finance_bp.expenses"))


@blueprint.route("/expenses/<int:expense_id>")  # type: ignore[misc]
@login_required  # type: ignore[misc]
def expense_detail(expense_id: int) -> str:
    """View expense details."""
    expense = Expense.scoped().get_or_404(expense_id)

    # Users can only view their own expenses unless admin
    if not current_user.is_admin and expense.submitted_by_id != current_user.id:
        flash(_("You don't have permission to view this expense"), "error")
        return redirect(url_for("finance_bp.expenses"))

    return render_device_template(
        "finance/desktop/expenses/detail.html",
        active_page="expenses",
        title="Expense Details",
        expense=expense,
        ExpenseStatus=ExpenseStatus,
        ReimbursementStatus=ReimbursementStatus,
        module_home="dashboard_bp.index",
    )


@blueprint.route("/expenses/<int:expense_id>/approve", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def expense_approve(expense_id: int) -> str:
    """Approve an expense (admin only)."""
    expense = Expense.scoped().get_or_404(expense_id)
    expense.status = ExpenseStatus.APPROVED
    expense.reviewed_by_id = current_user.id
    expense.reviewed_at = datetime.utcnow()
    db.session.commit()

    # Auto-sync business expenses to accounting ledger
    if not expense.billable_to_client:
        try:
            AccountingLedger.create_from_expense(expense, user_id=current_user.id)
        except Exception as e:
            # Log error but don't fail the approval
            import logging
            logging.getLogger(__name__).error(f"Error syncing expense to accounting: {e}")

    flash(_("Expense approved"), "success")
    return redirect(url_for("finance_bp.expenses"))


@blueprint.route("/expenses/<int:expense_id>/reject", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def expense_reject(expense_id: int) -> str:
    """Reject an expense (admin only)."""
    expense = Expense.scoped().get_or_404(expense_id)
    expense.status = ExpenseStatus.REJECTED
    expense.reviewed_by_id = current_user.id
    expense.reviewed_at = datetime.utcnow()
    expense.rejection_reason = request.form.get("reason", "")
    db.session.commit()
    flash(_("Expense rejected"), "warning")
    return redirect(url_for("finance_bp.expenses"))


# -----------------------------------------------------------------------------
# Reimbursement Routes
# -----------------------------------------------------------------------------


@blueprint.route("/reimbursements")  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def reimbursements() -> str:
    """Reimbursement queue - pending reimbursements (admin only)."""
    pending = Expense.get_pending_reimbursement()
    stats = Expense.get_reimbursement_stats()

    return render_device_template(
        "finance/desktop/reimbursements/index.html",
        active_page="reimbursements",
        title="Reimbursements",
        expenses=pending,
        stats=stats,
        ReimbursementStatus=ReimbursementStatus,
        module_home="dashboard_bp.index",
    )


@blueprint.route("/expenses/<int:expense_id>/reimburse", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def expense_reimburse(expense_id: int) -> str:
    """Mark an expense as reimbursed (admin only)."""
    expense = Expense.scoped().get_or_404(expense_id)

    method = request.form.get("method", "")
    reference = request.form.get("reference", "")

    expense.mark_reimbursed(
        method=method,
        reference=reference,
        user_id=current_user.id,
    )

    flash(_("Expense reimbursed via %(method)s") % {"method": method}, "success")
    return redirect(url_for("finance_bp.reimbursements"))


@blueprint.route("/expenses/<int:expense_id>/waive", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def expense_waive(expense_id: int) -> str:
    """Waive reimbursement for an expense (admin only)."""
    expense = Expense.scoped().get_or_404(expense_id)
    expense.waive_reimbursement(user_id=current_user.id)
    flash(_("Reimbursement waived"), "info")
    return redirect(url_for("finance_bp.reimbursements"))


# -----------------------------------------------------------------------------
# Accounting Routes
# -----------------------------------------------------------------------------


@blueprint.route("/accounting")  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def accounting() -> str:
    """Business expense ledger view (admin only)."""
    year = request.args.get("year", datetime.now().year, type=int)

    entries = AccountingLedger.get_expense_entries(year)
    category_summary = AccountingLedger.get_expense_summary(year)
    monthly_totals = AccountingLedger.get_monthly_totals(year)
    grand_total = AccountingLedger.get_grand_total(year)

    # Get available years for dropdown
    available_years = AccountingLedger.get_available_years()
    if year not in available_years:
        available_years.insert(0, year)
    available_years = sorted(available_years, reverse=True)

    return render_template(
        "finance/desktop/accounting/index.html",
        active_page="accounting",
        title="Business Expenses",
        entries=entries,
        category_summary=category_summary,
        monthly_totals=monthly_totals,
        grand_total=grand_total,
        year=year,
        available_years=available_years,
        module_home="dashboard_bp.index",
    )


@blueprint.route("/accounting/sync", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def accounting_sync() -> str:
    """Sync approved business expenses to accounting ledger."""
    unsynced = Expense.get_unsynced_business_expenses()

    synced_count = 0
    for expense in unsynced:
        try:
            AccountingLedger.create_from_expense(expense, user_id=current_user.id)
            synced_count += 1
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Error syncing expense {expense.id}: {e}")

    if synced_count > 0:
        flash(_("Synced %(count)s expense(s) to accounting") % {"count": synced_count}, "success")
    else:
        flash(_("No new expenses to sync"), "info")

    return redirect(url_for("finance_bp.accounting"))


@blueprint.route("/accounting/report")  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def accounting_report() -> str:
    """Generate tax-ready expense report."""
    year = request.args.get("year", datetime.now().year, type=int)
    format_type = request.args.get("format", "html")

    entries = AccountingLedger.get_expense_entries(year)
    category_summary = AccountingLedger.get_expense_summary(year)
    grand_total = AccountingLedger.get_grand_total(year)

    if format_type == "csv":
        # Generate CSV download
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["Date", "Description", "Account Code", "Account Name", "Amount", "Vendor"])

        for entry in entries:
            writer.writerow([
                entry.entry_date.strftime("%Y-%m-%d"),
                entry.description,
                entry.account.code,
                entry.account.name,
                f"{entry.debit:.2f}",
                entry.vendor_name or "",
            ])

        # Add summary section
        writer.writerow([])
        writer.writerow(["Summary by Category"])
        writer.writerow(["Account Code", "Account Name", "Total", "Count"])
        for cat in category_summary:
            writer.writerow([cat["code"], cat["name"], f"{cat['total']:.2f}", cat["count"]])

        writer.writerow([])
        writer.writerow(["Grand Total", "", f"{grand_total:.2f}"])

        response = make_response(output.getvalue())
        response.headers["Content-Type"] = "text/csv"
        response.headers["Content-Disposition"] = f"attachment; filename=business_expenses_{year}.csv"
        return response

    return render_template(
        "finance/desktop/accounting/report.html",
        active_page="report",
        title=f"Expense Report {year}",
        year=year,
        entries=entries,
        category_summary=category_summary,
        grand_total=grand_total,
        module_home="dashboard_bp.index",
    )


# -----------------------------------------------------------------------------
# Settings Routes
# -----------------------------------------------------------------------------


@blueprint.route("/settings")  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def settings() -> str:
    """Finance settings landing page (admin only)."""
    return render_template(
        "finance/desktop/settings/index.html",
        active_page="settings",
        title="Finance Settings",
        module_home="dashboard_bp.index",
    )


@blueprint.route("/settings/accounts")  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def accounts_settings() -> str:
    """Chart of Accounts management (admin only)."""
    accounts = AccountingAccount.scoped().order_by(
        AccountingAccount.code
    ).all()

    return render_template(
        "finance/desktop/settings/accounts.html",
        active_page="settings",
        title="Chart of Accounts",
        accounts=accounts,
        AccountType=AccountType,
        module_home="dashboard_bp.index",
    )


@blueprint.route("/settings/accounts/new", methods=["GET", "POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def account_new() -> str:
    """Create a new account."""
    if request.method == "POST":
        account = AccountingAccount(
            code=request.form["code"],
            name=request.form["name"],
            account_type=AccountType(request.form["account_type"]),
            parent_id=request.form.get("parent_id") or None,
            description=request.form.get("description"),
            tax_category=request.form.get("tax_category"),
        )
        db.session.add(account)
        db.session.commit()
        flash(_("Account %(code)s - %(name)s created") % {"code": account.code, "name": account.name}, "success")
        return redirect(url_for("finance_bp.accounts_settings"))

    # GET - show form
    parent_accounts = AccountingAccount.scoped().filter(
        AccountingAccount.parent_id.is_(None)
    ).order_by(AccountingAccount.code).all()

    return render_template(
        "finance/desktop/settings/account_form.html",
        active_page="settings",
        title="New Account",
        account=None,
        parent_accounts=parent_accounts,
        AccountType=AccountType,
        module_home="dashboard_bp.index",
    )


@blueprint.route("/settings/accounts/<int:account_id>/edit", methods=["GET", "POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def account_edit(account_id: int) -> str:
    """Edit an existing account."""
    account = AccountingAccount.scoped().get_or_404(account_id)

    if request.method == "POST":
        account.code = request.form["code"]
        account.name = request.form["name"]
        account.account_type = AccountType(request.form["account_type"])
        account.parent_id = request.form.get("parent_id") or None
        account.description = request.form.get("description")
        account.tax_category = request.form.get("tax_category")
        account.is_active = request.form.get("is_active") == "on"
        db.session.commit()
        flash(_("Account %(code)s updated") % {"code": account.code}, "success")
        return redirect(url_for("finance_bp.accounts_settings"))

    # GET - show form
    parent_accounts = AccountingAccount.scoped().filter(
        AccountingAccount.parent_id.is_(None),
        AccountingAccount.id != account_id,
    ).order_by(AccountingAccount.code).all()

    return render_template(
        "finance/desktop/settings/account_form.html",
        active_page="settings",
        title=f"Edit Account {account.code}",
        account=account,
        parent_accounts=parent_accounts,
        AccountType=AccountType,
        module_home="dashboard_bp.index",
    )


@blueprint.route("/settings/accounts/<int:account_id>/delete", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def account_delete(account_id: int) -> str:
    """Delete an account. If it has entries, move them to another account first."""
    account = AccountingAccount.scoped().get_or_404(account_id)

    # Check if account has ledger entries
    entry_count = AccountingLedger.scoped().filter_by(account_id=account_id).count()

    if entry_count > 0:
        # Move entries to the selected target account
        target_id = request.form.get("target_account_id")
        if not target_id:
            flash(_("Please select an account to move entries to"), "error")
            return redirect(url_for("finance_bp.accounts_settings"))

        AccountingLedger.scoped().filter_by(account_id=account_id).update(
            {"account_id": int(target_id)}
        )
        db.session.commit()
        flash(_("Moved %(count)s entries to new account") % {"count": entry_count}, "info")

    # Check if account has children
    child_count = AccountingAccount.scoped().filter_by(parent_id=account_id).count()
    if child_count > 0:
        # Move children to be top-level
        AccountingAccount.scoped().filter_by(parent_id=account_id).update(
            {"parent_id": None}
        )
        db.session.commit()

    # Now delete the account
    db.session.delete(account)
    db.session.commit()
    flash(_("Account %(code)s - %(name)s deleted") % {"code": account.code, "name": account.name}, "success")
    return redirect(url_for("finance_bp.accounts_settings"))
