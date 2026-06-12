# -----------------------------------------------------------------------------
# sparQ - Email Templates
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""Email templates for transactional emails.

This module provides HTML and plain text email templates for
various business transactions including quotes, invoices, and
payment receipts.

Functions:
    get_quote_email_html: Generate HTML email for a quote.
    get_quote_email_text: Generate plain text email for a quote.
    get_invoice_email_html: Generate HTML email for an invoice.
    get_invoice_email_text: Generate plain text email for an invoice.
    get_payment_receipt_email_html: Generate HTML payment receipt.
    get_payment_receipt_email_text: Generate plain text payment receipt.
    get_visit_request_email_html: Generate HTML visit request notification.
    get_visit_request_email_text: Generate plain text visit request.
    get_password_reset_email_html: Generate HTML password reset email.
    get_magic_link_email_html: Generate HTML magic link login email.

Example:
    Generate and send a quote email::

        from system.email import send_email
        from system.email.templates import get_quote_email_html, get_quote_email_text

        html = get_quote_email_html(quote, company_settings, portal_url="/portal/q/abc123")
        text = get_quote_email_text(quote, company_settings, portal_url="/portal/q/abc123")

        send_email(
            to=quote.contact.email,
            subject=f"Quote {quote.quote_number} from {company_settings.company_name}",
            html_body=html,
            text_body=text
        )
"""

from system.i18n.translation import translate as _


def _fmt_dt(dt, fmt: str, company_settings) -> str:
    """Format a datetime converting from UTC to company timezone.

    Works outside Flask request context by reading timezone from company_settings.
    """
    if not dt:
        return ""
    try:
        import pytz

        tz_name = getattr(company_settings, "timezone", None) or "America/Chicago"
        local_tz = pytz.timezone(tz_name)
        if getattr(dt, "tzinfo", None) is None:
            dt = pytz.UTC.localize(dt)
        return dt.astimezone(local_tz).strftime(fmt)
    except Exception:
        return dt.strftime(fmt)


def get_quote_email_html(
    quote, company_settings, portal_url: str | None = None, esign_docs: list | None = None
) -> str:
    """Generate HTML email for a quote.

    Args:
        quote: The quote to generate email for
        company_settings: Company settings for branding
        portal_url: URL to view quote in customer portal
        esign_docs: List of dicts with 'filename' and 'signing_url' for e-sign documents
    """
    company_name = company_settings.company_name or "Our Company"
    company_phone = ""
    company_email = ""
    company_address = ""

    # Build line items HTML
    line_items_html = ""
    for item in quote.line_items_list:
        qty_display = f"{item.quantity:.0f}" if item.quantity == int(item.quantity) else f"{item.quantity:.2f}"
        line_items_html += f"""
        <tr>
            <td style="padding: 12px 0; border-bottom: 1px solid #e5e7eb;">{item.description}</td>
            <td style="padding: 12px 0; border-bottom: 1px solid #e5e7eb; text-align: center;">{qty_display}</td>
            <td style="padding: 12px 0; border-bottom: 1px solid #e5e7eb; text-align: right;">${item.unit_price:.2f}</td>
            <td style="padding: 12px 0; border-bottom: 1px solid #e5e7eb; text-align: right;">${item.line_total:.2f}</td>
        </tr>
        """

    # Customer notes section
    notes_html = ""
    if quote.customer_notes:
        notes_html = f"""
        <div style="margin-top: 30px; padding: 15px; background-color: #f9fafb; border-radius: 6px;">
            <p style="margin: 0; color: #374151; font-size: 14px;">{quote.customer_notes}</p>
        </div>
        """

    # Terms section
    terms_html = ""
    if quote.terms:
        terms_html = f"""
        <div style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #e5e7eb;">
            <p style="margin: 0; color: #6b7280; font-size: 13px;"><strong>Terms:</strong> {quote.terms}</p>
        </div>
        """

    valid_until = quote.valid_until.strftime('%B %d, %Y') if quote.valid_until else "30 days"

    # E-sign documents section
    esign_html = ""
    if esign_docs:
        docs_html = ""
        for doc in esign_docs:
            docs_html += f"""
                <div style="padding: 12px; background-color: white; border-radius: 4px; margin-bottom: 8px;">
                    <table style="width: 100%;">
                        <tr>
                            <td style="color: #374151; font-size: 14px;">
                                <strong style="color: #dc2626;">📄</strong> {doc['filename']}
                            </td>
                            <td style="text-align: right;">
                                <a href="{doc['signing_url']}" style="display: inline-block; background-color: #2563eb; color: white; padding: 8px 16px; font-size: 13px; font-weight: 600; text-decoration: none; border-radius: 4px;">
                                    Review & Sign
                                </a>
                            </td>
                        </tr>
                    </table>
                </div>
            """
        esign_html = f"""
            <!-- E-Sign Documents -->
            <div style="margin-top: 30px; padding: 20px; background-color: #fef3c7; border-radius: 6px; border: 1px solid #fcd34d;">
                <h3 style="margin: 0 0 15px 0; color: #92400e; font-size: 16px;">
                    ✍️ Document(s) Requiring Your Signature
                </h3>
                <p style="margin: 0 0 15px 0; color: #78350f; font-size: 14px;">
                    Please review and sign the following document(s) to proceed:
                </p>
                {docs_html}
            </div>
        """

    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <!-- Header -->
        <div style="background-color: #1a365d; padding: 30px; border-radius: 8px 8px 0 0;">
            <h1 style="margin: 0; color: white; font-size: 24px;">{company_name}</h1>
            {"" if not company_address else f'<p style="margin: 8px 0 0 0; color: rgba(255,255,255,0.7); font-size: 13px;">{company_address}</p>'}
        </div>

        <!-- Main Content -->
        <div style="background-color: white; padding: 30px; border-radius: 0 0 8px 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <p style="color: #374151; font-size: 16px; margin-top: 0;">
                Hello {quote.contact.display_name},
            </p>

            <p style="color: #374151; font-size: 16px;">
                Thank you for your interest in our services. Please find your quote details below.
            </p>

            <!-- Quote Info -->
            <div style="background-color: #f9fafb; padding: 15px; border-radius: 6px; margin: 20px 0;">
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="color: #6b7280; font-size: 14px;">Quote Number:</td>
                        <td style="color: #111827; font-size: 14px; text-align: right;"><strong>{quote.quote_number}</strong></td>
                    </tr>
                    <tr>
                        <td style="color: #6b7280; font-size: 14px;">Quote Title:</td>
                        <td style="color: #111827; font-size: 14px; text-align: right;">{quote.title}</td>
                    </tr>
                    <tr>
                        <td style="color: #6b7280; font-size: 14px;">Valid Until:</td>
                        <td style="color: #111827; font-size: 14px; text-align: right;">{valid_until}</td>
                    </tr>
                </table>
            </div>

            <!-- Line Items -->
            <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                <thead>
                    <tr style="border-bottom: 2px solid #e5e7eb;">
                        <th style="padding: 10px 0; text-align: left; color: #374151; font-size: 14px;">Description</th>
                        <th style="padding: 10px 0; text-align: center; color: #374151; font-size: 14px;">Qty</th>
                        <th style="padding: 10px 0; text-align: right; color: #374151; font-size: 14px;">Price</th>
                        <th style="padding: 10px 0; text-align: right; color: #374151; font-size: 14px;">Total</th>
                    </tr>
                </thead>
                <tbody>
                    {line_items_html}
                </tbody>
            </table>

            <!-- Totals -->
            <div style="margin-top: 20px; text-align: right;">
                <table style="margin-left: auto; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 5px 20px; color: #6b7280;">Subtotal:</td>
                        <td style="padding: 5px 0; color: #111827;">${quote.subtotal:.2f}</td>
                    </tr>
                    {"" if quote.tax_rate == 0 else f'''
                    <tr>
                        <td style="padding: 5px 20px; color: #6b7280;">Tax ({quote.tax_rate:.2f}%):</td>
                        <td style="padding: 5px 0; color: #111827;">${quote.tax_amount:.2f}</td>
                    </tr>
                    '''}
                    <tr style="border-top: 2px solid #e5e7eb;">
                        <td style="padding: 10px 20px; color: #111827; font-size: 18px;"><strong>Total:</strong></td>
                        <td style="padding: 10px 0; color: #111827; font-size: 18px;"><strong>${quote.total:.2f}</strong></td>
                    </tr>
                </table>
            </div>

            {notes_html}
            {terms_html}

            {"" if not portal_url else f'''
            <!-- View & Accept Button -->
            <div style="margin-top: 30px; text-align: center;">
                <a href="{portal_url}" style="display: inline-block; background-color: #10b981; color: white; padding: 14px 32px; font-size: 16px; font-weight: 600; text-decoration: none; border-radius: 6px;">
                    View & Accept Quote
                </a>
                <p style="color: #6b7280; font-size: 13px; margin-top: 10px;">
                    Click above to view full details and accept this quote
                </p>
            </div>
            '''}

            {esign_html}

            <!-- CTA -->
            <div style="margin-top: 30px; text-align: center;">
                <p style="color: #374151; font-size: 14px;">
                    If you have any questions about this quote, please don't hesitate to contact us.
                </p>
            </div>

            <!-- Footer -->
            <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb; text-align: center;">
                <p style="color: #6b7280; font-size: 13px; margin: 0;">
                    {company_name}<br>
                    {f'{company_phone}<br>' if company_phone else ''}
                    {f'{company_email}' if company_email else ''}
                </p>
                <p style="margin-top: 15px; color: #9ca3af; font-size: 11px;">
                    Powered by <a href="https://www.gosparq.com?ref=email" style="color: #9ca3af; text-decoration: none;">sparQ</a>
                </p>
            </div>
        </div>
    </div>
</body>
</html>
"""


