# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     PDF generation service using ReportLab for document creation.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

"""PDF generation service using ReportLab (pure Python).

This module provides professional PDF generation for business documents
with consistent styling, company branding, and proper formatting.

Functions:
    generate_quote_pdf: Create a PDF for customer quotes.
    generate_invoice_pdf: Create a PDF for invoices with optional payment instructions.
    generate_job_pdf: Create a PDF summarizing a job with line items and visits.
    generate_request_pdf: Create a PDF for service requests.

The generated PDFs include:
- Company header with contact info
- Customer/contact information
- Line items table with quantities and pricing
- Subtotals, taxes, and totals
- Notes and terms sections
- Professional footer with branding

Example:
    Generate an invoice PDF::

        from system.pdf.service import generate_invoice_pdf

        pdf_bytes = generate_invoice_pdf(
            invoice,
            company_settings,
            payment_instructions="Wire transfer to Account #12345"
        )

        # Save to file
        with open("invoice.pdf", "wb") as f:
            f.write(pdf_bytes)
"""

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)


def _fmt_dt(dt, fmt: str, company_settings) -> str:
    """Format a datetime converting from UTC to company timezone."""
    if not dt:
        return "-"
    try:
        import pytz

        tz_name = getattr(company_settings, "timezone", None) or "America/Chicago"
        local_tz = pytz.timezone(tz_name)
        if getattr(dt, "tzinfo", None) is None:
            dt = pytz.UTC.localize(dt)
        return dt.astimezone(local_tz).strftime(fmt)
    except Exception:
        return dt.strftime(fmt)


def _get_styles():
    """Get custom paragraph styles."""
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name='CompanyName',
        fontSize=16,
        fontName='Helvetica-Bold',
        textColor=colors.HexColor('#1a365d'),
        spaceAfter=6,
        leading=18
    ))

    styles.add(ParagraphStyle(
        name='DocTitle',
        fontSize=20,
        fontName='Helvetica-Bold',
        textColor=colors.HexColor('#1a365d'),
        alignment=2,  # Right align
        leading=24
    ))

    styles.add(ParagraphStyle(
        name='DocNumber',
        fontSize=10,
        textColor=colors.HexColor('#666666'),
        alignment=2,
        spaceBefore=4
    ))

    styles.add(ParagraphStyle(
        name='SectionHeader',
        fontSize=10,
        fontName='Helvetica-Bold',
        textColor=colors.HexColor('#666666'),
        spaceAfter=8,
        spaceBefore=4
    ))

    styles.add(ParagraphStyle(
        name='ContactName',
        fontSize=11,
        fontName='Helvetica-Bold',
        spaceAfter=4
    ))

    styles.add(ParagraphStyle(
        name='SmallText',
        fontSize=9,
        textColor=colors.HexColor('#666666'),
        leading=12
    ))

    styles.add(ParagraphStyle(
        name='InfoText',
        fontSize=10,
        leading=14,
        spaceAfter=2
    ))

    styles.add(ParagraphStyle(
        name='Footer',
        fontSize=9,
        textColor=colors.HexColor('#666666'),
        alignment=1  # Center
    ))

    return styles


def _format_currency(value) -> str:
    """Format a value as currency."""
    if value is None:
        return "$0.00"
    return f"${float(value):,.2f}"


def _create_header(company, doc_type: str, doc_number: str, styles) -> list:
    """Create the document header with company info and document title."""
    elements = []

    # Build header table (company info on left, doc info on right)
    company_name = company.company_name if company else "Company Name"

    # Build left column with company info
    left_content = [Paragraph(company_name, styles['CompanyName'])]

    # Build right column with doc type and number
    right_content = [
        Paragraph(doc_type.upper(), styles['DocTitle']),
        Spacer(1, 4),
        Paragraph(doc_number, styles['DocNumber'])
    ]

    header_data = [[left_content, right_content]]
    header_table = Table(header_data, colWidths=[4.5*inch, 2.5*inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
    ]))

    elements.append(header_table)
    elements.append(Spacer(1, 0.15*inch))
    elements.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#1a365d')))
    elements.append(Spacer(1, 0.35*inch))

    return elements


