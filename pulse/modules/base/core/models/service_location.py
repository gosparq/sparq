# -----------------------------------------------------------------------------
# sparQ - ServiceLocation Model
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from datetime import datetime

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.workspace import WorkspaceMixin
from system.exceptions import ValidationError
from system.db.raise_on_lazy import LAZY


@ModelRegistry.register
class ServiceLocation(db.Model, WorkspaceMixin):
    """Service location model for tracking job sites associated with contacts."""

    __tablename__ = "service_location"

    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(
        db.Integer, db.ForeignKey("contact.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Location details
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(255))
    address_2 = db.Column(db.String(255), nullable=True)
    city = db.Column(db.String(100))
    state = db.Column(db.String(100))
    zip_code = db.Column(db.String(20))
    country = db.Column(db.String(100), default="USA")

    # Access information
    access_notes = db.Column(db.Text)
    gate_code = db.Column(db.String(50))

    # Default location flag
    is_default = db.Column(db.Boolean, default=False)

    # Geolocation (for mapping/routing)
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    contact = db.relationship("Contact", back_populates="service_locations", lazy=LAZY)

    # --- Properties ---

    @property
    def full_address(self) -> str:
        """Return formatted full address."""
        parts = [self.address, self.address_2, self.city, self.state, self.zip_code, self.country]
        return ", ".join(filter(None, parts))

    @property
    def display_name(self) -> str:
        """Return display name with address preview."""
        if self.address:
            return f"{self.name} - {self.address}"
        return self.name

    # --- Validation ---

    def validate(self) -> None:
        """Validate service location data before saving."""
        if not self.name or not self.name.strip():
            raise ValidationError("Location name is required", field="name")
        if not self.contact_id:
            raise ValidationError("Contact is required", field="contact_id")

    # --- Class Methods ---

    @classmethod
    def create(
        cls,
        contact_id: int,
        name: str,
        address: str | None = None,
        address_2: str | None = None,
        city: str | None = None,
        state: str | None = None,
        zip_code: str | None = None,
        country: str | None = "USA",
        access_notes: str | None = None,
        gate_code: str | None = None,
        is_default: bool = False,
        lat: float | None = None,
        lng: float | None = None,
    ) -> "ServiceLocation":
        """Create a new service location with validation."""
        location = cls(
            contact_id=contact_id,
            name=name,
            address=address,
            address_2=address_2,
            city=city,
            state=state,
            zip_code=zip_code,
            country=country,
            access_notes=access_notes,
            gate_code=gate_code,
            is_default=is_default,
            lat=lat,
            lng=lng,
        )
        location.validate()

        # If this is the default, unset other defaults for this contact
        if is_default:
            cls._clear_default_for_contact(contact_id)

        db.session.add(location)
        db.session.commit()
        return location

    @classmethod
    def get_by_id(cls, location_id: int) -> "ServiceLocation | None":
        """Get service location by ID."""
        return cls.scoped().filter_by(id=location_id).first()

    @classmethod
    def get_for_contact(cls, contact_id: int) -> list["ServiceLocation"]:
        """Get all service locations for a contact."""
        return cls.scoped().filter_by(contact_id=contact_id).order_by(
            cls.is_default.desc(), cls.name.asc()
        ).all()

    @classmethod
    def _clear_default_for_contact(cls, contact_id: int) -> None:
        """Clear the default flag for all locations of a contact."""
        cls.scoped().filter_by(contact_id=contact_id, is_default=True).update(
            {"is_default": False}
        )

    def update(self, **kwargs) -> "ServiceLocation":
        """Update service location fields with validation."""
        # Handle is_default specially
        if kwargs.get("is_default") and not self.is_default:
            self._clear_default_for_contact(self.contact_id)

        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

        self.validate()
        db.session.commit()
        return self

    def delete(self) -> None:
        """Delete service location."""
        db.session.delete(self)
        db.session.commit()

    def set_as_default(self) -> None:
        """Set this location as the default for its contact."""
        self._clear_default_for_contact(self.contact_id)
        self.is_default = True
        db.session.commit()
