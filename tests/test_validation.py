"""Tests for invoice business validation."""

from datetime import date

import pytest
from pydantic import ValidationError

from invoice_processor.models import InvoiceData
from invoice_processor.validation import validate_invoice


def valid_invoice() -> InvoiceData:
    return InvoiceData(
        supplier_name="Example Supplies",
        invoice_number="INV-100",
        invoice_date=date(2026, 1, 10),
        due_date=date(2026, 2, 10),
        currency="EUR",
        net_amount=100,
        tax_amount=19,
        total_amount=119,
    )


def test_valid_invoice_has_no_issues() -> None:
    assert validate_invoice(valid_invoice()) == []


def test_finds_total_and_date_mismatches() -> None:
    invoice = valid_invoice().model_copy(
        update={"total_amount": 120, "due_date": date(2026, 1, 1)}
    )

    issues = validate_invoice(invoice)

    fields = {issue.field for issue in issues}
    assert "total_amount" in fields
    assert "due_date" in fields


def test_finds_missing_important_fields() -> None:
    issues = validate_invoice(InvoiceData())

    fields = {issue.field for issue in issues}
    assert {"supplier_name", "invoice_number", "currency", "total_amount"} <= fields


def test_allows_a_small_rounding_difference() -> None:
    invoice = valid_invoice().model_copy(update={"total_amount": 119.02})

    assert validate_invoice(invoice) == []


def test_warns_about_an_invalid_currency_code() -> None:
    invoice = valid_invoice().model_copy(update={"currency": "EURO"})

    issues = validate_invoice(invoice)

    assert "currency" in {issue.field for issue in issues}


def test_rejects_a_negative_total_for_an_ordinary_invoice() -> None:
    invoice = valid_invoice().model_copy(
        update={"net_amount": -100, "tax_amount": -19, "total_amount": -119}
    )

    issues = validate_invoice(invoice, "INVOICE INV-100")

    assert any(
        issue.field == "total_amount" and "credit note" in issue.message
        for issue in issues
    )


def test_allows_a_negative_total_for_a_credit_note() -> None:
    invoice = valid_invoice().model_copy(
        update={"net_amount": -100, "tax_amount": -19, "total_amount": -119}
    )

    assert validate_invoice(invoice, "CREDIT NOTE CN-100") == []


@pytest.mark.parametrize(
    ("field", "value"),
    [("total_amount", "not-a-number"), ("invoice_date", "not-a-date")],
)
def test_typed_model_rejects_invalid_amounts_and_dates(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        InvoiceData.model_validate({field: value})
