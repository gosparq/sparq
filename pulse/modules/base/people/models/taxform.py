# -----------------------------------------------------------------------------
# sparQ - Tax Form Record Model
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""Tax form record model for tracking generated tax documents.

This module provides the TaxFormRecord model for tracking 1099-NEC and other
tax forms generated for contractors. IMPORTANT: TINs are NEVER stored for security.

Classes:
    TaxFormRecord: Record of tax forms generated (no TIN storage).

Example:
    Recording a generated 1099-NEC::

        from modules.base.people.models.taxform import TaxFormRecord

        record = TaxFormRecord.create(
            employee_id=contractor.id,
            form_type="1099-NEC",
            tax_year=2025,
            nonemployee_compensation=50000.00,
            federal_tax_withheld=0,
            created_by_id=current_user.id,
            attachment_id=attachment.id,
        )
"""

from datetime import datetime, timezone

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.raise_on_lazy import LAZY
from system.db.workspace import WorkspaceMixin


@ModelRegistry.register
class TaxFormRecord(db.Model, WorkspaceMixin):
    """Record of tax forms generated for contractors.

    SECURITY NOTE: TINs (SSN/EIN) are intentionally NOT stored.
    They are entered fresh each time and used only in memory
    during PDF generation, then immediately discarded.

    Attributes:
        id: Primary key.
        employee_id: Foreign key to Employee (contractor).
        form_type: Type of tax form (e.g., "1099-NEC").
        tax_year: The tax year the form is for.
        nonemployee_compensation: Box 1 - Total compensation paid.
        federal_tax_withheld: Box 4 - Federal tax withheld (usually $0).
        created_at: Timestamp when form was generated.
        created_by_id: User who generated the form.
        attachment_id: Foreign key to stored PDF attachment.

    Relationships:
        employee: The contractor who received the form.
        created_by: The admin user who generated the form.
        attachment: The stored PDF file.
    """

    __tablename__ = "tax_form_record"

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey("workspace_user.id"), nullable=False)
    form_type = db.Column(db.String(20), nullable=False)  # "1099-NEC"
    tax_year = db.Column(db.Integer, nullable=False)
    nonemployee_compensation = db.Column(db.Numeric(10, 2), nullable=False)
    federal_tax_withheld = db.Column(db.Numeric(10, 2), default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    created_by_id = db.Column(db.Integer, db.ForeignKey("workspace_user.id"), nullable=False)
    attachment_id = db.Column(db.Integer, db.ForeignKey("attachment.id"), nullable=True)

    # NOTE: NO TIN fields - intentionally omitted for security
    # TINs are entered fresh each time and never persisted

    # Relationships
    member = db.relationship("WorkspaceUser", foreign_keys=[member_id], backref=db.backref("tax_form_records", lazy="dynamic"), lazy=LAZY)
    created_by = db.relationship("WorkspaceUser", foreign_keys=[created_by_id], backref=db.backref("created_tax_forms", lazy="dynamic"), lazy=LAZY)
    attachment = db.relationship("Attachment", backref=db.backref("tax_form_record", lazy=LAZY), lazy=LAZY)

    # --- Class Methods (CRUD) ---
    @classmethod
    def create(
        cls,
        member_id: int,
        form_type: str,
        tax_year: int,
        nonemployee_compensation: float,
        federal_tax_withheld: float,
        created_by_id: int,
        attachment_id: int | None = None,
    ) -> "TaxFormRecord":
        """Create a new tax form record.

        Args:
            member_id: ID of the contractor member.
            form_type: Type of form (e.g., "1099-NEC").
            tax_year: Tax year the form is for.
            nonemployee_compensation: Box 1 - Total compensation paid.
            federal_tax_withheld: Box 4 - Federal tax withheld.
            created_by_id: ID of the user who generated the form.
            attachment_id: Optional ID of stored PDF attachment.

        Returns:
            The created TaxFormRecord instance.
        """
        record = cls(
            member_id=member_id,
            form_type=form_type,
            tax_year=tax_year,
            nonemployee_compensation=nonemployee_compensation,
            federal_tax_withheld=federal_tax_withheld,
            created_by_id=created_by_id,
            attachment_id=attachment_id,
        )
        db.session.add(record)
        db.session.commit()
        return record

    @classmethod
    def get_by_member(cls, member_id: int) -> list["TaxFormRecord"]:
        """Get all tax forms for a member.

        Args:
            member_id: ID of the member.

        Returns:
            List of TaxFormRecord instances ordered by tax year (descending).
        """
        return cls.scoped().filter_by(member_id=member_id).order_by(
            cls.tax_year.desc(), cls.created_at.desc()
        ).all()

    @classmethod
    def get_by_id(cls, record_id: int) -> "TaxFormRecord | None":
        """Get tax form by ID.

        Args:
            record_id: ID of the tax form record.

        Returns:
            TaxFormRecord instance or None if not found.
        """
        return cls.scoped().filter_by(id=record_id).first()

    @classmethod
    def delete_by_id(cls, record_id: int) -> bool:
        """Delete a tax form record by ID.

        Args:
            record_id: ID of the tax form record to delete.

        Returns:
            True if deleted, False if not found.
        """
        record = cls.scoped().filter_by(id=record_id).first()
        if record:
            db.session.delete(record)
            db.session.commit()
            return True
        return False

    # --- Properties ---
    @property
    def formatted_compensation(self) -> str:
        """Return formatted compensation amount."""
        return f"${self.nonemployee_compensation:,.2f}"

    @property
    def formatted_withheld(self) -> str:
        """Return formatted withheld amount."""
        return f"${self.federal_tax_withheld:,.2f}"

    def __repr__(self) -> str:
        return f"<TaxFormRecord {self.form_type} {self.tax_year} for Member {self.member_id}>"
