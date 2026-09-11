"""Tests for invoice business validation."""

from datetime import date

import pytest
from pydantic import ValidationError

from invoice_processor.customer_profiles import get_customer_profile
from invoice_processor.models import InvoiceData, InvoiceLineItem
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


def test_standard_profile_requires_invoice_date() -> None:
    invoice = valid_invoice().model_copy(
        update={"invoice_date": None}
    )

    issues = validate_invoice(invoice)

    assert "invoice_date" in {
        issue.field for issue in issues
    }


def test_services_profile_requires_service_summary() -> None:
    profile = get_customer_profile("services")

    issues = validate_invoice(
        valid_invoice(),
        profile=profile,
    )

    assert "products_services_summary" in {
        issue.field for issue in issues
    }


def test_purchase_order_profile_requires_po_number() -> None:
    profile = get_customer_profile("purchase_order")

    issues = validate_invoice(
        valid_invoice(),
        profile=profile,
    )

    assert "purchase_order_number" in {
        issue.field for issue in issues
    }


def test_vat_profile_requires_net_and_tax_amounts() -> None:
    profile = get_customer_profile("vat")
    invoice = valid_invoice().model_copy(
        update={
            "net_amount": None,
            "tax_amount": None,
        }
    )

    issues = validate_invoice(
        invoice,
        profile=profile,
    )
    issue_fields = {issue.field for issue in issues}

    assert {"net_amount", "tax_amount"} <= issue_fields


def test_accepts_a_valid_line_item() -> None:
    item = InvoiceLineItem(
        description="Wireless keyboard",
        item_type="product",
        quantity=2,
        unit_price=40,
        net_amount=80,
        tax_rate_percent=20,
        tax_amount=16,
        total_amount=96,
    )
    invoice = valid_invoice().model_copy(
        update={"line_items": [item]}
    )

    assert validate_invoice(invoice) == []


def test_detects_a_missing_line_description() -> None:
    item = InvoiceLineItem(description="")
    invoice = valid_invoice().model_copy(
        update={"line_items": [item]}
    )

    issues = validate_invoice(invoice)

    assert "line_items[0].description" in {
        issue.field for issue in issues
    }


def test_detects_incorrect_line_net_amount() -> None:
    item = InvoiceLineItem(
        description="Keyboard",
        quantity=2,
        unit_price=40,
        net_amount=90,
    )
    invoice = valid_invoice().model_copy(
        update={"line_items": [item]}
    )

    issues = validate_invoice(invoice)

    assert "line_items[0].net_amount" in {
        issue.field for issue in issues
    }


def test_detects_incorrect_line_total() -> None:
    item = InvoiceLineItem(
        description="Keyboard",
        net_amount=80,
        tax_amount=16,
        total_amount=100,
    )
    invoice = valid_invoice().model_copy(
        update={"line_items": [item]}
    )

    issues = validate_invoice(invoice)

    assert "line_items[0].total_amount" in {
        issue.field for issue in issues
    }


def test_detects_incorrect_line_tax() -> None:
    item = InvoiceLineItem(
        description="Keyboard",
        net_amount=80,
        tax_rate_percent=20,
        tax_amount=10,
    )
    invoice = valid_invoice().model_copy(
        update={"line_items": [item]}
    )

    issues = validate_invoice(invoice)

    assert "line_items[0].tax_amount" in {
        issue.field for issue in issues
    }


def test_detects_invalid_service_periods() -> None:
    incomplete_period = InvoiceLineItem(
        description="Monthly support",
        item_type="service",
        service_period_start=date(2026, 8, 1),
    )
    reversed_period = InvoiceLineItem(
        description="Security monitoring",
        item_type="service",
        service_period_start=date(2026, 8, 31),
        service_period_end=date(2026, 8, 1),
    )
    invoice = valid_invoice().model_copy(
        update={
            "line_items": [
                incomplete_period,
                reversed_period,
            ]
        }
    )

    issues = validate_invoice(invoice)
    issue_fields = {issue.field for issue in issues}

    assert "line_items[0].service_period_end" in issue_fields
    assert "line_items[1].service_period_end" in issue_fields