def get_quote_email_text(
    quote, company_settings, portal_url: str | None = None, esign_docs: list | None = None
) -> str:
    """Generate plain text email for a quote.

    Args:
        quote: The quote to generate email for
        company_settings: Company settings for branding
        portal_url: URL to view quote in customer portal
        esign_docs: List of dicts with 'filename' and 'signing_url' for e-sign documents
    """
    company_name = company_settings.company_name or "Our Company"

    lines = [
        f"{company_name}",
        "=" * 50,
        "",
        f"Hello {quote.contact.display_name},",
        "",
        "Thank you for your interest in our services. Please find your quote details below.",
        "",
        "-" * 50,
        f"Quote Number: {quote.quote_number}",
        f"Quote Title: {quote.title}",
        f"Valid Until: {quote.valid_until.strftime('%B %d, %Y') if quote.valid_until else '30 days'}",
        "-" * 50,
        "",
        "LINE ITEMS:",
        "",
    ]

    for item in quote.line_items_list:
        qty = f"{item.quantity:.0f}" if item.quantity == int(item.quantity) else f"{item.quantity:.2f}"
        lines.append(f"  {item.description}")
        lines.append(f"    {qty} x ${item.unit_price:.2f} = ${item.line_total:.2f}")
        lines.append("")

    lines.extend([
        "-" * 50,
        f"Subtotal: ${quote.subtotal:.2f}",
    ])

    if quote.tax_rate > 0:
        lines.append(f"Tax ({quote.tax_rate:.2f}%): ${quote.tax_amount:.2f}")

    lines.extend([
        f"TOTAL: ${quote.total:.2f}",
        "-" * 50,
        "",
    ])

    if quote.customer_notes:
        lines.extend([
            "Notes:",
            quote.customer_notes,
            "",
        ])

    if quote.terms:
        lines.extend([
            "Terms:",
            quote.terms,
            "",
        ])

    if portal_url:
        lines.extend([
            "-" * 50,
            "VIEW & ACCEPT QUOTE:",
            portal_url,
            "(Click above to view full details and accept this quote)",
            "",
        ])

    if esign_docs:
        lines.extend([
            "-" * 50,
            "DOCUMENTS REQUIRING YOUR SIGNATURE:",
            "",
        ])
        for doc in esign_docs:
            lines.extend([
                f"  * {doc['filename']}",
                f"    Sign here: {doc['signing_url']}",
                "",
            ])

    lines.extend([
        "If you have any questions about this quote, please don't hesitate to contact us.",
        "",
        "Best regards,",
        company_name,
        "",
        "-" * 50,
        "Powered by sparQ — https://www.gosparq.com?ref=email",
    ])

    return "\n".join(lines)


def get_invoice_email_html(
    invoice, company_settings, portal_url: str | None = None, pay_url: str | None = None
) -> str:
    """Generate HTML email for an invoice.

    Args:
        invoice: The invoice to generate email for
        company_settings: Company settings for branding
        portal_url: URL to view invoice in customer portal
        pay_url: Optional URL for online payment (if Stripe is configured)
    """
    company_name = company_settings.company_name or "Our Company"
    company_phone = ""
    company_email = ""
    company_address = ""

    # Build line items HTML
    line_items_html = ""
    for item in invoice.line_items_list:
        qty_display = f"{item.quantity:.0f}" if item.quantity == int(item.quantity) else f"{item.quantity:.2f}"
        line_items_html += f"""
        <tr>
            <td style="padding: 12px 0; border-bottom: 1px solid #e5e7eb;">{item.description}</td>
            <td style="padding: 12px 0; border-bottom: 1px solid #e5e7eb; text-align: center;">{qty_display}</td>
            <td style="padding: 12px 0; border-bottom: 1px solid #e5e7eb; text-align: right;">${item.unit_price:.2f}</td>
            <td style="padding: 12px 0; border-bottom: 1px solid #e5e7eb; text-align: right;">${item.line_total:.2f}</td>
        </tr>
        """

    # Notes section
    notes_html = ""
    if invoice.notes:
        notes_html = f"""
        <div style="margin-top: 30px; padding: 15px; background-color: #f9fafb; border-radius: 6px;">
            <p style="margin: 0; color: #374151; font-size: 14px;">{invoice.notes}</p>
        </div>
        """

    due_date = invoice.due_date.strftime('%B %d, %Y') if invoice.due_date else "Upon receipt"
    issue_date = invoice.issue_date.strftime('%B %d, %Y') if invoice.issue_date else ""

    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <!-- Header -->
        <div style="background-color: #1a365d; padding: 30px; border-radius: 8px 8px 0 0;">
            <h1 style="margin: 0; color: white; font-size: 24px;">{company_name}</h1>
            {"" if not company_address else f'<p style="margin: 8px 0 0 0; color: rgba(255,255,255,0.7); font-size: 13px;">{company_address}</p>'}
            <p style="margin: 10px 0 0 0; color: rgba(255,255,255,0.8); font-size: 16px;">Invoice</p>
        </div>

        <!-- Main Content -->
        <div style="background-color: white; padding: 30px; border-radius: 0 0 8px 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <p style="color: #374151; font-size: 16px; margin-top: 0;">
                Hello {invoice.contact.display_name},
            </p>

            <p style="color: #374151; font-size: 16px;">
                Please find your invoice details below. Payment is due by <strong>{due_date}</strong>.
            </p>

            <!-- Invoice Info -->
            <div style="background-color: #f9fafb; padding: 15px; border-radius: 6px; margin: 20px 0;">
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="color: #6b7280; font-size: 14px;">Invoice Number:</td>
                        <td style="color: #111827; font-size: 14px; text-align: right;"><strong>{invoice.invoice_number}</strong></td>
                    </tr>
                    <tr>
                        <td style="color: #6b7280; font-size: 14px;">Issue Date:</td>
                        <td style="color: #111827; font-size: 14px; text-align: right;">{issue_date}</td>
                    </tr>
                    <tr>
                        <td style="color: #6b7280; font-size: 14px;">Due Date:</td>
                        <td style="color: #111827; font-size: 14px; text-align: right;">{due_date}</td>
                    </tr>
                    <tr>
                        <td style="color: #6b7280; font-size: 14px;">Payment Terms:</td>
                        <td style="color: #111827; font-size: 14px; text-align: right;">{invoice.payment_terms or 'Net 30'}</td>
                    </tr>
                </table>
            </div>

            <!-- Line Items -->
            <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                <thead>
                    <tr style="border-bottom: 2px solid #e5e7eb;">
                        <th style="padding: 10px 0; text-align: left; color: #374151; font-size: 14px;">Description</th>
                        <th style="padding: 10px 0; text-align: center; color: #374151; font-size: 14px;">Qty</th>
                        <th style="padding: 10px 0; text-align: right; color: #374151; font-size: 14px;">Price</th>
                        <th style="padding: 10px 0; text-align: right; color: #374151; font-size: 14px;">Total</th>
                    </tr>
                </thead>
                <tbody>
                    {line_items_html}
                </tbody>
            </table>

            <!-- Totals -->
            <div style="margin-top: 20px; text-align: right;">
                <table style="margin-left: auto; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 5px 20px; color: #6b7280;">Subtotal:</td>
                        <td style="padding: 5px 0; color: #111827;">${invoice.subtotal:.2f}</td>
                    </tr>
                    {"" if invoice.tax_rate == 0 else f'''
                    <tr>
                        <td style="padding: 5px 20px; color: #6b7280;">Tax ({invoice.tax_rate:.2f}%):</td>
                        <td style="padding: 5px 0; color: #111827;">${invoice.tax_amount:.2f}</td>
                    </tr>
                    '''}
                    <tr style="border-top: 2px solid #e5e7eb;">
                        <td style="padding: 10px 20px; color: #111827; font-size: 18px;"><strong>Total:</strong></td>
                        <td style="padding: 10px 0; color: #111827; font-size: 18px;"><strong>${invoice.total:.2f}</strong></td>
                    </tr>
                    {"" if invoice.amount_paid == 0 else f'''
                    <tr>
                        <td style="padding: 5px 20px; color: #059669;">Amount Paid:</td>
                        <td style="padding: 5px 0; color: #059669;">-${invoice.amount_paid:.2f}</td>
                    </tr>
                    '''}
                    <tr style="background-color: #fef3c7; border-radius: 4px;">
                        <td style="padding: 10px 20px; color: #92400e; font-size: 18px;"><strong>Balance Due:</strong></td>
                        <td style="padding: 10px 0; color: #92400e; font-size: 18px;"><strong>${invoice.balance_due:.2f}</strong></td>
                    </tr>
                </table>
            </div>

            {notes_html}

            {"" if not portal_url else f'''
            <!-- View Invoice Button -->
            <div style="margin-top: 30px; text-align: center;">
                <a href="{portal_url}" style="display: inline-block; background-color: #10b981; color: white; padding: 14px 32px; font-size: 16px; font-weight: 600; text-decoration: none; border-radius: 6px;">
                    View Invoice Details
                </a>
                <p style="color: #6b7280; font-size: 13px; margin-top: 10px;">
                    View your invoice and account details
                </p>
            </div>
            '''}

            {"" if not pay_url else f'''
            <!-- Pay Online Button -->
            <div style="margin-top: 20px; text-align: center;">
                <a href="{pay_url}" style="display: inline-block; background-color: #2563eb; color: white; padding: 14px 32px; font-size: 16px; font-weight: 600; text-decoration: none; border-radius: 6px;">
                    Pay Online - ${invoice.balance_due:.2f}
                </a>
                <p style="color: #6b7280; font-size: 13px; margin-top: 10px;">
                    Secure payment powered by Stripe
                </p>
            </div>
            '''}

            <!-- Footer -->
            <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb; text-align: center;">
                <p style="color: #374151; font-size: 14px;">
                    Thank you for your business!
                </p>
                <p style="color: #6b7280; font-size: 13px; margin: 0;">
                    {company_name}<br>
                    {f'{company_phone}<br>' if company_phone else ''}
                    {f'{company_email}' if company_email else ''}
                </p>
                <p style="margin-top: 15px; color: #9ca3af; font-size: 11px;">
                    Powered by <a href="https://www.gosparq.com?ref=email" style="color: #9ca3af; text-decoration: none;">sparQ</a>
                </p>
            </div>
        </div>
    </div>
