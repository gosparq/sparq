# -----------------------------------------------------------------------------
# sparQ - PDF Utilities for E-Sign
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""PDF utilities for e-signature: rendering pages and generating certificates."""

import io
import logging
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

logger = logging.getLogger(__name__)


def generate_certificate_pdf(request) -> bytes:
    """
    Generate a signed PDF with certificate page appended.

    For v1, we append a certificate page to the original PDF.
    The certificate contains all signature information and audit data.

    Args:
        request: SignatureRequest with completed signatures

    Returns:
        Bytes of the final signed PDF
    """
    from PyPDF2 import PdfReader, PdfWriter
    from .storage import get_attachment_path

    # Read original PDF
    original_path = get_attachment_path(request.original_attachment)
    original_reader = PdfReader(original_path)

    # Create certificate page
    certificate_bytes = _create_certificate_page(request)
    certificate_reader = PdfReader(io.BytesIO(certificate_bytes))

    # Combine: original pages + certificate page
    writer = PdfWriter()

    # Add all original pages
    for page in original_reader.pages:
        writer.add_page(page)

    # Add certificate page
    for page in certificate_reader.pages:
        writer.add_page(page)

    # Write combined PDF to bytes
    output = io.BytesIO()
    writer.write(output)
    output.seek(0)

    return output.read()


def _create_certificate_page(request) -> bytes:
    """
    Create a signature certificate page.

    Args:
        request: SignatureRequest with signatures

    Returns:
        Bytes of the certificate PDF page
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title",
        parent=styles["Heading1"],
        fontSize=18,
        textColor=colors.HexColor("#1a365d"),
        spaceAfter=20,
        alignment=1,  # Center
    )
    heading_style = ParagraphStyle(
        "Heading",
        parent=styles["Heading2"],
        fontSize=12,
        textColor=colors.HexColor("#374151"),
        spaceBefore=15,
        spaceAfter=8,
    )
    normal_style = ParagraphStyle(
        "Normal",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#4b5563"),
        spaceAfter=4,
    )
    small_style = ParagraphStyle(
        "Small",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.HexColor("#6b7280"),
    )

    elements = []

    # Title
    elements.append(Paragraph("SIGNATURE CERTIFICATE", title_style))
    elements.append(Spacer(1, 10))

    # Horizontal line
    elements.append(
        Table(
            [[""]],
            colWidths=[7 * inch],
            style=TableStyle([("LINEBELOW", (0, 0), (-1, -1), 1, colors.HexColor("#e5e7eb"))]),
        )
    )
    elements.append(Spacer(1, 15))

    # Document Information
    elements.append(Paragraph("Document Information", heading_style))

    doc_info = [
        ["Document Title:", request.title],
        ["Document ID:", request.uuid],
        ["Original Hash (SHA-256):", request.original_document_hash[:32] + "..."],
        ["Created:", request.created_at.strftime("%B %d, %Y at %H:%M UTC") if request.created_at else "N/A"],
        ["Completed:", datetime.utcnow().strftime("%B %d, %Y at %H:%M UTC")],
    ]

    doc_table = Table(
        doc_info,
        colWidths=[1.8 * inch, 5.2 * inch],
        style=TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#374151")),
            ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#4b5563")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]),
    )
    elements.append(doc_table)
    elements.append(Spacer(1, 20))

    # Signatures
    elements.append(Paragraph("Electronic Signatures", heading_style))

    for recipient in request.signed_recipients:
        # Build signature data rows
        sig_data = [
            [Paragraph(f"<b>{recipient.signed_name}</b>", normal_style)],
            [Paragraph(f"Name: {recipient.name}", small_style)],
            [Paragraph(f"Email: {recipient.email}", small_style)],
            [Paragraph(f"Signed: {recipient.signed_at.strftime('%B %d, %Y at %H:%M:%S UTC') if recipient.signed_at else 'N/A'}", small_style)],
            [Paragraph(f"IP Address: {recipient.ip_address or 'N/A'}", small_style)],
        ]

        # Add geolocation if available
        if recipient.has_geolocation:
            if recipient.geo_location_name:
                # Show human-readable location with coordinates
                location_str = f"Location: {recipient.geo_location_name}"
                sig_data.append([Paragraph(location_str, small_style)])
                coords_str = f"Coordinates: {recipient.geo_latitude:.6f}, {recipient.geo_longitude:.6f}"
                if recipient.geo_accuracy:
                    coords_str += f" (±{int(recipient.geo_accuracy)}m)"
                sig_data.append([Paragraph(coords_str, small_style)])
            else:
                # Just show coordinates
                location_str = f"Location: {recipient.geo_latitude:.6f}, {recipient.geo_longitude:.6f}"
                if recipient.geo_accuracy:
                    location_str += f" (±{int(recipient.geo_accuracy)}m accuracy)"
                sig_data.append([Paragraph(location_str, small_style)])

        # Add device info if available
        device = recipient.device_info_dict
        if device:
            browser = device.get("browser", "Unknown")
            os_name = device.get("os", "Unknown")
            sig_data.append([Paragraph(f"Device: {browser} on {os_name}", small_style)])

            timezone = device.get("timezone")
            if timezone:
                sig_data.append([Paragraph(f"Timezone: {timezone}", small_style)])

        sig_data.append([Paragraph("✓ Confirmed intent to electronically sign this document", small_style)])

        sig_table = Table(
            sig_data,
            colWidths=[6.5 * inch],
            style=TableStyle([
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#d1d5db")),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f9fafb")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ]),
        )
        elements.append(sig_table)
        elements.append(Spacer(1, 10))

    # Footer
    elements.append(Spacer(1, 30))
    elements.append(
        Table(
            [[""]],
            colWidths=[7 * inch],
            style=TableStyle([("LINEABOVE", (0, 0), (-1, -1), 1, colors.HexColor("#e5e7eb"))]),
        )
    )
    elements.append(Spacer(1, 10))

    footer_style = ParagraphStyle(
        "Footer",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.HexColor("#9ca3af"),
        alignment=1,
    )
    elements.append(
        Paragraph(
            f"This document was electronically signed using sparQ E-Sign<br/>"
            f"Verify at: /verify/{request.uuid}",
            footer_style,
        )
    )

    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer.read()


def pdf_to_images(pdf_path: str, dpi: int = 150) -> list[bytes]:
    """
    Convert PDF pages to PNG images.

    Uses pypdfium2 (PDFium) for rendering. If not available,
    returns an empty list and the signing page will show a download link instead.

    Args:
        pdf_path: Path to the PDF file
        dpi: Resolution for rendering (default 150)

    Returns:
        List of PNG image bytes, one per page
    """
    try:
        import pypdfium2 as pdfium
        from io import BytesIO

        images = []
        pdf = pdfium.PdfDocument(pdf_path)
        scale = dpi / 72  # 72 is the default PDF DPI

        for page in pdf:
            bitmap = page.render(scale=scale)
            pil_image = bitmap.to_pil()
            buf = BytesIO()
            pil_image.save(buf, format="PNG")
            images.append(buf.getvalue())

        pdf.close()
        return images

    except ImportError:
        logger.warning("pypdfium2 not installed - PDF preview not available")
        return []
    except Exception as e:
        logger.error(f"Error converting PDF to images: {e}")
        return []


def get_pdf_page_count(pdf_path: str) -> int:
    """Get the number of pages in a PDF."""
    try:
        from PyPDF2 import PdfReader

        reader = PdfReader(pdf_path)
        return len(reader.pages)
    except Exception as e:
        logger.error(f"Error getting PDF page count: {e}")
        return 0
