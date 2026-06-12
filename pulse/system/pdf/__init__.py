# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     PDF generation module initialization.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

"""PDF generation service for business documents.

This package provides PDF generation for quotes, invoices, jobs,
and service requests using ReportLab (pure Python).

Functions:
    generate_quote_pdf: Generate a quote PDF with line items and totals.
    generate_invoice_pdf: Generate an invoice PDF with payment info.
    generate_job_pdf: Generate a job summary PDF with visits.
    generate_request_pdf: Generate a service request PDF.

Example:
    Generate and serve a quote PDF::

        from system.pdf import generate_quote_pdf
        from flask import Response

        @route("/quote/<id>/pdf")
        def download_quote(id):
            quote = Quote.query.get_or_404(id)
            company = WorkspaceSettings.get_instance()
            pdf_bytes = generate_quote_pdf(quote, company)

            return Response(
                pdf_bytes,
                mimetype="application/pdf",
                headers={
                    "Content-Disposition": f"attachment; filename={quote.quote_number}.pdf"
                }
            )
"""

from system.pdf.service import (
    generate_quote_pdf,
    generate_invoice_pdf,
    generate_job_pdf,
    generate_request_pdf,
)

__all__ = [
    "generate_quote_pdf",
    "generate_invoice_pdf",
    "generate_job_pdf",
    "generate_request_pdf",
]