</body>
</html>
"""


def get_invoice_email_text(
    invoice, company_settings, portal_url: str | None = None, pay_url: str | None = None
) -> str:
    """Generate plain text email for an invoice.

    Args:
        invoice: The invoice to generate email for
        company_settings: Company settings for branding
        portal_url: URL to view invoice in customer portal
        pay_url: Optional URL for online payment (if Stripe is configured)
    """
    company_name = company_settings.company_name or "Our Company"

    lines = [
        f"{company_name}",
        "INVOICE",
        "=" * 50,
        "",
        f"Hello {invoice.contact.display_name},",
        "",
        f"Please find your invoice details below. Payment is due by {invoice.due_date.strftime('%B %d, %Y') if invoice.due_date else 'upon receipt'}.",
        "",
        "-" * 50,
        f"Invoice Number: {invoice.invoice_number}",
        f"Issue Date: {invoice.issue_date.strftime('%B %d, %Y') if invoice.issue_date else ''}",
        f"Due Date: {invoice.due_date.strftime('%B %d, %Y') if invoice.due_date else 'Upon receipt'}",
        f"Payment Terms: {invoice.payment_terms or 'Net 30'}",
        "-" * 50,
        "",
        "LINE ITEMS:",
        "",
    ]

    for item in invoice.line_items_list:
        qty = f"{item.quantity:.0f}" if item.quantity == int(item.quantity) else f"{item.quantity:.2f}"
        lines.append(f"  {item.description}")
        lines.append(f"    {qty} x ${item.unit_price:.2f} = ${item.line_total:.2f}")
        lines.append("")

    lines.extend([
        "-" * 50,
        f"Subtotal: ${invoice.subtotal:.2f}",
    ])

    if invoice.tax_rate > 0:
        lines.append(f"Tax ({invoice.tax_rate:.2f}%): ${invoice.tax_amount:.2f}")

    lines.append(f"TOTAL: ${invoice.total:.2f}")

    if invoice.amount_paid > 0:
        lines.append(f"Amount Paid: -${invoice.amount_paid:.2f}")

    lines.extend([
        f"BALANCE DUE: ${invoice.balance_due:.2f}",
        "-" * 50,
        "",
    ])

    if invoice.notes:
        lines.extend([
            "Notes:",
            invoice.notes,
            "",
        ])

    if portal_url:
        lines.extend([
            "-" * 50,
            "VIEW INVOICE:",
            portal_url,
            "(View your invoice and account details)",
            "",
        ])

    if pay_url:
        lines.extend([
            "-" * 50,
            "PAY ONLINE:",
            pay_url,
            "(Secure payment powered by Stripe)",
            "",
        ])

    lines.extend([
        "Thank you for your business!",
        "",
        "Best regards,",
        company_name,
        "",
        "-" * 50,
        "Powered by sparQ — https://www.gosparq.com?ref=email",
    ])

    return "\n".join(lines)


def get_payment_receipt_email_html(payment, invoice, company_settings) -> str:
    """Generate HTML email for a payment receipt.

    Args:
        payment: The payment that was received
        invoice: The invoice the payment was applied to
        company_settings: Company settings for branding
    """
    company_name = company_settings.company_name or "Our Company"
    company_phone = ""
    company_email = ""
    company_address = ""

    payment_date = payment.payment_date.strftime('%B %d, %Y') if payment.payment_date else ""
    method_display = payment.payment_method.value if payment.payment_method else "Other"

    # Reference number section
    reference_html = ""
    if payment.reference_number:
        reference_html = f"""
                    <tr>
                        <td style="color: #6b7280; font-size: 14px;">Reference #:</td>
                        <td style="color: #111827; font-size: 14px; text-align: right;">{payment.reference_number}</td>
                    </tr>
        """

    # Balance section
    balance_html = ""
    if invoice.balance_due > 0:
        balance_html = f"""
            <div style="margin-top: 20px; padding: 15px; background-color: #fef3c7; border-radius: 6px; text-align: center;">
                <p style="margin: 0; color: #92400e; font-size: 14px;">
                    <strong>Remaining Balance:</strong> ${invoice.balance_due:.2f}
                </p>
            </div>
        """
    else:
        balance_html = """
            <div style="margin-top: 20px; padding: 15px; background-color: #d1fae5; border-radius: 6px; text-align: center;">
                <p style="margin: 0; color: #065f46; font-size: 14px;">
                    <strong>Invoice Paid in Full</strong>
                </p>
            </div>
        """

    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <!-- Header -->
        <div style="background-color: #059669; padding: 30px; border-radius: 8px 8px 0 0;">
            <h1 style="margin: 0; color: white; font-size: 24px;">{company_name}</h1>
            {"" if not company_address else f'<p style="margin: 8px 0 0 0; color: rgba(255,255,255,0.7); font-size: 13px;">{company_address}</p>'}
            <p style="margin: 10px 0 0 0; color: rgba(255,255,255,0.9); font-size: 16px;">Payment Receipt</p>
        </div>

        <!-- Main Content -->
        <div style="background-color: white; padding: 30px; border-radius: 0 0 8px 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <p style="color: #374151; font-size: 16px; margin-top: 0;">
                Hello {invoice.contact.display_name},
            </p>

            <p style="color: #374151; font-size: 16px;">
                Thank you for your payment! This email confirms that we have received your payment.
            </p>

            <!-- Payment Details -->
            <div style="background-color: #f9fafb; padding: 20px; border-radius: 6px; margin: 20px 0;">
                <h3 style="margin: 0 0 15px 0; color: #111827; font-size: 16px;">Payment Details</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="color: #6b7280; font-size: 14px;">Payment Number:</td>
                        <td style="color: #111827; font-size: 14px; text-align: right;"><strong>{payment.payment_number}</strong></td>
                    </tr>
                    <tr>
                        <td style="color: #6b7280; font-size: 14px;">Payment Date:</td>
                        <td style="color: #111827; font-size: 14px; text-align: right;">{payment_date}</td>
                    </tr>
                    <tr>
                        <td style="color: #6b7280; font-size: 14px;">Payment Method:</td>
                        <td style="color: #111827; font-size: 14px; text-align: right;">{method_display}</td>
                    </tr>
                    {reference_html}
                    <tr style="border-top: 1px solid #e5e7eb;">
                        <td style="padding-top: 10px; color: #059669; font-size: 16px;"><strong>Amount Paid:</strong></td>
                        <td style="padding-top: 10px; color: #059669; font-size: 16px; text-align: right;"><strong>${payment.amount:.2f}</strong></td>
                    </tr>
                </table>
            </div>

            <!-- Invoice Reference -->
            <div style="background-color: #f9fafb; padding: 20px; border-radius: 6px; margin: 20px 0;">
                <h3 style="margin: 0 0 15px 0; color: #111827; font-size: 16px;">Applied To</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="color: #6b7280; font-size: 14px;">Invoice Number:</td>
                        <td style="color: #111827; font-size: 14px; text-align: right;"><strong>{invoice.invoice_number}</strong></td>
                    </tr>
                    <tr>
                        <td style="color: #6b7280; font-size: 14px;">Invoice Total:</td>
                        <td style="color: #111827; font-size: 14px; text-align: right;">${invoice.total:.2f}</td>
                    </tr>
                    <tr>
                        <td style="color: #6b7280; font-size: 14px;">Total Paid:</td>
                        <td style="color: #111827; font-size: 14px; text-align: right;">${invoice.amount_paid:.2f}</td>
                    </tr>
                </table>
            </div>

            {balance_html}

            <!-- Footer -->
            <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb; text-align: center;">
                <p style="color: #374151; font-size: 14px;">
                    Thank you for your business!
                </p>
                <p style="color: #6b7280; font-size: 13px; margin: 0;">
                    {company_name}<br>
                    {f'{company_phone}<br>' if company_phone else ''}
                    {f'{company_email}' if company_email else ''}
                </p>
                <p style="margin-top: 15px; color: #9ca3af; font-size: 11px;">
                    Powered by <a href="https://www.gosparq.com?ref=email" style="color: #9ca3af; text-decoration: none;">sparQ</a>
                </p>
            </div>
        </div>
    </div>
</body>
</html>
"""


def get_payment_receipt_email_text(payment, invoice, company_settings) -> str:
    """Generate plain text email for a payment receipt.

    Args:
        payment: The payment that was received
        invoice: The invoice the payment was applied to
        company_settings: Company settings for branding
    """
    company_name = company_settings.company_name or "Our Company"

    lines = [
        f"{company_name}",
        "PAYMENT RECEIPT",
        "=" * 50,
        "",
        f"Hello {invoice.contact.display_name},",
        "",
        "Thank you for your payment! This email confirms that we have received your payment.",
        "",
        "-" * 50,
        "PAYMENT DETAILS",
        "-" * 50,
        f"Payment Number: {payment.payment_number}",
        f"Payment Date: {payment.payment_date.strftime('%B %d, %Y') if payment.payment_date else ''}",
        f"Payment Method: {payment.payment_method.value if payment.payment_method else 'Other'}",
    ]

    if payment.reference_number:
        lines.append(f"Reference #: {payment.reference_number}")

    lines.extend([
        f"Amount Paid: ${payment.amount:.2f}",
        "",
        "-" * 50,
        "APPLIED TO",
        "-" * 50,
        f"Invoice Number: {invoice.invoice_number}",
        f"Invoice Total: ${invoice.total:.2f}",
        f"Total Paid: ${invoice.amount_paid:.2f}",
    ])

    if invoice.balance_due > 0:
        lines.extend([
            "",
            f"REMAINING BALANCE: ${invoice.balance_due:.2f}",
        ])
    else:
        lines.extend([
            "",
            "*** INVOICE PAID IN FULL ***",
        ])

    lines.extend([
        "",
        "-" * 50,
        "",
        "Thank you for your business!",
        "",
        "Best regards,",
        company_name,
        "",
        "-" * 50,
        "Powered by sparQ — https://www.gosparq.com?ref=email",
    ])

    return "\n".join(lines)


# -----------------------------------------------------------------------------
# Visit Request Email Templates
# -----------------------------------------------------------------------------


def get_visit_request_email_html(visit_request, company_settings, portal_url: str) -> str:
    """Generate HTML email for a visit request notification.

    Args:
        visit_request: The visit request to notify about
        company_settings: Company settings for branding
        portal_url: URL to the customer portal
    """
    company_name = company_settings.company_name or "Our Company"
    company_phone = ""
    company_address = ""
    contact_name = (
        visit_request.contact.first_name
        if visit_request.contact.first_name
        else visit_request.contact.display_name
    )

    proposed_date = _fmt_dt(visit_request.proposed_datetime, "%A, %B %d, %Y", company_settings)
    proposed_time = _fmt_dt(visit_request.proposed_datetime, "%I:%M %p", company_settings)

    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <!-- Header -->
        <div style="background-color: #1a365d; padding: 30px; border-radius: 8px 8px 0 0;">
            <h1 style="margin: 0; color: white; font-size: 24px;">{company_name}</h1>
            {"" if not company_address else f'<p style="margin: 8px 0 0 0; color: rgba(255,255,255,0.7); font-size: 13px;">{company_address}</p>'}
        </div>

        <!-- Main Content -->
        <div style="background-color: white; padding: 30px; border-radius: 0 0 8px 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <p style="color: #374151; font-size: 16px; margin-top: 0;">
                Hello {contact_name},
            </p>

            <p style="color: #374151; font-size: 16px;">
                We'd like to schedule a <strong>{visit_request.title}</strong> with you.
            </p>

            <!-- Proposed Time Box -->
            <div style="background-color: #fef3c7; padding: 25px; border-radius: 8px; margin: 25px 0; text-align: center;">
                <p style="color: #92400e; font-size: 12px; margin: 0 0 8px 0; text-transform: uppercase; letter-spacing: 1px; font-weight: 600;">
                    Proposed Visit Time
                </p>
                <p style="color: #1a365d; font-size: 24px; font-weight: bold; margin: 0;">
                    {proposed_date}
                </p>
                <p style="color: #374151; font-size: 18px; margin: 8px 0 0 0;">
                    at {proposed_time}
                </p>
            </div>

            <!-- CTA Button -->
            <div style="text-align: center; margin: 30px 0;">
                <a href="{portal_url}" style="display: inline-block; background-color: #10b981; color: white; padding: 16px 40px; font-size: 16px; font-weight: 600; text-decoration: none; border-radius: 6px;">
                    Confirm or Request Change
                </a>
            </div>

            <p style="color: #6b7280; font-size: 14px; text-align: center;">
                Click the button above to confirm this time or request a different time that works better for you.
            </p>

            <!-- Footer -->
            <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb; text-align: center;">
                <p style="color: #6b7280; font-size: 13px; margin: 0;">
                    {company_name}<br>
                    {f'{company_phone}' if company_phone else ''}
                </p>
                <p style="margin-top: 15px; color: #9ca3af; font-size: 11px;">
                    Powered by <a href="https://www.gosparq.com?ref=email" style="color: #9ca3af; text-decoration: none;">sparQ</a>
                </p>
            </div>
        </div>
    </div>
