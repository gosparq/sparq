# -----------------------------------------------------------------------------
# sparQ - E-Sign Service
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""E-signature service for document signing workflows."""

import base64
import hashlib
import json
import logging
import os
from typing import TypedDict

from flask import url_for

from system.email.service import send_email_async, is_configured as email_is_configured
from system.i18n.translation import translate as _

from ..models.attachment import Attachment
from ..models.settings import ResourcesSettings
from ..models.signature_audit_log import SignatureAuditLog
from ..models.signature_recipient import SignatureRecipient
from ..models.signature_request import SignatureRequest
from .storage import get_attachment_path

logger = logging.getLogger(__name__)


class EmailAttachment(TypedDict):
    """Type definition for email attachment structure."""

    filename: str
    content: str  # Base64-encoded content
    content_type: str


class ESignService:
    """Public API for e-signature functionality."""

    @staticmethod
    def create_request(
        document_path: str | None = None,
        title: str = "",
        signers: list[dict] | None = None,
        message: str | None = None,
        created_by_id: int | None = None,
        created_by=None,  # User object (convenience)
        context: dict | None = None,
        callback_url: str | None = None,
        expires_days: int | None = None,
        send_email: bool = True,
        attachment: "Attachment | None" = None,  # Use existing attachment
    ) -> SignatureRequest:
        """
        Create a signature request and optionally send to signers.

        Args:
            document_path: Path to the PDF document to sign (if no attachment provided)
            title: Title for the signature request
            signers: List of dicts with 'email' and 'name' keys
            message: Optional message to include in email
            created_by_id: User ID of requester
            created_by: User object (alternative to created_by_id)
            context: Optional context dict (stored as JSON)
            callback_url: Optional URL to POST when complete
            expires_days: Days until expiration (uses settings default if not specified)
            send_email: If True (default), sends e-sign notification emails.
                       If False, caller is responsible for sending emails with signing links.
            attachment: Use an existing Attachment instead of document_path

        Returns:
            SignatureRequest instance
        """
        if signers is None:
            signers = []

        settings = ResourcesSettings.get()

        if expires_days is None:
            expires_days = settings.esign_default_expiry_days or 30

        # Handle created_by as User object
        if created_by and not created_by_id:
            created_by_id = created_by.id

        # Use existing attachment or create from document_path
        if attachment:
            # Use existing attachment - read and hash the file
            doc_path = get_attachment_path(attachment)
            with open(doc_path, "rb") as f:
                document_bytes = f.read()
            document_hash = hashlib.sha256(document_bytes).hexdigest()
        elif document_path:
            # Read and hash the document
            with open(document_path, "rb") as f:
                document_bytes = f.read()
            document_hash = hashlib.sha256(document_bytes).hexdigest()

            # Create attachment for original document
            filename = os.path.basename(document_path)
            attachment = Attachment.create(
                filename=filename,
                mime_type="application/pdf",
                size_bytes=len(document_bytes),
            )

            # Save document to attachments directory
            dest_path = get_attachment_path(attachment)
            with open(dest_path, "wb") as f:
                f.write(document_bytes)
        else:
            raise ValueError("Either document_path or attachment must be provided")

        # Create signature request
        request = SignatureRequest.create(
            title=title,
            original_attachment_id=attachment.id,
            document_hash=document_hash,
            created_by_id=created_by_id,
            message=message,
            context=json.dumps(context) if context else None,
            callback_url=callback_url,
            expires_days=expires_days,
        )

        # Create recipients
        for i, signer in enumerate(signers):
            SignatureRecipient.create(
                request_id=request.id,
                email=signer["email"],
                name=signer["name"],
                role=signer.get("role", "signer"),
                order=i,
            )

        # Log creation
        SignatureAuditLog.log(
            request_id=request.id,
            event_type="created",
            actor_user_id=created_by_id,
            details={"title": title, "signers": [s["email"] for s in signers]},
        )

        # Mark as pending
        request.mark_pending()

        # Send notifications if requested
        if send_email:
            ESignService._send_notifications(request)

        return request

    @staticmethod
    def get_signing_url(recipient: SignatureRecipient) -> str:
        """
        Get the signing URL for a recipient.

        Use this when you want to include the signing link in your own email
        instead of using the default e-sign notification email.

        Args:
            recipient: The SignatureRecipient to get URL for

        Returns:
            Full signing URL
        """
        return url_for(
            "resources_sign_bp.sign_document",
            token=recipient.token,
            _external=True,
        )

    @staticmethod
    def get_signing_urls(request: SignatureRequest) -> dict[str, str]:
        """
        Get signing URLs for all recipients of a request.

        Returns:
            Dict mapping recipient email to their signing URL
        """
        return {
            recipient.email: ESignService.get_signing_url(recipient)
            for recipient in request.recipients
        }

    @staticmethod
    def _send_notifications(request: SignatureRequest) -> None:
        """Send email notifications to all pending recipients."""
        if not email_is_configured():
            logger.warning("Email not configured - skipping e-sign notifications")
            return

        from modules.base.core.models.workspace_settings import WorkspaceSettings

        company = WorkspaceSettings.get_instance()
        company_name = company.company_name or "sparQ"

        for recipient in request.recipients:
            if recipient.status in ("pending", "viewed") and recipient.role == "signer":
                ESignService._send_signing_email(request, recipient, company_name)

    @staticmethod
    def _send_signing_email(
        request: SignatureRequest, recipient: SignatureRecipient, company_name: str
    ) -> bool:
        """Send signing email to a recipient."""
        try:
            # Build signing URL
            sign_url = url_for(
                "resources_sign_bp.sign_document",
                token=recipient.token,
                _external=True,
            )

            subject = f"Signature requested: {request.title}"

            html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background-color: #1a365d; padding: 30px; border-radius: 8px 8px 0 0;">
            <h1 style="margin: 0; color: white; font-size: 24px;">{company_name}</h1>
            <p style="margin: 10px 0 0 0; color: rgba(255,255,255,0.8); font-size: 16px;">Document Signature Request</p>
        </div>

        <div style="background-color: white; padding: 30px; border-radius: 0 0 8px 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <p style="color: #374151; font-size: 16px; margin-top: 0;">
                Hello {recipient.name},
            </p>

            <p style="color: #374151; font-size: 16px;">
                You have been requested to sign the following document:
            </p>

            <div style="background-color: #f9fafb; padding: 20px; border-radius: 6px; margin: 20px 0;">
                <p style="margin: 0; color: #111827; font-size: 16px;"><strong>{request.title}</strong></p>
                {f'<p style="margin: 10px 0 0 0; color: #6b7280; font-size: 14px;">{request.message}</p>' if request.message else ''}
            </div>

            <div style="margin: 30px 0; text-align: center;">
                <a href="{sign_url}" style="display: inline-block; background-color: #2563eb; color: white; padding: 14px 32px; font-size: 16px; font-weight: 600; text-decoration: none; border-radius: 6px;">
                    Review & Sign Document
                </a>
            </div>

            <p style="color: #6b7280; font-size: 14px; text-align: center;">
                This link will expire on {request.expires_at.strftime('%B %d, %Y') if request.expires_at else 'N/A'}
            </p>

            <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb;">
                <p style="color: #6b7280; font-size: 13px; margin: 0;">
                    If you did not expect this email, you can safely ignore it.
                </p>
            </div>
        </div>

        <p style="margin-top: 15px; text-align: center; color: #9ca3af; font-size: 11px;">
            Powered by <a href="https://www.gosparq.com?ref=email" style="color: #9ca3af; text-decoration: none;">sparQ</a>
        </p>
    </div>
</body>
</html>
"""

            text_body = f"""
{company_name}
Document Signature Request
{'=' * 50}

Hello {recipient.name},

You have been requested to sign the following document:

{request.title}
{request.message or ''}

Review & Sign Document:
{sign_url}

This link will expire on {request.expires_at.strftime('%B %d, %Y') if request.expires_at else 'N/A'}

If you did not expect this email, you can safely ignore it.
"""

            # Send email asynchronously (fire-and-forget)
            send_email_async(recipient.email, subject, html_body, text_body)

            # Record notification immediately (email is queued)
            recipient.record_notification()
            SignatureAuditLog.log(
                request_id=request.id,
                event_type="sent",
                actor_email=recipient.email,
                recipient_id=recipient.id,
            )

            return True

        except Exception as e:
            logger.error(f"Failed to send signing email: {e}")
            return False

    @staticmethod
    def get_request(uuid: str) -> SignatureRequest | None:
        """Get request by public UUID."""
        return SignatureRequest.get_by_uuid(uuid)

    @staticmethod
    def get_recipient_by_token(token: str) -> SignatureRecipient | None:
        """Get recipient by access token."""
        return SignatureRecipient.get_by_token(token)

    @staticmethod
    def record_view(recipient: SignatureRecipient, ip: str, user_agent: str) -> None:
        """Record that a recipient viewed the document."""
        recipient.mark_viewed()
        SignatureAuditLog.log(
            request_id=recipient.request_id,
            event_type="viewed",
            actor_email=recipient.email,
            recipient_id=recipient.id,
            ip_address=ip,
            user_agent=user_agent,
        )

    @staticmethod
    def sign(
        recipient: SignatureRecipient,
        signed_name: str,
        ip: str,
        user_agent: str,
        device_info: str | None = None,
        geo_latitude: float | None = None,
        geo_longitude: float | None = None,
        geo_accuracy: float | None = None,
    ) -> bool:
        """
        Process a signature submission.

        Args:
            recipient: The recipient signing
            signed_name: The typed signature name
            ip: IP address of signer
            user_agent: Browser user agent
            device_info: JSON string with browser/device metadata
            geo_latitude: Latitude from browser geolocation
            geo_longitude: Longitude from browser geolocation
            geo_accuracy: Accuracy in meters from browser geolocation

        Returns:
            True if successful
        """
        if not recipient.can_sign:
            return False

        request = recipient.request

        # Check if request is still valid
        if request.status != "pending" or request.is_expired:
            return False

        # Record the signature with all metadata
        recipient.mark_signed(
            signed_name,
            ip,
            user_agent,
            device_info=device_info,
            geo_latitude=geo_latitude,
            geo_longitude=geo_longitude,
            geo_accuracy=geo_accuracy,
        )

        # Build details for audit log
        details: dict = {"signed_name": signed_name}
        if geo_latitude and geo_longitude:
            details["location"] = {
                "latitude": geo_latitude,
                "longitude": geo_longitude,
                "accuracy": geo_accuracy,
            }

        # Log the event
        SignatureAuditLog.log(
            request_id=request.id,
            event_type="signed",
            actor_email=recipient.email,
            recipient_id=recipient.id,
            ip_address=ip,
            user_agent=user_agent,
            details=details,
        )

        # Check if all signers have signed
        if request.all_signed:
            try:
                ESignService._complete_request(request)
            except Exception as e:
                logger.error(f"Error completing signature request {request.id}: {e}")
                # Still return True - the signature was recorded even if completion failed

        return True

    @staticmethod
    def _complete_request(request: SignatureRequest) -> None:
        """Complete a request when all signatures are collected."""
        from .pdf import generate_certificate_pdf

        # Generate signed document with certificate
        signed_pdf_bytes = generate_certificate_pdf(request)

        # Create attachment for signed document
        original = request.original_attachment
        signed_filename = f"signed_{original.filename}"
        signed_attachment = Attachment.create(
            filename=signed_filename,
            mime_type="application/pdf",
            size_bytes=len(signed_pdf_bytes),
        )

        # Save signed document
        dest_path = get_attachment_path(signed_attachment)
        with open(dest_path, "wb") as f:
            f.write(signed_pdf_bytes)

        # Mark request as completed
        request.mark_completed(signed_attachment.id)

        # Log completion
        SignatureAuditLog.log(
            request_id=request.id,
            event_type="completed",
            details={"signed_attachment_id": signed_attachment.id},
        )

        # Update onboarding task if this is an onboarding signature
        ESignService._update_onboarding_task(request)

        # Send completion notification to creator
        ESignService._send_completion_notification(request)

        # Send copies to all signers
        ESignService._send_signer_copies(request, signed_attachment, signed_pdf_bytes)

        # Trigger callback if configured
        if request.callback_url:
            ESignService._trigger_callback(request)

    @staticmethod
    def _update_onboarding_task(request: SignatureRequest) -> None:
        """Update onboarding task when a signature request is completed."""
        import json

        if not request.context:
            return

        try:
            context = json.loads(request.context)
        except (json.JSONDecodeError, TypeError):
            return

        onboarding_id = context.get("onboarding_id")
        doc_type = context.get("doc_type")

        if not onboarding_id or not doc_type:
            return

        try:
            from modules.base.people.models.onboarding import OnboardingRecord

            record = OnboardingRecord.get_by_id(onboarding_id)
            if not record:
                logger.warning(f"Onboarding record {onboarding_id} not found")
                return

            # Map doc_type to task_key
            task_key = doc_type  # offer_letter or contract

            task = record.get_task(task_key)
            if task and not task.is_complete:
                task.complete({"signed_request_id": request.id})
                logger.info(
                    f"Updated onboarding task '{task_key}' for record {onboarding_id}"
                )
        except Exception as e:
            logger.error(f"Error updating onboarding task: {e}")

    @staticmethod
    def _send_completion_notification(request: SignatureRequest) -> None:
        """Send notification that all signatures have been collected."""
        if not request.created_by:
            return

        if not email_is_configured():
            return

        from modules.base.core.models.workspace_settings import WorkspaceSettings

        company = WorkspaceSettings.get_instance()
        company_name = company.company_name or "sparQ"

        creator = request.created_by
        download_url = url_for(
            "resources_esign_bp.download_signed",
            uuid=request.uuid,
            _external=True,
        )

        subject = f"Document signed: {request.title}"

        signers_html = ""
        for r in request.signed_recipients:
            signers_html += f"""
            <tr>
                <td style="padding: 8px 0; color: #374151;">{r.name}</td>
                <td style="padding: 8px 0; color: #6b7280;">{r.email}</td>
                <td style="padding: 8px 0; color: #059669;">{r.signed_at.strftime('%b %d, %Y %H:%M') if r.signed_at else 'N/A'}</td>
            </tr>
            """

        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background-color: #1a365d; padding: 30px; border-radius: 8px 8px 0 0;">
            <h1 style="margin: 0; color: white; font-size: 24px;">{company_name}</h1>
            <p style="margin: 10px 0 0 0; color: rgba(255,255,255,0.8); font-size: 16px;">Document Signed</p>
        </div>

        <div style="background-color: white; padding: 30px; border-radius: 0 0 8px 8px;">
            <p style="color: #374151; font-size: 16px; margin-top: 0;">
                All signatures have been collected for:
            </p>

            <div style="background-color: #f9fafb; padding: 20px; border-radius: 6px; margin: 20px 0;">
                <p style="margin: 0; color: #111827; font-size: 16px;"><strong>{request.title}</strong></p>
            </div>

            <h3 style="color: #374151; font-size: 14px; margin-bottom: 10px;">Signatures:</h3>
            <table style="width: 100%; border-collapse: collapse;">
                <thead>
                    <tr style="border-bottom: 1px solid #e5e7eb;">
                        <th style="text-align: left; padding: 8px 0; color: #6b7280; font-size: 13px;">Name</th>
                        <th style="text-align: left; padding: 8px 0; color: #6b7280; font-size: 13px;">Email</th>
                        <th style="text-align: left; padding: 8px 0; color: #6b7280; font-size: 13px;">Signed</th>
                    </tr>
                </thead>
                <tbody>
                    {signers_html}
                </tbody>
            </table>

            <div style="margin: 30px 0; text-align: center;">
                <a href="{download_url}" style="display: inline-block; background-color: #2563eb; color: white; padding: 14px 32px; font-size: 16px; font-weight: 600; text-decoration: none; border-radius: 6px;">
                    Download Signed Document
                </a>
            </div>
        </div>

        <p style="margin-top: 15px; text-align: center; color: #9ca3af; font-size: 11px;">
            Powered by <a href="https://www.gosparq.com?ref=email" style="color: #9ca3af; text-decoration: none;">sparQ</a>
        </p>
    </div>
