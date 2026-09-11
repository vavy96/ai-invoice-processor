"""CSV and XLSX export helpers."""

from io import BytesIO

import pandas as pd

from .duplicate_detector import find_duplicate_invoices
from .metrics import compare_invoice_fields, field_accuracy_percent
from .models import ProcessedInvoice, ProcessingMetrics


INVOICE_COLUMNS = [
    "source_filename",
    "customer_profile",
    "supplier_name",
    "supplier_tax_id",
    "invoice_number",
    "invoice_date",
    "due_date",
    "currency",
    "net_amount",
    "tax_amount",
    "total_amount",
    "purchase_order_number",
    "products_services_summary",
    "confidence_notes",
    "extraction_method",
    "local_extraction_seconds",
    "ai_processing_seconds",
    "total_processing_seconds",
    "model",
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "total_tokens",
    "estimated_cost_usd",
    "possible_duplicate",
    "duplicate_of",
]

ACCURACY_COLUMNS = [
    "source_filename",
    "field_name",
    "ai_extracted_value",
    "reviewed_value",
    "correct",
    "invoice_agreement_percent",
]


def invoices_dataframe(
    results: list[ProcessedInvoice],
) -> pd.DataFrame:
    """Flatten reviewed invoices and measurements into one row per PDF."""

    rows = []
    duplicate_matches = {
        duplicate.duplicate_index: duplicate
        for duplicate in find_duplicate_invoices(results)
    }

    for index, result in enumerate(results):
        invoice = result.invoice
        duplicate = duplicate_matches.get(index)
        metrics = getattr(
            result,
            "processing_metrics",
            ProcessingMetrics(),
        )
        total_processing_seconds = (
            metrics.local_extraction_seconds
            + metrics.ai_processing_seconds
        )

        rows.append(
            {
                "source_filename": result.source_filename,
                "customer_profile": getattr(
                    result,
                    "customer_profile_key",
                    "standard",
                ),
                "supplier_name": invoice.supplier_name,
                "supplier_tax_id": invoice.supplier_tax_id,
                "invoice_number": invoice.invoice_number,
                "invoice_date": (
                    invoice.invoice_date.isoformat()
                    if invoice.invoice_date
                    else ""
                ),
                "due_date": (
                    invoice.due_date.isoformat()
                    if invoice.due_date
                    else ""
                ),
                "currency": invoice.currency,
                "net_amount": invoice.net_amount,
                "tax_amount": invoice.tax_amount,
                "total_amount": invoice.total_amount,
                "purchase_order_number": (
                    invoice.purchase_order_number
                ),
                "products_services_summary": (
                    invoice.products_services_summary
                ),
                "confidence_notes": invoice.confidence_notes,
                "extraction_method": metrics.extraction_method,
                "local_extraction_seconds": (
                    metrics.local_extraction_seconds
                ),
                "ai_processing_seconds": (
                    metrics.ai_processing_seconds
                ),
                "total_processing_seconds": (
                    total_processing_seconds
                ),
                "model": metrics.model,
                "input_tokens": metrics.input_tokens,
                "cached_input_tokens": (
                    metrics.cached_input_tokens
                ),
                "output_tokens": metrics.output_tokens,
                "total_tokens": metrics.total_tokens,
                "estimated_cost_usd": metrics.estimated_cost_usd,
                "possible_duplicate": duplicate is not None,
                "duplicate_of": (
                    duplicate.original_filename
                    if duplicate is not None
                    else ""
                ),
            }
        )

    return pd.DataFrame(rows, columns=INVOICE_COLUMNS)


def accuracy_dataframe(
    original_results: list[ProcessedInvoice],
    reviewed_results: list[ProcessedInvoice],
) -> pd.DataFrame:
    """Create one comparison row for every reviewed invoice field."""

    if len(original_results) != len(reviewed_results):
        raise ValueError(
            "Original and reviewed invoice counts do not match."
        )

    rows = []

    for original, reviewed in zip(
        original_results,
        reviewed_results,
        strict=True,
    ):
        if original.source_filename != reviewed.source_filename:
            raise ValueError(
                "Original and reviewed invoice order does not match."
            )

        comparisons = compare_invoice_fields(
            original.invoice,
            reviewed.invoice,
        )
        agreement = field_accuracy_percent(comparisons)

        for comparison in comparisons:
            rows.append(
                {
                    "source_filename": original.source_filename,
                    "field_name": comparison.field_name,
                    "ai_extracted_value": (
                        comparison.extracted_value
                        if comparison.extracted_value is not None
                        else ""
                    ),
                    "reviewed_value": (
                        comparison.reviewed_value
                        if comparison.reviewed_value is not None
                        else ""
                    ),
                    "correct": comparison.correct,
                    "invoice_agreement_percent": agreement,
                }
            )

    return pd.DataFrame(rows, columns=ACCURACY_COLUMNS)


def to_csv_bytes(results: list[ProcessedInvoice]) -> bytes:
    """Create a UTF-8 CSV containing invoices and measurements."""

    return (
        invoices_dataframe(results)
        .to_csv(index=False)
        .encode("utf-8-sig")
    )


def to_accuracy_csv_bytes(
    original_results: list[ProcessedInvoice],
    reviewed_results: list[ProcessedInvoice],
) -> bytes:
    """Create a UTF-8 field-level accuracy report."""

    return (
        accuracy_dataframe(original_results, reviewed_results)
        .to_csv(index=False)
        .encode("utf-8-sig")
    )


def to_xlsx_bytes(
    reviewed_results: list[ProcessedInvoice],
    *,
    original_results: list[ProcessedInvoice] | None = None,
) -> bytes:
    """Create an Excel workbook with invoices and accuracy details."""

    comparison_results = (
        original_results
        if original_results is not None
        else reviewed_results
    )

    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        invoices_dataframe(reviewed_results).to_excel(
            writer,
            sheet_name="Invoices",
            index=False,
        )
        accuracy_dataframe(
            comparison_results,
            reviewed_results,
        ).to_excel(
            writer,
            sheet_name="Field Accuracy",
            index=False,
        )

    return output.getvalue()
