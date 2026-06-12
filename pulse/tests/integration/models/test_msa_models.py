# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

import pytest
from unittest.mock import patch


@pytest.mark.integration
class TestInstanceSettings:
    """Tests for InstanceSettings singleton model."""

    def test_get_instance_creates_row(self, app, db_session):
        from modules.base.msa.models.instance_settings import InstanceSettings

        with app.app_context():
            instance = InstanceSettings.get_instance()
            assert instance is not None
            assert instance.id is not None
            assert instance.email_verified is False

    def test_get_instance_returns_same_row(self, app, db_session):
        from modules.base.msa.models.instance_settings import InstanceSettings

        with app.app_context():
            a = InstanceSettings.get_instance()
            b = InstanceSettings.get_instance()
            assert a.id == b.id

    def test_update_sets_fields(self, app, db_session):
        from modules.base.msa.models.instance_settings import InstanceSettings

        with app.app_context():
            instance = InstanceSettings.get_instance()
            instance.update(
                email_provider="gmail",
                email_host="smtp.gmail.com",
                email_port=587,
                email_username="test@gmail.com",
                email_from="test@gmail.com",
            )
            assert instance.email_provider == "gmail"
            assert instance.email_host == "smtp.gmail.com"
            assert instance.email_port == 587

    def test_update_resets_email_verified(self, app, db_session):
        from modules.base.msa.models.instance_settings import InstanceSettings

        with app.app_context():
            instance = InstanceSettings.get_instance()
            instance.update(email_verified=True)
            assert instance.email_verified is True

            instance.update(email_host="new.smtp.com")
            assert instance.email_verified is False

    def test_update_preserves_verified_when_no_email_change(self, app, db_session):
        from modules.base.msa.models.instance_settings import InstanceSettings

        with app.app_context():
            instance = InstanceSettings.get_instance()
            instance.update(email_verified=True)
            assert instance.email_verified is True

            instance.update(email_verified=True)
            assert instance.email_verified is True

    def test_update_ignores_unknown_fields(self, app, db_session):
        from modules.base.msa.models.instance_settings import InstanceSettings

        with app.app_context():
            instance = InstanceSettings.get_instance()
            instance.update(nonexistent_field="value")
            assert not hasattr(instance, "nonexistent_field") or getattr(instance, "nonexistent_field", None) is None

    def test_update_same_value_no_verified_reset(self, app, db_session):
        from modules.base.msa.models.instance_settings import InstanceSettings

        with app.app_context():
            instance = InstanceSettings.get_instance()
            instance.update(email_host="smtp.test.com", email_verified=True)
            assert instance.email_verified is True

            instance.update(email_host="smtp.test.com")
            assert instance.email_verified is True

    def test_is_email_configured(self, app, db_session):
        from modules.base.msa.models.instance_settings import InstanceSettings

        with app.app_context():
            instance = InstanceSettings.get_instance()
            assert instance.is_email_configured() is False

            instance.update(email_host="smtp.test.com", email_password="secret")
            assert instance.is_email_configured() is True

    def test_is_email_configured_partial(self, app, db_session):
        from modules.base.msa.models.instance_settings import InstanceSettings

        with app.app_context():
            instance = InstanceSettings.get_instance()
            instance.update(email_host="smtp.test.com")
            assert instance.is_email_configured() is False

            instance.update(email_password="secret", email_host="")
            assert instance.is_email_configured() is False

    def test_is_email_configured_via_env(self, app, db_session):
        from modules.base.msa.models.instance_settings import InstanceSettings

        with app.app_context():
            instance = InstanceSettings.get_instance()
            with patch.dict("os.environ", {"SMTP_HOST": "env.smtp.com", "SMTP_PASSWORD": "envpass"}):
                assert instance.is_email_configured() is True

    def test_get_env_overrides(self, app, db_session):
        from modules.base.msa.models.instance_settings import InstanceSettings

        with app.app_context():
            overrides = InstanceSettings.get_env_overrides()
            assert isinstance(overrides, dict)
            assert all(v is False for v in overrides.values())

    def test_get_env_overrides_detects_env(self, app, db_session):
        from modules.base.msa.models.instance_settings import InstanceSettings

        with app.app_context():
            with patch.dict("os.environ", {"SMTP_HOST": "env.smtp.com"}):
                overrides = InstanceSettings.get_env_overrides()
                assert overrides["email_host"] is True
                assert overrides["email_password"] is False

    def test_any_env_overrides_false(self, app, db_session):
        from modules.base.msa.models.instance_settings import InstanceSettings

        with app.app_context():
            assert InstanceSettings.any_env_overrides() is False

    def test_any_env_overrides_true(self, app, db_session):
        from modules.base.msa.models.instance_settings import InstanceSettings

        with app.app_context():
            with patch.dict("os.environ", {"SMTP_PASSWORD": "s3cret"}):
                assert InstanceSettings.any_env_overrides() is True

    def test_update_returns_self(self, app, db_session):
        from modules.base.msa.models.instance_settings import InstanceSettings

        with app.app_context():
            instance = InstanceSettings.get_instance()
            result = instance.update(email_provider="custom")
            assert result is instance

    def test_password_stored_encrypted(self, app, db_session):
        from modules.base.msa.models.instance_settings import InstanceSettings

        with app.app_context():
            instance = InstanceSettings.get_instance()
            instance.update(email_password="my-secret-password")
            assert instance.email_password != "my-secret-password"
            assert instance.email_password  # non-empty encrypted value
            assert instance.get_email_password() == "my-secret-password"

    def test_get_email_password_empty(self, app, db_session):
        from modules.base.msa.models.instance_settings import InstanceSettings

        with app.app_context():
            instance = InstanceSettings.get_instance()
            assert instance.get_email_password() == ""
