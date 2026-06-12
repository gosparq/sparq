# -----------------------------------------------------------------------------
# sparQ - Knowledge Base Subcategory Model
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
class KBSubcategory(db.Model, WorkspaceMixin, AuditMixin):
    """Second-level knowledge base subcategory (optional)."""

    __tablename__ = "kb_subcategory"

    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(
        db.Integer,
        db.ForeignKey("kb_category.id", ondelete="CASCADE"),
        nullable=False,
    )
    name = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255), nullable=False, index=True)
    description = db.Column(db.Text)
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    articles = db.relationship(
        "KBArticle",
        backref=db.backref("subcategory", lazy=LAZY),
        lazy="dynamic",
    )

    # Unique constraint: slug must be unique within a category
    __table_args__ = (
        db.UniqueConstraint("category_id", "slug", name="uq_kb_subcategory_category_slug"),
    )

    @staticmethod
    def generate_slug(text: str) -> str:
        """Generate URL-safe slug from text."""
        slug = normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
        slug = re.sub(r"[^\w\s-]", "", slug)
        slug = re.sub(r"[-\s]+", "-", slug).strip("-")
        return slug

    @classmethod
    def get_by_id(cls, subcategory_id: int) -> "KBSubcategory | None":
        """Get subcategory by ID."""
        return cls.scoped().filter_by(id=subcategory_id).first()

    @classmethod
    def get_by_slug(cls, category_id: int, slug: str) -> "KBSubcategory | None":
        """Get subcategory by slug within a category."""
        return cls.scoped().filter_by(
            category_id=category_id, slug=slug, is_active=True
        ).first()

    @classmethod
    def get_by_category(
        cls, category_id: int, active_only: bool = True
    ) -> list["KBSubcategory"]:
        """Get all subcategories for a category."""
        query = cls.scoped().filter_by(category_id=category_id)
        if active_only:
            query = query.filter_by(is_active=True)
        return query.order_by(cls.sort_order, cls.name).all()

    @classmethod
    def create(
        cls,
        category_id: int,
        name: str,
        description: str | None = None,
        sort_order: int = 0,
    ) -> "KBSubcategory":
        """Create a new subcategory."""
        slug = cls.generate_slug(name)

        # Handle slug collisions within category
        base_slug = slug
        counter = 1
        while cls.scoped().filter_by(category_id=category_id, slug=slug).first():
            slug = f"{base_slug}-{counter}"
            counter += 1

        subcategory = cls(
            category_id=category_id,
            name=name,
            slug=slug,
            description=description,
            sort_order=sort_order,
        )

        if current_user and hasattr(current_user, "id") and current_user.is_authenticated:
            subcategory.created_by_id = current_user.id

        db.session.add(subcategory)
        db.session.commit()
        return subcategory

    def update(
        self,
        name: str | None = None,
        description: str | None = None,
        sort_order: int | None = None,
        is_active: bool | None = None,
    ) -> "KBSubcategory":
        """Update subcategory."""
        if name is not None and name != self.name:
            self.name = name
            self.slug = self.generate_slug(name)
            # Handle slug collisions
            base_slug = self.slug
            counter = 1
            while KBSubcategory.scoped().filter(
                KBSubcategory.category_id == self.category_id,
                KBSubcategory.slug == self.slug,
                KBSubcategory.id != self.id,
            ).first():
                self.slug = f"{base_slug}-{counter}"
                counter += 1

        if description is not None:
            self.description = description
        if sort_order is not None:
            self.sort_order = sort_order
        if is_active is not None:
            self.is_active = is_active

        if current_user and hasattr(current_user, "id") and current_user.is_authenticated:
            self.updated_by_id = current_user.id

        db.session.commit()
        return self

    def delete(self) -> bool:
        """Delete subcategory. Returns False if articles exist."""
        if self.articles.count() > 0:
            return False
        db.session.delete(self)
        db.session.commit()
        return True

    @property
    def article_count(self) -> int:
        """Total active articles in this subcategory."""
        return self.articles.filter_by(is_active=True).count()

    @property
    def public_article_count(self) -> int:
        """Total public articles in this subcategory."""
        return self.articles.filter_by(is_active=True, is_public=True).count()

    @property
    def breadcrumbs(self) -> list:
        """Return breadcrumb trail [category, subcategory]."""
        return [self.category, self]