</body>
</html>
"""


def get_visit_request_email_text(visit_request, company_settings, portal_url: str) -> str:
    """Generate plain text email for a visit request notification.

    Args:
        visit_request: The visit request to notify about
        company_settings: Company settings for branding
        portal_url: URL to the customer portal
    """
    company_name = company_settings.company_name or "Our Company"
    contact_name = (
        visit_request.contact.first_name
        if visit_request.contact.first_name
        else visit_request.contact.display_name
    )

    proposed_date = _fmt_dt(visit_request.proposed_datetime, "%A, %B %d, %Y", company_settings)
    proposed_time = _fmt_dt(visit_request.proposed_datetime, "%I:%M %p", company_settings)

    return f"""{company_name}
{'=' * 50}

Hello {contact_name},

We'd like to schedule a {visit_request.title} with you.

PROPOSED VISIT TIME:
{proposed_date} at {proposed_time}

{'-' * 50}

To confirm or request a different time, please visit:
{portal_url}

Thank you!
{company_name}

{'-' * 50}
Powered by sparQ — https://www.gosparq.com?ref=email
"""


# -----------------------------------------------------------------------------
# Visit Scheduled Email Templates
# -----------------------------------------------------------------------------


def get_visit_scheduled_email_html(visit, company_settings) -> str:
    """Generate HTML email notifying a customer their visit has been scheduled.

    Args:
        visit: The ScheduledVisit that was scheduled
        company_settings: Company settings for branding
    """
    company_name = company_settings.company_name or "Our Company"
    company_phone = ""
    company_email = ""
    company_address = ""
    contact = visit.resolved_contact
    contact_name = (
        contact.first_name
        if contact.first_name
        else contact.display_name
    )

    scheduled_date = _fmt_dt(visit.proposed_datetime, "%A, %B %d, %Y", company_settings)
    scheduled_time = _fmt_dt(visit.proposed_datetime, "%I:%M %p", company_settings)

    reschedule_section = """
            <p style="color: #374151; font-size: 16px; text-align: center;">
                If you need to reschedule or change the services requested, please contact us.
            </p>"""
    if company_email:
        reschedule_section += f"""
            <p style="color: #6b7280; font-size: 14px; text-align: center;">
                <a href="mailto:{company_email}" style="color: #2563eb; text-decoration: none;">{company_email}</a>
                {f'&nbsp;&middot;&nbsp;{company_phone}' if company_phone else ''}
            </p>"""

    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <!-- Header -->
        <div style="background-color: #1a365d; padding: 30px; border-radius: 8px 8px 0 0;">
            <h1 style="margin: 0; color: white; font-size: 24px;">{company_name}</h1>
            {"" if not company_address else f'<p style="margin: 8px 0 0 0; color: rgba(255,255,255,0.7); font-size: 13px;">{company_address}</p>'}
        </div>

        <!-- Main Content -->
        <div style="background-color: white; padding: 30px; border-radius: 0 0 8px 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <p style="color: #374151; font-size: 16px; margin-top: 0;">
                Hello {contact_name},
            </p>

            <p style="color: #374151; font-size: 16px;">
                Your <strong>{visit.display_name}</strong> has been scheduled.
            </p>

            <!-- Scheduled Time Box -->
            <div style="background-color: #d1fae5; padding: 25px; border-radius: 8px; margin: 25px 0; text-align: center;">
                <p style="color: #065f46; font-size: 12px; margin: 0 0 8px 0; text-transform: uppercase; letter-spacing: 1px; font-weight: 600;">
                    Scheduled Visit
                </p>
                <p style="color: #1a365d; font-size: 24px; font-weight: bold; margin: 0;">
                    {scheduled_date}
                </p>
                <p style="color: #374151; font-size: 18px; margin: 8px 0 0 0;">
                    at {scheduled_time}
                </p>
            </div>
{reschedule_section}
            <!-- Footer -->
            <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb; text-align: center;">
                <p style="color: #6b7280; font-size: 13px; margin: 0;">
                    {company_name}<br>
                    {f'{company_phone}' if company_phone else ''}
                </p>
                <p style="margin-top: 15px; color: #9ca3af; font-size: 11px;">
                    Powered by <a href="https://www.gosparq.com?ref=email" style="color: #9ca3af; text-decoration: none;">sparQ</a>
                </p>
            </div>
        </div>
    </div>
</body>
</html>
"""


def get_visit_scheduled_email_text(visit, company_settings) -> str:
    """Generate plain text email notifying a customer their visit has been scheduled.

    Args:
        visit: The ScheduledVisit that was scheduled
        company_settings: Company settings for branding
    """
    company_name = company_settings.company_name or "Our Company"
    company_email = ""
    company_phone = ""
    contact = visit.resolved_contact
    contact_name = (
        contact.first_name
        if contact.first_name
        else contact.display_name
    )

    scheduled_date = _fmt_dt(visit.proposed_datetime, "%A, %B %d, %Y", company_settings)
    scheduled_time = _fmt_dt(visit.proposed_datetime, "%I:%M %p", company_settings)

    reschedule_line = "\nIf you need to reschedule or change the services requested, please contact us."
    if company_email:
        reschedule_line += f"\n{company_email}"
        if company_phone:
            reschedule_line += f" | {company_phone}"
    reschedule_line += "\n"

    return f"""{company_name}
{'=' * 50}

Hello {contact_name},

Your {visit.display_name} has been scheduled.

SCHEDULED VISIT:
{scheduled_date} at {scheduled_time}

{'-' * 50}
{reschedule_line}
Thank you!
{company_name}

{'-' * 50}
Powered by sparQ — https://www.gosparq.com?ref=email
"""


# -----------------------------------------------------------------------------
# Service Request Confirmation Email Templates
# -----------------------------------------------------------------------------


def get_service_request_confirmation_email_html(
    service_request,
    contact,
    company_settings,
    sales_settings=None,
) -> str:
    """Generate HTML email for service request confirmation.

    Args:
        service_request: The ServiceRequest that was submitted
        contact: The Contact who submitted the request
        company_settings: Company settings for branding
        sales_settings: Optional SalesSettings for custom confirmation text

    Returns:
        HTML string for the email body
    """
    import html as html_module

    company_name = company_settings.company_name or "Our Company"
    company_phone = ""
    company_email = ""
    company_address = ""

    contact_name = contact.first_name if contact.first_name else contact.display_name

    # Custom confirmation message (escaped for HTML safety)
    custom_confirmation = None
    if sales_settings and sales_settings.confirmation_message:
        custom_confirmation = html_module.escape(sales_settings.confirmation_message)

    # Custom next steps (newline-separated, escaped)
    custom_next_steps = None
    if sales_settings and sales_settings.next_steps:
        custom_next_steps = [
            html_module.escape(line.strip())
            for line in sales_settings.next_steps.splitlines()
            if line.strip()
        ]

    # Format requested date/time if provided
    date_time_html = ""
    if service_request.requested_date:
        date_str = service_request.requested_date.strftime("%B %d, %Y")
        time_str = service_request.preferred_time or ""
        date_time_html = f"""
                    <tr>
                        <td style="color: #6b7280; font-size: 14px; padding: 5px 0;">Preferred Date:</td>
                        <td style="color: #111827; font-size: 14px; text-align: right;">{date_str}</td>
                    </tr>
        """
        if time_str:
            date_time_html += f"""
                    <tr>
                        <td style="color: #6b7280; font-size: 14px; padding: 5px 0;">Preferred Time:</td>
                        <td style="color: #111827; font-size: 14px; text-align: right;">{time_str}</td>
                    </tr>
            """

    # Service address from service location
    address_html = ""
    if service_request.service_location and service_request.service_location.full_address:
        address_html = f"""
                    <tr>
                        <td style="color: #6b7280; font-size: 14px; padding: 5px 0;">Service Address:</td>
                        <td style="color: #111827; font-size: 14px; text-align: right;">{service_request.service_location.full_address}</td>
                    </tr>
        """

    # Description section
    description_html = ""
    if service_request.description:
        description_html = f"""
            <div style="margin-top: 20px; padding: 15px; background-color: #f9fafb; border-radius: 6px;">
                <p style="margin: 0 0 8px 0; color: #6b7280; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;">Additional Details</p>
                <p style="margin: 0; color: #374151; font-size: 14px;">{service_request.description}</p>
            </div>
        """

    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <!-- Header -->
        <div style="background-color: #1a365d; padding: 30px; border-radius: 8px 8px 0 0;">
            <h1 style="margin: 0; color: white; font-size: 24px;">{company_name}</h1>
            {"" if not company_address else f'<p style="margin: 8px 0 0 0; color: rgba(255,255,255,0.7); font-size: 13px;">{company_address}</p>'}
            <p style="margin: 10px 0 0 0; color: rgba(255,255,255,0.9); font-size: 16px;">Service Request Received</p>
        </div>

        <!-- Main Content -->
        <div style="background-color: white; padding: 30px; border-radius: 0 0 8px 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <p style="color: #374151; font-size: 16px; margin-top: 0;">
                Hi {contact_name},
            </p>

            <p style="color: #374151; font-size: 16px;">
                {custom_confirmation or "Thank you for your service request! We've received your submission and will be in touch shortly."}
            </p>

            <!-- Request Details -->
            <div style="background-color: #f9fafb; padding: 20px; border-radius: 6px; margin: 20px 0;">
                <h3 style="margin: 0 0 15px 0; color: #111827; font-size: 16px;">Request Details</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="color: #6b7280; font-size: 14px; padding: 5px 0;">Request Number:</td>
                        <td style="color: #111827; font-size: 14px; text-align: right;"><strong>{service_request.request_number}</strong></td>
                    </tr>
                    <tr>
                        <td style="color: #6b7280; font-size: 14px; padding: 5px 0;">Service Requested:</td>
                        <td style="color: #111827; font-size: 14px; text-align: right;">{service_request.title}</td>
                    </tr>
                    {address_html}
                    {date_time_html}
                </table>
            </div>

            {description_html}

            <!-- What happens next -->
            <div style="margin-top: 20px; padding: 20px; background-color: #fef3c7; border-radius: 6px; border: 1px solid #fcd34d;">
                <h3 style="margin: 0 0 15px 0; color: #92400e; font-size: 16px;">
                    What happens next?
                </h3>
                <ul style="margin: 0; padding-left: 20px; color: #78350f; font-size: 14px;">
                    {''.join(f'<li style="margin-bottom: 8px;">{step}</li>' for step in custom_next_steps) if custom_next_steps else '<li style="margin-bottom: 8px;">Our team will review your request</li><li style="margin-bottom: 8px;">We&#x27;ll contact you within 1-2 business days</li><li>We may schedule a site visit if needed</li>'}
                </ul>
            </div>

            <!-- Footer -->
            <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb; text-align: center;">
                <p style="color: #374151; font-size: 14px;">
                    Questions? Feel free to contact us.
                </p>
                <p style="color: #6b7280; font-size: 13px; margin: 0;">
                    {company_name}<br>
                    {f'{company_phone}<br>' if company_phone else ''}
                    {f'{company_email}' if company_email else ''}
                </p>
                <p style="margin-top: 15px; color: #9ca3af; font-size: 11px;">
                    Powered by <a href="https://www.gosparq.com?ref=email" style="color: #9ca3af; text-decoration: none;">sparQ</a>
                </p>
            </div>
        </div>
    </div>
