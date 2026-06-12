# -----------------------------------------------------------------------------
# sparQ - Contact Model
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

import re
import secrets
from datetime import datetime
from enum import Enum

from flask_login import current_user

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.mixins import AuditMixin, SoftDeleteMixin
from system.db.workspace import WorkspaceMixin
from system.exceptions import ValidationError


class ContactType(Enum):
    """Type of contact relationship"""

    PROSPECT = "Prospect"
    CUSTOMER = "Customer"
    VENDOR = "Vendor"
    OTHER = "Other"


class ContactSource(Enum):
    """How the contact was acquired"""

    WEBSITE = "Website"
    REFERRAL = "Referral"
    PHONE = "Phone"
    SOCIAL = "Social"
    OTHER = "Other"


@ModelRegistry.register
class Contact(db.Model, WorkspaceMixin, AuditMixin, SoftDeleteMixin):
    """Contact model for managing prospects, customers, and vendors"""

    __tablename__ = "contact"

    id = db.Column(db.Integer, primary_key=True)

    # Basic info
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    email = db.Column(db.String(255))
    phone = db.Column(db.String(50))

    # Company info
    is_company = db.Column(db.Boolean, default=False)
    company_name = db.Column(db.String(255))

    # Contact type and source
    contact_type = db.Column(
        db.Enum(ContactType), default=ContactType.PROSPECT, nullable=False
    )
    source = db.Column(db.Enum(ContactSource), default=ContactSource.OTHER)

    # Billing address
    billing_address = db.Column(db.String(255))
    billing_address_2 = db.Column(db.String(255), nullable=True)
    city = db.Column(db.String(100))
    state = db.Column(db.String(100))
    zip_code = db.Column(db.String(20))
    country = db.Column(db.String(100))

    # Billing preferences
    payment_terms = db.Column(db.Integer, default=30)  # Days until due
    tax_exempt = db.Column(db.Boolean, default=False)

    # Notes
    notes = db.Column(db.Text)

    # Portal access token (for passwordless customer portal)
    portal_access_token = db.Column(db.String(64), unique=True, nullable=True, index=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    converted_to_customer_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    service_locations = db.relationship(
        "ServiceLocation",
        back_populates="contact",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    # --- Properties ---

    @property
    def display_name(self) -> str:
        """Return display name (company name or full name)"""
        if self.is_company and self.company_name:
            return self.company_name
        parts = [self.first_name, self.last_name]
        return " ".join(filter(None, parts)) or "Unnamed Contact"

    @property
    def full_address(self) -> str:
        """Return formatted full billing address"""
        parts = [self.billing_address, self.billing_address_2, self.city, self.state, self.zip_code, self.country]
        return ", ".join(filter(None, parts))

    @property
    def has_billing_address(self) -> bool:
        """Check if contact has billing address data."""
        return bool(self.billing_address or self.city)

    # --- Validation ---

    def validate(self) -> None:
        """Validate contact data before saving."""
        if self.is_company:
            if not self.company_name or not self.company_name.strip():
                raise ValidationError("Company name is required", field="company_name")
        else:
            if not self.first_name or not self.first_name.strip():
                raise ValidationError("First name is required", field="first_name")
            if not self.last_name or not self.last_name.strip():
                raise ValidationError("Last name is required", field="last_name")

        if self.email and not self._is_valid_email(self.email):
            raise ValidationError("Please enter a valid email address", field="email")

    @staticmethod
    def _is_valid_email(email: str) -> bool:
        """Validate email format."""
        return bool(re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email))

    # --- Class Methods ---

    @classmethod
    def get_including_deleted(cls, contact_id):
        """Get contact by ID, including soft-deleted records."""
        return cls.with_deleted().filter(cls.id == contact_id).first()

    @classmethod
    def get_by_email(cls, email: str) -> "Contact | None":
        """Get contact by email address."""
        if not email:
            return None
        return cls.scoped().filter_by(email=email).first()

    @classmethod
    def _generate_portal_token(cls) -> str:
        """Generate a unique portal access token."""
        while True:
            token = secrets.token_urlsafe(32)
            if not cls.scoped().filter_by(portal_access_token=token).first():
                return token

    @classmethod
    def create(
        cls,
        first_name: str | None = None,
        last_name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        is_company: bool = False,
        company_name: str | None = None,
        contact_type: ContactType = ContactType.PROSPECT,
        source: ContactSource = ContactSource.OTHER,
        **kwargs,
    ) -> "Contact":
        """Create a new contact with validation."""
        contact = cls(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            is_company=is_company,
            company_name=company_name,
            contact_type=contact_type,
            source=source,
            portal_access_token=cls._generate_portal_token(),
            **kwargs,
        )
        # Set audit fields
        if current_user and hasattr(current_user, "id") and current_user.is_authenticated:
            contact.created_by_id = current_user.id
        contact.validate()
        db.session.add(contact)
        db.session.commit()

        # Auto-create default service location from billing address
        contact.ensure_default_service_location()

        return contact

    @classmethod
    def get_by_portal_token(cls, token: str) -> "Contact | None":
        """Get contact by portal access token."""
        if not token:
            return None
        return cls.scoped().filter_by(portal_access_token=token).first()

    @classmethod
    def get_all(cls, contact_type: ContactType | None = None):
        """Get all active contacts, optionally filtered by type"""
        query = cls.active()
        if contact_type:
            query = query.filter(cls.contact_type == contact_type)
        return query.order_by(cls.created_at.desc()).all()

    @classmethod
    def get_by_id(cls, contact_id: int) -> "Contact | None":
        """Get contact by ID"""
        return cls.scoped().filter_by(id=contact_id).first()

    @classmethod
    def search(cls, query: str):
        """Search active contacts by name, company, or email"""
        search_term = f"%{query}%"
        return cls.active().filter(
            db.or_(
                cls.first_name.ilike(search_term),
                cls.last_name.ilike(search_term),
                cls.company_name.ilike(search_term),
                cls.email.ilike(search_term),
            )
        ).all()

    @classmethod
    def get_filtered(
        cls,
        filter_type: str = "active",
        contact_type: str | None = None,
        search_query: str | None = None,
    ) -> list["Contact"]:
        """Get contacts with filtering by deletion status, type, and search.

        Args:
            filter_type: Deletion filter - 'active', 'deleted', or 'all'
            contact_type: Contact type filter - 'prospect', 'customer', 'vendor', or None/all
            search_query: Search term for name, company, or email

        Returns:
            List of matching contacts ordered by created_at desc
        """
        # Base query based on deletion filter
        if filter_type == "deleted":
            query = cls.deleted()
        elif filter_type == "all":
            query = cls.with_deleted()
        else:
            query = cls.active()

        # Apply type filter
        if contact_type and contact_type != "all":
            try:
                type_enum = ContactType[contact_type.upper()]
                query = query.filter(cls.contact_type == type_enum)
            except KeyError:
                pass

        # Apply search
        if search_query:
            search_term = f"%{search_query}%"
            query = query.filter(
                db.or_(
                    cls.first_name.ilike(search_term),
                    cls.last_name.ilike(search_term),
                    cls.company_name.ilike(search_term),
                    cls.email.ilike(search_term),
                )
            )

        return query.order_by(cls.created_at.desc()).all()

    @classmethod
    def get_filter_counts(cls) -> dict:
        """Get counts for deletion filter tabs.

        Returns:
            Dict with 'active', 'deleted', and 'all' counts
        """
        return {
            "active": cls.active().count(),
            "deleted": cls.deleted().count(),
            "all": cls.with_deleted().count(),
        }

    def upgrade_to_customer(self) -> None:
        """Upgrade contact from Prospect to Customer"""
        if self.contact_type == ContactType.PROSPECT:
            self.contact_type = ContactType.CUSTOMER
            self.converted_to_customer_at = datetime.utcnow()
            db.session.commit()

    def regenerate_portal_token(self) -> str:
        """Regenerate portal access token (for security purposes)."""
        self.portal_access_token = self._generate_portal_token()
        db.session.commit()
        return self.portal_access_token

    def ensure_portal_token(self) -> str:
        """Ensure contact has a portal token, generating one if needed."""
        if not self.portal_access_token:
            self.portal_access_token = self._generate_portal_token()
            db.session.commit()
        return self.portal_access_token

    def ensure_default_service_location(self) -> "ServiceLocation | None":  # noqa: F821
        """Ensure contact has a default service location if address data exists.

        Creates a ServiceLocation from the billing address if:
        1. Contact has address data (billing_address or city)
        2. No default ServiceLocation exists for this contact

        Returns:
            The default ServiceLocation (existing or newly created), or None if no address data.
        """
        from modules.base.core.models.service_location import ServiceLocation

        # Check if default location already exists
        existing_default = self.service_locations.filter_by(is_default=True).first()
        if existing_default:
            return existing_default

        # Only create if we have address data
        if not self.has_billing_address:
            return None

        # Use consistent name for auto-created locations
        name = "Billing Address"

        # Create the service location
        location = ServiceLocation.create(
            contact_id=self.id,
            name=name,
            address=self.billing_address,
            address_2=self.billing_address_2,
            city=self.city,
            state=self.state,
            zip_code=self.zip_code,
            country=self.country or "USA",
            is_default=True,
        )

        return location

    def update_address_if_empty(self, address, address_2=None, city=None, state=None, zip_code=None):
        """Update billing address fields only if contact has no existing address."""
        if not address or self.billing_address:
            return
        self.billing_address = address
        self.billing_address_2 = address_2 or None
        self.city = city
        self.state = state
        self.zip_code = zip_code
        db.session.commit()

    def update(self, **kwargs) -> "Contact":
        """Update contact fields with validation."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        # Set audit fields
        if current_user and hasattr(current_user, "id") and current_user.is_authenticated:
            self.updated_by_id = current_user.id
        self.validate()
        db.session.commit()
        return self

    def delete(self) -> None:
        """Soft delete contact."""
        self.soft_delete()

    @classmethod
    def get_stats(cls) -> dict:
        """Get contact statistics for dashboard display (active contacts only)."""
        from datetime import timedelta

        now = datetime.utcnow()
        thirty_days_ago = now - timedelta(days=30)

        total = cls.active().count()
        prospects = cls.active().filter(cls.contact_type == ContactType.PROSPECT).count()
        customers = cls.active().filter(cls.contact_type == ContactType.CUSTOMER).count()
        vendors = cls.active().filter(cls.contact_type == ContactType.VENDOR).count()

        # New contacts in last 30 days
        new_last_30 = cls.active().filter(cls.created_at >= thirty_days_ago).count()

        # New customers in last 30 days (converted)
        new_customers_30 = cls.active().filter(
            cls.contact_type == ContactType.CUSTOMER,
            cls.converted_to_customer_at >= thirty_days_ago
        ).count()

        return {
            "total": total,
            "prospects": prospects,
            "customers": customers,
            "vendors": vendors,
            "new_last_30": new_last_30,
            "new_customers_30": new_customers_30,
        }
