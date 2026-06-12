# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - Resources Model Integration Tests
#
# Tests for Document, Note, Folder, Attachment, AttachmentLink, KB*,
# Signature*, WorkingAgreement, DriveConnection, and ResourcesSettings.
# -----------------------------------------------------------------------------


import pytest
from flask import g

from system.db.database import db


# ── Helpers ──────────────────────────────────────────────────────────────────

def _setup_g(ws):
    g.organization_id = ws["organization"].id
    g.workspace_id = ws["workspace"].id


def _make_second_member(ws):
    import uuid as _uuid
    from modules.base.core.models.user import User
    from modules.base.core.models.organization_user import OrganizationUser
    from modules.base.core.models.workspace_user import WorkspaceUser

    user2 = User.create(
        email=f"res-{_uuid.uuid4().hex[:8]}@test.com",
        password="testpass123",
        first_name="Res",
        last_name="Member",
        is_admin=False,
    )
    org_user2 = OrganizationUser.create(
        organization_id=ws["organization"].id,
        user_id=user2.id,
        role="member",
    )
    member2 = WorkspaceUser(
        user_id=user2.id,
        workspace_id=ws["workspace"].id,
        organization_id=ws["organization"].id,
        organization_user_id=org_user2.id,
        role="member",
    )
    db.session.add(member2)
    db.session.commit()
    return member2


