# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - Static Asset Caching Integration Tests
#
# Tests long-lived static caching + cache-busting.
# (system/startup/config.py → SEND_FILE_MAX_AGE_DEFAULT,
#  system/startup/templates.py → register_static_cache_busting).
# -----------------------------------------------------------------------------

import pytest


@pytest.mark.integration
class TestStaticAssetCaching:
    """Verify static assets are cached long-term and cache-busted per build.

    The test suite runs with FLASK_DEBUG=False (see tests/conftest.py), so the
    app is in production mode where SEND_FILE_MAX_AGE_DEFAULT is one year.
    """

    def test_static_asset_has_long_lived_cache(self, client, db_session):
        """A static file is served with a 1-year public cache in production."""
        resp = client.get("/assets/css/base.css")
        assert resp.status_code == 200
        cache_control = resp.headers.get("Cache-Control", "")
        assert "public" in cache_control
        assert "max-age=31536000" in cache_control

    def test_rendered_static_urls_are_cache_busted(self, client, db_session):
        """Rendered pages append a ?v= cache-bust param to static URLs."""
        resp = client.get("/login")
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        assert "/assets/vendor/" in body
        assert "?v=" in body

    def test_cache_bust_token_includes_build_hash(self, client, db_session):
        """The bust token is <version>-<git hash>, not the bare version.

        Regression guard: keying only on get_version() would fail to bust the
        cache on a production/public-repo build that changes assets without a
        manual VERSION bump. The git hash changes every build, so it must be
        part of the token.
        """
        from system.version import get_build_info, get_version

        git_hash, _ = get_build_info()
        expected = f"{get_version()}-{git_hash}"

        resp = client.get("/login")
        body = resp.get_data(as_text=True)
        assert f"?v={expected}" in body
        # The token must carry the build hash, not just the semantic version.
        assert git_hash in expected
