# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Team module controllers for onboarding functionality.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

import secrets
from datetime import datetime

from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.orm import joinedload, selectinload

from system.db.database import db
from system.i18n.translation import translate as _

from ..decorators import admin_required
from modules.base.core.models.workspace_user import WorkspaceUser, EmployeeType, SalaryType
from ..models.offboarding import OffboardingTask
from ..models.onboarding import (
    OnboardingRecord,
    OnboardingStatus,
    OnboardingTaskTemplate,
    OnboardingType,
    TaskAssignee,
    TaskStatus,
    W2_TASK_TEMPLATES,
    CONTRACTOR_TASK_TEMPLATES,
)
from . import blueprint


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------


def _send_welcome_email(record):
    """Send welcome email after onboarding is approved."""
    from flask import url_for
    from system.email.service import send_email_async, is_configured
    from system.email.templates import (
        get_onboarding_welcome_email_html,
        get_onboarding_welcome_email_text,
    )

    if not is_configured():
        return False

    from modules.base.core.models.workspace_settings import WorkspaceSettings

    company = WorkspaceSettings.get_instance()
    company_name = company.company_name or "Your Company"
    login_url = url_for("core_bp.login", _external=True)

    subject = f"{_('Welcome to')} {company_name} - {_('Your Account is Ready!')}"
    html_body = get_onboarding_welcome_email_html(
        company_name, record.first_name, record.personal_email, login_url
    )
    text_body = get_onboarding_welcome_email_text(
        company_name, record.first_name, record.personal_email, login_url
    )

    send_email_async(record.personal_email, subject, html_body, text_body)
    return True


def _send_onboarding_invite_email(record):
    """Send onboarding invite email with magic link."""
    from flask import url_for
    from system.email.service import send_email_async, is_configured
    from system.email.templates import (
        get_onboarding_invite_email_html,
        get_onboarding_invite_email_text,
    )

    if not is_configured():
        return False

    from modules.base.core.models.workspace_settings import WorkspaceSettings

    company = WorkspaceSettings.get_instance()
    company_name = company.company_name or "Your Company"
    magic_link = url_for(
        "people_bp.onboarding_start",
        token=record.token,
        _external=True,
    )
    start_date_str = (
        record.start_date.strftime("%B %d, %Y") if record.start_date else None
    )

    subject = f"{_('Welcome to')} {company_name} - {_('Complete Your Onboarding')}"
    html_body = get_onboarding_invite_email_html(
        company_name, record.first_name, record.position, start_date_str, magic_link
    )
    text_body = get_onboarding_invite_email_text(
        company_name, record.first_name, record.position, start_date_str, magic_link
    )

    send_email_async(record.personal_email, subject, html_body, text_body)
    return True


def _perform_send_invite(record, current_user_id):
    """
    Perform the actual send invite logic.

    Args:
        record: OnboardingRecord
        current_user_id: ID of the user performing the action

    Returns:
        tuple: (success: bool, message: str)
    """
    from modules.base.core.models.user import User

    if record.status not in (OnboardingStatus.DRAFT, OnboardingStatus.SENT):
        return False, _("Cannot send invite for this record.")

    try:
        # Create user and employee if not exists
        if not record.member_id:
            employee_type = (
                EmployeeType.FULL_TIME
                if record.onboarding_type == OnboardingType.W2
                else EmployeeType.CONTRACTOR
            )

            # Check if user already exists with this email
            existing_user = User.get_by_email(record.personal_email)
            if existing_user:
                user = existing_user

                # Check for existing employee (e.g., from cancelled onboarding)
                existing_employee = WorkspaceUser.get_by_user_id(user.id)
                if existing_employee:
                    existing_employee.reactivate_for_onboarding(
                        type=employee_type,
                        position=record.position,
                        department=record.department,
                        start_date=record.start_date,
                        salary=record.salary,
                        salary_type=record.salary_type,
                        manager_id=record.manager_id,
                    )
                    record.member_id = existing_employee.id
            else:
                # Create passwordless user (they'll use magic link to access)
                user = User.create_from_oauth(
                    email=record.personal_email,
                    first_name=record.first_name,
                    last_name=record.last_name,
                )
                db.session.commit()

            # Create new employee if we didn't reuse an existing one
            if not record.member_id:
                employee = WorkspaceUser.create_for_onboarding(
                    user,
                    type=employee_type,
                    position=record.position,
                    department=record.department,
                    start_date=record.start_date,
                    salary=record.salary,
                    salary_type=record.salary_type,
                    manager_id=record.manager_id,
                )
                record.member_id = employee.id

        # Generate/regenerate magic link token
        record.token = secrets.token_urlsafe(32)
        db.session.commit()

        # Mark as sent
        record.mark_sent()

        # Send onboarding invite email with magic link
        _send_onboarding_invite_email(record)

        return True, _("Onboarding invite sent to %(email)s.") % {"email": record.personal_email}

    except Exception as e:
        db.session.rollback()
        return False, _("Error sending invite: %(error)s") % {"error": str(e)}


