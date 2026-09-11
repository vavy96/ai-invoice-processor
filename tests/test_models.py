"""Tests for invoice data models."""

from datetime import date

import pytest
from pydantic import ValidationError

from invoice_processor.models import InvoiceData, InvoiceLineItem


def test_invoice_defaults_to_an_empty_line_item_list() -> None:
    first_invoice = InvoiceData()
    second_invoice = InvoiceData()

    first_invoice.line_items.append(
        InvoiceLineItem(description="Keyboard")
    )

    assert len(first_invoice.line_items) == 1
    assert second_invoice.line_items == []


def test_stores_a_product_line() -> None:
    item = InvoiceLineItem(
        description="Wireless keyboard",
        item_type="product",
        quantity=2,
        unit="piece",
        unit_price=40,
        net_amount=80,
        tax_rate_percent=20,
        tax_amount=16,
        total_amount=96,
    )

    assert item.description == "Wireless keyboard"
    assert item.item_type == "product"
    assert item.quantity == 2
    assert item.total_amount == 96


def test_stores_a_service_period() -> None:
    item = InvoiceLineItem(
        description="Managed IT support",
        item_type="service",
        net_amount=500,
        service_period_start=date(2026, 8, 1),
        service_period_end=date(2026, 8, 31),
    )

    assert item.item_type == "service"
    assert item.service_period_start == date(2026, 8, 1)
    assert item.service_period_end == date(2026, 8, 31)


def test_rejects_an_unknown_item_type() -> None:
    with pytest.raises(ValidationError):
        InvoiceLineItem(
            description="Unknown item",
            item_type="unsupported",
        )


def test_requires_a_description() -> None:
    with pytest.raises(ValidationError):
        InvoiceLineItem()