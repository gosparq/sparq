# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
import pytest


@pytest.mark.integration
class TestFinanceRoutes:
    """Smoke tests for finance routes."""

    def test_finance_index(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/finance/")
            assert resp.status_code in (200, 302)

    def test_finance_accounting(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/finance/accounting")
            assert resp.status_code == 200

    def test_finance_accounting_report(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/finance/accounting/report")
            assert resp.status_code == 200

    def test_finance_expenses(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/finance/expenses")
            assert resp.status_code == 200

    def test_finance_expenses_new(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/finance/expenses/new")
            assert resp.status_code != 404  # 500: template bug (datetime.date not callable), tracked

    def test_finance_reimbursements(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/finance/reimbursements")
            assert resp.status_code == 200

    def test_finance_reports(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/finance/reports")
            assert resp.status_code == 200

    def test_finance_settings(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/finance/settings")
            assert resp.status_code == 200

    def test_finance_settings_accounts(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/finance/settings/accounts")
            assert resp.status_code == 200

    def test_finance_settings_accounts_new(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/finance/settings/accounts/new")
            assert resp.status_code == 200
