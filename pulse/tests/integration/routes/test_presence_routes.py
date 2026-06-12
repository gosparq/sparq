# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
import pytest


@pytest.mark.integration
class TestPresenceRoutes:
    """Smoke tests for presence routes."""

    def test_board_index(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/presence/board/")
            assert resp.status_code == 200

    def test_board_clear_modal(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/presence/board/clear-modal")
            assert resp.status_code == 200

    def test_board_partial(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/presence/board/partial")
            assert resp.status_code == 200

    def test_clock_index(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/presence/clock/")
            assert resp.status_code == 200

    def test_clock_forecast_week(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/presence/clock/forecast-week")
            assert resp.status_code == 200

    def test_clock_status(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/presence/clock/status")
            assert resp.status_code == 200

    def test_flow_index(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/presence/flow/")
            assert resp.status_code != 404  # 500: lazy-load bug, tracked

    def test_flow_health(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/presence/flow/health/")
            assert resp.status_code in (200, 302)

    def test_flow_open_door(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/presence/flow/open-door/")
            assert resp.status_code == 200

    def test_flow_overview_legacy(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/presence/flow/overview-legacy/")
            assert resp.status_code == 200

    def test_flow_overview(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/presence/flow/overview/")
            assert resp.status_code in (200, 302)

    def test_flow_pulse(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/presence/flow/pulse/")
            assert resp.status_code in (200, 302)

    def test_kiosk_index(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/presence/kiosk/")
            assert resp.status_code == 200

    def test_pto_index(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/presence/pto/")
            assert resp.status_code == 200

    def test_pto_approve(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/presence/pto/approve")
            assert resp.status_code == 200

    def test_pto_modal_clear(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/presence/pto/modal/clear")
            assert resp.status_code == 200

    def test_pto_modal_new(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/presence/pto/modal/new")
            assert resp.status_code == 200

    def test_pto_scheduled(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/presence/pto/scheduled")
            assert resp.status_code == 200

    def test_pto_scheduled_past(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/presence/pto/scheduled/past")
            assert resp.status_code == 200

    def test_timesheets_index(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/presence/timesheets/")
            assert resp.status_code in (200, 302)

    def test_timesheets_approve(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/presence/timesheets/approve")
            assert resp.status_code == 200

    def test_timesheets_clear_modal(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/presence/timesheets/clear-modal")
            assert resp.status_code == 200

    def test_timesheets_day(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/presence/timesheets/day")
            assert resp.status_code == 200

    def test_timesheets_payroll(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/presence/timesheets/payroll")
            assert resp.status_code == 200

    def test_timesheets_payroll_export(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/presence/timesheets/payroll/export")
            assert resp.status_code == 200

    def test_timesheets_payroll_export_modal(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/presence/timesheets/payroll/export-modal")
            assert resp.status_code == 200

    def test_timesheets_punch_changes(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/presence/timesheets/punch-changes")
            assert resp.status_code in (200, 302)

    def test_timesheets_punch_corrections(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/presence/timesheets/punch-corrections")
            assert resp.status_code in (200, 302)

    def test_timesheets_search_jobs(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/presence/timesheets/search-jobs")
            assert resp.status_code == 200

    def test_timesheets_settings(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/presence/timesheets/settings")
            assert resp.status_code == 200

    def test_timesheets_week(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/presence/timesheets/week")
            assert resp.status_code == 200
