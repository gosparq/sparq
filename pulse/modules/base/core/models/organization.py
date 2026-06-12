# -----------------------------------------------------------------------------
# sparQ - Organization Model
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import orm

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.utils.email_domain import normalize_domain
from system.db.raise_on_lazy import LAZY

_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{1,49}$")


@ModelRegistry.register
class Organization(db.Model):
    """Company-level container that owns one or more workspaces.

    Organization sits above workspace scope — it is NOT workspace-scoped.
    Contains legal entity info needed for payroll, tax forms, and compliance,
    plus billing and plan state.

    """

    __tablename__ = "organization"

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    plan = db.Column(db.String(50), default="free")
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    claimed_domain = db.Column(db.String(253), nullable=True, index=True)

    # Legal entity info — populated as features require
    phone = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(255), nullable=True)
    website = db.Column(db.String(255), nullable=True)
    address = db.Column(db.String(255), nullable=True)
    address_2 = db.Column(db.String(255), nullable=True)
    city = db.Column(db.String(100), nullable=True)
    state = db.Column(db.String(100), nullable=True)
    zip_code = db.Column(db.String(20), nullable=True)
    country = db.Column(db.String(100), nullable=True)
    tax_id = db.Column(db.String(100), nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    owner = db.relationship("User", backref=db.backref("owned_organizations", lazy=LAZY), lazy=LAZY)
    workspaces = db.relationship("Workspace", backref=db.backref("organization", lazy=LAZY), lazy=LAZY)

    def __repr__(self):
        return f"<Organization {self.slug}>"

    @orm.validates("claimed_domain")
    def _normalize_claimed_domain(self, _key: str, value: str | None) -> str | None:
        """Normalize claimed_domain on write: lowercase, strip, no leading @."""
        if value is None:
            return None
        normalized = normalize_domain(value)
        return normalized or None

    # ------------------------------------------------------------------
    # Domain query helpers
    # ------------------------------------------------------------------

    @classmethod
    def find_by_domain(cls, domain: str) -> list[Organization]:
        """Find all active organizations claiming a given domain."""
        normalized = normalize_domain(domain)
        if not normalized:
            return []
        return cls.query.filter_by(
            claimed_domain=normalized, is_active=True,
        ).all()

    @classmethod
    def count_by_domain(cls, domain: str) -> int:
        """Count active organizations claiming a given domain."""
        normalized = normalize_domain(domain)
        if not normalized:
            return 0
        return cls.query.filter_by(
            claimed_domain=normalized, is_active=True,
        ).count()

    @classmethod
    def get_sole_claimer(cls, domain: str) -> Organization | None:
        """Return the single org claiming this domain, or None if 0 or 2+."""
        orgs = cls.find_by_domain(domain)
        if len(orgs) == 1:
            return orgs[0]
        return None

    @classmethod
    def count(cls) -> int:
        """Count all organizations."""
        return cls.query.count()

    @classmethod
    def get_all(cls) -> list[Organization]:
        """Get all organizations ordered by creation date (newest first)."""
        return cls.query.options(orm.joinedload(cls.owner)).order_by(cls.created_at.desc()).all()

    @classmethod
    def get_by_id_or_404(cls, org_id: uuid.UUID) -> Organization:
        """Get organization by ID or raise 404."""
        return cls.query.options(orm.joinedload(cls.owner)).filter_by(id=org_id).first_or_404()

    @classmethod
    def get_by_ids(cls, ids: set[uuid.UUID]) -> dict[uuid.UUID, Organization]:
        """Get organizations by a set of IDs, returned as {id: Organization}."""
        if not ids:
            return {}
        orgs = cls.query.filter(cls.id.in_(ids)).all()
        return {o.id: o for o in orgs}

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        name: str,
        slug: str,
        plan: str = "free",
        owner_id: int | None = None,
        claimed_domain: str | None = None,
    ) -> Organization:
        """Create a new organization.

        Args:
            name: Display name.
            slug: URL-safe identifier (lowercase, 2-50 chars).
            plan: Billing plan label.
            owner_id: Optional owner user ID.
            claimed_domain: Optional email domain claim.

        Returns:
            The new Organization instance.

        Raises:
            ValueError: If slug is invalid or already taken.
        """
        slug = slug.strip().lower()
        if not _SLUG_RE.match(slug):
            raise ValueError("Invalid slug format.")
        if cls.query.filter_by(slug=slug).first():
            raise ValueError(f"Slug '{slug}' already exists.")

        org = cls(
            name=name.strip(),
            slug=slug,
            plan=plan or "free",
            owner_id=owner_id,
            claimed_domain=claimed_domain or None,
        )
        db.session.add(org)
        db.session.commit()
        return org

    def update(
        self,
        name: str | None = None,
        slug: str | None = None,
        plan: str | None = None,
        claimed_domain: str | None = ...,
    ) -> Organization:
        """Update organization fields.

        Args:
            name: New display name (None to skip).
            slug: New slug (None to skip).
            plan: New plan label (None to skip).
            claimed_domain: New domain claim (None to clear, ... to skip).

        Returns:
            self

        Raises:
            ValueError: If new slug is invalid or already taken.
        """
        if name is not None:
            self.name = name.strip()
        if slug is not None:
            slug = slug.strip().lower()
            if not _SLUG_RE.match(slug):
                raise ValueError("Invalid slug format.")
            if slug != self.slug and Organization.query.filter_by(slug=slug).first():
                raise ValueError(f"Slug '{slug}' already exists.")
            self.slug = slug
        if plan is not None:
            self.plan = plan
        if claimed_domain is not ...:
            self.claimed_domain = claimed_domain or None
        db.session.commit()
        return self

    _INFO_LIMITS: dict[str, int] = {
        "phone": 50, "email": 255, "website": 255, "tax_id": 100,
        "address": 255, "address_2": 255, "city": 100, "state": 100,
        "zip_code": 20, "country": 100,
    }

    def update_info(self, name: str | None = None, **kwargs: str | None) -> Organization:
        """Update legal entity / contact info fields.

        Args:
            name: New display name (None to skip, empty string preserves current).
            **kwargs: Contact/address fields to update. Values are stripped and
                truncated to column limits. Empty strings become None.

        Returns:
            self
        """
        if name is not None:
            self.name = name.strip() or self.name
        for field, limit in self._INFO_LIMITS.items():
            if field in kwargs:
                val = kwargs[field]
                val = val.strip()[:limit] if val else None
                setattr(self, field, val)
        db.session.commit()
        return self

    def deactivate(self) -> None:
        """Deactivate this organization."""
        self.is_active = False
        db.session.commit()

    def activate(self) -> None:
        """Reactivate this organization."""
        self.is_active = True
        db.session.commit()

    @classmethod
    def can_delete(cls, organization_id, user_id: int) -> bool:
        """Check if user can delete this organization.

        Requires: user is the owner AND owns at least one other active org.
        """
        org = cls.query.get(organization_id)
        if not org or org.owner_id != user_id:
            return False
        owned_count = cls.query.filter_by(owner_id=user_id, is_active=True).count()
        return owned_count > 1