</body>
</html>
"""

        # Send completion notification asynchronously
        send_email_async(creator.email, subject, html_body)

    @staticmethod
    def _send_signer_copies(
        request: SignatureRequest,
        signed_attachment: "Attachment",
        signed_pdf_bytes: bytes,
    ) -> None:
        """
        Send a copy of the signed document to all signers.

        Called after completion when the signed PDF is ready.
        """
        if not email_is_configured():
            return

        # Get company branding
        from modules.base.core.models.workspace_settings import WorkspaceSettings

        settings = ResourcesSettings.get()
        company = WorkspaceSettings.get_instance()
        company_name = settings.esign_company_name or company.company_name or "sparQ"

        # Base64-encode the PDF bytes we already have
        attachment_data = base64.b64encode(signed_pdf_bytes).decode("utf-8")

        attachment: EmailAttachment = {
            "filename": signed_attachment.filename,
            "content": attachment_data,
            "content_type": "application/pdf",
        }

        # Send to each signer who completed
        for recipient in request.recipients:
            if recipient.status != "signed":
                continue

            ESignService._send_signer_copy_email(
                recipient, request, company_name, attachment
            )

    @staticmethod
    def _send_signer_copy_email(
        recipient: SignatureRecipient,
        request: SignatureRequest,
        company_name: str,
        attachment: EmailAttachment,
    ) -> None:
        """Send signed document copy to an individual signer."""
        subject = _("Your signed document: %(title)s") % {"title": request.title}

        # Translatable strings
        header_text = _("Document Signed Successfully")
        greeting = _("Hello %(name)s,") % {"name": recipient.name or recipient.email}
        thank_you = _("Thank you for signing the following document:")
        signed_on = _("Signed on %(date)s") % {
            "date": recipient.signed_at.strftime("%B %d, %Y at %H:%M UTC")
            if recipient.signed_at
            else "N/A"
        }
        attachment_note = _(
            "A copy of the signed document is attached to this email for your records."
        )
        legal_note = _(
            "This document was electronically signed and is legally binding under the ESIGN Act."
        )

        # Build HTML email (matches existing completion notification style)
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background-color: #1a365d; padding: 30px; border-radius: 8px 8px 0 0;">
            <h1 style="margin: 0; color: white; font-size: 24px;">{company_name}</h1>
            <p style="margin: 10px 0 0 0; color: rgba(255,255,255,0.8); font-size: 16px;">{header_text}</p>
        </div>

        <div style="background-color: white; padding: 30px; border-radius: 0 0 8px 8px;">
            <p style="color: #374151; font-size: 16px; margin-top: 0;">
                {greeting}
            </p>

            <p style="color: #374151; font-size: 16px;">
                {thank_you}
            </p>

            <div style="background-color: #f9fafb; padding: 20px; border-radius: 6px; margin: 20px 0;">
                <p style="margin: 0; color: #111827; font-size: 16px;"><strong>{request.title}</strong></p>
                <p style="margin: 5px 0 0 0; color: #6b7280; font-size: 14px;">
                    {signed_on}
                </p>
            </div>

            <p style="color: #374151; font-size: 16px;">
                {attachment_note}
            </p>

            <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb;">
                <p style="color: #6b7280; font-size: 13px; margin: 0;">
                    {legal_note}
                </p>
            </div>
        </div>

        <p style="margin-top: 15px; text-align: center; color: #9ca3af; font-size: 11px;">
            Powered by <a href="https://www.gosparq.com?ref=email" style="color: #9ca3af; text-decoration: none;">sparQ</a>
        </p>
    </div>
</body>
</html>
"""

        text_body = f"""
{company_name} - {header_text}

{greeting}

{thank_you} {request.title}
{signed_on}

{attachment_note}

{legal_note}
"""

        send_email_async(recipient.email, subject, html_body, text_body, [attachment])

    @staticmethod
    def _trigger_callback(request: SignatureRequest) -> None:
        """Trigger callback URL when request is complete."""
        # This would POST to the callback URL
        # For now, we'll just log it - could be enhanced with actual HTTP call
        logger.info(f"Would trigger callback to {request.callback_url} for request {request.uuid}")

    @staticmethod
    def decline(recipient: SignatureRecipient, ip: str, user_agent: str) -> bool:
        """Record that a recipient declined to sign."""
        if not recipient.can_sign:
            return False

        recipient.mark_declined()

        SignatureAuditLog.log(
            request_id=recipient.request_id,
            event_type="declined",
            actor_email=recipient.email,
            recipient_id=recipient.id,
            ip_address=ip,
            user_agent=user_agent,
        )

        return True

    @staticmethod
    def cancel(request: SignatureRequest, user_id: int | None = None) -> bool:
        """Cancel a pending request."""
        if request.status not in ("draft", "pending"):
            return False

        request.mark_cancelled()

        SignatureAuditLog.log(
            request_id=request.id,
            event_type="cancelled",
            actor_user_id=user_id,
        )

        return True

    @staticmethod
    def resend_notification(recipient: SignatureRecipient) -> bool:
        """Resend notification email to a recipient."""
        if recipient.status == "signed":
            return False

        from modules.base.core.models.workspace_settings import WorkspaceSettings

        company = WorkspaceSettings.get_instance()
        company_name = company.company_name or "sparQ"

        result = ESignService._send_signing_email(
            recipient.request, recipient, company_name
        )

        if result:
            SignatureAuditLog.log(
                request_id=recipient.request_id,
                event_type="reminder_sent",
                recipient_id=recipient.id,
            )

        return result

    @staticmethod
    def get_document_path(request: SignatureRequest) -> str | None:
        """Get the path to the original document."""
        if request.original_attachment:
            return get_attachment_path(request.original_attachment)
        return None

    @staticmethod
    def get_signed_document_path(request: SignatureRequest) -> str | None:
        """Get the path to the signed document."""
        if request.signed_attachment:
            return get_attachment_path(request.signed_attachment)
        return None
