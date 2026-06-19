# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
import pytest


@pytest.fixture(autouse=True)
def _enable_msa(monkeypatch):
    """Enable MSA for every test in this module.

    The routes read MSA_USER / MSA_PASS at request time, so setting them here
    makes these tests independent of the ambient environment (e.g. a developer's
    local .env vs. CI, which has neither). monkeypatch restores them afterward.
    """
    monkeypatch.setenv("MSA_USER", "msa-admin")
    monkeypatch.setenv("MSA_PASS", "msa-secret-pass")


@pytest.mark.integration
class TestMsaRoutes:
    """Smoke tests for MSA routes."""

    def test_msa_index(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/msa/")
            assert resp.status_code in (200, 302)

    def test_msa_login(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/msa/login")
            assert resp.status_code == 200

    def test_msa_logout(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/msa/logout")
            assert resp.status_code in (200, 302)

    def test_msa_organizations(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/msa/organizations")
            assert resp.status_code in (200, 302)

    def test_msa_workspaces(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/msa/workspaces")
            assert resp.status_code in (200, 302)

    def test_msa_email_config(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/msa/email")
            assert resp.status_code in (200, 302)

    def test_msa_email_provider_form(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/msa/email/provider/gmail")
            assert resp.status_code in (200, 302)

    def test_msa_email_provider_invalid(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/msa/email/provider/bogus")
            assert resp.status_code in (400, 302)


@pytest.mark.integration
class TestMsaEmailRoutes:
    """Tests for MSA email configuration routes with authentication."""

    def _msa_client(self, app):
        """Return a test client with MSA session authenticated."""
        client = app.test_client()
        with client.session_transaction() as sess:
            sess["msa_authenticated"] = True
        return client

    def test_email_page_loads_authenticated(self, app_with_sample_data):
        with app_with_sample_data.app_context():
            client = self._msa_client(app_with_sample_data)
            resp = client.get("/msa/email")
            assert resp.status_code == 200
            assert b"Configuration" in resp.data

    def test_email_page_redirects_unauthenticated(self, app_with_sample_data):
        with app_with_sample_data.app_context():
            client = app_with_sample_data.test_client()
            resp = client.get("/msa/email")
            assert resp.status_code in (302, 404)

    def test_email_provider_form_returns_html(self, app_with_sample_data):
        with app_with_sample_data.app_context():
            client = self._msa_client(app_with_sample_data)
            for provider in ["gmail", "microsoft_365", "sendgrid", "custom"]:
                resp = client.get(f"/msa/email/provider/{provider}")
                assert resp.status_code == 200
                assert b"csrf_token" in resp.data

    def test_email_provider_invalid_returns_400(self, app_with_sample_data):
        with app_with_sample_data.app_context():
            client = self._msa_client(app_with_sample_data)
            resp = client.get("/msa/email/provider/notreal")
            assert resp.status_code == 400

    def test_email_save_persists_settings(self, app_with_sample_data):
        with app_with_sample_data.app_context():
            from modules.base.msa.models.instance_settings import InstanceSettings

            client = self._msa_client(app_with_sample_data)
            resp = client.post("/msa/email", data={
                "provider": "gmail",
                "username": "test@gmail.com",
                "password": "app-password-123",
                "from_email": "test@gmail.com",
            }, follow_redirects=True)
            assert resp.status_code == 200

            settings = InstanceSettings.get_instance()
            assert settings.email_provider == "gmail"
            assert settings.email_username == "test@gmail.com"
            assert settings.email_from == "test@gmail.com"
            assert settings.email_host == "smtp.gmail.com"

    def test_email_save_invalid_provider_rejected(self, app_with_sample_data):
        with app_with_sample_data.app_context():
            client = self._msa_client(app_with_sample_data)
            resp = client.post("/msa/email", data={
                "provider": "invalid",
            }, follow_redirects=True)
            assert resp.status_code == 200

    def test_email_save_custom_smtp_fields(self, app_with_sample_data):
        with app_with_sample_data.app_context():
            from modules.base.msa.models.instance_settings import InstanceSettings

            client = self._msa_client(app_with_sample_data)
            resp = client.post("/msa/email", data={
                "provider": "custom",
                "host": "mail.example.com",
                "port": "465",
                "use_tls": "1",
                "username": "user",
                "password": "pass",
                "from_email": "noreply@example.com",
            }, follow_redirects=True)
            assert resp.status_code == 200

            settings = InstanceSettings.get_instance()
            assert settings.email_host == "mail.example.com"
            assert settings.email_port == 465

    def test_email_test_connection_returns_partial(self, app_with_sample_data):
        with app_with_sample_data.app_context():
            client = self._msa_client(app_with_sample_data)
            resp = client.post("/msa/email/test")
            assert resp.status_code == 200

    def test_email_send_test_validates_email(self, app_with_sample_data):
        with app_with_sample_data.app_context():
            client = self._msa_client(app_with_sample_data)
            resp = client.post("/msa/email/send-test", data={"test_email": ""})
            assert resp.status_code == 200
            assert b"valid email" in resp.data.lower()

    def test_email_send_test_invalid_address(self, app_with_sample_data):
        with app_with_sample_data.app_context():
            client = self._msa_client(app_with_sample_data)
            resp = client.post("/msa/email/send-test", data={"test_email": "notanemail"})
            assert resp.status_code == 200
            assert b"valid email" in resp.data.lower()


@pytest.mark.integration
class TestMsaDisabled:
    """MSA routes are disabled (404) when MSA_USER / MSA_PASS are not set."""

    def test_index_returns_404_when_disabled(self, app_with_sample_data, monkeypatch):
        # Override the module-level enable fixture: simulate CI / no credentials.
        monkeypatch.delenv("MSA_USER", raising=False)
        monkeypatch.delenv("MSA_PASS", raising=False)
        with app_with_sample_data.app_context():
            resp = app_with_sample_data.test_client().get("/msa/")
            assert resp.status_code == 404

    def test_login_returns_404_when_disabled(self, app_with_sample_data, monkeypatch):
        monkeypatch.delenv("MSA_USER", raising=False)
        monkeypatch.delenv("MSA_PASS", raising=False)
        with app_with_sample_data.app_context():
            resp = app_with_sample_data.test_client().get("/msa/login")
            assert resp.status_code == 404
