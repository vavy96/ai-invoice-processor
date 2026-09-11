"""CSV and XLSX export helpers."""

from io import BytesIO

import pandas as pd

from .models import ProcessedInvoice


INVOICE_COLUMNS = [
    "source_filename",
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
]


def invoices_dataframe(results: list[ProcessedInvoice]) -> pd.DataFrame:
    """Flatten invoice summaries into one row per uploaded PDF."""

    rows = []
    for result in results:
        invoice = result.invoice
        rows.append(
            {
                "source_filename": result.source_filename,
                "supplier_name": invoice.supplier_name,
                "supplier_tax_id": invoice.supplier_tax_id,
                "invoice_number": invoice.invoice_number,
                "invoice_date": invoice.invoice_date.isoformat() if invoice.invoice_date else "",
                "due_date": invoice.due_date.isoformat() if invoice.due_date else "",
                "currency": invoice.currency,
                "net_amount": invoice.net_amount,
                "tax_amount": invoice.tax_amount,
                "total_amount": invoice.total_amount,
                "purchase_order_number": invoice.purchase_order_number,
                "products_services_summary": getattr(
                    invoice, "products_services_summary", None
                ),
                "confidence_notes": invoice.confidence_notes,
            }
        )
    return pd.DataFrame(rows, columns=INVOICE_COLUMNS)


def to_csv_bytes(results: list[ProcessedInvoice]) -> bytes:
    """Create a UTF-8 CSV containing invoice-level fields."""

    return invoices_dataframe(results).to_csv(index=False).encode("utf-8-sig")


def to_xlsx_bytes(results: list[ProcessedInvoice]) -> bytes:
    """Create an Excel workbook containing the fixed invoice schema."""

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        invoices_dataframe(results).to_excel(writer, sheet_name="Invoices", index=False)
    return output.getvalue()