</body>
</html>
"""


def get_service_request_confirmation_email_text(
    service_request,
    contact,
    company_settings,
    sales_settings=None,
) -> str:
    """Generate plain text email for service request confirmation.

    Args:
        service_request: The ServiceRequest that was submitted
        contact: The Contact who submitted the request
        company_settings: Company settings for branding
        sales_settings: Optional SalesSettings for custom confirmation text

    Returns:
        Plain text string for the email body
    """
    company_name = company_settings.company_name or "Our Company"
    contact_name = contact.first_name if contact.first_name else contact.display_name

    # Custom text from settings
    confirmation_msg = "Thank you for your service request! We've received your submission and will be in touch shortly."
    if sales_settings and sales_settings.confirmation_message:
        confirmation_msg = sales_settings.confirmation_message

    lines = [
        f"{company_name}",
        "SERVICE REQUEST RECEIVED",
        "=" * 50,
        "",
        f"Hi {contact_name},",
        "",
        confirmation_msg,
        "",
        "-" * 50,
        "REQUEST DETAILS",
        "-" * 50,
        f"Request Number: {service_request.request_number}",
        f"Service Requested: {service_request.title}",
    ]

    if service_request.service_location and service_request.service_location.full_address:
        lines.append(f"Service Address: {service_request.service_location.full_address}")

    if service_request.requested_date:
        lines.append(f"Preferred Date: {service_request.requested_date.strftime('%B %d, %Y')}")
        if service_request.preferred_time:
            lines.append(f"Preferred Time: {service_request.preferred_time}")

    if service_request.description:
        lines.extend([
            "",
            "Additional Details:",
            service_request.description,
        ])

    # Custom or default next steps
    custom_next_steps = None
    if sales_settings and sales_settings.next_steps:
        custom_next_steps = [
            line.strip() for line in sales_settings.next_steps.splitlines()
            if line.strip()
        ]

    lines.extend([
        "",
        "-" * 50,
        "WHAT HAPPENS NEXT?",
        "-" * 50,
    ])
    if custom_next_steps:
        lines.extend(f"* {step}" for step in custom_next_steps)
    else:
        lines.extend([
            "* Our team will review your request",
            "* We'll contact you within 1-2 business days",
            "* We may schedule a site visit if needed",
        ])
    lines.extend([
        "",
        "-" * 50,
        "",
        "Questions? Feel free to contact us.",
        "",
        "Thank you,",
        company_name,
        "",
        "-" * 50,
        "Powered by sparQ — https://www.gosparq.com?ref=email",
    ])

    return "\n".join(lines)


# -----------------------------------------------------------------------------
# Timesheet Submission Email Templates
# -----------------------------------------------------------------------------


def get_timesheet_submitted_email_html(
    employee_name: str,
    entry_count: int,
    period: str,
    company_settings,
    approve_url: str | None = None
) -> str:
    """Generate HTML email for timesheet submission notification.

    Args:
        employee_name: Name of employee who submitted
        entry_count: Number of entries submitted
        period: Date period string (e.g., "Jan 13 - Jan 19, 2026")
        company_settings: Company settings for branding
        approve_url: URL to approve timesheets page
    """
    company_name = company_settings.company_name or "Our Company"
    company_phone = ""
    company_email = ""
    company_address = ""

    entry_word = "entry" if entry_count == 1 else "entries"

    cta_html = ""
    if approve_url:
        cta_html = f"""
            <div style="margin-top: 30px; text-align: center;">
                <a href="{approve_url}" style="display: inline-block; background-color: #10b981; color: white; padding: 14px 32px; font-size: 16px; font-weight: 600; text-decoration: none; border-radius: 6px;">
                    Review Timesheets
                </a>
            </div>
        """

    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <!-- Header -->
        <div style="background-color: #1a365d; padding: 30px; border-radius: 8px 8px 0 0;">
            <h1 style="margin: 0; color: white; font-size: 24px;">{company_name}</h1>
            {"" if not company_address else f'<p style="margin: 8px 0 0 0; color: rgba(255,255,255,0.7); font-size: 13px;">{company_address}</p>'}
            <p style="margin: 10px 0 0 0; color: rgba(255,255,255,0.8); font-size: 16px;">Timesheet Notification</p>
        </div>

        <!-- Main Content -->
        <div style="background-color: white; padding: 30px; border-radius: 0 0 8px 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <p style="color: #374151; font-size: 16px; margin-top: 0;">
                A timesheet has been submitted for your review.
            </p>

            <!-- Submission Details -->
            <div style="background-color: #f9fafb; padding: 20px; border-radius: 6px; margin: 20px 0;">
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="color: #6b7280; font-size: 14px; padding: 5px 0;">Employee:</td>
                        <td style="color: #111827; font-size: 14px; text-align: right;"><strong>{employee_name}</strong></td>
                    </tr>
                    <tr>
                        <td style="color: #6b7280; font-size: 14px; padding: 5px 0;">Entries Submitted:</td>
                        <td style="color: #111827; font-size: 14px; text-align: right;">{entry_count} {entry_word}</td>
                    </tr>
                    <tr>
                        <td style="color: #6b7280; font-size: 14px; padding: 5px 0;">Period:</td>
                        <td style="color: #111827; font-size: 14px; text-align: right;">{period}</td>
                    </tr>
                </table>
            </div>

            {cta_html}

            <!-- Footer -->
            <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb; text-align: center;">
                <p style="color: #6b7280; font-size: 13px; margin: 0;">
                    {company_name}<br>
                    {f'{company_phone}<br>' if company_phone else ''}
                    {f'{company_email}' if company_email else ''}
                </p>
                <p style="margin-top: 15px; color: #9ca3af; font-size: 11px;">
                    Powered by <a href="https://www.gosparq.com?ref=email" style="color: #9ca3af; text-decoration: none;">sparQ</a>
                </p>
            </div>
        </div>
    </div>
</body>
</html>
"""


def get_timesheet_submitted_email_text(
    employee_name: str,
    entry_count: int,
    period: str,
    company_settings,
    approve_url: str | None = None
) -> str:
    """Generate plain text email for timesheet submission notification.

    Args:
        employee_name: Name of employee who submitted
        entry_count: Number of entries submitted
        period: Date period string (e.g., "Jan 13 - Jan 19, 2026")
        company_settings: Company settings for branding
        approve_url: URL to approve timesheets page
    """
    company_name = company_settings.company_name or "Our Company"
    entry_word = "entry" if entry_count == 1 else "entries"

    lines = [
        f"{company_name}",
        "TIMESHEET NOTIFICATION",
        "=" * 50,
        "",
        "A timesheet has been submitted for your review.",
        "",
        "-" * 50,
        f"Employee: {employee_name}",
        f"Entries Submitted: {entry_count} {entry_word}",
        f"Period: {period}",
        "-" * 50,
        "",
    ]

    if approve_url:
        lines.extend([
            "REVIEW TIMESHEETS:",
            approve_url,
            "",
        ])

    lines.extend([
        "Thank you,",
        company_name,
        "",
        "-" * 50,
        "Powered by sparQ — https://www.gosparq.com?ref=email",
    ])

    return "\n".join(lines)


def get_password_reset_email_html(company_name: str, reset_url: str) -> str:
    """Generate HTML email for a password reset request.

    Args:
        company_name: Display name shown in the email header and footer.
        reset_url: The fully-qualified URL to reset the password.
    """
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background-color: #1a365d; padding: 30px; border-radius: 8px 8px 0 0;">
            <h1 style="margin: 0; color: white; font-size: 24px;">{company_name}</h1>
            <p style="margin: 10px 0 0 0; color: rgba(255,255,255,0.8); font-size: 16px;">{_("Password Reset")}</p>
        </div>

        <div style="background-color: white; padding: 30px; border-radius: 0 0 8px 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <p style="color: #374151; font-size: 16px; margin-top: 0;">
                {_("We received a request to reset your password for")} {company_name}.
            </p>
            <p style="color: #374151; font-size: 16px;">
                {_("Click the button below to reset your password. This link expires in 1 hour.")}
            </p>

            <div style="margin: 30px 0; text-align: center;">
                <a href="{reset_url}" style="display: inline-block; background-color: #2563eb; color: white; padding: 14px 32px; font-size: 16px; font-weight: 600; text-decoration: none; border-radius: 6px;">
                    {_("Reset Password")}
                </a>
            </div>

            <p style="color: #6b7280; font-size: 14px;">
                {_("If you didn't request this, you can safely ignore this email.")}
            </p>

            <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb;">
                <p style="color: #6b7280; font-size: 13px; margin: 0;">
                    {_("This email was sent by")} {company_name}.
                </p>
            </div>
        </div>

        <p style="margin-top: 15px; text-align: center; color: #9ca3af; font-size: 11px;">
            Powered by <a href="https://www.gosparq.com?ref=email" style="color: #9ca3af; text-decoration: none;">sparQ</a>
        </p>
    </div>
