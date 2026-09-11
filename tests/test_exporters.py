"""Tests for CSV, XLSX and accuracy exports."""

from datetime import date
from io import BytesIO

import pandas as pd
import pytest

from invoice_processor.exporters import (
    invoices_dataframe,
    line_items_dataframe,
    to_accuracy_csv_bytes,
    to_csv_bytes,
    to_line_items_csv_bytes,
    to_xlsx_bytes,
)
from invoice_processor.models import (
    InvoiceData,
    InvoiceLineItem,
    ProcessedInvoice,
    ProcessingMetrics,
)


def sample_results(
    *,
    total_amount: float = 12,
) -> list[ProcessedInvoice]:
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
                total_amount=total_amount,
                purchase_order_number="PO-9",
                products_services_summary=(
                    "Monthly support "
                    "(service period: January 2026); Keyboard"
                ),
                confidence_notes="All values were clearly shown.",
            ),
            processing_metrics=ProcessingMetrics(
                extraction_method="ocr",
                local_extraction_seconds=1.25,
                ai_processing_seconds=0.75,
                model="gpt-4.1-mini",
                input_tokens=500,
                cached_input_tokens=100,
                output_tokens=100,
                total_tokens=600,
                estimated_cost_usd=0.00032,
            ),
        )
    ]


def test_csv_contains_invoice_and_measurements() -> None:
    csv_text = to_csv_bytes(sample_results()).decode("utf-8-sig")

    assert "source_filename" in csv_text
    assert "invoice.pdf" in csv_text
    assert "INV-1" in csv_text
    assert "products_services_summary" in csv_text
    assert "total_processing_seconds" in csv_text
    assert "estimated_cost_usd" in csv_text
    assert "gpt-4.1-mini" in csv_text
    assert "600" in csv_text


def test_xlsx_contains_invoices_and_accuracy() -> None:
    original = sample_results(total_amount=12)
    reviewed = sample_results(total_amount=15)

    workbook = pd.ExcelFile(
        BytesIO(
            to_xlsx_bytes(
                reviewed,
                original_results=original,
            )
        )
    )

    assert workbook.sheet_names == [
        "Invoices",
        "Line Items",
        "Field Accuracy",
    ]

    invoices = pd.read_excel(workbook, sheet_name="Invoices")
    accuracy = pd.read_excel(
        workbook,
        sheet_name="Field Accuracy",
    )

    assert invoices.loc[0, "purchase_order_number"] == "PO-9"
    assert invoices.loc[0, "total_amount"] == 15
    assert invoices.loc[0, "total_tokens"] == 600

    total_row = accuracy.loc[
        accuracy["field_name"] == "total_amount"
    ].iloc[0]

    assert float(total_row["ai_extracted_value"]) == 12
    assert float(total_row["reviewed_value"]) == 15
    assert bool(total_row["correct"]) is False
    assert total_row[
        "invoice_agreement_percent"
    ] == pytest.approx(91.67)


def test_accuracy_csv_identifies_corrected_field() -> None:
    original = sample_results(total_amount=12)
    reviewed = sample_results(total_amount=15)

    csv_text = to_accuracy_csv_bytes(
        original,
        reviewed,
    ).decode("utf-8-sig")

    assert "field_name" in csv_text
    assert "ai_extracted_value" in csv_text
    assert "reviewed_value" in csv_text
    assert "total_amount" in csv_text
    assert "False" in csv_text
    assert "91.67" in csv_text


def test_invoice_export_identifies_duplicate() -> None:
    original = sample_results()[0]
    duplicate = original.model_copy(
        update={"source_filename": "invoice-copy.pdf"},
        deep=True,
    )

    dataframe = invoices_dataframe([original, duplicate])

    assert dataframe.loc[0, "possible_duplicate"] == False
    assert dataframe.loc[0, "duplicate_of"] == ""

    assert dataframe.loc[1, "possible_duplicate"] == True
    assert dataframe.loc[1, "duplicate_of"] == "invoice.pdf"


def test_csv_and_xlsx_include_customer_profile() -> None:
    result = sample_results()[0].model_copy(
        update={"customer_profile_key": "vat"},
        deep=True,
    )

    csv_text = to_csv_bytes([result]).decode("utf-8-sig")

    assert "customer_profile" in csv_text
    assert "vat" in csv_text

    invoices = pd.read_excel(
        BytesIO(to_xlsx_bytes([result])),
        sheet_name="Invoices",
    )

    assert invoices.loc[0, "customer_profile"] == "vat"


def test_csv_and_xlsx_export_reviewed_line_items() -> None:
    result = sample_results()[0]
    invoice = result.invoice.model_copy(
        update={
            "line_items": [
                InvoiceLineItem(
                    description="Managed IT support",
                    item_type="service",
                    quantity=1,
                    unit="month",
                    unit_price=500,
                    net_amount=500,
                    tax_rate_percent=20,
                    tax_amount=100,
                    total_amount=600,
                    service_period_start=date(2026, 8, 1),
                    service_period_end=date(2026, 8, 31),
                )
            ]
        }
    )
    reviewed_result = result.model_copy(
        update={
            "invoice": invoice,
            "customer_profile_key": "services",
        }
    )

    dataframe = line_items_dataframe([reviewed_result])

    assert len(dataframe) == 1
    assert dataframe.loc[0, "line_number"] == 1
    assert dataframe.loc[0, "description"] == "Managed IT support"
    assert dataframe.loc[0, "customer_profile"] == "services"
    assert dataframe.loc[0, "service_period_start"] == "2026-08-01"
    assert dataframe.loc[0, "service_period_end"] == "2026-08-31"

    csv_text = to_line_items_csv_bytes(
        [reviewed_result]
    ).decode("utf-8-sig")

    assert "Managed IT support" in csv_text
    assert "2026-08-01" in csv_text

    workbook = pd.ExcelFile(
        BytesIO(to_xlsx_bytes([reviewed_result]))
    )
    exported_lines = pd.read_excel(
        workbook,
        sheet_name="Line Items",
    )

    assert len(exported_lines) == 1
    assert (
        exported_lines.loc[0, "description"]
        == "Managed IT support"
    )
    assert (
        exported_lines.loc[0, "customer_profile"]
        == "services"
    )


def test_empty_line_item_csv_keeps_its_headers() -> None:
    csv_text = to_line_items_csv_bytes([]).decode("utf-8-sig")
    lines = csv_text.splitlines()

    assert len(lines) == 1
    assert "source_filename" in lines[0]
    assert "description" in lines[0]
    assert "service_period_end" in lines[0]
