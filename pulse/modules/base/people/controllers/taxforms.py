# -----------------------------------------------------------------------------
# sparQ - Tax Forms Controller
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""Tax forms routes for generating 1099-NEC forms.

SECURITY: TINs (SSN/EIN) are NEVER stored in the database. They are entered
fresh each time, used only in memory for PDF generation, then discarded.

Routes:
    create_1099_modal: Display the 1099-NEC form modal
    preview_1099: Generate and preview the 1099-NEC PDF
    generate_1099: Generate PDF, save to documents, and download
    download_1099: Download stored 1099-NEC PDF
    delete_1099: Delete a 1099-NEC record and its stored PDF
"""

import logging
import os
from datetime import datetime, timezone
from io import BytesIO

from flask import flash, redirect, render_template, request, url_for, Response, send_file
from flask.typing import ResponseReturnValue
from flask_login import current_user, login_required

from sqlalchemy.orm import joinedload
from system.i18n.translation import translate as _

from modules.base.core.models.workspace_settings import WorkspaceSettings
from modules.base.resources.models.attachment import Attachment
from modules.base.resources.models.attachment_link import AttachmentLink
from modules.base.resources.services.storage import (
    get_attachments_dir,
    get_storage_filename,
    ensure_directories,
)
from ..decorators import admin_required
from modules.base.core.models.workspace_user import WorkspaceUser
from modules.base.people.models.taxform import TaxFormRecord
from system.db.database import db
from system.pdf.service import fill_1099_nec_pdf

from . import blueprint

logger = logging.getLogger(__name__)


@blueprint.route("/people/<int:employee_id>/taxforms/1099-modal")
@login_required
@admin_required
def create_1099_modal(employee_id: int) -> ResponseReturnValue:
    """Display the 1099-NEC form modal."""
    member = WorkspaceUser.scoped().options(joinedload(WorkspaceUser.user)).filter_by(id=employee_id).first_or_404()
    company = WorkspaceSettings.get_instance()

    # Calculate previous tax year as default
    current_year = datetime.now(timezone.utc).year
    default_tax_year = current_year - 1

    # Calculate total compensation paid in the previous year
    # This would typically come from time entries or payment records
    # For now, we'll show 0 and let the admin enter the amount
    suggested_compensation = 0.0

    # Generate tax year options (current year and previous 3 years)
    tax_years = list(range(current_year, current_year - 4, -1))

    return render_template(
        "people/desktop/taxforms/create-1099-modal.html",
        employee=member,
        company=company,
        default_tax_year=default_tax_year,
        tax_years=tax_years,
        suggested_compensation=suggested_compensation,
    )


@blueprint.route("/people/<int:employee_id>/taxforms/1099-preview", methods=["POST"])
@login_required
@admin_required
def preview_1099(employee_id: int) -> ResponseReturnValue:
    """Generate and preview the 1099-NEC PDF."""
    member = WorkspaceUser.scoped().options(joinedload(WorkspaceUser.user)).filter_by(id=employee_id).first_or_404()
    company = WorkspaceSettings.get_instance()

    # Get form data - TINs are used in memory only
    tax_year = int(request.form.get("tax_year", datetime.now(timezone.utc).year - 1))
    payer_tin = request.form.get("payer_tin", "").strip()
    recipient_tin = request.form.get("recipient_tin", "").strip()
    compensation = float(request.form.get("compensation", 0))
    tax_withheld = float(request.form.get("tax_withheld", 0))

    # Validate required fields
    if not payer_tin or not recipient_tin:
        return Response("Payer TIN and Recipient TIN are required", status=400)

    if compensation <= 0:
        return Response("Compensation amount must be greater than 0", status=400)

    # Build payer info from company settings
    payer_name = company.company_name or "Company Name"
    payer_address = company.address or ""
    if company.address_2:
        payer_address += f"\n{company.address_2}"
    payer_city_state_zip = f"{company.city or ''}, {company.state or ''} {company.zip_code or ''}".strip()
    payer_phone = company.phone or ""

    # Build recipient info from employee
    recipient_name = f"{member.user.first_name} {member.user.last_name}"
    recipient_address = member.address or ""
    if member.address_2:
        recipient_address += f"\n{member.address_2}"
    recipient_city_state_zip = f"{member.city or ''}, {member.state or ''} {member.zip_code or ''}".strip()

    # Generate PDF - TINs are passed in memory only, never logged
    try:
        pdf_bytes = fill_1099_nec_pdf(
            payer_name=payer_name,
            payer_address=payer_address,
            payer_city_state_zip=payer_city_state_zip,
            payer_tin=payer_tin,
            payer_phone=payer_phone,
            recipient_name=recipient_name,
            recipient_address=recipient_address,
            recipient_city_state_zip=recipient_city_state_zip,
            recipient_tin=recipient_tin,
            tax_year=tax_year,
            compensation=compensation,
            tax_withheld=tax_withheld,
        )
    except Exception as e:
        logger.error(f"Failed to generate 1099-NEC PDF: {e}")
        return Response(f"Failed to generate PDF: {e}", status=500)

    # Return PDF for preview
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename=1099-NEC-{tax_year}-{member.employee_id}.pdf"
        }
    )


@blueprint.route("/people/<int:employee_id>/taxforms/1099-generate", methods=["POST"])
@login_required
@admin_required
def generate_1099(employee_id: int) -> ResponseReturnValue:
    """Generate 1099-NEC PDF, save to documents, and download."""
    member = WorkspaceUser.scoped().options(joinedload(WorkspaceUser.user)).filter_by(id=employee_id).first_or_404()
    company = WorkspaceSettings.get_instance()

    # Get form data - TINs are used in memory only
    tax_year = int(request.form.get("tax_year", datetime.now(timezone.utc).year - 1))
    payer_tin = request.form.get("payer_tin", "").strip()
    recipient_tin = request.form.get("recipient_tin", "").strip()
    compensation = float(request.form.get("compensation", 0))
    tax_withheld = float(request.form.get("tax_withheld", 0))

    # Validate required fields
    errors = []
    if not payer_tin:
        errors.append("Payer TIN (Company EIN) is required")
    if not recipient_tin:
        errors.append("Recipient TIN (Contractor SSN/EIN) is required")
    if compensation <= 0:
        errors.append("Compensation amount must be greater than 0")

    if errors:
        for error in errors:
            flash(_(error), "error")
        return redirect(url_for("people_bp.person_detail", employee_id=employee_id))

    # Build payer info from company settings
    payer_name = company.company_name or "Company Name"
    payer_address = company.address or ""
    if company.address_2:
        payer_address += f"\n{company.address_2}"
    payer_city_state_zip = f"{company.city or ''}, {company.state or ''} {company.zip_code or ''}".strip()
    payer_phone = company.phone or ""

    # Build recipient info from employee
    recipient_name = f"{member.user.first_name} {member.user.last_name}"
    recipient_address = member.address or ""
    if member.address_2:
        recipient_address += f"\n{member.address_2}"
    recipient_city_state_zip = f"{member.city or ''}, {member.state or ''} {member.zip_code or ''}".strip()

    # Generate PDF - TINs are passed in memory only, never logged
    try:
        pdf_bytes = fill_1099_nec_pdf(
            payer_name=payer_name,
            payer_address=payer_address,
            payer_city_state_zip=payer_city_state_zip,
            payer_tin=payer_tin,
            payer_phone=payer_phone,
            recipient_name=recipient_name,
            recipient_address=recipient_address,
            recipient_city_state_zip=recipient_city_state_zip,
            recipient_tin=recipient_tin,
            tax_year=tax_year,
            compensation=compensation,
            tax_withheld=tax_withheld,
        )
    except Exception as e:
        logger.error(f"Failed to generate 1099-NEC PDF: {e}")
        flash(_("Failed to generate PDF: %(error)s") % {"error": e}, "error")
        return redirect(url_for("people_bp.person_detail", employee_id=employee_id))

    # Save PDF as attachment
    attachment = None
    try:
        ensure_directories()
        filename = f"1099-NEC-{tax_year}-{member.user.last_name}.pdf"
        attachment = Attachment.create(
            filename=filename,
            mime_type="application/pdf",
            size_bytes=len(pdf_bytes),
        )
        # Save PDF to attachments directory
        storage_name = get_storage_filename(attachment.uuid, attachment.filename)
        file_path = os.path.join(get_attachments_dir(), storage_name)
        with open(file_path, "wb") as f:
            f.write(pdf_bytes)

        # Link attachment to employee
        AttachmentLink.create(
            attachment_id=attachment.id,
            entity_type="employee",
            entity_id=member.id,
        )
        logger.info(f"Saved 1099-NEC PDF as attachment {attachment.id} for employee {member.id}")
    except Exception as e:
        logger.error(f"Failed to save 1099-NEC PDF as attachment: {e}")
        flash(_("Failed to save PDF to documents."), "error")
        # Still return the PDF for download even if storage failed

    # Create TaxFormRecord (no sent_to_email)
    TaxFormRecord.create(
        employee_id=member.id,
        form_type="1099-NEC",
        tax_year=tax_year,
        nonemployee_compensation=compensation,
        federal_tax_withheld=tax_withheld,
        created_by_id=current_user.id,
        attachment_id=attachment.id if attachment else None,
    )

    # Log success (NO TINs in log message)
    logger.info(
        f"1099-NEC generated for employee {member.id} (tax year {tax_year}) "
        f"by user {current_user.id}"
    )

    # Return PDF as download
    return send_file(
        BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"1099-NEC-{tax_year}-{member.user.last_name}.pdf",
    )


@blueprint.route("/people/<int:employee_id>/taxforms/<int:record_id>/download")
@login_required
@admin_required
def download_1099(employee_id: int, record_id: int) -> ResponseReturnValue:
    """Download stored 1099-NEC PDF."""
    member = WorkspaceUser.scoped().options(joinedload(WorkspaceUser.user)).filter_by(id=employee_id).first_or_404()
    record = TaxFormRecord.get_by_id(record_id)

    if not record or record.member_id != employee_id:
        flash(_("Tax form record not found."), "error")
        return redirect(url_for("people_bp.person_detail", employee_id=employee_id))

    if not record.attachment_id:
        flash(_("No stored PDF available for this record."), "error")
        return redirect(url_for("people_bp.person_detail", employee_id=employee_id))

    attachment = Attachment.get_by_id(record.attachment_id)
    if not attachment:
        flash(_("Stored PDF attachment not found."), "error")
        return redirect(url_for("people_bp.person_detail", employee_id=employee_id))

    # Get file path from storage
    storage_name = get_storage_filename(attachment.uuid, attachment.filename)
    file_path = os.path.join(get_attachments_dir(), storage_name)

    if not os.path.exists(file_path):
        flash(_("Stored PDF file not found on disk."), "error")
        return redirect(url_for("people_bp.person_detail", employee_id=employee_id))

    # Construct download filename
    download_filename = f"1099-NEC-{record.tax_year}-{member.user.last_name}.pdf"

    return send_file(
        file_path,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=download_filename,
    )


@blueprint.route("/people/<int:employee_id>/taxforms/<int:record_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_1099(employee_id: int, record_id: int) -> ResponseReturnValue:
    """Delete a 1099-NEC record and its stored PDF."""
    member = WorkspaceUser.scoped().options(joinedload(WorkspaceUser.user)).filter_by(id=employee_id).first_or_404()
    record = TaxFormRecord.get_by_id(record_id)

    if not record or record.member_id != employee_id:
        flash(_("Tax form record not found."), "error")
        return redirect(url_for("people_bp.person_detail", employee_id=employee_id))

    # Delete attachment file from disk if exists
    if record.attachment_id:
        attachment = Attachment.get_by_id(record.attachment_id)
        if attachment:
            # Delete file from disk
            storage_name = get_storage_filename(attachment.uuid, attachment.filename)
            file_path = os.path.join(get_attachments_dir(), storage_name)
            if os.path.exists(file_path):
                os.remove(file_path)

            # Delete AttachmentLink
            link = AttachmentLink.get_link(attachment.id, "employee", member.id)
            if link:
                db.session.delete(link)

            # Delete Attachment record
            db.session.delete(attachment)

    # Delete TaxFormRecord
    db.session.delete(record)
    db.session.commit()

    logger.info(
        f"1099-NEC deleted for employee {member.id} (tax year {record.tax_year}) "
        f"by user {current_user.id}"
    )
    flash(_("1099-NEC deleted."), "success")
    return redirect(url_for("people_bp.person_detail", employee_id=employee_id))