</body>
</html>"""


def get_magic_link_email_html(company_name: str, magic_link_url: str) -> str:
    """Generate HTML email for a magic link login request.

    Args:
        company_name: Display name shown in the email header and footer.
        magic_link_url: The fully-qualified URL the recipient clicks to log in.
    """
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background-color: #1a365d; padding: 30px; border-radius: 8px 8px 0 0;">
            <h1 style="margin: 0; color: white; font-size: 24px;">{company_name}</h1>
            <p style="margin: 10px 0 0 0; color: rgba(255,255,255,0.8); font-size: 16px;">{_("Login Link")}</p>
        </div>

        <div style="background-color: white; padding: 30px; border-radius: 0 0 8px 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <p style="color: #374151; font-size: 16px; margin-top: 0;">
                {_("Click the button below to log in. This link expires in 15 minutes.")}
            </p>

            <div style="margin: 30px 0; text-align: center;">
                <a href="{magic_link_url}" style="display: inline-block; background-color: #2563eb; color: white; padding: 14px 32px; font-size: 16px; font-weight: 600; text-decoration: none; border-radius: 6px;">
                    {_("Log In")}
                </a>
            </div>

            <p style="color: #6b7280; font-size: 14px;">
                {_("If you didn't request this link, you can safely ignore this email.")}
            </p>

            <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb;">
                <p style="color: #6b7280; font-size: 13px; margin: 0;">
                    {_("This email was sent by")} {company_name}.
                </p>
            </div>
        </div>

        <p style="margin-top: 15px; text-align: center; color: #9ca3af; font-size: 11px;">
            Powered by <a href="https://www.gosparq.com?ref=email" style="color: #9ca3af; text-decoration: none;">sparQ</a>
        </p>
    </div>
</body>
</html>"""


def get_email_confirmation_html(confirm_url: str) -> str:
    """Generate HTML email for signup email confirmation.

    Args:
        confirm_url: The fully-qualified URL the recipient clicks to confirm.
    """
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #fafafa;">
    <div style="max-width: 520px; margin: 0 auto; padding: 40px 20px;">
        <div style="text-align: center; margin-bottom: 24px;">
            <span style="font-size: 24px; font-weight: 600; color: #0f172a; letter-spacing: -0.02em;">spar<span style="color: #E8431A;">Q</span></span>
        </div>

        <div style="background-color: #ffffff; padding: 32px; border-radius: 12px; border: 1px solid #e2e8f0; box-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 4px 12px rgba(0,0,0,0.03);">
            <h2 style="margin: 0 0 8px 0; color: #0f172a; font-size: 1.25rem; font-weight: 600; text-align: center; letter-spacing: -0.02em;">
                {_("Welcome to sparQ")}
            </h2>
            <p style="color: #64748b; font-size: 14px; margin: 0 0 24px 0; text-align: center;">
                {_("Confirm your email to set up your workspace.")}
            </p>

            <div style="text-align: center; margin: 28px 0;">
                <a href="{confirm_url}" style="display: inline-block; background-color: #2563eb; color: white; padding: 12px 28px; font-size: 15px; font-weight: 500; text-decoration: none; border-radius: 8px;">
                    {_("Confirm & Get Started")}
                </a>
            </div>

            <p style="color: #94a3b8; font-size: 13px; text-align: center; margin: 0 0 20px 0;">
                {_("This link expires in 30 minutes.")}
            </p>

            <p style="color: #94a3b8; font-size: 11px; text-align: center; margin: 0; word-break: break-all;">
                {_("Or copy and paste this URL into your browser:")}<br>
                <a href="{confirm_url}" style="color: #64748b; text-decoration: none;">{confirm_url}</a>
            </p>

            <div style="margin-top: 28px; padding-top: 20px; border-top: 1px solid #e2e8f0;">
                <p style="color: #94a3b8; font-size: 12px; margin: 0; text-align: center;">
                    {_("If you didn't create an account, you can safely ignore this email.")}
                </p>
            </div>
        </div>

        <p style="margin-top: 16px; text-align: center; color: #94a3b8; font-size: 11px;">
            Powered by <a href="https://www.gosparq.com?ref=email" style="color: #94a3b8; text-decoration: none;">sparQ</a>
        </p>
    </div>
</body>
</html>"""


def get_onboarding_invite_email_html(
    company_name: str,
    first_name: str,
    position: str | None,
    start_date_str: str | None,
    magic_link: str,
) -> str:
    """Generate HTML email for an onboarding invite.

    Args:
        company_name: Display name shown in the email header.
        first_name: Employee's first name.
        position: Job position title, or None.
        start_date_str: Formatted start date string, or None.
        magic_link: The fully-qualified magic link URL.
    """
    position_text = f" as a {position}" if position else ""
    start_date_text = f" Your start date is {start_date_str}." if start_date_str else ""

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background-color: #1a365d; padding: 30px; border-radius: 8px 8px 0 0;">
            <h1 style="margin: 0; color: white; font-size: 24px;">{company_name}</h1>
            <p style="margin: 10px 0 0 0; color: rgba(255,255,255,0.8); font-size: 16px;">{_("Welcome to the Team!")}</p>
        </div>

        <div style="background-color: white; padding: 30px; border-radius: 0 0 8px 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <p style="color: #374151; font-size: 16px; margin-top: 0;">
                Hello {first_name},
            </p>

            <p style="color: #374151; font-size: 16px;">
                {_("We're excited to have you join us")}{position_text}!{start_date_text}
            </p>

            <p style="color: #374151; font-size: 16px;">
                {_("Please complete your onboarding by clicking the button below. You'll provide your personal information, sign any required documents, and complete tax forms.")}
            </p>

            <div style="margin: 30px 0; text-align: center;">
                <a href="{magic_link}" style="display: inline-block; background-color: #2563eb; color: white; padding: 14px 32px; font-size: 16px; font-weight: 600; text-decoration: none; border-radius: 6px;">
                    {_("Start Onboarding")}
                </a>
            </div>

            <p style="color: #6b7280; font-size: 14px; text-align: center;">
                {_("This link is unique to you. Please do not share it with others.")}
            </p>

            <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb;">
                <p style="color: #6b7280; font-size: 13px; margin: 0;">
                    {_("If you have any questions, please contact your manager or HR.")}
                </p>
            </div>
        </div>

        <p style="margin-top: 15px; text-align: center; color: #9ca3af; font-size: 11px;">
            Powered by <a href="https://www.gosparq.com?ref=email" style="color: #9ca3af; text-decoration: none;">sparQ</a>
        </p>
    </div>
</body>
</html>"""


def get_onboarding_invite_email_text(
    company_name: str,
    first_name: str,
    position: str | None,
    start_date_str: str | None,
    magic_link: str,
) -> str:
    """Generate plain text email for an onboarding invite.

    Args:
        company_name: Display name shown in the email header.
        first_name: Employee's first name.
        position: Job position title, or None.
        start_date_str: Formatted start date string, or None.
        magic_link: The fully-qualified magic link URL.
    """
    position_text = f" as a {position}" if position else ""
    start_date_text = f" Your start date is {start_date_str}." if start_date_str else ""

    return f"""{company_name}
{_("Welcome to the Team!")}
{'=' * 50}

Hello {first_name},

{_("We're excited to have you join us")}{position_text}!{start_date_text}

{_("Please complete your onboarding by visiting the link below:")}
{magic_link}

{_("This link is unique to you. Please do not share it with others.")}

{_("If you have any questions, please contact your manager or HR.")}"""


def get_onboarding_welcome_email_html(
    company_name: str, first_name: str, email: str, login_url: str
) -> str:
    """Generate HTML email for onboarding completion welcome.

    Args:
        company_name: Display name shown in the email header.
        first_name: Employee's first name.
        email: Employee's login email address.
        login_url: The fully-qualified login page URL.
    """
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background-color: #1a365d; padding: 30px; border-radius: 8px 8px 0 0;">
            <h1 style="margin: 0; color: white; font-size: 24px;">{company_name}</h1>
            <p style="margin: 10px 0 0 0; color: rgba(255,255,255,0.9); font-size: 16px;">{_("Your Onboarding is Complete!")}</p>
        </div>

        <div style="background-color: white; padding: 30px; border-radius: 0 0 8px 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <p style="color: #374151; font-size: 16px; margin-top: 0;">
                Hello {first_name},
            </p>

            <p style="color: #374151; font-size: 16px;">
                {_("Great news! Your onboarding has been approved and your account is now fully active.")}
            </p>

            <p style="color: #374151; font-size: 16px;">
                {_("Click the button below to log in and get started:")}
            </p>

            <div style="margin: 30px 0; text-align: center;">
                <a href="{login_url}" style="display: inline-block; background-color: #2563eb; color: white; padding: 14px 32px; font-size: 16px; font-weight: 600; text-decoration: none; border-radius: 6px;">
                    {_("Login to Get Started")}
                </a>
            </div>

            <div style="background-color: #f3f4f6; padding: 15px; border-radius: 6px; margin: 20px 0;">
                <p style="color: #374151; font-size: 14px; margin: 0;">
                    <strong>{_("Your login email:")}</strong> {email}
                </p>
            </div>

            <p style="color: #6b7280; font-size: 14px;">
                {_("Enter your email on the login page and we'll send you a secure link to sign in.")}
            </p>

            <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb;">
                <p style="color: #6b7280; font-size: 13px; margin: 0;">
                    {_("If you have any questions, please contact your manager or HR.")}
                </p>
            </div>
        </div>

        <p style="margin-top: 15px; text-align: center; color: #9ca3af; font-size: 11px;">
            Powered by <a href="https://www.gosparq.com?ref=email" style="color: #9ca3af; text-decoration: none;">sparQ</a>
        </p>
    </div>
</body>
</html>"""


def get_onboarding_welcome_email_text(
    company_name: str, first_name: str, email: str, login_url: str
) -> str:
    """Generate plain text email for onboarding completion welcome.

    Args:
        company_name: Display name shown in the email header.
        first_name: Employee's first name.
        email: Employee's login email address.
        login_url: The fully-qualified login page URL.
    """
    return f"""{company_name}
{_("Your Onboarding is Complete!")}
{'=' * 50}

Hello {first_name},

{_("Great news! Your onboarding has been approved and your account is now fully active.")}

{_("To get started, log in at:")}
{login_url}

{_("Your login email:")} {email}