def _handle_document_upload(record, file, doc_type, created_by_id):
    """
    Handle document upload and create e-sign request.

    Args:
        record: OnboardingRecord
        file: Uploaded file from request.files
        doc_type: 'offer_letter' or 'contract'
        created_by_id: User ID of creator

    Returns:
        SignatureRequest or None
    """
    if not file or not file.filename:
        return None

    from modules.base.resources.models.attachment import Attachment
    from modules.base.resources.services import storage
    from modules.base.resources.services.esign import ESignService

    # Create attachment
    attachment = Attachment.create(
        filename=file.filename,
        mime_type=file.content_type or "application/pdf",
        size_bytes=0,
    )

    # Save file
    file_path = storage.save_to_attachments(file, attachment)

    # Update size
    import os
    attachment.size_bytes = os.path.getsize(file_path)
    db.session.commit()

    # Create e-sign request (but don't send email yet - wait for onboarding send)
    title = f"{'Offer Letter' if doc_type == 'offer_letter' else 'Employment Agreement'} - {record.full_name}"

    sig_request = ESignService.create_request(
        attachment=attachment,
        title=title,
        signers=[{
            "email": record.personal_email,
            "name": record.full_name,
            "role": "signer",
        }],
        message="Please review and sign this document as part of your onboarding.",
        created_by_id=created_by_id,
        context={"onboarding_id": record.id, "doc_type": doc_type},
        send_email=False,  # We'll handle this when onboarding is sent
    )

    # Link to onboarding record
    if doc_type == "offer_letter":
        record.offer_letter_request_id = sig_request.id
    else:
        record.contract_request_id = sig_request.id
    db.session.commit()

    return sig_request


# -----------------------------------------------------------------------------
# Admin Routes
# -----------------------------------------------------------------------------


@blueprint.route("/onboarding")
@login_required
@admin_required
def onboarding_list():
    """List all onboarding records."""
    # Get filter from query params
    status_filter = request.args.get("status", "")

    # Get records
    if status_filter:
        try:
            status = OnboardingStatus[status_filter.upper().replace(" ", "_")]
            records = OnboardingRecord.get_all(status=status)
        except KeyError:
            records = OnboardingRecord.get_all()
    else:
        records = OnboardingRecord.get_all()

    # Get counts for tabs
    counts = {
        "all": OnboardingRecord.scoped().count(),
        "draft": OnboardingRecord.scoped().filter_by(status=OnboardingStatus.DRAFT).count(),
        "sent": OnboardingRecord.scoped().filter_by(status=OnboardingStatus.SENT).count(),
        "in_progress": OnboardingRecord.scoped().filter_by(
            status=OnboardingStatus.IN_PROGRESS
        ).count(),
        "pending_review": OnboardingRecord.scoped().filter_by(
            status=OnboardingStatus.PENDING_REVIEW
        ).count(),
        "completed": OnboardingRecord.scoped().filter_by(
            status=OnboardingStatus.COMPLETED
        ).count(),
    }

    return render_template(
        "people/desktop/onboarding/index.html",
        records=records,
        counts=counts,
        status_filter=status_filter,
        OnboardingStatus=OnboardingStatus,
        active_page="onboarding",
        module_home="dashboard_bp.index",
    )


@blueprint.route("/onboarding/new", methods=["GET", "POST"])
@login_required
@admin_required
def onboarding_new():
    """Create a new onboarding record."""
    if request.method == "POST":
        try:
            # Parse form data
            onboarding_type = OnboardingType[request.form.get("onboarding_type", "W2")]
            start_date = None
            if request.form.get("start_date"):
                start_date = datetime.strptime(
                    request.form.get("start_date"), "%Y-%m-%d"
                ).date()

            salary = None
            if request.form.get("salary"):
                salary = float(request.form.get("salary"))

            salary_type = SalaryType.YEARLY
            if request.form.get("salary_type"):
                salary_type = SalaryType[request.form.get("salary_type")]

            manager_id = None
            if request.form.get("manager_id"):
                manager_id = int(request.form.get("manager_id"))

            # Create onboarding record with tasks
            record = OnboardingRecord.create(
                first_name=request.form.get("first_name"),
                last_name=request.form.get("last_name"),
                personal_email=request.form.get("personal_email"),
                work_email=request.form.get("work_email") or None,
                onboarding_type=onboarding_type,
                position=request.form.get("position") or None,
                department=request.form.get("department") or None,
                start_date=start_date,
                salary=salary,
                salary_type=salary_type,
                manager_id=manager_id,
                admin_notes=request.form.get("admin_notes") or None,
                created_by_id=current_user.id,
            )

            # Handle document uploads
            if "offer_letter" in request.files:
                _handle_document_upload(
                    record, request.files["offer_letter"], "offer_letter", current_user.id
                )
            if "contract" in request.files:
                _handle_document_upload(
                    record, request.files["contract"], "contract", current_user.id
                )

            flash(_("Onboarding record created successfully."), "success")

            # If "Save and Send" was clicked, send invite directly
            if request.form.get("action") == "send":
                success, message = _perform_send_invite(record, current_user.id)
                if success:
                    flash(message, "success")
                else:
                    flash(message, "error")

            return redirect(url_for("people_bp.onboarding_detail", record_id=record.id))

        except Exception as e:
            db.session.rollback()
            flash(_("Error creating onboarding: %(error)s") % {"error": str(e)}, "error")
            return redirect(url_for("people_bp.onboarding_new"))

    # GET - show form
    potential_managers = WorkspaceUser.scoped().options(joinedload(WorkspaceUser.user)).all()
    return render_template(
        "people/desktop/onboarding/form.html",
        record=None,
        potential_managers=potential_managers,
        OnboardingType=OnboardingType,
        active_page="onboarding",
        module_home="dashboard_bp.index",
    )


