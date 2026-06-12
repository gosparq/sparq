# -----------------------------------------------------------------------------
# sparQ - Knowledge Base Article Model
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

import re
from datetime import datetime
from unicodedata import normalize

import markdown  # type: ignore[import-untyped]
from flask_login import current_user

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.mixins import AuditMixin
from system.db.workspace import WorkspaceMixin
from system.db.raise_on_lazy import LAZY


@ModelRegistry.register
class KBArticle(db.Model, WorkspaceMixin, AuditMixin):
    """Knowledge base article with Markdown content."""

    __tablename__ = "kb_article"

    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(
        db.Integer,
        db.ForeignKey("kb_category.id"),
        nullable=False,
    )
    subcategory_id = db.Column(
        db.Integer,
        db.ForeignKey("kb_subcategory.id", ondelete="SET NULL"),
        nullable=True,
    )

    title = db.Column(db.String(500), nullable=False)
    slug = db.Column(db.String(500), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    excerpt = db.Column(db.String(500))

    is_public = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, default=0)
    view_count = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    feedback = db.relationship(
        "KBFeedback",
        backref=db.backref("article", lazy=LAZY),
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    # Unique constraint: slug must be unique within category/subcategory
    __table_args__ = (
        db.UniqueConstraint(
            "category_id", "subcategory_id", "slug", name="uq_kb_article_category_subcategory_slug"
        ),
    )

    @staticmethod
    def generate_slug(text: str) -> str:
        """Generate URL-safe slug from text."""
        slug = normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
        slug = re.sub(r"[^\w\s-]", "", slug)
        slug = re.sub(r"[-\s]+", "-", slug).strip("-")
        return slug

    @staticmethod
    def generate_excerpt(content: str, max_length: int = 200) -> str:
        """Generate excerpt from Markdown content."""
        # Strip markdown formatting for excerpt
        text = re.sub(r"[#*_`\[\]()]", "", content)
        text = re.sub(r"\n+", " ", text).strip()
        if len(text) > max_length:
            text = text[:max_length].rsplit(" ", 1)[0] + "..."
        return text

    @classmethod
    def get_by_id(cls, article_id: int) -> "KBArticle | None":
        """Get article by ID."""
        return cls.scoped().filter_by(id=article_id).first()

    @classmethod
    def get_by_slug(
        cls,
        category_slug: str,
        article_slug: str,
        subcategory_slug: str | None = None,
    ) -> "KBArticle | None":
        """Get article by category/subcategory/article slugs."""
        from .kb_category import KBCategory
        from .kb_subcategory import KBSubcategory

        category = KBCategory.scoped().filter_by(slug=category_slug, is_active=True).first()
        if not category:
            return None

        if subcategory_slug:
            subcategory = KBSubcategory.scoped().filter_by(
                category_id=category.id, slug=subcategory_slug, is_active=True
            ).first()
            if not subcategory:
                return None
            return cls.scoped().filter_by(
                category_id=category.id,
                subcategory_id=subcategory.id,
                slug=article_slug,
                is_active=True,
            ).first()
        else:
            return cls.scoped().filter_by(
                category_id=category.id,
                subcategory_id=None,
                slug=article_slug,
                is_active=True,
            ).first()

    @classmethod
    def get_all(cls, active_only: bool = True) -> list["KBArticle"]:
        """Get all articles."""
        query = cls.query
        if active_only:
            query = query.filter_by(is_active=True)
        return query.order_by(cls.created_at.desc()).all()

    @classmethod
    def get_by_category(
        cls,
        category_id: int,
        include_private: bool = True,
        active_only: bool = True,
    ) -> list["KBArticle"]:
        """Get articles by category (direct, not in subcategory)."""
        query = cls.scoped().filter_by(category_id=category_id, subcategory_id=None)
        if active_only:
            query = query.filter_by(is_active=True)
        if not include_private:
            query = query.filter_by(is_public=True)
        return query.order_by(cls.sort_order, cls.title).all()

    @classmethod
    def get_by_subcategory(
        cls,
        subcategory_id: int,
        include_private: bool = True,
        active_only: bool = True,
    ) -> list["KBArticle"]:
        """Get articles by subcategory."""
        query = cls.scoped().filter_by(subcategory_id=subcategory_id)
        if active_only:
            query = query.filter_by(is_active=True)
        if not include_private:
            query = query.filter_by(is_public=True)
        return query.order_by(cls.sort_order, cls.title).all()

    @classmethod
    def search(
        cls,
        query_text: str,
        include_private: bool = True,
        limit: int = 50,
    ) -> list["KBArticle"]:
        """Search articles by title and content."""
        search_term = f"%{query_text}%"
        query = cls.scoped().filter(
            cls.is_active == True,
            db.or_(
                cls.title.ilike(search_term),
                cls.content.ilike(search_term),
                cls.excerpt.ilike(search_term),
            ),
        )
        if not include_private:
            query = query.filter_by(is_public=True)
        return query.order_by(cls.title).limit(limit).all()

    @classmethod
    def get_recent(
        cls,
        limit: int = 10,
        include_private: bool = True,
    ) -> list["KBArticle"]:
        """Get recently updated articles."""
        query = cls.scoped().filter_by(is_active=True)
        if not include_private:
            query = query.filter_by(is_public=True)
        return query.order_by(cls.updated_at.desc()).limit(limit).all()

    @classmethod
    def create(
        cls,
        category_id: int,
        title: str,
        content: str,
        subcategory_id: int | None = None,
        excerpt: str | None = None,
        is_public: bool = False,
        sort_order: int = 0,
    ) -> "KBArticle":
        """Create a new article."""
        slug = cls.generate_slug(title)

        # Handle slug collisions within category/subcategory
        base_slug = slug
        counter = 1
        while cls.scoped().filter_by(
            category_id=category_id, subcategory_id=subcategory_id, slug=slug
        ).first():
            slug = f"{base_slug}-{counter}"
            counter += 1

        article = cls(
            category_id=category_id,
            subcategory_id=subcategory_id,
            title=title,
            slug=slug,
            content=content,
            excerpt=excerpt or cls.generate_excerpt(content),
            is_public=is_public,
            sort_order=sort_order,
        )

        if current_user and hasattr(current_user, "id") and current_user.is_authenticated:
            article.created_by_id = current_user.id

        db.session.add(article)
        db.session.commit()
        return article

    def update(
        self,
        title: str | None = None,
        content: str | None = None,
        category_id: int | None = None,
        subcategory_id: int | None = None,
        excerpt: str | None = None,
        is_public: bool | None = None,
        is_active: bool | None = None,
        sort_order: int | None = None,
    ) -> "KBArticle":
        """Update article."""
        if title is not None and title != self.title:
            self.title = title
            self.slug = self.generate_slug(title)
            # Handle slug collisions
            base_slug = self.slug
            counter = 1
            target_cat = category_id if category_id is not None else self.category_id
            target_sub = subcategory_id if subcategory_id is not None else self.subcategory_id
            while KBArticle.scoped().filter(
                KBArticle.category_id == target_cat,
                KBArticle.subcategory_id == target_sub,
                KBArticle.slug == self.slug,
                KBArticle.id != self.id,
            ).first():
                self.slug = f"{base_slug}-{counter}"
                counter += 1

        if content is not None:
            self.content = content
            if excerpt is None:
                self.excerpt = self.generate_excerpt(content)

        if category_id is not None:
            self.category_id = category_id
        if subcategory_id is not None:
            self.subcategory_id = subcategory_id if subcategory_id != 0 else None
        if excerpt is not None:
            self.excerpt = excerpt
        if is_public is not None:
            self.is_public = is_public
        if is_active is not None:
            self.is_active = is_active
        if sort_order is not None:
            self.sort_order = sort_order

        if current_user and hasattr(current_user, "id") and current_user.is_authenticated:
            self.updated_by_id = current_user.id

        db.session.commit()
        return self

    def delete(self) -> None:
        """Delete article and all feedback."""
        db.session.delete(self)
        db.session.commit()

    def increment_view_count(self) -> None:
        """Increment view count (without updating updated_at)."""
        self.view_count = (self.view_count or 0) + 1
        db.session.execute(
            db.update(KBArticle)
            .where(KBArticle.id == self.id)
            .values(view_count=self.view_count)
        )
        db.session.commit()

    def render_content(self) -> str:
        """Convert Markdown content to HTML."""
        md = markdown.Markdown(
            extensions=["fenced_code", "tables", "toc", "nl2br"],
            extension_configs={
                "toc": {"title": "Table of Contents"},
            },
        )
        return md.convert(self.content)

    @property
    def helpful_count(self) -> int:
        """Count of helpful feedback."""
        return self.feedback.filter_by(is_helpful=True).count()

    @property
    def not_helpful_count(self) -> int:
        """Count of not helpful feedback."""
        return self.feedback.filter_by(is_helpful=False).count()

    @property
    def breadcrumbs(self) -> list:
        """Return breadcrumb trail [category, subcategory?, article]."""
        crumbs = [self.category]
        if self.subcategory:
            crumbs.append(self.subcategory)
        crumbs.append(self)
        return crumbs

    @property
    def public_url(self) -> str:
        """Generate public URL path for this article."""
        if self.subcategory:
            return f"/kb/{self.category.slug}/{self.subcategory.slug}/{self.slug}"
        return f"/kb/{self.category.slug}/{self.slug}"
