"""Accuracy and API-cost measurement helpers."""

from dataclasses import dataclass

from .models import InvoiceData


MODEL_PRICING_USD_PER_MILLION = {
    "gpt-4.1-mini": {
        "input": 0.40,
        "cached_input": 0.10,
        "output": 1.60,
    },
    "gpt-4.1-mini-2025-04-14": {
        "input": 0.40,
        "cached_input": 0.10,
        "output": 1.60,
    },
}


@dataclass(frozen=True)
class FieldComparison:
    """One AI-extracted field compared with its reviewed value."""

    field_name: str
    extracted_value: object
    reviewed_value: object
    correct: bool


def estimate_api_cost_usd(
    model: str,
    *,
    input_tokens: int,
    output_tokens: int,
    cached_input_tokens: int = 0,
) -> float | None:
    """Estimate token cost using the configured model price table."""

    if input_tokens < 0 or output_tokens < 0 or cached_input_tokens < 0:
        raise ValueError("Token counts cannot be negative.")

    pricing = MODEL_PRICING_USD_PER_MILLION.get(model)
    if pricing is None:
        return None

    cached_tokens = min(cached_input_tokens, input_tokens)
    uncached_tokens = input_tokens - cached_tokens

    estimated_cost = (
        uncached_tokens * pricing["input"]
        + cached_tokens * pricing["cached_input"]
        + output_tokens * pricing["output"]
    ) / 1_000_000

    return round(estimated_cost, 8)


def compare_invoice_fields(
    extracted: InvoiceData,
    reviewed: InvoiceData,
) -> list[FieldComparison]:
    """Compare AI output with values confirmed during human review."""

    extracted_values = extracted.model_dump(mode="json")
    reviewed_values = reviewed.model_dump(mode="json")

    return [
        FieldComparison(
            field_name=field_name,
            extracted_value=extracted_values[field_name],
            reviewed_value=reviewed_values[field_name],
            correct=extracted_values[field_name] == reviewed_values[field_name],
        )
        for field_name in InvoiceData.model_fields
    ]


def field_accuracy_percent(
    comparisons: list[FieldComparison],
) -> float:
    """Calculate the percentage of reviewed fields that were unchanged."""

    if not comparisons:
        return 0.0

    correct_fields = sum(comparison.correct for comparison in comparisons)
    return round(correct_fields / len(comparisons) * 100, 2)