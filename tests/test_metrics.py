"""Tests for accuracy and API-cost measurements."""

import pytest

from invoice_processor.metrics import (
    compare_invoice_fields,
    estimate_api_cost_usd,
    field_accuracy_percent,
)
from invoice_processor.models import InvoiceData


def test_estimates_gpt_4_1_mini_cost() -> None:
    cost = estimate_api_cost_usd(
        "gpt-4.1-mini",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
    )

    assert cost == pytest.approx(2.00)


def test_applies_cached_input_discount() -> None:
    cost = estimate_api_cost_usd(
        "gpt-4.1-mini",
        input_tokens=1_000,
        cached_input_tokens=200,
        output_tokens=500,
    )

    assert cost == pytest.approx(0.00114)


def test_returns_none_for_unknown_model() -> None:
    cost = estimate_api_cost_usd(
        "unknown-model",
        input_tokens=1_000,
        output_tokens=500,
    )

    assert cost is None


def test_detects_corrected_invoice_fields() -> None:
    extracted = InvoiceData(
        supplier_name="Example SRL",
        invoice_number="INV-1",
        currency="EUR",
        total_amount=100,
    )
    reviewed = InvoiceData(
        supplier_name="Example SRL",
        invoice_number="INV-1",
        currency="EUR",
        total_amount=120,
    )

    comparisons = compare_invoice_fields(extracted, reviewed)
    comparisons_by_field = {
        comparison.field_name: comparison
        for comparison in comparisons
    }

    assert comparisons_by_field["supplier_name"].correct is True
    assert comparisons_by_field["total_amount"].correct is False
    assert comparisons_by_field["total_amount"].extracted_value == 100.0
    assert comparisons_by_field["total_amount"].reviewed_value == 120.0


def test_calculates_field_accuracy() -> None:
    extracted = InvoiceData(
        supplier_name="Example SRL",
        invoice_number="INV-1",
        currency="EUR",
        total_amount=100,
    )
    reviewed = InvoiceData(
        supplier_name="Example SRL",
        invoice_number="INV-1",
        currency="EUR",
        total_amount=120,
    )

    comparisons = compare_invoice_fields(extracted, reviewed)

    assert field_accuracy_percent(comparisons) == pytest.approx(91.67)