{_("Enter your email on the login page and we'll send you a secure link to sign in.")}

{_("If you have any questions, please contact your manager or HR.")}"""


def get_workspace_invite_email_html(company_name: str, invite_url: str) -> str:
    """Generate HTML email for a workspace invite.

    Args:
        company_name: Display name shown in the email header.
        invite_url: The fully-qualified invite acceptance URL.
    """
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background-color: #1a365d; padding: 30px; border-radius: 8px 8px 0 0;">
            <h1 style="margin: 0; color: white; font-size: 24px;">{company_name}</h1>
            <p style="margin: 10px 0 0 0; color: rgba(255,255,255,0.8); font-size: 16px;">{_("You're Invited!")}</p>
        </div>

        <div style="background-color: white; padding: 30px; border-radius: 0 0 8px 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <p style="color: #374151; font-size: 16px; margin-top: 0;">
                {_("Hello,")}
            </p>

            <p style="color: #374151; font-size: 16px;">
                {_("You've been invited to join")} <strong>{company_name}</strong> {_("on sparQ. Click the button below to set up your account and join the team.")}
            </p>

            <div style="margin: 30px 0; text-align: center;">
                <a href="{invite_url}" style="display: inline-block; background-color: #2563eb; color: white; padding: 14px 32px; font-size: 16px; font-weight: 600; text-decoration: none; border-radius: 6px;">
                    {_("Join Team")}
                </a>
            </div>

            <p style="color: #6b7280; font-size: 14px; text-align: center;">
                {_("This link expires in 7 days. Please do not share it with others.")}
            </p>

            <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb;">
                <p style="color: #6b7280; font-size: 13px; margin: 0;">
                    {_("If you weren't expecting this invite, you can safely ignore this email.")}
                </p>
            </div>
        </div>

        <p style="margin-top: 15px; text-align: center; color: #9ca3af; font-size: 11px;">
            Powered by <a href="https://www.gosparq.com?ref=email" style="color: #9ca3af; text-decoration: none;">sparQ</a>
        </p>
    </div>
</body>
</html>"""


def get_workspace_invite_email_text(company_name: str, invite_url: str) -> str:
    """Generate plain text email for a workspace invite.

    Args:
        company_name: Display name shown in the email header.
        invite_url: The fully-qualified invite acceptance URL.
    """
    return f"""{company_name}
{_("You're Invited!")}
{'=' * 50}

{_("Hello,")}

{_("You've been invited to join")} {company_name} {_("on sparQ.")}

{_("Click the link below to set up your account and join the team:")}
{invite_url}

{_("This link expires in 7 days. Please do not share it with others.")}

{_("If you weren't expecting this invite, you can safely ignore this email.")}"""


def get_new_request_admin_email_html(
    service_request,
    contact,
    company_settings,
    request_url: str,
) -> str:
    """Generate HTML email for admin notification of a new service request.

    Args:
        service_request: The ServiceRequest that was submitted.
        contact: The Contact who submitted the request.
        company_settings: Company settings for branding.
        request_url: Deep link URL to the request detail page.

    Returns:
        HTML string for the email body.
    """
    company_name = company_settings.company_name or "Our Company"
    company_phone = ""
    company_email = ""
    company_address = ""

    contact_name = contact.display_name if contact else "Unknown"
    contact_email = contact.email or "—"
    contact_phone = contact.phone or "—"

    # Format requested date/time if provided
    date_time_html = ""
    if service_request.requested_date:
        date_str = service_request.requested_date.strftime("%B %d, %Y")
        date_time_html = f"""
                    <tr>
                        <td style="color: #6b7280; font-size: 14px; padding: 5px 0;">Preferred Date:</td>
                        <td style="color: #111827; font-size: 14px; text-align: right;">{date_str}</td>
                    </tr>
        """
        if service_request.preferred_time:
            date_time_html += f"""
                    <tr>
                        <td style="color: #6b7280; font-size: 14px; padding: 5px 0;">Preferred Time:</td>
                        <td style="color: #111827; font-size: 14px; text-align: right;">{service_request.preferred_time}</td>
                    </tr>
            """

    # Service address from service location
    address_html = ""
    if service_request.service_location and service_request.service_location.full_address:
        address_html = f"""
                    <tr>
                        <td style="color: #6b7280; font-size: 14px; padding: 5px 0;">Service Address:</td>
                        <td style="color: #111827; font-size: 14px; text-align: right;">{service_request.service_location.full_address}</td>
                    </tr>
        """

    # Description section
    description_html = ""
    if service_request.description:
        description_html = f"""
            <div style="margin-top: 20px; padding: 15px; background-color: #f9fafb; border-radius: 6px;">
                <p style="margin: 0 0 8px 0; color: #6b7280; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;">Additional Details</p>
                <p style="margin: 0; color: #374151; font-size: 14px;">{service_request.description}</p>
            </div>
        """

    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <!-- Header -->
        <div style="background-color: #1a365d; padding: 30px; border-radius: 8px 8px 0 0;">
            <h1 style="margin: 0; color: white; font-size: 24px;">{company_name}</h1>
            {"" if not company_address else f'<p style="margin: 8px 0 0 0; color: rgba(255,255,255,0.7); font-size: 13px;">{company_address}</p>'}
            <p style="margin: 10px 0 0 0; color: rgba(255,255,255,0.9); font-size: 16px;">New Service Request</p>
        </div>

        <!-- Main Content -->
        <div style="background-color: white; padding: 30px; border-radius: 0 0 8px 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">

            <!-- Contact Info (top, per spec) -->
            <div style="background-color: #eff6ff; padding: 15px; border-radius: 6px; margin-bottom: 20px; border: 1px solid #bfdbfe;">
                <h3 style="margin: 0 0 10px 0; color: #1e40af; font-size: 14px; text-transform: uppercase; letter-spacing: 0.5px;">Contact Information</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="color: #6b7280; font-size: 14px; padding: 3px 0;">Name:</td>
                        <td style="color: #111827; font-size: 14px; text-align: right;"><strong>{contact_name}</strong></td>
                    </tr>
                    <tr>
                        <td style="color: #6b7280; font-size: 14px; padding: 3px 0;">Email:</td>
                        <td style="color: #111827; font-size: 14px; text-align: right;"><a href="mailto:{contact_email}" style="color: #2563eb; text-decoration: none;">{contact_email}</a></td>
                    </tr>
                    <tr>
                        <td style="color: #6b7280; font-size: 14px; padding: 3px 0;">Phone:</td>
                        <td style="color: #111827; font-size: 14px; text-align: right;"><a href="tel:{contact_phone}" style="color: #2563eb; text-decoration: none;">{contact_phone}</a></td>
                    </tr>
                </table>
            </div>

            <!-- Request Details -->
            <div style="background-color: #f9fafb; padding: 20px; border-radius: 6px; margin: 20px 0;">
                <h3 style="margin: 0 0 15px 0; color: #111827; font-size: 16px;">Request Details</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="color: #6b7280; font-size: 14px; padding: 5px 0;">Request Number:</td>
                        <td style="color: #111827; font-size: 14px; text-align: right;"><strong>{service_request.request_number}</strong></td>
                    </tr>
                    <tr>
                        <td style="color: #6b7280; font-size: 14px; padding: 5px 0;">Service Requested:</td>
                        <td style="color: #111827; font-size: 14px; text-align: right;">{service_request.title}</td>
                    </tr>
                    {address_html}
                    {date_time_html}
                </table>
            </div>

            {description_html}

            <!-- CTA Button -->
            <div style="text-align: center; margin: 25px 0;">
                <a href="{request_url}" style="display: inline-block; background-color: #2563eb; color: white; padding: 12px 30px; border-radius: 6px; text-decoration: none; font-size: 16px; font-weight: 600;">View Request</a>
            </div>

            <!-- Footer -->
            <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb; text-align: center;">
                <p style="color: #6b7280; font-size: 13px; margin: 0;">
                    {company_name}<br>
                    {f'{company_phone}<br>' if company_phone else ''}
                    {f'{company_email}' if company_email else ''}
                </p>
                <p style="margin-top: 15px; color: #9ca3af; font-size: 11px;">
                    Powered by <a href="https://www.gosparq.com?ref=email" style="color: #9ca3af; text-decoration: none;">sparQ</a>
                </p>
            </div>
        </div>
    </div>
</body>
</html>
"""


def get_new_request_admin_email_text(
    service_request,
    contact,
    company_settings,
    request_url: str,
) -> str:
    """Generate plain text email for admin notification of a new service request.

    Args:
        service_request: The ServiceRequest that was submitted.
        contact: The Contact who submitted the request.
        company_settings: Company settings for branding.
        request_url: Deep link URL to the request detail page.

    Returns:
        Plain text string for the email body.
    """
    company_name = company_settings.company_name or "Our Company"

    contact_name = contact.display_name if contact else "Unknown"
    contact_email = contact.email or "—"
    contact_phone = contact.phone or "—"

    lines = [
        f"{company_name}",
        "NEW SERVICE REQUEST",
        "=" * 50,
        "",
        "-" * 50,
        "CONTACT INFORMATION",
        "-" * 50,
        f"Name: {contact_name}",
        f"Email: {contact_email}",
        f"Phone: {contact_phone}",
        "",
        "-" * 50,
        "REQUEST DETAILS",
        "-" * 50,
        f"Request Number: {service_request.request_number}",
        f"Service Requested: {service_request.title}",
    ]

    if service_request.service_location and service_request.service_location.full_address:
        lines.append(f"Service Address: {service_request.service_location.full_address}")

    if service_request.requested_date:
        lines.append(f"Preferred Date: {service_request.requested_date.strftime('%B %d, %Y')}")
        if service_request.preferred_time:
            lines.append(f"Preferred Time: {service_request.preferred_time}")

    if service_request.description:
        lines.extend([
            "",
            "Additional Details:",
            service_request.description,
        ])

    lines.extend([
        "",
        "-" * 50,
        "",
        f"View this request: {request_url}",
        "",
        "-" * 50,
        "",
        "Powered by sparQ — https://www.gosparq.com?ref=email",
    ])

    return "\n".join(lines)


# ── Task Emails ────────────────────────────────────────────────────


def get_task_assigned_email_html(
    company_name: str,
    assignee_first_name: str,
    raiser_name: str,
    title: str,
    urgency_label: str,
    urgency_color: str,
    context_note: str | None,
    action_url: str,
) -> str:
    """Generate HTML email notifying an assignee of a new Task.

    Args:
        company_name: Display name shown in the email header.
        assignee_first_name: Assignee's first name.
        raiser_name: Name of the person who raised the item.
        title: Action item title.
        urgency_label: Tier label (e.g. "Now", "Later", "Whenever").
        urgency_color: Hex color for the tier badge.
        context_note: Optional context from the raiser.
        action_url: Fully-qualified URL to the action item.
    """
    context_html = ""
    if context_note:
        context_html = f"""
            <p style="color: #6b7280; font-size: 14px; margin: 12px 0 0 0; font-style: italic;">
                &ldquo;{context_note}&rdquo;
            </p>"""

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background-color: #1a365d; padding: 30px; border-radius: 8px 8px 0 0;">
            <h1 style="margin: 0; color: white; font-size: 24px;">{company_name}</h1>
            <p style="margin: 10px 0 0 0; color: rgba(255,255,255,0.8); font-size: 16px;">Task Assigned</p>
        </div>

        <div style="background-color: white; padding: 30px; border-radius: 0 0 8px 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <p style="color: #374151; font-size: 16px; margin-top: 0;">
                Hi {assignee_first_name},
            </p>

            <p style="color: #374151; font-size: 16px;">
                {raiser_name} has assigned you an action item:
            </p>

            <div style="background-color: #f9fafb; border-radius: 6px; padding: 16px; margin: 20px 0;">
                <p style="color: #111827; font-size: 16px; font-weight: 600; margin: 0;">
                    {title}
                </p>
                <p style="margin: 8px 0 0 0;">
                    <span style="display: inline-block; background-color: {urgency_color}; color: white; padding: 2px 10px; border-radius: 4px; font-size: 12px; font-weight: 600;">
                        {urgency_label}
                    </span>
                </p>{context_html}
            </div>

            <div style="margin: 30px 0; text-align: center;">
                <a href="{action_url}" style="display: inline-block; background-color: #2563eb; color: white; padding: 14px 32px; font-size: 16px; font-weight: 600; text-decoration: none; border-radius: 6px;">
                    View Task
                </a>
            </div>

            <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb;">
                <p style="color: #6b7280; font-size: 13px; margin: 0;">
                    You can respond to this action item directly from sparQ.
                </p>
            </div>
        </div>

        <p style="margin-top: 15px; text-align: center; color: #9ca3af; font-size: 11px;">
            Powered by <a href="https://www.gosparq.com?ref=email" style="color: #9ca3af; text-decoration: none;">sparQ</a>
        </p>
    </div>
</body>
</html>"""


