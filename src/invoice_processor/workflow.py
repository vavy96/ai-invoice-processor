"""Framework-independent invoice processing workflow."""

from collections.abc import Callable

from .models import ExtractedInvoice, InvoiceData, ProcessedInvoice
from .pdf_extractor import extract_text_from_pdf


def extract_invoice_text(pdf_bytes: bytes, filename: str) -> ExtractedInvoice:
    """Extract local PDF text without contacting an AI service."""

    return ExtractedInvoice(
        source_filename=filename,
        text=extract_text_from_pdf(pdf_bytes),
    )


def process_extracted_invoice(
    extracted: ExtractedInvoice,
    ai_extractor: Callable[[str], InvoiceData],
) -> ProcessedInvoice:
    """Send already-previewed text to the configured AI extractor."""

    return ProcessedInvoice(
        source_filename=extracted.source_filename,
        invoice=ai_extractor(extracted.text),
        source_text=extracted.text,
    )


def process_invoice(
    pdf_bytes: bytes,
    filename: str,
    ai_extractor: Callable[[str], InvoiceData],
) -> ProcessedInvoice:
    """Run one invoice through PDF reading and structured AI extraction."""

    extracted = extract_invoice_text(pdf_bytes, filename)
    return process_extracted_invoice(extracted, ai_extractor)
