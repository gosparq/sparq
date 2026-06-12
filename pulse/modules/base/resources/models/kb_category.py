# -----------------------------------------------------------------------------
# sparQ - Knowledge Base Category Model
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

import re
from datetime import datetime
from unicodedata import normalize

from flask_login import current_user

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.mixins import AuditMixin
from system.db.workspace import WorkspaceMixin
from system.db.raise_on_lazy import LAZY


@ModelRegistry.register
class KBCategory(db.Model, WorkspaceMixin, AuditMixin):
    """Top-level knowledge base category."""

    __tablename__ = "kb_category"
    __table_args__ = (
        db.UniqueConstraint("slug", "workspace_id", name="uq_kb_category_slug_workspace"),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255), nullable=False, index=True)
    description = db.Column(db.Text)
    icon_class = db.Column(db.String(100), default="fa-solid fa-folder")
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    subcategories = db.relationship(
        "KBSubcategory",
        backref=db.backref("category", lazy=LAZY),
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    articles = db.relationship(
        "KBArticle",
        backref=db.backref("category", lazy=LAZY),
        lazy="dynamic",
    )

    @staticmethod
    def generate_slug(text: str) -> str:
        """Generate URL-safe slug from text."""
        slug = normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
        slug = re.sub(r"[^\w\s-]", "", slug)
        slug = re.sub(r"[-\s]+", "-", slug).strip("-")
        return slug

    @classmethod
    def get_by_id(cls, category_id: int) -> "KBCategory | None":
        """Get category by ID."""
        return cls.scoped().filter_by(id=category_id).first()

    @classmethod
    def get_by_slug(cls, slug: str) -> "KBCategory | None":
        """Get category by slug."""
        return cls.scoped().filter_by(slug=slug, is_active=True).first()

    @classmethod
    def get_all(cls, active_only: bool = True) -> list["KBCategory"]:
        """Get all categories."""
        query = cls.query
        if active_only:
            query = query.filter_by(is_active=True)
        return query.order_by(cls.sort_order, cls.name).all()

    @classmethod
    def create(
        cls,
        name: str,
        description: str | None = None,
        icon_class: str | None = None,
        sort_order: int = 0,
    ) -> "KBCategory":
        """Create a new category."""
        slug = cls.generate_slug(name)

        # Handle slug collisions
        base_slug = slug
        counter = 1
        while cls.scoped().filter_by(slug=slug).first():
            slug = f"{base_slug}-{counter}"
            counter += 1

        category = cls(
            name=name,
            slug=slug,
            description=description,
            icon_class=icon_class or "fa-solid fa-folder",
            sort_order=sort_order,
        )

        if current_user and hasattr(current_user, "id") and current_user.is_authenticated:
            category.created_by_id = current_user.id

        db.session.add(category)
        db.session.commit()
        return category

    def update(
        self,
        name: str | None = None,
        description: str | None = None,
        icon_class: str | None = None,
        sort_order: int | None = None,
        is_active: bool | None = None,
    ) -> "KBCategory":
        """Update category."""
        if name is not None and name != self.name:
            self.name = name
            self.slug = self.generate_slug(name)
            # Handle slug collisions
            base_slug = self.slug
            counter = 1
            while KBCategory.scoped().filter(
                KBCategory.slug == self.slug, KBCategory.id != self.id
            ).first():
                self.slug = f"{base_slug}-{counter}"
                counter += 1

        if description is not None:
            self.description = description
        if icon_class is not None:
            self.icon_class = icon_class
        if sort_order is not None:
            self.sort_order = sort_order
        if is_active is not None:
            self.is_active = is_active

        if current_user and hasattr(current_user, "id") and current_user.is_authenticated:
            self.updated_by_id = current_user.id

        db.session.commit()
        return self

    def delete(self) -> bool:
        """Delete category. Returns False if articles exist."""
        if self.articles.count() > 0:
            return False
        db.session.delete(self)
        db.session.commit()
        return True

    @property
    def article_count(self) -> int:
        """Total articles in this category (direct + in subcategories)."""
        direct = self.articles.filter_by(is_active=True).count()
        from .kb_article import KBArticle

        sub_count = (
            KBArticle.scoped().join(KBArticle.subcategory)
            .filter(
                KBArticle.subcategory.has(category_id=self.id),
                KBArticle.is_active == True,
            )
            .count()
        )
        return direct + sub_count

    @property
    def public_article_count(self) -> int:
        """Total public articles in this category."""
        direct = self.articles.filter_by(is_active=True, is_public=True).count()
        from .kb_article import KBArticle

        sub_count = (
            KBArticle.scoped().join(KBArticle.subcategory)
            .filter(
                KBArticle.subcategory.has(category_id=self.id),
                KBArticle.is_active == True,
                KBArticle.is_public == True,
            )
            .count()
        )
        return direct + sub_count