def get_task_assigned_email_text(
    company_name: str,
    assignee_first_name: str,
    raiser_name: str,
    title: str,
    urgency_label: str,
    context_note: str | None,
    action_url: str,
) -> str:
    """Generate plain text email notifying an assignee of a new Task.

    Args:
        company_name: Display name shown in the email header.
        assignee_first_name: Assignee's first name.
        raiser_name: Name of the person who raised the item.
        title: Action item title.
        urgency_label: Tier label (e.g. "Now", "Later", "Whenever").
        context_note: Optional context from the raiser.
        action_url: Fully-qualified URL to the action item.
    """
    context_text = f'\n"{context_note}"\n' if context_note else ""

    return f"""{company_name}
Task Assigned
{'=' * 50}

Hi {assignee_first_name},

{raiser_name} has assigned you an action item:

{title}
Priority: {urgency_label}
{context_text}
View Task: {action_url}

{'-' * 50}

Powered by sparQ — https://www.gosparq.com?ref=email"""


def get_task_resolved_email_html(
    company_name: str,
    raiser_first_name: str,
    assignee_name: str,
    title: str,
    resolution_note: str | None,
    action_url: str,
) -> str:
    """Generate HTML email notifying the raiser that an Task was resolved.

    Args:
        company_name: Display name shown in the email header.
        raiser_first_name: Raiser's first name.
        assignee_name: Full or first name of the person who resolved it.
        title: Action item title.
        resolution_note: Optional note from the resolver.
        action_url: Fully-qualified URL to the action item.
    """
    note_html = ""
    if resolution_note:
        note_html = f"""
                <p style="color: #6b7280; font-size: 14px; margin: 12px 0 0 0;">
                    <strong>Note:</strong> {resolution_note}
                </p>"""

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background-color: #1a365d; padding: 30px; border-radius: 8px 8px 0 0;">
            <h1 style="margin: 0; color: white; font-size: 24px;">{company_name}</h1>
            <p style="margin: 10px 0 0 0; color: rgba(255,255,255,0.8); font-size: 16px;">Task Resolved</p>
        </div>

        <div style="background-color: white; padding: 30px; border-radius: 0 0 8px 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <p style="color: #374151; font-size: 16px; margin-top: 0;">
                Hi {raiser_first_name},
            </p>

            <p style="color: #374151; font-size: 16px;">
                {assignee_name} has resolved your action item:
            </p>

            <div style="background-color: #f0fdf4; border-radius: 6px; padding: 16px; margin: 20px 0;">
                <p style="color: #111827; font-size: 16px; font-weight: 600; margin: 0;">
                    {title}
                </p>
                <p style="margin: 8px 0 0 0;">
                    <span style="display: inline-block; background-color: #16a34a; color: white; padding: 2px 10px; border-radius: 4px; font-size: 12px; font-weight: 600;">
                        Resolved
                    </span>
                </p>{note_html}
            </div>

            <div style="margin: 30px 0; text-align: center;">
                <a href="{action_url}" style="display: inline-block; background-color: #2563eb; color: white; padding: 14px 32px; font-size: 16px; font-weight: 600; text-decoration: none; border-radius: 6px;">
                    View Details
                </a>
            </div>

            <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb;">
                <p style="color: #6b7280; font-size: 13px; margin: 0;">
                    No further action is needed on your part.
                </p>
            </div>
        </div>

        <p style="margin-top: 15px; text-align: center; color: #9ca3af; font-size: 11px;">
            Powered by <a href="https://www.gosparq.com?ref=email" style="color: #9ca3af; text-decoration: none;">sparQ</a>
        </p>
    </div>
</body>
</html>"""


def get_task_resolved_email_text(
    company_name: str,
    raiser_first_name: str,
    assignee_name: str,
    title: str,
    resolution_note: str | None,
    action_url: str,
) -> str:
    """Generate plain text email notifying the raiser that an Task was resolved.

    Args:
        company_name: Display name shown in the email header.
        raiser_first_name: Raiser's first name.
        assignee_name: Full or first name of the person who resolved it.
        title: Action item title.
        resolution_note: Optional note from the resolver.
        action_url: Fully-qualified URL to the action item.
    """
    note_text = f"\nNote: {resolution_note}\n" if resolution_note else ""

    return f"""{company_name}
Task Resolved
{'=' * 50}

Hi {raiser_first_name},

{assignee_name} has resolved your action item:

{title}
{note_text}
View Details: {action_url}

{'-' * 50}

Powered by sparQ — https://www.gosparq.com?ref=email"""


def get_task_watcher_resolved_email_html(
    company_name: str,
    watcher_first_name: str,
    assignee_name: str,
    raiser_name: str,
    title: str,
    resolution_note: str | None,
    action_url: str,
) -> str:
    """Generate HTML email notifying a watcher that an Task was resolved.

    Args:
        company_name: Display name shown in the email header.
        watcher_first_name: Watcher's first name.
        assignee_name: Name of the person who resolved it.
        raiser_name: Name of the person who raised it.
        title: Action item title.
        resolution_note: Optional note from the resolver.
        action_url: Fully-qualified URL to the action item.
    """
    note_html = ""
    if resolution_note:
        note_html = f"""
                <p style="color: #6b7280; font-size: 14px; margin: 12px 0 0 0;">
                    <strong>Note:</strong> {resolution_note}
                </p>"""

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background-color: #1a365d; padding: 30px; border-radius: 8px 8px 0 0;">
            <h1 style="margin: 0; color: white; font-size: 24px;">{company_name}</h1>
            <p style="margin: 10px 0 0 0; color: rgba(255,255,255,0.8); font-size: 16px;">Task Resolved</p>
        </div>

        <div style="background-color: white; padding: 30px; border-radius: 0 0 8px 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <p style="color: #374151; font-size: 16px; margin-top: 0;">
                Hi {watcher_first_name},
            </p>

            <p style="color: #374151; font-size: 16px;">
                An action item you're watching has been resolved by {assignee_name}:
            </p>

            <div style="background-color: #f0fdf4; border-radius: 6px; padding: 16px; margin: 20px 0;">
                <p style="color: #111827; font-size: 16px; font-weight: 600; margin: 0;">
                    {title}
                </p>
                <p style="margin: 8px 0 0 0;">
                    <span style="display: inline-block; background-color: #16a34a; color: white; padding: 2px 10px; border-radius: 4px; font-size: 12px; font-weight: 600;">
                        Resolved
                    </span>
                </p>
                <p style="color: #6b7280; font-size: 13px; margin: 8px 0 0 0;">
                    Raised by {raiser_name}
                </p>{note_html}
            </div>

            <div style="margin: 30px 0; text-align: center;">
                <a href="{action_url}" style="display: inline-block; background-color: #2563eb; color: white; padding: 14px 32px; font-size: 16px; font-weight: 600; text-decoration: none; border-radius: 6px;">
                    View Details
                </a>
            </div>

            <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb;">
                <p style="color: #6b7280; font-size: 13px; margin: 0;">
                    You received this because you were added as a watcher on this action item.
                </p>
            </div>
        </div>

        <p style="margin-top: 15px; text-align: center; color: #9ca3af; font-size: 11px;">
            Powered by <a href="https://www.gosparq.com?ref=email" style="color: #9ca3af; text-decoration: none;">sparQ</a>
        </p>
    </div>
</body>
</html>"""


def get_task_watcher_resolved_email_text(
    company_name: str,
    watcher_first_name: str,
    assignee_name: str,
    raiser_name: str,
    title: str,
    resolution_note: str | None,
    action_url: str,
) -> str:
    """Generate plain text email notifying a watcher that an Task was resolved.

    Args:
        company_name: Display name shown in the email header.
        watcher_first_name: Watcher's first name.
        assignee_name: Name of the person who resolved it.
        raiser_name: Name of the person who raised it.
        title: Action item title.
        resolution_note: Optional note from the resolver.
        action_url: Fully-qualified URL to the action item.
    """
    note_text = f"\nNote: {resolution_note}\n" if resolution_note else ""

    return f"""{company_name}
Task Resolved
{'=' * 50}

Hi {watcher_first_name},

An action item you're watching has been resolved by {assignee_name}:

{title}
Raised by {raiser_name}
{note_text}
View Details: {action_url}

{'-' * 50}
You received this because you were added as a watcher on this action item.

Powered by sparQ — https://www.gosparq.com?ref=email"""
