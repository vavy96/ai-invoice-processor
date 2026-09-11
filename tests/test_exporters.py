"""Tests for CSV and XLSX exports."""

from io import BytesIO

import pandas as pd

from invoice_processor.exporters import to_csv_bytes, to_xlsx_bytes
from invoice_processor.models import InvoiceData, ProcessedInvoice


def sample_results() -> list[ProcessedInvoice]:
    return [
        ProcessedInvoice(
            source_filename="invoice.pdf",
            invoice=InvoiceData(
                supplier_name="Example Ltd",
                supplier_tax_id="TAX-123",
                invoice_number="INV-1",
                currency="USD",
                net_amount=10,
                tax_amount=2,
                total_amount=12,
                purchase_order_number="PO-9",
                products_services_summary=(
                    "Monthly support (service period: January 2026); Keyboard"
                ),
                confidence_notes="All values were clearly shown.",
            ),
        )
    ]


def test_csv_contains_invoice_summary() -> None:
    csv_text = to_csv_bytes(sample_results()).decode("utf-8-sig")

    assert "source_filename" in csv_text
    assert "invoice.pdf" in csv_text
    assert "INV-1" in csv_text
    assert "products_services_summary" in csv_text
    assert "Monthly support (service period: January 2026); Keyboard" in csv_text


def test_xlsx_contains_the_fixed_invoice_schema() -> None:
    workbook = pd.ExcelFile(BytesIO(to_xlsx_bytes(sample_results())))

    assert workbook.sheet_names == ["Invoices"]
    invoices = pd.read_excel(workbook, sheet_name="Invoices")
    assert invoices.loc[0, "purchase_order_number"] == "PO-9"
    assert (
        invoices.loc[0, "products_services_summary"]
        == "Monthly support (service period: January 2026); Keyboard"
    )
    assert invoices.loc[0, "confidence_notes"] == "All values were clearly shown."
