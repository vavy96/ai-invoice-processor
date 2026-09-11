"""Tests for duplicate-invoice detection."""

from invoice_processor.duplicate_detector import find_duplicate_invoices
from invoice_processor.models import InvoiceData, ProcessedInvoice


def make_result(
    filename: str,
    *,
    supplier_name: str | None = "Example Supplier",
    supplier_tax_id: str | None = "RO123456",
    invoice_number: str | None = "INV-100",
) -> ProcessedInvoice:
    """Create a small processed invoice for duplicate tests."""

    return ProcessedInvoice(
        source_filename=filename,
        invoice=InvoiceData(
            supplier_name=supplier_name,
            supplier_tax_id=supplier_tax_id,
            invoice_number=invoice_number,
        ),
    )


def test_detects_duplicate_using_tax_id_and_invoice_number() -> None:
    results = [
        make_result("first.pdf"),
        make_result("duplicate.pdf"),
    ]

    duplicates = find_duplicate_invoices(results)

    assert len(duplicates) == 1
    assert duplicates[0].original_index == 0
    assert duplicates[0].duplicate_index == 1
    assert duplicates[0].original_filename == "first.pdf"
    assert duplicates[0].duplicate_filename == "duplicate.pdf"


def test_normalizes_identifier_formatting() -> None:
    results = [
        make_result(
            "first.pdf",
            supplier_tax_id="RO 123-456",
            invoice_number="INV-100",
        ),
        make_result(
            "duplicate.pdf",
            supplier_tax_id="ro123456",
            invoice_number="inv 100",
        ),
    ]

    duplicates = find_duplicate_invoices(results)

    assert len(duplicates) == 1


def test_different_invoice_numbers_are_not_duplicates() -> None:
    results = [
        make_result("first.pdf", invoice_number="INV-100"),
        make_result("second.pdf", invoice_number="INV-101"),
    ]

    duplicates = find_duplicate_invoices(results)

    assert duplicates == []


def test_different_suppliers_are_not_duplicates() -> None:
    results = [
        make_result("first.pdf", supplier_tax_id="RO111"),
        make_result("second.pdf", supplier_tax_id="RO222"),
    ]

    duplicates = find_duplicate_invoices(results)

    assert duplicates == []


def test_uses_supplier_name_when_tax_id_is_missing() -> None:
    results = [
        make_result(
            "first.pdf",
            supplier_name="Example Supplier SRL",
            supplier_tax_id=None,
        ),
        make_result(
            "duplicate.pdf",
            supplier_name="example supplier srl",
            supplier_tax_id=None,
        ),
    ]

    duplicates = find_duplicate_invoices(results)

    assert len(duplicates) == 1


def test_missing_invoice_number_is_not_marked_duplicate() -> None:
    results = [
        make_result("first.pdf", invoice_number=None),
        make_result("second.pdf", invoice_number=None),
    ]

    duplicates = find_duplicate_invoices(results)

    assert duplicates == []