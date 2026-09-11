"""Framework-independent invoice processing workflow."""

from collections.abc import Callable
from time import perf_counter

from .models import (
    AIExtractionResult,
    ExtractedInvoice,
    InvoiceData,
    ProcessedInvoice,
    ProcessingMetrics,
)
from .pdf_extractor import extract_text_from_pdf_with_method


AIExtractor = Callable[
    [str],
    InvoiceData | AIExtractionResult,
]


def extract_invoice_text(
    pdf_bytes: bytes,
    filename: str,
) -> ExtractedInvoice:
    """Extract PDF text locally and record its method and duration."""

    started_at = perf_counter()
    text, extraction_method = extract_text_from_pdf_with_method(pdf_bytes)
    extraction_seconds = perf_counter() - started_at

    return ExtractedInvoice(
        source_filename=filename,
        text=text,
        extraction_method=extraction_method,
        local_extraction_seconds=round(extraction_seconds, 4),
    )


def process_extracted_invoice(
    extracted: ExtractedInvoice,
    ai_extractor: AIExtractor,
) -> ProcessedInvoice:
    """Process previewed text and retain timing and usage metadata."""

    ai_result = ai_extractor(extracted.text)

    if isinstance(ai_result, AIExtractionResult):
        invoice = ai_result.invoice
        metrics = ai_result.metrics.model_copy(
            update={
                "extraction_method": extracted.extraction_method,
                "local_extraction_seconds": (
                    extracted.local_extraction_seconds
                ),
            }
        )
    else:
        invoice = ai_result
        metrics = ProcessingMetrics(
            extraction_method=extracted.extraction_method,
            local_extraction_seconds=extracted.local_extraction_seconds,
        )

    return ProcessedInvoice(
        source_filename=extracted.source_filename,
        invoice=invoice,
        source_text=extracted.text,
        processing_metrics=metrics,
    )


def process_invoice(
    pdf_bytes: bytes,
    filename: str,
    ai_extractor: AIExtractor,
) -> ProcessedInvoice:
    """Run one invoice through PDF reading and AI extraction."""

    extracted = extract_invoice_text(pdf_bytes, filename)
    return process_extracted_invoice(extracted, ai_extractor)