def _create_info_section(left_title: str, left_content: list, right_title: str, right_content: list, styles) -> list:
    """Create a two-column info section."""
    elements = []

    left_paras = [Paragraph(f"<b>{left_title}</b>", styles['SectionHeader'])]
    left_paras.append(Spacer(1, 4))
    for item in left_content:
        left_paras.append(Paragraph(item, styles['InfoText']))

    right_paras = [Paragraph(f"<b>{right_title}</b>", styles['SectionHeader'])]
    right_paras.append(Spacer(1, 4))
    for label, value in right_content:
        right_paras.append(Paragraph(f"<font color='#666666'>{label}:</font> {value}", styles['InfoText']))

    info_data = [[left_paras, right_paras]]
    info_table = Table(info_data, colWidths=[3.5*inch, 3.5*inch])
    info_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))

    elements.append(info_table)
    elements.append(Spacer(1, 0.35*inch))

    return elements


def _create_line_items_table(headers: list, rows: list, totals: list) -> Table:
    """Create a styled line items table."""
    # Header row
    data = [headers]

    # Data rows
    for row in rows:
        data.append(row)

    # Calculate column widths based on number of columns
    if len(headers) == 4:
        col_widths = [3.5*inch, 1*inch, 1.25*inch, 1.25*inch]
    else:
        col_widths = [3*inch, 0.8*inch, 1.2*inch, 0.8*inch, 1.2*inch]

    table = Table(data, colWidths=col_widths)

    style = [
        # Header styling
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a365d')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('ALIGN', (0, 0), (-1, 0), 'LEFT'),
        ('ALIGN', (1, 0), (-1, 0), 'CENTER'),
        ('ALIGN', (-1, 0), (-1, 0), 'RIGHT'),
        ('ALIGN', (-2, 0), (-2, 0), 'RIGHT'),

        # Data styling
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('ALIGN', (1, 1), (1, -1), 'CENTER'),
        ('ALIGN', (-1, 1), (-1, -1), 'RIGHT'),
        ('ALIGN', (-2, 1), (-2, -1), 'RIGHT'),

        # Grid
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]

    table.setStyle(TableStyle(style))
    return table


def _create_totals_table(totals: list) -> Table:
    """Create a right-aligned totals table."""
    data = []
    for label, value, is_bold in totals:
        if is_bold:
            data.append([Paragraph(f"<b>{label}</b>", ParagraphStyle('TotalLabel', fontSize=12, alignment=2)),
                        Paragraph(f"<b>{value}</b>", ParagraphStyle('TotalValue', fontSize=12, alignment=2))])
        else:
            data.append([label, value])

    table = Table(data, colWidths=[1.5*inch, 1.25*inch])
    table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#666666')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    return table