@blueprint.route("/onboarding/<int:record_id>")
@login_required
@admin_required
def onboarding_detail(record_id):
    """View onboarding record details."""
    from modules.base.resources.models.signature_request import SignatureRequest

    record = (
        OnboardingRecord.scoped()
        .options(
            joinedload(OnboardingRecord.manager).joinedload(WorkspaceUser.user),
            joinedload(OnboardingRecord.member).joinedload(WorkspaceUser.user),
            selectinload(OnboardingRecord.tasks),
            joinedload(OnboardingRecord.tax_form_attachment),
            joinedload(OnboardingRecord.offer_letter_request).joinedload(SignatureRequest.signed_attachment),
            joinedload(OnboardingRecord.contract_request).joinedload(SignatureRequest.signed_attachment),
        )
        .filter_by(id=record_id)
        .first()
    )
    if not record:
        flash(_("Onboarding record not found."), "error")
        return redirect(url_for("people_bp.onboarding_list"))

    # Separate tasks by assignee
    employee_tasks = [t for t in record.tasks if t.assignee == TaskAssignee.EMPLOYEE]
    admin_tasks = [t for t in record.tasks if t.assignee == TaskAssignee.ADMIN]

    return render_template(
        "people/desktop/onboarding/detail.html",
        record=record,
        employee_tasks=employee_tasks,
        admin_tasks=admin_tasks,
        OnboardingStatus=OnboardingStatus,
        TaskStatus=TaskStatus,
        active_page="onboarding",
        module_home="dashboard_bp.index",
    )