# ═════════════════════════════════════════════════════════════════════════════
# Document
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestDocument:
    """Tests for Document model CRUD and file metadata."""

    def test_create_document(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.document import Document

        ws = seeded_workspace
        _setup_g(ws)

        doc = Document.create(
            filename="report.pdf",
            mime_type="application/pdf",
            size_bytes=102400,
        )
        assert doc.id is not None
        assert doc.uuid is not None
        assert doc.filename == "report.pdf"
        assert doc.mime_type == "application/pdf"

    def test_extension_property(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.document import Document

        ws = seeded_workspace
        _setup_g(ws)

        doc = Document.create(filename="archive.tar.gz")
        assert doc.extension == "gz"

        doc2 = Document.create(filename="README")
        assert doc2.extension == ""

    def test_size_display(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.document import Document

        ws = seeded_workspace
        _setup_g(ws)

        doc = Document.create(filename="small.txt", size_bytes=500)
        assert "500" in doc.size_display and "B" in doc.size_display

        doc2 = Document.create(filename="big.zip", size_bytes=2 * 1024 * 1024)
        assert "MB" in doc2.size_display

    def test_get_by_uuid(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.document import Document

        ws = seeded_workspace
        _setup_g(ws)

        doc = Document.create(filename="uuid-test.txt")
        found = Document.get_by_uuid(doc.uuid)
        assert found is not None
        assert found.id == doc.id

    def test_rename_document(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.document import Document

        ws = seeded_workspace
        _setup_g(ws)

        doc = Document.create(filename="old.txt")
        doc.rename("new.txt")
        assert doc.filename == "new.txt"

    def test_move_document(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.document import Document
        from modules.base.resources.models.folder import Folder

        ws = seeded_workspace
        _setup_g(ws)

        folder = Folder.create(name="Target")
        doc = Document.create(filename="move-me.txt")
        doc.move(folder.id)
        assert doc.folder_id == folder.id

    def test_delete_document(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.document import Document

        ws = seeded_workspace
        _setup_g(ws)

        doc = Document.create(filename="delete-me.txt")
        did = doc.id
        doc.delete()
        assert Document.get_by_id(did) is None


# ═════════════════════════════════════════════════════════════════════════════
# Note
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestNote:
    """Tests for Note model creation, title extraction, and visibility."""

    def test_create_note(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.note import Note

        ws = seeded_workspace
        _setup_g(ws)

        note = Note.create(
            member_id=ws["membership"].id,
            content="# My Note\nSome content",
            visibility="personal",
        )
        assert note.id is not None
        assert note.title == "My Note"
        assert note.visibility == "personal"

    def test_extract_title_from_markdown(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.note import Note

        ws = seeded_workspace
        _setup_g(ws)

        note = Note.create(member_id=ws["membership"].id, content="## Header\nBody")
        assert note.title == "Header"

    def test_extract_title_empty(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.note import Note

        ws = seeded_workspace
        _setup_g(ws)

        note = Note.create(member_id=ws["membership"].id, content="")
        assert note.title == "Untitled"

    def test_update_content(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.note import Note

        ws = seeded_workspace
        _setup_g(ws)

        note = Note.create(member_id=ws["membership"].id, content="Old")
        note.update_content("# New Title\nNew body")
        assert note.title == "New Title"
        assert "New body" in note.content

    def test_get_for_member(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.note import Note

        ws = seeded_workspace
        _setup_g(ws)

        Note.create(member_id=ws["membership"].id, content="Personal", visibility="personal")
        Note.create(member_id=ws["membership"].id, content="Team", visibility="team")

        personal = Note.get_for_member(ws["membership"].id, visibility="personal")
        assert all(n.visibility == "personal" for n in personal)

        team = Note.get_for_member(ws["membership"].id, visibility="team")
        assert all(n.visibility == "team" for n in team)


# ═════════════════════════════════════════════════════════════════════════════
# Folder
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestFolder:
    """Tests for Folder model nesting, paths, and CRUD."""

    def test_create_folder(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.folder import Folder

        ws = seeded_workspace
        _setup_g(ws)

        folder = Folder.create(name="My Folder")
        assert folder.id is not None
        assert folder.name == "My Folder"
        assert folder.parent_id is None

    def test_nested_folder(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.folder import Folder

        ws = seeded_workspace
        _setup_g(ws)

        parent = Folder.create(name="Parent")
        child = Folder.create(name="Child", parent_id=parent.id)
        assert child.parent_id == parent.id

    def test_path_property(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.folder import Folder

        ws = seeded_workspace
        _setup_g(ws)

        parent = Folder.create(name="Root")
        child = Folder.create(name="Sub", parent_id=parent.id)
        assert child.path == "/Root/Sub"

    def test_rename_folder(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.folder import Folder

        ws = seeded_workspace
        _setup_g(ws)

        folder = Folder.create(name="Old Name")
        folder.rename("New Name")
        assert folder.name == "New Name"

    def test_get_root_folders(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.folder import Folder

        ws = seeded_workspace
        _setup_g(ws)

        Folder.create(name="Root1")
        Folder.create(name="Root2")
        roots = Folder.get_root_folders()
        assert len(roots) >= 2

    def test_delete_folder(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.folder import Folder

        ws = seeded_workspace
        _setup_g(ws)

        folder = Folder.create(name="Delete Me")
        fid = folder.id
        folder.delete()
        assert Folder.get_by_id(fid) is None


# ═════════════════════════════════════════════════════════════════════════════
# Attachment
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestAttachment:
    """Tests for Attachment model creation and UUID lookup."""

    def test_create_attachment(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.attachment import Attachment

        ws = seeded_workspace
        _setup_g(ws)

        att = Attachment.create(
            filename="photo.jpg",
            mime_type="image/jpeg",
            size_bytes=50000,
        )
        assert att.id is not None
        assert att.uuid is not None
        assert att.filename == "photo.jpg"

    def test_get_by_uuid(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.attachment import Attachment

        ws = seeded_workspace
        _setup_g(ws)

        att = Attachment.create(filename="test.png")
        found = Attachment.get_by_uuid(att.uuid)
        assert found is not None

    def test_extension_and_size_display(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.attachment import Attachment

        ws = seeded_workspace
        _setup_g(ws)

        att = Attachment.create(filename="doc.pdf", size_bytes=1536)
        assert att.extension == "pdf"
        assert "KB" in att.size_display


# ═════════════════════════════════════════════════════════════════════════════
# AttachmentLink
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestAttachmentLink:
    """Tests for AttachmentLink entity binding and lookups."""

    def test_create_and_exists(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.attachment import Attachment
        from modules.base.resources.models.attachment_link import AttachmentLink

        ws = seeded_workspace
        _setup_g(ws)

        att = Attachment.create(filename="linked.pdf")
        link = AttachmentLink.create(att.id, "task", 42)
        assert link.id is not None
        assert AttachmentLink.exists(att.id, "task", 42) is True
        assert AttachmentLink.exists(att.id, "task", 99) is False

    def test_get_for_entity(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.attachment import Attachment
        from modules.base.resources.models.attachment_link import AttachmentLink

        ws = seeded_workspace
        _setup_g(ws)

        att = Attachment.create(filename="entity.pdf")
        AttachmentLink.create(att.id, "project", 10)
        links = AttachmentLink.get_for_entity("project", 10)
        assert len(links) == 1

    def test_delete_link(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.attachment import Attachment
        from modules.base.resources.models.attachment_link import AttachmentLink

        ws = seeded_workspace
        _setup_g(ws)

        att = Attachment.create(filename="delete-link.pdf")
        link = AttachmentLink.create(att.id, "task", 1)
        lid = link.id
        link.delete()
        assert AttachmentLink.get_by_id(lid) is None


# ═════════════════════════════════════════════════════════════════════════════
# KBCategory
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestKBCategory:
    """Tests for KBCategory model CRUD and slug generation."""

    def test_create_category(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.kb_category import KBCategory

        ws = seeded_workspace
        _setup_g(ws)

        cat = KBCategory.create(name="Getting Started", description="Onboarding")
        assert cat.id is not None
        assert cat.slug == "getting-started"

    def test_slug_collision_handled(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.kb_category import KBCategory

        ws = seeded_workspace
        _setup_g(ws)

        cat1 = KBCategory.create(name="FAQ")
        cat2 = KBCategory.create(name="FAQ")
        assert cat1.slug != cat2.slug

    def test_get_by_slug(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.kb_category import KBCategory

        ws = seeded_workspace
        _setup_g(ws)

        KBCategory.create(name="Policies")
        found = KBCategory.get_by_slug("policies")
        assert found is not None

    def test_delete_empty_category(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.kb_category import KBCategory

        ws = seeded_workspace
        _setup_g(ws)

        cat = KBCategory.create(name="Deletable")
        assert cat.delete() is True

    def test_update_category(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.kb_category import KBCategory

        ws = seeded_workspace
        _setup_g(ws)

        cat = KBCategory.create(name="Old")
        cat.update(name="Updated")
        assert cat.name == "Updated"
        assert cat.slug == "updated"


# ═════════════════════════════════════════════════════════════════════════════
# KBSubcategory
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestKBSubcategory:
    """Tests for KBSubcategory model CRUD and category linkage."""

    def test_create_subcategory(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.kb_category import KBCategory
        from modules.base.resources.models.kb_subcategory import KBSubcategory

        ws = seeded_workspace
        _setup_g(ws)

        cat = KBCategory.create(name="Parent Cat")
        sub = KBSubcategory.create(category_id=cat.id, name="Sub Section")
        assert sub.id is not None
        assert sub.slug == "sub-section"
        assert sub.category_id == cat.id

    def test_get_by_category(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.kb_category import KBCategory
        from modules.base.resources.models.kb_subcategory import KBSubcategory

        ws = seeded_workspace
        _setup_g(ws)

        cat = KBCategory.create(name="With Subs")
        KBSubcategory.create(category_id=cat.id, name="Sub A")
        KBSubcategory.create(category_id=cat.id, name="Sub B")
        subs = KBSubcategory.get_by_category(cat.id)
        assert len(subs) == 2

    def test_delete_empty_subcategory(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.kb_category import KBCategory
        from modules.base.resources.models.kb_subcategory import KBSubcategory

        ws = seeded_workspace
        _setup_g(ws)

        cat = KBCategory.create(name="Del Sub Cat")
        sub = KBSubcategory.create(category_id=cat.id, name="Deletable Sub")
        assert sub.delete() is True


# ═════════════════════════════════════════════════════════════════════════════
# KBArticle
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestKBArticle:
    """Tests for KBArticle model CRUD, search, and view tracking."""

    def test_create_article(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.kb_category import KBCategory
        from modules.base.resources.models.kb_article import KBArticle

        ws = seeded_workspace
        _setup_g(ws)

        cat = KBCategory.create(name="Article Cat")
        article = KBArticle.create(
            category_id=cat.id,
            title="How to Get Started",
            content="## Step 1\nDo the thing.",
        )
        assert article.id is not None
        assert article.slug == "how-to-get-started"
        assert article.excerpt is not None

    def test_generate_slug(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.kb_article import KBArticle

        assert KBArticle.generate_slug("Hello World!") == "hello-world"

    def test_generate_excerpt(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.kb_article import KBArticle

        excerpt = KBArticle.generate_excerpt("## Title\nSome **bold** text here.")
        assert "bold" in excerpt
        assert "#" not in excerpt

    def test_increment_view_count(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.kb_category import KBCategory
        from modules.base.resources.models.kb_article import KBArticle

        ws = seeded_workspace
        _setup_g(ws)

        cat = KBCategory.create(name="Views Cat")
        article = KBArticle.create(category_id=cat.id, title="Viewable", content="Content")
        assert article.view_count == 0
        article.increment_view_count()
        assert article.view_count == 1

    def test_search_articles(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.kb_category import KBCategory
        from modules.base.resources.models.kb_article import KBArticle

        ws = seeded_workspace
        _setup_g(ws)

        cat = KBCategory.create(name="Search Cat")
        KBArticle.create(category_id=cat.id, title="Unique Keyword XYZ", content="Findable")
        results = KBArticle.search("XYZ")
        assert len(results) >= 1

    def test_delete_article(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.kb_category import KBCategory
        from modules.base.resources.models.kb_article import KBArticle

        ws = seeded_workspace
        _setup_g(ws)

        cat = KBCategory.create(name="Del Art Cat")
        article = KBArticle.create(category_id=cat.id, title="Temp Article", content="Temp")
        aid = article.id
        article.delete()
        assert KBArticle.get_by_id(aid) is None

    def test_category_with_articles_cannot_delete(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.kb_category import KBCategory
        from modules.base.resources.models.kb_article import KBArticle

        ws = seeded_workspace
        _setup_g(ws)

        cat = KBCategory.create(name="Non Del Cat")
        KBArticle.create(category_id=cat.id, title="Blocking Article", content="Blocks delete")
        assert cat.delete() is False


# ═════════════════════════════════════════════════════════════════════════════
# KBFeedback
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestKBFeedback:
    """Tests for KBFeedback submission, deduplication, and stats."""

    def test_submit_feedback(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.kb_category import KBCategory
        from modules.base.resources.models.kb_article import KBArticle
        from modules.base.resources.models.kb_feedback import KBFeedback

        ws = seeded_workspace
        _setup_g(ws)

        cat = KBCategory.create(name="Feedback Cat")
        article = KBArticle.create(category_id=cat.id, title="Feedbackable", content="Content")

        fb = KBFeedback.submit(
            article_id=article.id,
            is_helpful=True,
            user_id=ws["user"].id,
        )
        assert fb is not None
        assert fb.is_helpful is True

    def test_duplicate_feedback_returns_none(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.kb_category import KBCategory
        from modules.base.resources.models.kb_article import KBArticle
        from modules.base.resources.models.kb_feedback import KBFeedback

        ws = seeded_workspace
        _setup_g(ws)

        cat = KBCategory.create(name="Dup FB Cat")
        article = KBArticle.create(category_id=cat.id, title="Dup Test", content="Content")

        KBFeedback.submit(article_id=article.id, is_helpful=True, user_id=ws["user"].id)
        result = KBFeedback.submit(article_id=article.id, is_helpful=False, user_id=ws["user"].id)
        assert result is None

    def test_get_stats(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.kb_category import KBCategory
        from modules.base.resources.models.kb_article import KBArticle
        from modules.base.resources.models.kb_feedback import KBFeedback

        ws = seeded_workspace
        _setup_g(ws)

        cat = KBCategory.create(name="Stats Cat")
        article = KBArticle.create(category_id=cat.id, title="Stats", content="Content")

        KBFeedback.submit(article_id=article.id, is_helpful=True, session_id="s1")
        KBFeedback.submit(article_id=article.id, is_helpful=False, session_id="s2")

        stats = KBFeedback.get_stats(article.id)
        assert stats["helpful"] == 1
        assert stats["not_helpful"] == 1
        assert stats["total"] == 2


# ═════════════════════════════════════════════════════════════════════════════
# SignatureRequest
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestSignatureRequest:
    """Tests for SignatureRequest lifecycle and status transitions."""

    def test_create_signature_request(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.attachment import Attachment
        from modules.base.resources.models.signature_request import SignatureRequest

        ws = seeded_workspace
        _setup_g(ws)

        att = Attachment.create(filename="contract.pdf")
        req = SignatureRequest.create(
            title="Employment Contract",
            original_attachment_id=att.id,
            document_hash="abc123def456",
            created_by_id=ws["membership"].id,
        )
        assert req.id is not None
        assert req.status == "draft"
        assert req.uuid is not None
        assert req.expires_at is not None

    def test_mark_pending_and_completed(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.attachment import Attachment
        from modules.base.resources.models.signature_request import SignatureRequest

        ws = seeded_workspace
        _setup_g(ws)

        att = Attachment.create(filename="doc.pdf")
        signed_att = Attachment.create(filename="signed-doc.pdf")
        req = SignatureRequest.create(
            title="NDA",
            original_attachment_id=att.id,
            document_hash="hash123",
        )
        req.mark_pending()
        assert req.status == "pending"

        req.mark_completed(signed_att.id)
        assert req.status == "completed"
        assert req.completed_at is not None

    def test_mark_cancelled(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.attachment import Attachment
        from modules.base.resources.models.signature_request import SignatureRequest

        ws = seeded_workspace
        _setup_g(ws)

        att = Attachment.create(filename="cancel.pdf")
        req = SignatureRequest.create(
            title="Cancel Me",
            original_attachment_id=att.id,
            document_hash="hash",
        )
        req.mark_cancelled()
        assert req.status == "cancelled"

    def test_get_by_uuid(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.attachment import Attachment
        from modules.base.resources.models.signature_request import SignatureRequest

        ws = seeded_workspace
        _setup_g(ws)

        att = Attachment.create(filename="uuid-sig.pdf")
        req = SignatureRequest.create(
            title="UUID Test",
            original_attachment_id=att.id,
            document_hash="hash",
        )
        found = SignatureRequest.get_by_uuid(req.uuid)
        assert found is not None


# ═════════════════════════════════════════════════════════════════════════════
# SignatureRecipient
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestSignatureRecipient:
    """Tests for SignatureRecipient signing workflow."""

    def test_create_recipient(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.attachment import Attachment
        from modules.base.resources.models.signature_request import SignatureRequest
        from modules.base.resources.models.signature_recipient import SignatureRecipient

        ws = seeded_workspace
        _setup_g(ws)

        att = Attachment.create(filename="recip.pdf")
        req = SignatureRequest.create(
            title="Recip Test",
            original_attachment_id=att.id,
            document_hash="hash",
        )
        recip = SignatureRecipient.create(
            request_id=req.id,
            email="signer@example.com",
            name="Test Signer",
        )
        assert recip.id is not None
        assert recip.token is not None
        assert recip.status == "pending"
        assert recip.is_signer is True
        assert recip.can_sign is True

    def test_mark_viewed_and_signed(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.attachment import Attachment
        from modules.base.resources.models.signature_request import SignatureRequest
        from modules.base.resources.models.signature_recipient import SignatureRecipient

        ws = seeded_workspace
        _setup_g(ws)

        att = Attachment.create(filename="sign.pdf")
        req = SignatureRequest.create(
            title="Sign Flow",
            original_attachment_id=att.id,
            document_hash="hash",
        )
        recip = SignatureRecipient.create(
            request_id=req.id,
            email="signer@example.com",
            name="Signer",
        )
        recip.mark_viewed()
        assert recip.status == "viewed"

        recip.mark_signed(
            signed_name="Signer Name",
            ip_address="127.0.0.1",
            user_agent="TestAgent",
        )
        assert recip.status == "signed"
        assert recip.has_signed is True
        assert recip.can_sign is False

    def test_mark_declined(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.attachment import Attachment
        from modules.base.resources.models.signature_request import SignatureRequest
        from modules.base.resources.models.signature_recipient import SignatureRecipient

        ws = seeded_workspace
        _setup_g(ws)

        att = Attachment.create(filename="decline.pdf")
        req = SignatureRequest.create(
            title="Decline Test",
            original_attachment_id=att.id,
            document_hash="hash",
        )
        recip = SignatureRecipient.create(
            request_id=req.id,
            email="decliner@example.com",
            name="Decliner",
        )
        recip.mark_declined()
        assert recip.status == "declined"


# ═════════════════════════════════════════════════════════════════════════════
# SignatureAuditLog
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestSignatureAuditLog:
    """Tests for SignatureAuditLog event recording."""

    def test_log_event(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.attachment import Attachment
        from modules.base.resources.models.signature_request import SignatureRequest
        from modules.base.resources.models.signature_audit_log import SignatureAuditLog

        ws = seeded_workspace
        _setup_g(ws)

        att = Attachment.create(filename="audit.pdf")
        req = SignatureRequest.create(
            title="Audit Test",
            original_attachment_id=att.id,
            document_hash="hash",
        )
        entry = SignatureAuditLog.log(
            request_id=req.id,
            event_type="created",
            actor_email="admin@example.com",
            details={"note": "test"},
        )
        assert entry.id is not None
        assert entry.event_type == "created"
        assert entry.details_dict["note"] == "test"
        assert entry.event_description == "Request created"

    def test_get_for_request(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.attachment import Attachment
        from modules.base.resources.models.signature_request import SignatureRequest
        from modules.base.resources.models.signature_audit_log import SignatureAuditLog

        ws = seeded_workspace
        _setup_g(ws)

        att = Attachment.create(filename="audit2.pdf")
        req = SignatureRequest.create(
            title="Audit List",
            original_attachment_id=att.id,
            document_hash="hash",
        )
        SignatureAuditLog.log(request_id=req.id, event_type="created")
        SignatureAuditLog.log(request_id=req.id, event_type="sent")

        logs = SignatureAuditLog.get_for_request(req.id)
        assert len(logs) == 2


# ═════════════════════════════════════════════════════════════════════════════
# WorkingAgreement
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestWorkingAgreement:
    """Tests for WorkingAgreement versioning and acknowledgment."""

    def test_get_or_create(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.working_agreement import WorkingAgreement

        ws = seeded_workspace
        _setup_g(ws)

        agreement = WorkingAgreement.get_or_create()
        assert agreement.id is not None
        assert agreement.version == 0

        agreement2 = WorkingAgreement.get_or_create()
        assert agreement2.id == agreement.id

    def test_save_agreement(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.working_agreement import WorkingAgreement

        ws = seeded_workspace
        _setup_g(ws)

        agreement = WorkingAgreement.save("# Team Rules\n1. Be kind", ws["membership"].id)
        assert agreement.content == "# Team Rules\n1. Be kind"
        assert agreement.version == 1

        agreement2 = WorkingAgreement.save("# Updated Rules", ws["membership"].id)
        assert agreement2.version == 2

    def test_acknowledge(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.working_agreement import (
            WorkingAgreement, WorkingAgreementAck,
        )

        ws = seeded_workspace
        _setup_g(ws)

        agreement = WorkingAgreement.save("Rules v1", ws["membership"].id)
        ack = WorkingAgreementAck.acknowledge(agreement.id, ws["membership"].id, agreement.version)
        assert ack.id is not None
        assert WorkingAgreementAck.is_acknowledged(agreement.id, ws["membership"].id, agreement.version) is True


# ═════════════════════════════════════════════════════════════════════════════
# DriveConnection
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestDriveConnection:
    """Tests for DriveConnection provider management."""

    def test_create_drive_connection(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.drive_connection import DriveConnection

        ws = seeded_workspace
        _setup_g(ws)

        conn = DriveConnection.create(
            provider="google",
            connected_by_id=ws["user"].id,
            access_token="test-token",
            refresh_token="test-refresh",
        )
        assert conn.id is not None
        assert conn.provider == "google"

    def test_get_by_provider(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.drive_connection import DriveConnection

        ws = seeded_workspace
        _setup_g(ws)

        DriveConnection.create(
            provider="google",
            connected_by_id=ws["user"].id,
            access_token="tok",
        )
        found = DriveConnection.get_by_provider("google")
        assert found is not None

    def test_selected_folders(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.drive_connection import DriveConnection

        ws = seeded_workspace
        _setup_g(ws)

        conn = DriveConnection.create(
            provider="google",
            connected_by_id=ws["user"].id,
            access_token="tok",
        )
        assert conn.get_selected_folders() == []

        conn.set_selected_folders([{"id": "abc", "name": "Docs"}])
        folders = conn.get_selected_folders()
        assert len(folders) == 1
        assert folders[0]["name"] == "Docs"

    def test_disconnect(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.drive_connection import DriveConnection

        ws = seeded_workspace
        _setup_g(ws)

        conn = DriveConnection.create(
            provider="google",
            connected_by_id=ws["user"].id,
            access_token="tok",
        )
        conn.disconnect()
        assert DriveConnection.get_by_provider("google") is None


# ═════════════════════════════════════════════════════════════════════════════
# ResourcesSettings
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestResourcesSettings:
    """Tests for ResourcesSettings singleton and e-sign configuration."""

    def test_get_creates_singleton(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.settings import ResourcesSettings

        ws = seeded_workspace
        _setup_g(ws)

        settings = ResourcesSettings.get()
        assert settings.id is not None
        assert settings.esign_enabled is True

        settings2 = ResourcesSettings.get()
        assert settings2.id == settings.id

    def test_update_settings(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.settings import ResourcesSettings

        ws = seeded_workspace
        _setup_g(ws)

        settings = ResourcesSettings.update_settings(
            esign_enabled=False,
            esign_default_expiry_days=14,
        )
        assert settings.esign_enabled is False
        assert settings.esign_default_expiry_days == 14

    def test_is_esign_enabled(self, app, db_session, seeded_workspace):
        from modules.base.resources.models.settings import ResourcesSettings

        ws = seeded_workspace
        _setup_g(ws)

        assert ResourcesSettings.is_esign_enabled() is True
        ResourcesSettings.update_settings(esign_enabled=False)
        assert ResourcesSettings.is_esign_enabled() is False