def generate_quote_pdf(quote, company) -> bytes:
    """Generate a PDF for a quote."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                           leftMargin=0.75*inch, rightMargin=0.75*inch,
                           topMargin=0.75*inch, bottomMargin=0.75*inch)
    styles = _get_styles()
    elements = []

    # Header
    elements.extend(_create_header(company, "Quote", quote.quote_number, styles))

    # Info section
    left_content = [f"<b>{quote.contact.display_name}</b>"]
    if quote.contact.email:
        left_content.append(quote.contact.email)
    if quote.contact.phone:
        left_content.append(quote.contact.phone)
    if quote.service_location:
        left_content.append("")
        left_content.append("<b>Service Location:</b>")
        left_content.append(quote.service_location.name)
        left_content.append(quote.service_location.full_address)

    right_content = [
        ("Quote Title", quote.title),
        ("Date", _fmt_dt(quote.created_at, '%B %d, %Y', company) if quote.created_at else '-'),
        ("Valid Until", quote.valid_until.strftime('%B %d, %Y') if quote.valid_until else '-'),
    ]
    if quote.accepted_at:
        right_content.append(("Accepted", _fmt_dt(quote.accepted_at, '%B %d, %Y', company)))

    elements.extend(_create_info_section("Bill To", left_content, "Quote Details", right_content, styles))

    # Description
    if quote.description:
        elements.append(Paragraph("<b>Description</b>", styles['SectionHeader']))
        elements.append(Paragraph(quote.description, styles['Normal']))
        elements.append(Spacer(1, 0.2*inch))

    # Line items
    headers = ["Description", "Quantity", "Unit Price", "Total"]
    rows = []
    for item in quote.line_items_list:
        desc = item.description
        if item.discount_percent and item.discount_percent > 0:
            desc += f" ({int(item.discount_percent)}% discount)"
        rows.append([
            desc,
            f"{float(item.quantity):.2f} {item.unit}",
            _format_currency(item.unit_price),
            _format_currency(item.line_total)
        ])

    if rows:
        elements.append(_create_line_items_table(headers, rows, []))
    else:
        elements.append(Paragraph("No items", styles['Normal']))

    elements.append(Spacer(1, 0.2*inch))

    # Totals (right aligned)
    totals = [
        ("Subtotal", _format_currency(quote.subtotal), False),
    ]
    if quote.tax_rate and quote.tax_rate > 0:
        totals.append((f"Tax ({float(quote.tax_rate):.2f}%)", _format_currency(quote.tax_amount), False))
    totals.append(("Total", _format_currency(quote.total), True))
    if quote.deposit_required and quote.deposit_amount and quote.deposit_amount > 0:
        totals.append(("Deposit Required", _format_currency(quote.deposit_amount), False))

    totals_wrapper = Table([[Spacer(1, 1), _create_totals_table(totals)]], colWidths=[4.5*inch, 2.75*inch])
    elements.append(totals_wrapper)
    elements.append(Spacer(1, 0.3*inch))

    # Notes
    if quote.customer_notes:
        elements.append(Paragraph("<b>Notes</b>", styles['SectionHeader']))
        elements.append(Paragraph(quote.customer_notes, styles['Normal']))
        elements.append(Spacer(1, 0.2*inch))

    # Terms
    if quote.terms:
        elements.append(Paragraph("<b>Terms & Conditions</b>", styles['SectionHeader']))
        elements.append(Paragraph(quote.terms, styles['SmallText']))
        elements.append(Spacer(1, 0.2*inch))

    # Footer
    elements.append(Spacer(1, 0.3*inch))
    elements.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#1a365d')))
    elements.append(Spacer(1, 0.1*inch))
    elements.append(Paragraph("Thank you for your business!", styles['Footer']))
    elements.append(Spacer(1, 0.15*inch))
    elements.append(Paragraph(
        '<font color="#9ca3af" size="8">Powered by sparQ</font>',
        styles['Footer']
    ))

    doc.build(elements)
    return buffer.getvalue()


def generate_invoice_pdf(invoice, company, payment_instructions: str = None) -> bytes:
    """Generate a PDF for an invoice.

    Args:
        invoice: The invoice object
        company: The company settings object
        payment_instructions: Optional payment instructions text to display
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                           leftMargin=0.75*inch, rightMargin=0.75*inch,
                           topMargin=0.75*inch, bottomMargin=0.75*inch)
    styles = _get_styles()
    elements = []

    # Header
    elements.extend(_create_header(company, "Invoice", invoice.invoice_number, styles))

    # Info section
    left_content = [f"<b>{invoice.contact.display_name}</b>"]
    if invoice.contact.email:
        left_content.append(invoice.contact.email)
    if invoice.contact.phone:
        left_content.append(invoice.contact.phone)
    if invoice.contact.billing_address:
        left_content.append("")
        left_content.append(invoice.contact.billing_address)
        if invoice.contact.billing_address_2:
            left_content.append(invoice.contact.billing_address_2)
        city_line = []
        if invoice.contact.city:
            city_line.append(invoice.contact.city)
        if invoice.contact.state:
            city_line.append(invoice.contact.state)
        if invoice.contact.zip_code:
            city_line.append(invoice.contact.zip_code)
        if city_line:
            left_content.append(", ".join(city_line[:2]) + (" " + city_line[2] if len(city_line) > 2 else ""))

    right_content = [
        ("Invoice Number", invoice.invoice_number),
        ("Issue Date", invoice.issue_date.strftime('%B %d, %Y') if invoice.issue_date else '-'),
        ("Due Date", invoice.due_date.strftime('%B %d, %Y') if invoice.due_date else '-'),
        ("Payment Terms", invoice.payment_terms or 'Net 30'),
    ]
    if invoice.job:
        right_content.append(("Related Job", invoice.job.job_number))

    elements.extend(_create_info_section("Bill To", left_content, "Invoice Details", right_content, styles))

    # Line items
    headers = ["Description", "Qty", "Unit Price", "Total"]
    rows = []
    for item in invoice.line_items_list:
        rows.append([
            item.description,
            f"{float(item.quantity):.2f}",
            _format_currency(item.unit_price),
            _format_currency(item.line_total)
        ])

    if rows:
        elements.append(_create_line_items_table(headers, rows, []))
    else:
        elements.append(Paragraph("No line items", styles['Normal']))

    elements.append(Spacer(1, 0.2*inch))

    # Totals
    totals = [
        ("Subtotal", _format_currency(invoice.subtotal), False),
    ]
    if invoice.tax_rate and invoice.tax_rate > 0:
        totals.append((f"Tax ({float(invoice.tax_rate):.2f}%)", _format_currency(invoice.tax_amount), False))
    totals.append(("Total", _format_currency(invoice.total), True))
    if invoice.amount_paid and invoice.amount_paid > 0:
        totals.append(("Amount Paid", f"-{_format_currency(invoice.amount_paid)}", False))
    totals.append(("Balance Due", _format_currency(invoice.balance_due), True))

    totals_wrapper = Table([[Spacer(1, 1), _create_totals_table(totals)]], colWidths=[4.5*inch, 2.75*inch])
    elements.append(totals_wrapper)
    elements.append(Spacer(1, 0.3*inch))

    # Notes
    if invoice.notes:
        elements.append(Paragraph("<b>Notes</b>", styles['SectionHeader']))
        elements.append(Paragraph(invoice.notes, styles['Normal']))
        elements.append(Spacer(1, 0.2*inch))

    # Payment Instructions
    if payment_instructions and invoice.balance_due > 0:
        elements.append(Paragraph("<b>Payment Instructions</b>", styles['SectionHeader']))
        # Handle multiline text
        for line in payment_instructions.split('\n'):
            if line.strip():
                elements.append(Paragraph(line, styles['Normal']))
            else:
                elements.append(Spacer(1, 0.1*inch))
        elements.append(Spacer(1, 0.2*inch))

    # Footer
    elements.append(Spacer(1, 0.3*inch))
    elements.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#1a365d')))
    elements.append(Spacer(1, 0.1*inch))
    elements.append(Paragraph("Thank you for your business!", styles['Footer']))
    elements.append(Spacer(1, 0.15*inch))
    elements.append(Paragraph(
        '<font color="#9ca3af" size="8">Powered by sparQ</font>',
        styles['Footer']
    ))

    doc.build(elements)
    return buffer.getvalue()


