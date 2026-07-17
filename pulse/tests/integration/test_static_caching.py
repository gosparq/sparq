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

    def test_cache_bust_token_is_per_file_content_hash(self, app, client, db_session):
        """The bust token is a per-file hash of the file's contents.

        Regression guard: the token must be derived from each file's bytes, not
        a single app-wide version/build token. A global token can silently
        degrade to a constant in a container without git/BUILD, failing to bust
        on deploy; and it busts every asset at once instead of only changed
        ones. This verifies (a) the token equals the file's content hash and
        (b) two different files carry different tokens.
        """
        import hashlib
        import os
        import re

        static_dir = app.static_folder

        def content_hash(rel_path: str) -> str:
            with open(os.path.join(static_dir, rel_path), "rb") as handle:
                return hashlib.md5(handle.read(), usedforsecurity=False).hexdigest()[:10]

        resp = client.get("/login")
        body = resp.get_data(as_text=True)

        # (a) the token for a vendored file equals the hash of its bytes
        expected = content_hash("vendor/css/bootstrap.min.css")
        assert f"vendor/css/bootstrap.min.css?v={expected}" in body

        # (b) per-file, not global: distinct files carry distinct tokens
        tokens = set(re.findall(r'/assets/[^"\'?]+\?v=([^"\'&]+)', body))
        assert len(tokens) >= 2, f"expected per-file hashes, got {tokens}"
