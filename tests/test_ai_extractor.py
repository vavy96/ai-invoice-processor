"""Tests for the AI integration boundary without making API calls."""

from datetime import date
from types import SimpleNamespace

import pytest

from invoice_processor.ai_extractor import (
    AIExtractionError,
    extract_invoice_with_ai,
)
from invoice_processor.models import InvoiceData, InvoiceLineItem


class FakeResponses:
    def __init__(self, parsed: InvoiceData | None) -> None:
        self.parsed = parsed
        self.arguments: dict[str, object] = {}

    def parse(self, **kwargs):
        self.arguments = kwargs
        usage = SimpleNamespace(
            input_tokens=1_000,
            output_tokens=200,
            total_tokens=1_200,
            input_tokens_details=SimpleNamespace(
                cached_tokens=100,
            ),
        )
        return SimpleNamespace(
            output_parsed=self.parsed,
            usage=usage,
        )


class FakeClient:
    def __init__(self, parsed: InvoiceData | None) -> None:
        self.responses = FakeResponses(parsed)


def test_requests_structured_output_without_response_storage() -> None:
    expected = InvoiceData(
        supplier_name="Vendor",
        invoice_number="INV-1",
        currency="EUR",
        total_amount=10,
        products_services_summary=(
            "Cloud hosting (service period: 2026-01-01 to 2026-01-31); "
            "USB cable"
        ),
    )
    client = FakeClient(expected)

    result = extract_invoice_with_ai(
        "Invoice text",
        api_key="",
        model="gpt-4.1-mini",
        client=client,
    )

    assert result.invoice == expected
    assert result.metrics.model == "gpt-4.1-mini"
    assert result.metrics.input_tokens == 1_000
    assert result.metrics.cached_input_tokens == 100
    assert result.metrics.output_tokens == 200
    assert result.metrics.total_tokens == 1_200
    assert result.metrics.estimated_cost_usd == pytest.approx(0.00069)

    assert client.responses.arguments["text_format"] is InvoiceData
    assert client.responses.arguments["store"] is False
    assert (
        "Use null when a value is missing"
        in client.responses.arguments["instructions"]
    )
    assert (
        "products_services_summary"
        in client.responses.arguments["instructions"]
    )
    assert (
        "Do not invent a service period"
        in client.responses.arguments["instructions"]
    )


def test_rejects_an_empty_model_result() -> None:
    with pytest.raises(AIExtractionError, match="did not return"):
        extract_invoice_with_ai(
            "Invoice text",
            api_key="",
            model="test-model",
            client=FakeClient(None),
        )


def test_missing_invoice_fields_are_null() -> None:
    invoice = InvoiceData()
    values = invoice.model_dump()
    line_items = values.pop("line_items")

    assert line_items == []
    assert all(value is None for value in values.values())


def test_returns_structured_line_items() -> None:
    expected = InvoiceData(
        supplier_name="Example Supplier",
        invoice_number="INV-200",
        currency="EUR",
        total_amount=596,
        line_items=[
            InvoiceLineItem(
                description="Wireless keyboard",
                item_type="product",
                quantity=2,
                unit="piece",
                unit_price=40,
                net_amount=80,
                tax_amount=16,
                total_amount=96,
            ),
            InvoiceLineItem(
                description="Managed IT support",
                item_type="service",
                quantity=1,
                unit_price=500,
                net_amount=500,
                service_period_start=date(2026, 8, 1),
                service_period_end=date(2026, 8, 31),
            ),
        ],
    )
    client = FakeClient(expected)

    result = extract_invoice_with_ai(
        "Invoice containing product and service lines",
        api_key="",
        model="gpt-4.1-mini",
        client=client,
    )

    assert len(result.invoice.line_items) == 2

    product = result.invoice.line_items[0]
    assert product.description == "Wireless keyboard"
    assert product.item_type == "product"
    assert product.quantity == 2
    assert product.total_amount == 96

    service = result.invoice.line_items[1]
    assert service.description == "Managed IT support"
    assert service.item_type == "service"
    assert service.service_period_start == date(2026, 8, 1)
    assert service.service_period_end == date(2026, 8, 31)

    instructions = client.responses.arguments["instructions"]
    assert "For line_items" in instructions
    assert "Do not calculate missing line-item values" in instructions
    assert "return an empty line_items list" in instructions