def generate_job_pdf(job, company) -> bytes:
    """Generate a PDF for a job."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                           leftMargin=0.75*inch, rightMargin=0.75*inch,
                           topMargin=0.75*inch, bottomMargin=0.75*inch)
    styles = _get_styles()
    elements = []

    # Header
    elements.extend(_create_header(company, "Job", job.job_number, styles))

    # Info section
    left_content = [f"<b>{job.contact.display_name}</b>"]
    if job.contact.email:
        left_content.append(job.contact.email)
    if job.contact.phone:
        left_content.append(job.contact.phone)
    if job.service_location:
        left_content.append("")
        left_content.append("<b>Service Location:</b>")
        left_content.append(job.service_location.name)
        left_content.append(job.service_location.full_address)

    right_content = [
        ("Job Title", job.title),
        ("Created", _fmt_dt(job.created_at, '%B %d, %Y', company) if job.created_at else '-'),
    ]
    if job.completed_at:
        right_content.append(("Completed", _fmt_dt(job.completed_at, '%B %d, %Y', company)))
    if job.quote:
        right_content.append(("From Quote", job.quote.quote_number))

    elements.extend(_create_info_section("Customer Information", left_content, "Job Details", right_content, styles))

    # Line items
    headers = ["Description", "Quantity", "Unit Price", "Total"]
    rows = []
    for item in job.line_items_list:
        desc = item.description
        if item.discount_percent and item.discount_percent > 0:
            desc += f" ({int(item.discount_percent)}% discount)"
        rows.append([
            desc,
            f"{float(item.quantity):.2f} {item.unit}",
            _format_currency(item.unit_price),
            _format_currency(item.line_total)
        ])

    if rows:
        elements.append(_create_line_items_table(headers, rows, []))
    else:
        elements.append(Paragraph("No items", styles['Normal']))

    elements.append(Spacer(1, 0.2*inch))

    # Totals
    totals = [
        ("Subtotal", _format_currency(job.subtotal), False),
    ]
    if job.tax_rate and job.tax_rate > 0:
        totals.append((f"Tax ({float(job.tax_rate):.2f}%)", _format_currency(job.tax_amount), False))
    totals.append(("Total", _format_currency(job.total), True))

    totals_wrapper = Table([[Spacer(1, 1), _create_totals_table(totals)]], colWidths=[4.5*inch, 2.75*inch])
    elements.append(totals_wrapper)
    elements.append(Spacer(1, 0.3*inch))

    # Visits section
    visits = job.visits.order_by('visit_number').all()
    if visits:
        elements.append(Spacer(1, 0.1*inch))
        elements.append(Paragraph("<b>Visits</b>", styles['SectionHeader']))
        elements.append(Spacer(1, 0.1*inch))
        visit_data = [["#", "Scheduled Date", "Time", "Status"]]
        for v in visits:
            date_str = v.scheduled_date.strftime('%b %d, %Y') if v.scheduled_date else "Unscheduled"
            time_str = v.display_time if hasattr(v, 'display_time') and v.scheduled_start_time else "All day"
            visit_data.append([f"Visit {v.visit_number}", date_str, time_str, v.status.value])

        visit_table = Table(visit_data, colWidths=[1*inch, 2.5*inch, 1.5*inch, 2*inch])
        visit_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f3f4f6')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(visit_table)
        elements.append(Spacer(1, 0.25*inch))

    # Notes
    if job.customer_notes:
        elements.append(Paragraph("<b>Notes</b>", styles['SectionHeader']))
        elements.append(Paragraph(job.customer_notes, styles['Normal']))
        elements.append(Spacer(1, 0.2*inch))

    # Footer
    elements.append(Spacer(1, 0.3*inch))
    elements.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#1a365d')))
    elements.append(Spacer(1, 0.1*inch))
    elements.append(Paragraph("Thank you for your business!", styles['Footer']))
    elements.append(Spacer(1, 0.15*inch))
    elements.append(Paragraph(
        '<font color="#9ca3af" size="8">Powered by sparQ</font>',
        styles['Footer']
    ))

    doc.build(elements)
    return buffer.getvalue()


def generate_request_pdf(request, company) -> bytes:
    """Generate a PDF for a service request."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                           leftMargin=0.75*inch, rightMargin=0.75*inch,
                           topMargin=0.75*inch, bottomMargin=0.75*inch)
    styles = _get_styles()
    elements = []

    # Header
    elements.extend(_create_header(company, "Service Request", request.request_number, styles))

    # Info section
    left_content = [f"<b>{request.contact.display_name}</b>"]
    if request.contact.email:
        left_content.append(request.contact.email)
    if request.contact.phone:
        left_content.append(request.contact.phone)
    if request.service_location:
        left_content.append("")
        left_content.append("<b>Service Location:</b>")
        left_content.append(request.service_location.name)
        left_content.append(request.service_location.full_address)

    right_content = [
        ("Title", request.title),
        ("Status", request.status.value),
        ("Source", request.source.value if request.source else '-'),
        ("Created", _fmt_dt(request.created_at, '%B %d, %Y', company) if request.created_at else '-'),
    ]
    if request.requested_date:
        right_content.append(("Requested Date", request.requested_date.strftime('%B %d, %Y')))
    if request.preferred_time:
        right_content.append(("Preferred Time", request.preferred_time))

    elements.extend(_create_info_section("Customer Information", left_content, "Request Details", right_content, styles))

    # Description
    if request.description:
        elements.append(Paragraph("<b>Description</b>", styles['SectionHeader']))
        elements.append(Spacer(1, 0.1*inch))
        elements.append(Paragraph(request.description, styles['Normal']))
        elements.append(Spacer(1, 0.3*inch))

    # Related Quote (if any)
    if hasattr(request, 'quote') and request.quote:
        elements.append(Paragraph("<b>Related Quote</b>", styles['SectionHeader']))
        elements.append(Spacer(1, 0.1*inch))
        elements.append(Paragraph(
            f"{request.quote.quote_number} - {request.quote.title} (${float(request.quote.total):,.2f})",
            styles['Normal']
        ))
        elements.append(Spacer(1, 0.3*inch))

    # Footer
    elements.append(Spacer(1, 0.3*inch))
    elements.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#1a365d')))
    elements.append(Spacer(1, 0.1*inch))
    elements.append(Paragraph("Thank you for your interest!", styles['Footer']))
    elements.append(Spacer(1, 0.15*inch))
    elements.append(Paragraph(
        '<font color="#9ca3af" size="8">Powered by sparQ</font>',
        styles['Footer']
    ))

    doc.build(elements)
    return buffer.getvalue()