@blueprint.route("/onboarding/<int:record_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def onboarding_edit(record_id):
    """Edit an onboarding record (only if DRAFT)."""
    record = OnboardingRecord.get_by_id(record_id)
    if not record:
        flash(_("Onboarding record not found."), "error")
        return redirect(url_for("people_bp.onboarding_list"))

    if record.status != OnboardingStatus.DRAFT:
        flash(_("Only draft records can be edited."), "error")
        return redirect(url_for("people_bp.onboarding_detail", record_id=record_id))

    if request.method == "POST":
        try:
            # Update fields
            record.first_name = request.form.get("first_name")
            record.last_name = request.form.get("last_name")
            record.personal_email = request.form.get("personal_email")
            record.work_email = request.form.get("work_email") or None
            record.onboarding_type = OnboardingType[
                request.form.get("onboarding_type", "W2")
            ]
            record.position = request.form.get("position") or None
            record.department = request.form.get("department") or None
            record.admin_notes = request.form.get("admin_notes") or None

            if request.form.get("start_date"):
                record.start_date = datetime.strptime(
                    request.form.get("start_date"), "%Y-%m-%d"
                ).date()
            else:
                record.start_date = None

            if request.form.get("salary"):
                record.salary = float(request.form.get("salary"))
            else:
                record.salary = None

            if request.form.get("salary_type"):
                record.salary_type = SalaryType[request.form.get("salary_type")]

            if request.form.get("manager_id"):
                record.manager_id = int(request.form.get("manager_id"))
            else:
                record.manager_id = None

            record.updated_by_id = current_user.id
            db.session.commit()

            # Handle document uploads
            if "offer_letter" in request.files:
                _handle_document_upload(
                    record, request.files["offer_letter"], "offer_letter", current_user.id
                )
            if "contract" in request.files:
                _handle_document_upload(
                    record, request.files["contract"], "contract", current_user.id
                )

            flash(_("Onboarding record updated."), "success")

            # If "Save and Send" was clicked, send invite directly
            if request.form.get("action") == "send":
                success, message = _perform_send_invite(record, current_user.id)
                if success:
                    flash(message, "success")
                else:
                    flash(message, "error")

            return redirect(url_for("people_bp.onboarding_detail", record_id=record_id))

        except Exception as e:
            db.session.rollback()
            flash(_("Error updating onboarding: %(error)s") % {"error": str(e)}, "error")

    # GET - show form
    potential_managers = WorkspaceUser.scoped().options(joinedload(WorkspaceUser.user)).all()
    return render_template(
        "people/desktop/onboarding/form.html",
        record=record,
        potential_managers=potential_managers,
        OnboardingType=OnboardingType,
        active_page="onboarding",
        module_home="dashboard_bp.index",
    )


@blueprint.route("/onboarding/<int:record_id>/delete", methods=["POST"])
@login_required
@admin_required
def onboarding_delete(record_id):
    """Delete a draft onboarding record."""
    record = OnboardingRecord.get_by_id(record_id)
    if not record:
        flash(_("Onboarding record not found."), "error")
        return redirect(url_for("people_bp.onboarding_list"))

    if record.status != OnboardingStatus.DRAFT:
        flash(_("Only draft records can be deleted."), "error")
        return redirect(url_for("people_bp.onboarding_list"))

    try:
        # Delete associated tasks first
        for task in record.tasks:
            db.session.delete(task)

        # Delete any signature requests if they exist
        if record.offer_letter_request:
            db.session.delete(record.offer_letter_request)
        if record.contract_request:
            db.session.delete(record.contract_request)

        name = record.full_name
        db.session.delete(record)
        db.session.commit()
        flash(_("Onboarding record for %(name)s has been deleted.") % {"name": name}, "success")
    except Exception as e:
        db.session.rollback()
        flash(_("Error deleting onboarding: %(error)s") % {"error": str(e)}, "error")

    return redirect(url_for("people_bp.onboarding_list"))


@blueprint.route("/onboarding/<int:record_id>/send", methods=["POST"])
@login_required
@admin_required
def onboarding_send(record_id):
    """Send onboarding invite to employee."""
    record = OnboardingRecord.get_by_id(record_id)
    if not record:
        flash(_("Onboarding record not found."), "error")
        return redirect(url_for("people_bp.onboarding_list"))

    success, message = _perform_send_invite(record, current_user.id)
    if success:
        flash(message, "success")
    else:
        flash(message, "error")

    return redirect(url_for("people_bp.onboarding_detail", record_id=record_id))


@blueprint.route("/onboarding/<int:record_id>/resend", methods=["POST"])
@login_required
@admin_required
def onboarding_resend(record_id):
    """Resend onboarding invite."""
    record = OnboardingRecord.get_by_id(record_id)
    if not record:
        flash(_("Onboarding record not found."), "error")
        return redirect(url_for("people_bp.onboarding_list"))

    if record.status not in (
        OnboardingStatus.SENT,
        OnboardingStatus.IN_PROGRESS,
    ):
        flash(_("Cannot resend invite for this record."), "error")
        return redirect(url_for("people_bp.onboarding_detail", record_id=record_id))

    try:
        # Generate a new token for security
        record.token = secrets.token_urlsafe(32)
        record.sent_at = datetime.utcnow()
        db.session.commit()

        # Resend the invite email
        _send_onboarding_invite_email(record)

        flash(
            _("Invite resent to %(email)s.") % {"email": record.personal_email},
            "success",
        )

    except Exception as e:
        db.session.rollback()
        flash(_("Error resending invite: %(error)s") % {"error": str(e)}, "error")

    return redirect(url_for("people_bp.onboarding_detail", record_id=record_id))


@blueprint.route("/onboarding/<int:record_id>/approve", methods=["POST"])
@login_required
@admin_required
def onboarding_approve(record_id):
    """Approve and complete onboarding."""
    record = OnboardingRecord.get_by_id(record_id)
    if not record:
        flash(_("Onboarding record not found."), "error")
        return redirect(url_for("people_bp.onboarding_list"))

    if record.status != OnboardingStatus.PENDING_REVIEW:
        flash(_("Only records pending review can be approved."), "error")
        return redirect(url_for("people_bp.onboarding_detail", record_id=record_id))

    try:
        # Update employee record with final data from onboarding
        if record.member:
            employee = record.member
            # Update position/department if changed
            if record.position:
                employee.position = record.position
            if record.department:
                employee.department = record.department
            if record.start_date:
                employee.start_date = record.start_date
            if record.salary:
                employee.salary = record.salary
            if record.salary_type:
                employee.salary_type = record.salary_type
            if record.manager_id:
                employee.manager_id = record.manager_id

            # Promote from INACTIVE to ACTIVE
            employee.activate()

        # Transfer onboarding documents to employee record
        record.transfer_documents_to_member()

        # Approve the record
        record.approve()

        # Send welcome email (isolated - don't fail approval on email error)
        try:
            _send_welcome_email(record)
        except Exception:
            pass  # Email failure shouldn't block approval

        flash(
            _("Onboarding completed for %(name)s! A welcome email has been sent.") % {"name": record.full_name},
            "success",
        )

    except Exception as e:
        db.session.rollback()
        flash(_("Error approving onboarding: %(error)s") % {"error": str(e)}, "error")

    return redirect(url_for("people_bp.onboarding_detail", record_id=record_id))


@blueprint.route("/onboarding/<int:record_id>/cancel", methods=["POST"])
@login_required
@admin_required
def onboarding_cancel(record_id):
    """Cancel onboarding."""
    record = OnboardingRecord.get_by_id(record_id)
    if not record:
        flash(_("Onboarding record not found."), "error")
        return redirect(url_for("people_bp.onboarding_list"))

    if record.status == OnboardingStatus.COMPLETED:
        flash(_("Cannot cancel completed onboarding."), "error")
        return redirect(url_for("people_bp.onboarding_detail", record_id=record_id))

    try:
        record.cancel()
        flash(_("Onboarding cancelled."), "success")

    except Exception as e:
        db.session.rollback()
        flash(_("Error cancelling onboarding: %(error)s") % {"error": str(e)}, "error")

    return redirect(url_for("people_bp.onboarding_detail", record_id=record_id))


@blueprint.route("/onboarding/<int:record_id>/resume", methods=["POST"])
@login_required
@admin_required
def onboarding_resume(record_id):
    """Resume a cancelled onboarding so the employee can pick up where they left off."""
    record = OnboardingRecord.get_by_id(record_id)
    if not record:
        flash(_("Onboarding record not found."), "error")
        return redirect(url_for("people_bp.onboarding_list"))

    if record.status != OnboardingStatus.CANCELLED:
        flash(_("Only cancelled onboarding records can be resumed."), "error")
        return redirect(url_for("people_bp.onboarding_detail", record_id=record_id))

    try:
        record.resume()

        # Re-send the invite email with new magic link
        _send_onboarding_invite_email(record)

        flash(_("Onboarding resumed. A new invite has been sent."), "success")

    except Exception as e:
        db.session.rollback()
        flash(_("Error resuming onboarding: %(error)s") % {"error": str(e)}, "error")

    return redirect(url_for("people_bp.onboarding_detail", record_id=record_id))


@blueprint.route("/onboarding/my/check-signature/<task_key>")
@login_required
def onboarding_check_signature(task_key: str):
    """Check if a signing task is complete (polled by wizard)."""
    employee = WorkspaceUser.get_by_user_id(current_user.id)
    if not employee:
        return jsonify({"complete": False})

    record = OnboardingRecord.get_by_member_id(employee.id)
    if not record:
        return jsonify({"complete": False})

    task = record.get_task(task_key)
    return jsonify({"complete": bool(task and task.is_complete)})


@blueprint.route("/onboarding/<int:record_id>/task/<int:task_id>/toggle", methods=["POST"])
@login_required
@admin_required
def onboarding_toggle_task(record_id, task_id):
    """Toggle an admin task completion status."""
    record = OnboardingRecord.get_by_id(record_id)
    if not record:
        return jsonify({"error": "Record not found"}), 404

    task = None
    for t in record.tasks:
        if t.id == task_id:
            task = t
            break

    if not task:
        return jsonify({"error": "Task not found"}), 404

    if task.assignee != TaskAssignee.ADMIN:
        return jsonify({"error": "Can only toggle admin tasks"}), 400

    try:
        if task.status == TaskStatus.COMPLETED:
            task.reset()
        else:
            task.complete()
        return jsonify({"success": True, "status": task.status.value})

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# -----------------------------------------------------------------------------
# Public Routes (Magic Link Authentication)
# -----------------------------------------------------------------------------


@blueprint.route("/onboarding/start/<token>")
def onboarding_start(token):
    """
    Magic link entry point for onboarding.

    This route is PUBLIC - no login required.
    The employee clicks the link in their email, gets logged in automatically,
    and is redirected to the onboarding wizard.
    """
    from flask_login import login_user

    # PUBLIC route: an anonymous new hire has no workspace context, so look the
    # record up by its unique token via the (unscoped) model method.
    record = OnboardingRecord.get_by_token(token)

    if not record:
        flash(_("Invalid or expired onboarding link."), "error")
        return redirect(url_for("core_bp.login"))

    if record.status == OnboardingStatus.CANCELLED:
        flash(_("This onboarding has been cancelled."), "error")
        return redirect(url_for("core_bp.login"))

    if record.status == OnboardingStatus.DRAFT:
        flash(_("This onboarding hasn't been sent yet."), "error")
        return redirect(url_for("core_bp.login"))

    # Get the employee and user
    if not record.member_id:
        flash(_("No employee record found for this onboarding."), "error")
        return redirect(url_for("core_bp.login"))

    # Use the record's relationship — no workspace scope needed on a public route.
    employee = record.member
    if not employee or not employee.user:
        flash(_("Account not found. Please contact HR."), "error")
        return redirect(url_for("core_bp.login"))

    # Log the user in
    login_user(employee.user, remember=True)

    # If onboarding is completed, redirect to password setup (if needed) or dashboard
    if record.status == OnboardingStatus.COMPLETED:
        if employee.user.needs_password_setup:
            return redirect(url_for("people_bp.onboarding_set_password"))
        return redirect(url_for("dashboard_bp.index"))

    # If pending review, let them know
    if record.status == OnboardingStatus.PENDING_REVIEW:
        flash(_("Your onboarding is pending review. You'll be notified when it's approved."), "info")
        if employee.user.needs_password_setup:
            return redirect(url_for("people_bp.onboarding_set_password"))
        return redirect(url_for("dashboard_bp.index"))

    # Redirect to the wizard
    return redirect(url_for("people_bp.onboarding_wizard"))


# -----------------------------------------------------------------------------
# Employee Routes (Wizard)
# -----------------------------------------------------------------------------


@blueprint.route("/onboarding/my")
@login_required
def onboarding_wizard():
    """Employee's onboarding wizard."""
    # Find onboarding record for current user's employee

    employee = WorkspaceUser.get_by_user_id(current_user.id)
    if not employee:
        flash(_("No employee profile found."), "error")
        return redirect(url_for("dashboard_bp.index"))

    record = OnboardingRecord.get_by_member_id(employee.id)
    if not record:
        flash(_("No onboarding in progress."), "info")
        return redirect(url_for("dashboard_bp.index"))

    if record.status == OnboardingStatus.COMPLETED:
        flash(_("Your onboarding has been completed."), "info")
        return redirect(url_for("dashboard_bp.index"))

    if record.status == OnboardingStatus.CANCELLED:
        flash(_("This onboarding has been cancelled."), "error")
        return redirect(url_for("dashboard_bp.index"))

    # Mark as in progress if just started
    if record.status == OnboardingStatus.SENT:
        record.mark_in_progress()

    # Get employee tasks only
    tasks = [t for t in record.tasks if t.assignee == TaskAssignee.EMPLOYEE]

    # Find current task (first incomplete)
    current_task = None
    for task in tasks:
        if not task.is_complete:
            current_task = task
            break

    # Get company settings for the template
    from modules.base.core.models.workspace_settings import WorkspaceSettings
    settings = WorkspaceSettings.get_instance()

    return render_template(
        "people/desktop/onboarding/person_wizard.html",
        record=record,
        tasks=tasks,
        current_task=current_task,
        TaskStatus=TaskStatus,
        settings=settings,
        active_page="onboarding",
        module_home="dashboard_bp.index",
    )


@blueprint.route("/onboarding/my/save", methods=["POST"])
@login_required
def onboarding_save_step():
    """Save wizard step progress (HTMX)."""
    employee = WorkspaceUser.scoped().filter_by(user_id=current_user.id).first()
    if not employee:
        return jsonify({"error": "No employee profile"}), 404

    record = OnboardingRecord.get_by_member_id(employee.id)
    if not record:
        return jsonify({"error": "No onboarding found"}), 404

    task_key = request.form.get("task_key")
    task = record.get_task(task_key)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    try:
        # Get form data as dict
        data = {k: v for k, v in request.form.items() if k != "task_key"}

        # Handle specific task types
        if task_key == "personal_info":
            # phone lives on WorkspaceUser; address / date-of-birth and other
            # personal fields live on the User record (WorkspaceUser has no
            # address/birthday columns — see the mapping in WorkspaceUser.create).
            user = employee.user
            employee.phone = data.get("phone", employee.phone)
            user.address = data.get("address", user.address)
            user.address_2 = data.get("address_2", user.address_2)
            user.city = data.get("city", user.city)
            user.state = data.get("state", user.state)
            user.zip_code = data.get("zip_code", user.zip_code)
            if data.get("birthday"):
                user.birthday = datetime.strptime(data["birthday"], "%Y-%m-%d").date()
            db.session.commit()

        elif task_key == "emergency_contact":
            # Emergency-contact fields live on the User record, not WorkspaceUser.
            user = employee.user
            user.emergency_contact_name = data.get(
                "emergency_contact_name", user.emergency_contact_name
            )
            user.emergency_contact_phone = data.get(
                "emergency_contact_phone", user.emergency_contact_phone
            )
            user.emergency_contact_relationship = data.get(
                "emergency_contact_relationship",
                user.emergency_contact_relationship,
            )
            db.session.commit()

        elif task_key in ("w4", "w9"):
            # Handle tax form upload
            if "tax_form" in request.files:
                file = request.files["tax_form"]
                if file and file.filename:
                    from modules.base.resources.models.attachment import Attachment
                    from modules.base.resources.services import storage

                    # Create attachment record
                    attachment = Attachment.create(
                        filename=file.filename,
                        mime_type=file.content_type,
                        size_bytes=0,  # Will be updated after save
                    )

                    # Save file to attachments directory
                    file_path = storage.save_to_attachments(file, attachment)

                    # Update size
                    import os
                    attachment.size_bytes = os.path.getsize(file_path)

                    # Link to onboarding record
                    record.tax_form_attachment_id = attachment.id
                    db.session.commit()

        # Mark task complete with data
        task.complete(data)

        return jsonify({"success": True, "progress": record.progress_percent})

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@blueprint.route("/onboarding/my/skip/<task_key>", methods=["POST"])
@login_required
def onboarding_skip_step(task_key):
    """Skip an optional wizard step."""
    employee = WorkspaceUser.scoped().filter_by(user_id=current_user.id).first()
    if not employee:
        return jsonify({"error": "No employee profile"}), 404

    record = OnboardingRecord.get_by_member_id(employee.id)
    if not record:
        return jsonify({"error": "No onboarding found"}), 404

    task = record.get_task(task_key)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    if task.required:
        return jsonify({"error": "Cannot skip required task"}), 400

    try:
        task.skip()
        return jsonify({"success": True, "progress": record.progress_percent})

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@blueprint.route("/onboarding/my/submit", methods=["POST"])
@login_required
def onboarding_submit():
    """Submit onboarding for admin review."""
    employee = WorkspaceUser.scoped().filter_by(user_id=current_user.id).first()
    if not employee:
        flash(_("No employee profile found."), "error")
        return redirect(url_for("people_bp.onboarding_wizard"))

    record = OnboardingRecord.get_by_member_id(employee.id)
    if not record:
        flash(_("No onboarding in progress."), "error")
        return redirect(url_for("dashboard_bp.index"))

    if not record.required_tasks_complete:
        flash(_("Please complete all required tasks before submitting."), "error")
        return redirect(url_for("people_bp.onboarding_wizard"))

    try:
        record.submit_for_review()
        flash(
            _("Your onboarding has been submitted for review. You'll be notified when it's approved."),
            "success",
        )
        # Redirect back to wizard which will show pending state
        return redirect(url_for("people_bp.onboarding_wizard"))

    except Exception as e:
        db.session.rollback()
        flash(_("Error submitting onboarding: %(error)s") % {"error": str(e)}, "error")
        return redirect(url_for("people_bp.onboarding_wizard"))


@blueprint.route("/onboarding/set-password", methods=["GET", "POST"])
@login_required
def onboarding_set_password():
    """Set password for users who logged in via magic link."""
    # Check if user needs to set password
    if not current_user.needs_password_setup:
        return redirect(url_for("dashboard_bp.index"))

    if request.method == "POST":
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        # Validate password
        if len(password) < 8:
            flash(_("Password must be at least 8 characters long."), "error")
            return redirect(url_for("people_bp.onboarding_set_password"))

        if password != confirm_password:
            flash(_("Passwords do not match."), "error")
            return redirect(url_for("people_bp.onboarding_set_password"))

        try:
            # Update password
            current_user.password = password
            current_user.needs_password_setup = False
            db.session.commit()

            flash(_("Your password has been set successfully!"), "success")
            return redirect(url_for("dashboard_bp.index"))

        except Exception as e:
            db.session.rollback()
            flash(_("Error setting password: %(error)s") % {"error": str(e)}, "error")
            return redirect(url_for("people_bp.onboarding_set_password"))

    return render_template(
        "people/desktop/onboarding/set_password.html",
        active_page="onboarding",
        module_home="dashboard_bp.index",
    )


# -----------------------------------------------------------------------------
# Settings Routes
# -----------------------------------------------------------------------------


@blueprint.route("/settings")
@login_required
@admin_required
def team_settings():
    """Team settings page with onboarding task templates and other settings."""
    # Check if any custom templates exist
    has_custom = OnboardingTaskTemplate.has_custom_templates()

    w2_templates = None
    contractor_templates = None

    if has_custom:
        # Get all templates including inactive for management
        w2_templates = OnboardingTaskTemplate.get_templates_for_type(
            OnboardingType.W2, include_inactive=True
        )
        contractor_templates = OnboardingTaskTemplate.get_templates_for_type(
            OnboardingType.CONTRACTOR, include_inactive=True
        )

    # Get offboarding task templates (initialize defaults if none exist)
    OffboardingTask.initialize_defaults()
    offboarding_tasks = OffboardingTask.get_all_tasks(include_inactive=True)

    return render_template(
        "people/desktop/settings.html",
        w2_templates=w2_templates,
        contractor_templates=contractor_templates,
        has_custom_templates=has_custom,
        W2_DEFAULTS=W2_TASK_TEMPLATES,
        CONTRACTOR_DEFAULTS=CONTRACTOR_TASK_TEMPLATES,
        OnboardingType=OnboardingType,
        TaskAssignee=TaskAssignee,
        offboarding_tasks=offboarding_tasks,
        active_tab=request.args.get("tab", "onboarding"),
        active_page="settings",
        module_home="dashboard_bp.index",
    )


@blueprint.route("/settings/onboarding/initialize", methods=["POST"])
@login_required
@admin_required
def onboarding_initialize_templates():
    """Initialize task templates from defaults."""
    try:
        initialized = OnboardingTaskTemplate.initialize_defaults()
        if initialized:
            flash(_("Task templates initialized from defaults."), "success")
        else:
            flash(_("Templates already exist."), "info")
    except Exception as e:
        db.session.rollback()
        flash(_("Error initializing templates: %(error)s") % {"error": str(e)}, "error")

    return redirect(url_for("people_bp.team_settings"))


@blueprint.route("/settings/onboarding/template/new", methods=["GET", "POST"])
@login_required
@admin_required
def onboarding_template_new():
    """Create a new task template."""
    if request.method == "POST":
        try:
            OnboardingTaskTemplate.create(
                onboarding_type=OnboardingType[request.form.get("onboarding_type", "W2")],
                task_key=request.form.get("task_key"),
                label=request.form.get("label"),
                description=request.form.get("description") or None,
                assignee=TaskAssignee[request.form.get("assignee", "EMPLOYEE")],
                required=request.form.get("required") == "on",
                order=int(request.form.get("order", 0)),
            )
            flash(_("Task template created."), "success")
            return redirect(url_for("people_bp.team_settings"))

        except Exception as e:
            db.session.rollback()
            flash(_("Error creating template: %(error)s") % {"error": str(e)}, "error")

    return render_template(
        "people/desktop/onboarding/template_form.html",
        template=None,
        OnboardingType=OnboardingType,
        TaskAssignee=TaskAssignee,
        next_order=OnboardingTaskTemplate.get_next_order_by_type(),
        active_page="settings",
        module_home="dashboard_bp.index",
    )


@blueprint.route("/settings/onboarding/template/<int:template_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def onboarding_template_edit(template_id):
    """Edit an existing task template."""
    template = OnboardingTaskTemplate.scoped().get_or_404(template_id)

    if request.method == "POST":
        try:
            template.update(
                onboarding_type=OnboardingType[request.form.get("onboarding_type", "W2")],
                task_key=request.form.get("task_key"),
                label=request.form.get("label"),
                description=request.form.get("description") or None,
                assignee=TaskAssignee[request.form.get("assignee", "EMPLOYEE")],
                required=request.form.get("required") == "on",
                order=int(request.form.get("order", 0)),
                active=request.form.get("active") == "on",
            )
            flash(_("Task template updated."), "success")
            return redirect(url_for("people_bp.team_settings"))

        except Exception as e:
            db.session.rollback()
            flash(_("Error updating template: %(error)s") % {"error": str(e)}, "error")

    return render_template(
        "people/desktop/onboarding/template_form.html",
        template=template,
        OnboardingType=OnboardingType,
        TaskAssignee=TaskAssignee,
        active_page="settings",
        module_home="dashboard_bp.index",
    )


@blueprint.route("/settings/onboarding/template/<int:template_id>/delete", methods=["POST"])
@login_required
@admin_required
def onboarding_template_delete(template_id):
    """Delete a task template."""
    template = OnboardingTaskTemplate.scoped().get_or_404(template_id)

    try:
        template.delete()
        flash(_("Task template deleted."), "success")
    except Exception as e:
        db.session.rollback()
        flash(_("Error deleting template: %(error)s") % {"error": str(e)}, "error")

    return redirect(url_for("people_bp.team_settings"))


@blueprint.route("/settings/onboarding/reset", methods=["POST"])
@login_required
@admin_required
def onboarding_reset_templates():
    """Reset all templates to defaults."""
    try:
        # Delete all existing templates
        OnboardingTaskTemplate.scoped().delete()
        db.session.commit()

        # Re-initialize from defaults
        OnboardingTaskTemplate.initialize_defaults()
        flash(_("Task templates reset to defaults."), "success")

    except Exception as e:
        db.session.rollback()
        flash(_("Error resetting templates: %(error)s") % {"error": str(e)}, "error")

    return redirect(url_for("people_bp.team_settings"))
