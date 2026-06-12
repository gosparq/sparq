# -----------------------------------------------------------------------------
# sparQ - Resources Module - Public Signing Controller
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""Public routes for document signing (token-based, no login required)."""

import base64
import json
import os

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from system.i18n.translation import translate as _

from ..models.signature_recipient import SignatureRecipient
from ..models.settings import ResourcesSettings
from ..services.esign import ESignService
from ..services.pdf import pdf_to_images, get_pdf_page_count
from system.services.geocoding import reverse_geocode_async


sign_blueprint = Blueprint(
    "resources_sign_bp",
    __name__,
    template_folder="../views/templates",
)


# -----------------------------------------------------------------------------
# Public Signing Routes (Token-Based)
# -----------------------------------------------------------------------------


@sign_blueprint.route("/<token>")
def sign_document(token: str):
    """
    Display document for signing.

    This is a public page - no login required.
    The token provides access to a specific signing request.
    """
    recipient = SignatureRecipient.get_by_token(token)
    if not recipient:
        return render_template("resources/desktop/sign/invalid.html"), 404

    sig_request = recipient.request

    # Check if request is still valid
    if sig_request.status == "cancelled":
        return render_template("resources/desktop/sign/cancelled.html", request=sig_request)

    if sig_request.status == "expired" or sig_request.is_expired:
        if sig_request.status != "expired":
            sig_request.mark_expired()
        return render_template("resources/desktop/sign/expired.html", request=sig_request)

    if sig_request.status == "completed":
        return render_template(
            "resources/desktop/sign/complete.html",
            request=sig_request,
            recipient=recipient,
            already_complete=True,
        )

    # Check if this recipient has already signed
    if recipient.status == "signed":
        return render_template(
            "resources/desktop/sign/complete.html",
            request=sig_request,
            recipient=recipient,
            already_signed=True,
        )

    if recipient.status == "declined":
        return render_template(
            "resources/desktop/sign/declined.html",
            request=sig_request,
            recipient=recipient,
        )

    # Record view
    ESignService.record_view(
        recipient,
        request.remote_addr,
        request.user_agent.string,
    )

    # Get PDF page images
    doc_path = ESignService.get_document_path(sig_request)
    page_images = []
    page_count = 0

    if doc_path and os.path.exists(doc_path):
        page_count = get_pdf_page_count(doc_path)
        # Convert to base64 for embedding in HTML
        raw_images = pdf_to_images(doc_path)
        for img_bytes in raw_images:
            page_images.append(base64.b64encode(img_bytes).decode("utf-8"))

    # Get company name for branding
    settings = ResourcesSettings.get()
    from modules.base.core.models.workspace_settings import WorkspaceSettings
    company = WorkspaceSettings.get_instance()
    company_name = settings.esign_company_name or company.company_name or "sparQ"

    return render_template(
        "resources/desktop/sign/document.html",
        request=sig_request,
        recipient=recipient,
        page_images=page_images,
        page_count=page_count,
        company_name=company_name,
        token=token,
    )


@sign_blueprint.route("/<token>", methods=["POST"])
def submit_signature(token: str):
    """
    Process signature submission.
    """
    recipient = SignatureRecipient.get_by_token(token)
    if not recipient:
        return render_template("resources/desktop/sign/invalid.html"), 404

    sig_request = recipient.request

    # Validate request is still signable
    if sig_request.status not in ("pending",) or not recipient.can_sign:
        flash(_("This document can no longer be signed"), "error")
        return redirect(url_for("resources_sign_bp.sign_document", token=token))

    # Get form data
    signed_name = request.form.get("signed_name", "").strip()
    agree_intent = request.form.get("agree_intent") == "on"

    # Get device/geo data
    device_info = request.form.get("device_info", "")
    geo_latitude = request.form.get("geo_latitude", "")
    geo_longitude = request.form.get("geo_longitude", "")
    geo_accuracy = request.form.get("geo_accuracy", "")

    # Parse geo values (they come as strings from the form)
    try:
        geo_lat = float(geo_latitude) if geo_latitude else None
        geo_lng = float(geo_longitude) if geo_longitude else None
        geo_acc = float(geo_accuracy) if geo_accuracy else None
    except (ValueError, TypeError):
        geo_lat = geo_lng = geo_acc = None

    # Validate
    errors = []
    if not signed_name:
        errors.append(_("Please enter your full legal name"))
    if not agree_intent:
        errors.append(_("You must agree to the electronic signature statement"))
    if geo_lat is None or geo_lng is None:
        errors.append(_("Location is required to sign this document. Please allow location access and try again."))

    if errors:
        for error in errors:
            flash(error, "error")
        return redirect(url_for("resources_sign_bp.sign_document", token=token))

    # Process signature
    success = ESignService.sign(
        recipient,
        signed_name,
        request.remote_addr,
        request.user_agent.string,
        device_info=device_info or None,
        geo_latitude=geo_lat,
        geo_longitude=geo_lng,
        geo_accuracy=geo_acc,
    )

    if success:
        # Async reverse geocode to get human-readable address
        if geo_lat and geo_lng:
            _start_reverse_geocode(recipient.id, geo_lat, geo_lng, host=request.host)

        # Check if this signing was part of onboarding
        is_onboarding = False
        if sig_request.context:
            try:
                context = json.loads(sig_request.context)
                is_onboarding = "onboarding_id" in context
            except (json.JSONDecodeError, TypeError):
                pass

        return render_template(
            "resources/desktop/sign/complete.html",
            request=sig_request,
            recipient=recipient,
            is_onboarding=is_onboarding,
        )
    else:
        flash(_("Failed to process signature. Please try again."), "error")
        return redirect(url_for("resources_sign_bp.sign_document", token=token))


def _start_reverse_geocode(recipient_id: int, latitude: float, longitude: float, host: str | None = None) -> None:
    """Start async reverse geocoding for a recipient.

    Updates the recipient's geo_location_name field with the human-readable address.
    """
    def update_location(address: str | None) -> None:
        if address:
            SignatureRecipient.set_geo_location_name(recipient_id, address)

    reverse_geocode_async(latitude, longitude, update_location, host=host)


@sign_blueprint.route("/<token>/decline", methods=["POST"])
def decline_signature(token: str):
    """
    Decline to sign the document.
    """
    recipient = SignatureRecipient.get_by_token(token)
    if not recipient:
        return render_template("resources/desktop/sign/invalid.html"), 404

    if recipient.can_sign:
        ESignService.decline(
            recipient,
            request.remote_addr,
            request.user_agent.string,
        )

    return render_template(
        "resources/desktop/sign/declined.html",
        request=recipient.request,
        recipient=recipient,
    )


@sign_blueprint.route("/<token>/download")
def download_document(token: str):
    """
    Allow signer to download the original document for review.
    """
    from flask import send_file

    recipient = SignatureRecipient.get_by_token(token)
    if not recipient:
        abort(404)

    sig_request = recipient.request
    doc_path = ESignService.get_document_path(sig_request)

    if not doc_path or not os.path.exists(doc_path):
        abort(404)

    return send_file(
        doc_path,
        as_attachment=True,
        download_name=sig_request.original_attachment.filename,
    )