def _download_1099_nec_form(form_path: str) -> bool:
    """Download official IRS 1099-NEC form if not present.

    Returns True if form is available (existing or downloaded), False otherwise.
    """
    import logging
    import os

    import requests

    logger = logging.getLogger(__name__)

    if os.path.exists(form_path):
        return True

    # Ensure forms directory exists
    forms_dir = os.path.dirname(form_path)
    os.makedirs(forms_dir, exist_ok=True)

    # Download from IRS
    irs_url = "https://www.irs.gov/pub/irs-pdf/f1099nec.pdf"
    try:
        logger.info(f"Downloading 1099-NEC form from {irs_url}")
        response = requests.get(irs_url, timeout=30)
        response.raise_for_status()

        with open(form_path, "wb") as f:
            f.write(response.content)

        logger.info(f"1099-NEC form downloaded to {form_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to download 1099-NEC form: {e}")
        return False


def fill_1099_nec_pdf(
    payer_name: str,
    payer_address: str,
    payer_city_state_zip: str,
    payer_tin: str,
    payer_phone: str,
    recipient_name: str,
    recipient_address: str,
    recipient_city_state_zip: str,
    recipient_tin: str,
    tax_year: int,
    compensation: float,
    tax_withheld: float = 0,
    account_number: str = "",
) -> bytes:
    """Fill an IRS 1099-NEC PDF form with Copy B and Copy 2 for the recipient.

    The IRS 1099-NEC PDF contains multiple copies:
    - Page 0: Instructions/Attention page
    - Page 1: Copy A (For IRS - not for recipient)
    - Page 2: Copy 1 (For State Tax Department)
    - Page 3: Copy B (For Recipient's federal records) - INCLUDED
    - Page 4: Instructions for Recipient
    - Page 5: Copy 2 (For recipient's state tax return) - INCLUDED

    This function extracts Copy B and Copy 2 and fills both with identical data,
    producing a 2-page PDF for the contractor.

    SECURITY NOTE: TINs are passed in memory only, never logged or stored.
    The caller is responsible for ensuring TINs are not persisted.

    Args:
        payer_name: Company/payer name
        payer_address: Payer street address
        payer_city_state_zip: Payer city, state, ZIP code
        payer_tin: Payer's EIN (format: XX-XXXXXXX)
        payer_phone: Payer phone number
        recipient_name: Contractor/recipient name
        recipient_address: Recipient street address
        recipient_city_state_zip: Recipient city, state, ZIP code
        recipient_tin: Recipient's SSN or EIN
        tax_year: The tax year (e.g., 2025)
        compensation: Box 1 - Nonemployee compensation amount
        tax_withheld: Box 4 - Federal income tax withheld (default 0)
        account_number: Optional account number for payer's records

    Returns:
        PDF file contents as bytes (2-page PDF with Copy B and Copy 2)

    Raises:
        FileNotFoundError: If the 1099-NEC form template is not found
        ValueError: If required fields are missing
    """
    import logging
    import os

    from PyPDF2 import PdfReader, PdfWriter
    from PyPDF2.generic import IndirectObject, NameObject, TextStringObject

    logger = logging.getLogger(__name__)

    # Locate the blank 1099-NEC form (auto-download if needed)
    form_path = os.path.join(os.path.dirname(__file__), "forms", "f1099nec.pdf")
    if not _download_1099_nec_form(form_path):
        logger.warning(
            f"1099-NEC form not available at {form_path}. Using fallback PDF generation."
        )
        return _generate_1099_nec_fallback(
            payer_name, payer_address, payer_city_state_zip, payer_tin, payer_phone,
            recipient_name, recipient_address, recipient_city_state_zip, recipient_tin,
            tax_year, compensation, tax_withheld, account_number
        )

    # Read the form
    reader = PdfReader(form_path)

    # IRS 1099-NEC PDF page structure (verified via inspection):
    # Page 0: Instructions/Attention page
    # Page 1: Copy A (For IRS)
    # Page 2: Copy 1 (For State Tax Department)
    # Page 3: Copy B (For Recipient - federal records)
    # Page 4: Instructions for Recipient
    # Page 5: Copy 2 (For recipient's state tax return)
    COPY_B_INDEX = 3  # For recipient's federal records
    COPY_2_INDEX = 5  # For recipient's state tax filing

    # Combine payer name, address, and phone into single field (form has one large field)
    payer_info = f"{payer_name}\n{payer_address}\n{payer_city_state_zip}\n{payer_phone}"

    # Field mapping for Copy B and Copy 2 (both use f2_* prefix with their copy path):
    # f2_1: Calendar year (in PgHeader)
    # f2_2: Payer name/address/city/phone (combined field)
    # f2_3: Payer TIN
    # f2_4: Recipient TIN
    # f2_5: Recipient name
    # f2_6: Recipient street address
    # f2_7: Recipient city/state/zip
    # f2_8: Account number
    # f2_9: Box 1 - Nonemployee compensation
    # f2_10: Box 3 - Excess golden parachute (not used)
    # f2_11: Box 4 - Federal income tax withheld

    # All fields to fill (both Copy B and Copy 2)
    fields_to_fill = {
        # Copy B fields
        "topmostSubform[0].CopyB[0].PgHeader[0].CalendarYear[0].f2_1[0]": str(tax_year),
        "topmostSubform[0].CopyB[0].LeftCol[0].f2_2[0]": payer_info,
        "topmostSubform[0].CopyB[0].LeftCol[0].f2_3[0]": payer_tin,
        "topmostSubform[0].CopyB[0].LeftCol[0].f2_4[0]": recipient_tin,
        "topmostSubform[0].CopyB[0].LeftCol[0].f2_5[0]": recipient_name,
        "topmostSubform[0].CopyB[0].LeftCol[0].f2_6[0]": recipient_address,
        "topmostSubform[0].CopyB[0].LeftCol[0].f2_7[0]": recipient_city_state_zip,
        "topmostSubform[0].CopyB[0].LeftCol[0].f2_8[0]": account_number,
        "topmostSubform[0].CopyB[0].RightCol[0].f2_9[0]": f"{compensation:.2f}",
        "topmostSubform[0].CopyB[0].RightCol[0].f2_11[0]": f"{tax_withheld:.2f}" if tax_withheld else "",
        # Copy 2 fields
        "topmostSubform[0].Copy2[0].PgHeader[0].CalendarYear[0].f2_1[0]": str(tax_year),
        "topmostSubform[0].Copy2[0].LeftCol[0].f2_2[0]": payer_info,
        "topmostSubform[0].Copy2[0].LeftCol[0].f2_3[0]": payer_tin,
        "topmostSubform[0].Copy2[0].LeftCol[0].f2_4[0]": recipient_tin,
        "topmostSubform[0].Copy2[0].LeftCol[0].f2_5[0]": recipient_name,
        "topmostSubform[0].Copy2[0].LeftCol[0].f2_6[0]": recipient_address,
        "topmostSubform[0].Copy2[0].LeftCol[0].f2_7[0]": recipient_city_state_zip,
        "topmostSubform[0].Copy2[0].LeftCol[0].f2_8[0]": account_number,
        "topmostSubform[0].Copy2[0].RightCol[0].f2_9[0]": f"{compensation:.2f}",
        "topmostSubform[0].Copy2[0].RightCol[0].f2_11[0]": f"{tax_withheld:.2f}" if tax_withheld else "",
    }

    def get_full_field_name(field):
        """Get the full field name including parent hierarchy."""
        name = str(field.get("/T", ""))
        parent = field.get("/Parent")
        while parent:
            if isinstance(parent, IndirectObject):
                parent = parent.get_object()
            parent_name = str(parent.get("/T", ""))
            if parent_name:
                name = parent_name + "." + name
            parent = parent.get("/Parent")
        return name

    def fill_field(fields_array, target_name, value):
        """Recursively find a field by name and set its value."""
        for field_ref in fields_array:
            field = field_ref.get_object() if isinstance(field_ref, IndirectObject) else field_ref

            full_name = get_full_field_name(field)
            if full_name == target_name:
                field[NameObject("/V")] = TextStringObject(value)
                field[NameObject("/DV")] = TextStringObject(value)
                return True

            kids = field.get("/Kids", [])
            if kids and fill_field(kids, target_name, value):
                return True

        return False

    # Get AcroForm fields and fill them
    try:
        acroform = reader.trailer["/Root"]["/AcroForm"]
        fields = acroform.get("/Fields", [])

        for field_name, value in fields_to_fill.items():
            fill_field(fields, field_name, value)

        # Extract only the recipient pages (Copy B and Copy 2) with filled data
        writer = PdfWriter()
        writer.append(reader, pages=[COPY_B_INDEX, COPY_2_INDEX])

        # Write to buffer
        buffer = BytesIO()
        writer.write(buffer)
        return buffer.getvalue()

    except Exception as e:
        logger.warning(f"Failed to fill 1099-NEC form fields: {e}. Using fallback.")
        return _generate_1099_nec_fallback(
            payer_name, payer_address, payer_city_state_zip, payer_tin, payer_phone,
            recipient_name, recipient_address, recipient_city_state_zip, recipient_tin,
            tax_year, compensation, tax_withheld, account_number
        )


