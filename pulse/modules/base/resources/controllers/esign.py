# -----------------------------------------------------------------------------
# sparQ - Resources Module - E-Sign Admin Controller
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""Admin routes for managing e-signature requests."""

import os

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required

from system.auth.decorators import admin_required
from system.i18n.translation import translate as _

from ..models.signature_request import SignatureRequest
from ..models.signature_recipient import SignatureRecipient
from ..models.signature_audit_log import SignatureAuditLog
from ..models.settings import ResourcesSettings
from ..services.esign import ESignService
from ..services.storage import get_attachment_path


esign_blueprint = Blueprint(
    "resources_esign_bp",
    __name__,
    template_folder="../views/templates",
)


def is_htmx_request() -> bool:
    """Check if request is from HTMX."""
    return request.headers.get("HX-Request") == "true"


# -----------------------------------------------------------------------------
# E-Sign Request List & Detail
# -----------------------------------------------------------------------------


@esign_blueprint.route("/")
@login_required
@admin_required
def index():
    """List all signature requests (admin only)."""
    status_filter = request.args.get("status")

    if status_filter:
        requests = SignatureRequest.get_all(status=status_filter)
    else:
        requests = SignatureRequest.get_all()

    # Get counts for filter tabs
    all_count = len(SignatureRequest.get_all())
    pending_count = len(SignatureRequest.get_all(status="pending"))
    completed_count = len(SignatureRequest.get_all(status="completed"))

    return render_template(
        "resources/desktop/esign/index.html",
        requests=requests,
        status_filter=status_filter,
        all_count=all_count,
        pending_count=pending_count,
        completed_count=completed_count,
        active_page="resources",
        module_home="dashboard_bp.index",
    )


@esign_blueprint.route("/<uuid>")
@login_required
@admin_required
def detail(uuid: str):
    """View signature request details (admin only)."""
    sig_request = SignatureRequest.get_by_uuid(uuid)
    if not sig_request:
        flash(_("Signature request not found"), "error")
        return redirect(url_for("resources_esign_bp.index"))

    # Get audit logs
    audit_logs = SignatureAuditLog.get_for_request(sig_request.id)

    return render_template(
        "resources/desktop/esign/detail.html",
        sig_request=sig_request,
        audit_logs=audit_logs,
        active_page="resources",
        module_home="dashboard_bp.index",
    )


# -----------------------------------------------------------------------------
# E-Sign Actions
# -----------------------------------------------------------------------------


@esign_blueprint.route("/create", methods=["POST"])
@login_required
@admin_required
def create():
    """Create a new signature request from the admin UI (admin only)."""
    import tempfile

    title = request.form.get("title", "").strip()
    signer_name = request.form.get("signer_name", "").strip()
    signer_email = request.form.get("signer_email", "").strip()
    message = request.form.get("message", "").strip() or None
    document = request.files.get("document")

    # Validate inputs
    if not title or not signer_name or not signer_email:
        flash(_("Please fill in all required fields"), "error")
        return redirect(url_for("resources_esign_bp.index"))

    if not document or not document.filename:
        flash(_("Please upload a PDF document"), "error")
        return redirect(url_for("resources_esign_bp.index"))

    if not document.filename.lower().endswith(".pdf"):
        flash(_("Only PDF files are supported"), "error")
        return redirect(url_for("resources_esign_bp.index"))

    # Save uploaded file to temp location
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        document.save(tmp.name)
        tmp_path = tmp.name

    try:
        # Create the signature request
        sig_request = ESignService.create_request(
            document_path=tmp_path,
            title=title,
            signers=[{"email": signer_email, "name": signer_name}],
            message=message,
            created_by_id=current_user.id,
        )

        flash(_("Signature request sent to %(email)s") % {"email": signer_email}, "success")
        return redirect(url_for("resources_esign_bp.detail", uuid=sig_request.uuid))

    except Exception as e:
        flash(_("Failed to create request: %(error)s") % {"error": str(e)}, "error")
        return redirect(url_for("resources_esign_bp.index"))
    finally:
        # Clean up temp file
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@esign_blueprint.route("/<uuid>/cancel", methods=["POST"])
@login_required
@admin_required
def cancel(uuid: str):
    """Cancel a signature request (admin only)."""
    sig_request = SignatureRequest.get_by_uuid(uuid)
    if not sig_request:
        flash(_("Signature request not found"), "error")
        return redirect(url_for("resources_esign_bp.index"))

    if ESignService.cancel(sig_request, current_user.id):
        flash(_("Signature request cancelled"), "success")
    else:
        flash(_("Cannot cancel this request"), "error")

    return redirect(url_for("resources_esign_bp.detail", uuid=uuid))


@esign_blueprint.route("/<uuid>/retry-complete", methods=["POST"])
@login_required
@admin_required
def retry_complete(uuid: str):
    """Retry completion for a stuck request (admin only)."""
    sig_request = SignatureRequest.get_by_uuid(uuid)
    if not sig_request:
        flash(_("Signature request not found"), "error")
        return redirect(url_for("resources_esign_bp.index"))

    # Check if all have signed but status is still pending
    if sig_request.status == "pending" and sig_request.all_signed:
        try:
            ESignService._complete_request(sig_request)
            flash(_("Request completed successfully"), "success")
        except Exception as e:
            flash(_("Completion failed: %(error)s") % {"error": str(e)}, "error")
    else:
        flash(_("Cannot retry - either not all signed or already completed"), "error")

    return redirect(url_for("resources_esign_bp.detail", uuid=uuid))


@esign_blueprint.route("/<uuid>/resend/<int:recipient_id>", methods=["POST"])
@login_required
@admin_required
def resend(uuid: str, recipient_id: int):
    """Resend notification to a recipient (admin only)."""
    sig_request = SignatureRequest.get_by_uuid(uuid)
    if not sig_request:
        flash(_("Signature request not found"), "error")
        return redirect(url_for("resources_esign_bp.index"))

    recipient = SignatureRecipient.get_by_id(recipient_id)
    if not recipient or recipient.request_id != sig_request.id:
        flash(_("Recipient not found"), "error")
        return redirect(url_for("resources_esign_bp.detail", uuid=uuid))

    if ESignService.resend_notification(recipient):
        flash(_("Reminder sent to %(email)s") % {"email": recipient.email}, "success")
    else:
        flash(_("Failed to send reminder"), "error")

    return redirect(url_for("resources_esign_bp.detail", uuid=uuid))


@esign_blueprint.route("/<uuid>/download")
@login_required
@admin_required
def download_signed(uuid: str):
    """Download the signed document (admin only)."""
    sig_request = SignatureRequest.get_by_uuid(uuid)
    if not sig_request:
        flash(_("Signature request not found"), "error")
        return redirect(url_for("resources_esign_bp.index"))

    if sig_request.status != "completed" or not sig_request.signed_attachment:
        flash(_("Signed document not available"), "error")
        return redirect(url_for("resources_esign_bp.detail", uuid=uuid))

    file_path = get_attachment_path(sig_request.signed_attachment)
    if not os.path.exists(file_path):
        flash(_("Document file not found"), "error")
        return redirect(url_for("resources_esign_bp.detail", uuid=uuid))

    # Log download
    SignatureAuditLog.log(
        request_id=sig_request.id,
        event_type="downloaded",
        actor_user_id=current_user.id,
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string,
    )

    return send_file(
        file_path,
        as_attachment=True,
        download_name=sig_request.signed_attachment.filename,
    )


@esign_blueprint.route("/<uuid>/download-original")
@login_required
@admin_required
def download_original(uuid: str):
    """Download the original document (admin only)."""
    sig_request = SignatureRequest.get_by_uuid(uuid)
    if not sig_request:
        flash(_("Signature request not found"), "error")
        return redirect(url_for("resources_esign_bp.index"))

    if not sig_request.original_attachment:
        flash(_("Original document not available"), "error")
        return redirect(url_for("resources_esign_bp.detail", uuid=uuid))

    file_path = get_attachment_path(sig_request.original_attachment)
    if not os.path.exists(file_path):
        flash(_("Document file not found"), "error")
        return redirect(url_for("resources_esign_bp.detail", uuid=uuid))

    return send_file(
        file_path,
        as_attachment=True,
        download_name=sig_request.original_attachment.filename,
    )


# -----------------------------------------------------------------------------
# API for Other Modules
# -----------------------------------------------------------------------------


@esign_blueprint.route("/api/create", methods=["POST"])
@login_required
@admin_required
def api_create():
    """
    API endpoint for creating e-sign requests from other modules (admin only).

    This allows other modules to create signature requests and get back
    the signing URL(s) to include in their own emails.

    Form data:
        - document: PDF file upload
        - title: Document title
        - recipient_name: Signer's full name
        - recipient_email: Signer's email
        - message: Optional message to signer
        - context: Optional JSON context (module, entity type, entity ID)

    Returns JSON:
        {
            "success": true,
            "request_uuid": "...",
            "signing_urls": {"email@example.com": "https://..."},
            "expires_at": "2025-02-15"
        }
    """
    import tempfile
    import json as json_module

    # Get form data
    document = request.files.get("document")
    title = request.form.get("title", "").strip()
    recipient_name = request.form.get("recipient_name", "").strip()
    recipient_email = request.form.get("recipient_email", "").strip()
    message = request.form.get("message", "").strip() or None
    context_str = request.form.get("context", "")

    # Validate
    errors = []
    if not document or not document.filename:
        errors.append("Document is required")
    elif not document.filename.lower().endswith(".pdf"):
        errors.append("Only PDF files are supported")
    if not title:
        errors.append("Title is required")
    if not recipient_name:
        errors.append("Recipient name is required")
    if not recipient_email:
        errors.append("Recipient email is required")

    if errors:
        return {"success": False, "errors": errors}, 400

    # Parse context if provided
    context = None
    if context_str:
        try:
            context = json_module.loads(context_str)
        except json_module.JSONDecodeError:
            pass

    # Save to temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        document.save(tmp.name)
        tmp_path = tmp.name

    try:
        # Create signature request WITHOUT sending email
        sig_request = ESignService.create_request(
            document_path=tmp_path,
            title=title,
            signers=[{"email": recipient_email, "name": recipient_name}],
            message=message,
            created_by_id=current_user.id,
            context=context,
            send_email=False,  # Caller will send their own email with the link
        )

        # Get signing URLs
        signing_urls = ESignService.get_signing_urls(sig_request)

        return {
            "success": True,
            "request_uuid": sig_request.uuid,
            "signing_urls": signing_urls,
            "expires_at": sig_request.expires_at.strftime("%Y-%m-%d") if sig_request.expires_at else None,
        }

    except Exception as e:
        return {"success": False, "errors": [str(e)]}, 500
    finally:
        # Clean up temp file
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


# -----------------------------------------------------------------------------
# Settings
# -----------------------------------------------------------------------------


@esign_blueprint.route("/settings", methods=["GET", "POST"])
@login_required
@admin_required
def settings():
    """E-Sign settings page."""
    settings = ResourcesSettings.get()

    if request.method == "POST":
        esign_enabled = request.form.get("esign_enabled") == "on"
        esign_default_expiry_days = int(request.form.get("esign_default_expiry_days", 30))
        esign_reminder_days = int(request.form.get("esign_reminder_days", 3))
        esign_company_name = request.form.get("esign_company_name", "").strip() or None

        ResourcesSettings.update_settings(
            esign_enabled=esign_enabled,
            esign_default_expiry_days=esign_default_expiry_days,
            esign_reminder_days=esign_reminder_days,
            esign_company_name=esign_company_name,
        )

        flash(_("E-Sign settings saved"), "success")
        return redirect(url_for("resources_esign_bp.settings"))

    # Get company name for default
    from modules.base.core.models.workspace_settings import WorkspaceSettings
    company = WorkspaceSettings.get_instance()

    return render_template(
        "resources/desktop/esign/settings.html",
        settings=settings,
        company_name=company.company_name,
        active_page="resources",
        module_home="dashboard_bp.index",
    )
