# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
import pytest


@pytest.mark.integration
class TestResourcesRoutes:
    """Smoke tests for resources routes."""

    def test_docs_index(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/resources/docs/")
            assert resp.status_code == 200

    def test_docs_browser(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/resources/docs/browser")
            assert resp.status_code == 200

    def test_docs_organization(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/resources/docs/organization")
            assert resp.status_code == 200

    def test_docs_organization_slash(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/resources/docs/organization/")
            assert resp.status_code == 200

    def test_drive_browse(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/resources/drive/browse")
            assert resp.status_code == 200

    def test_drive_callback_google(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/resources/drive/callback/google")
            assert resp.status_code in (200, 302)

    def test_drive_connect_google(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/resources/drive/connect/google")
            assert resp.status_code in (200, 302)

    def test_drive_folders(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/resources/drive/folders")
            assert resp.status_code == 200

    def test_esign_index(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/resources/esign/")
            assert resp.status_code == 200

    def test_esign_settings(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/resources/esign/settings")
            assert resp.status_code == 200

    def test_forms_index(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/resources/forms/")
            assert resp.status_code == 200

    def test_knowledge_index(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/resources/knowledge/")
            assert resp.status_code == 200

    def test_knowledge_articles(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/resources/knowledge/articles")
            assert resp.status_code == 200

    def test_knowledge_articles_new(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/resources/knowledge/articles/new")
            assert resp.status_code == 200

    def test_knowledge_browse(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/resources/knowledge/browse/")
            assert resp.status_code == 200

    def test_knowledge_browse_search(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/resources/knowledge/browse/search")
            assert resp.status_code in (200, 302)

    def test_knowledge_categories(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/resources/knowledge/categories")
            assert resp.status_code == 200

    def test_knowledge_categories_new(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/resources/knowledge/categories/new")
            assert resp.status_code == 200

    def test_knowledge_feedback(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/resources/knowledge/feedback")
            assert resp.status_code == 200

    def test_knowledge_subcategories_new(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/resources/knowledge/subcategories/new")
            assert resp.status_code == 200

    def test_notes_index(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/resources/notes/")
            assert resp.status_code == 200

    def test_notes_organization(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/resources/notes/organization")
            assert resp.status_code == 200

    def test_notes_organization_slash(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/resources/notes/organization/")
            assert resp.status_code == 200

    def test_settings(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/resources/settings/")
            assert resp.status_code == 200

    def test_working_agreement(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/resources/working-agreement/")
            assert resp.status_code == 200

    def test_working_agreement_edit(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/resources/working-agreement/edit")
            assert resp.status_code == 200