def _generate_1099_nec_fallback(
    payer_name: str,
    payer_address: str,
    payer_city_state_zip: str,
    payer_tin: str,
    payer_phone: str,
    recipient_name: str,
    recipient_address: str,
    recipient_city_state_zip: str,
    recipient_tin: str,
    tax_year: int,
    compensation: float,
    tax_withheld: float,
    account_number: str,
) -> bytes:
    """Generate a 1099-NEC-style PDF using ReportLab when form filling fails.

    This fallback creates a professional document with all required information
    in case the IRS fillable PDF isn't available or has incompatible fields.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )
    styles = _get_styles()
    elements = []

    # Title
    elements.append(Paragraph("<b>Form 1099-NEC</b>", styles["DocTitle"]))
    elements.append(Paragraph(f"Nonemployee Compensation - Tax Year {tax_year}", styles["DocNumber"]))
    elements.append(Spacer(1, 0.3 * inch))

    # Payer section
    elements.append(Paragraph("<b>PAYER'S Information</b>", styles["SectionHeader"]))
    elements.append(Paragraph(payer_name, styles["InfoText"]))
    elements.append(Paragraph(payer_address, styles["InfoText"]))
    elements.append(Paragraph(payer_city_state_zip, styles["InfoText"]))
    elements.append(Paragraph(f"TIN: {payer_tin}", styles["InfoText"]))
    elements.append(Paragraph(f"Phone: {payer_phone}", styles["InfoText"]))
    elements.append(Spacer(1, 0.2 * inch))

    # Recipient section
    elements.append(Paragraph("<b>RECIPIENT'S Information</b>", styles["SectionHeader"]))
    elements.append(Paragraph(recipient_name, styles["InfoText"]))
    elements.append(Paragraph(recipient_address, styles["InfoText"]))
    elements.append(Paragraph(recipient_city_state_zip, styles["InfoText"]))
    elements.append(Paragraph(f"TIN: {recipient_tin}", styles["InfoText"]))
    if account_number:
        elements.append(Paragraph(f"Account Number: {account_number}", styles["InfoText"]))
    elements.append(Spacer(1, 0.3 * inch))

    # Amounts table
    elements.append(Paragraph("<b>Compensation Details</b>", styles["SectionHeader"]))
    amounts_data = [
        ["Box", "Description", "Amount"],
        ["1", "Nonemployee compensation", f"${compensation:,.2f}"],
        ["4", "Federal income tax withheld", f"${tax_withheld:,.2f}"],
    ]
    amounts_table = Table(amounts_data, colWidths=[0.75 * inch, 4 * inch, 1.5 * inch])
    amounts_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a365d")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("ALIGN", (2, 0), (2, -1), "RIGHT"),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    elements.append(amounts_table)
    elements.append(Spacer(1, 0.4 * inch))

    # Disclaimer
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e5e7eb")))
    elements.append(Spacer(1, 0.1 * inch))
    elements.append(
        Paragraph(
            "<i>This is an informational copy. For official IRS filing, use the "
            "fillable 1099-NEC form from irs.gov.</i>",
            styles["SmallText"],
        )
    )

    doc.build(elements)
    return buffer.getvalue()
