"""Tests for the AI integration boundary without making API calls."""

from types import SimpleNamespace

import pytest

from invoice_processor.ai_extractor import AIExtractionError, extract_invoice_with_ai
from invoice_processor.models import InvoiceData


class FakeResponses:
    def __init__(self, parsed: InvoiceData | None) -> None:
        self.parsed = parsed
        self.arguments: dict[str, object] = {}

    def parse(self, **kwargs):
        self.arguments = kwargs
        return SimpleNamespace(output_parsed=self.parsed)


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
            "Cloud hosting (service period: 2026-01-01 to 2026-01-31); USB cable"
        ),
    )
    client = FakeClient(expected)

    result = extract_invoice_with_ai("Invoice text", api_key="", model="test-model", client=client)

    assert result == expected
    assert client.responses.arguments["text_format"] is InvoiceData
    assert client.responses.arguments["store"] is False
    assert "Use null when a value is missing" in client.responses.arguments["instructions"]
    assert "products_services_summary" in client.responses.arguments["instructions"]
    assert "Do not invent a service period" in client.responses.arguments["instructions"]


def test_rejects_an_empty_model_result() -> None:
    with pytest.raises(AIExtractionError, match="did not return"):
        extract_invoice_with_ai(
            "Invoice text", api_key="", model="test-model", client=FakeClient(None)
        )


def test_missing_invoice_fields_are_null() -> None:
    invoice = InvoiceData()

    assert all(value is None for value in invoice.model_dump().values())
