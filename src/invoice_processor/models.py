"""Typed data models shared across the application."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class InvoiceLineItem(BaseModel):
    """One product or service line extracted from an invoice."""

    model_config = ConfigDict(extra="forbid")

    description: str
    item_type: Literal["product", "service", "other"] | None = None
    quantity: float | None = None
    unit: str | None = None
    unit_price: float | None = None
    net_amount: float | None = None
    tax_rate_percent: float | None = None
    tax_amount: float | None = None
    total_amount: float | None = None
    service_period_start: date | None = None
    service_period_end: date | None = None


class InvoiceData(BaseModel):
    """The structured fields requested from the AI model."""

    model_config = ConfigDict(extra="forbid")

    supplier_name: str | None = None
    supplier_tax_id: str | None = None
    invoice_number: str | None = None
    invoice_date: date | None = None
    due_date: date | None = None
    currency: str | None = None
    net_amount: float | None = None
    tax_amount: float | None = None
    total_amount: float | None = None
    purchase_order_number: str | None = None
    products_services_summary: str | None = Field(
        default=None,
        description=(
            "Concise summary of billed products and services in source order. "
            "Include each service period only when the invoice states one."
        ),
    )

    line_items: list[InvoiceLineItem] = Field(
        default_factory=list,
        description=(
            "Products and services extracted in their original "
            "invoice order. Missing values must remain null."
        ),
    )

    confidence_notes: str | None = None

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else None


class ProcessingMetrics(BaseModel):
    """Timing, token usage and estimated cost for one invoice."""

    extraction_method: str = "digital"
    local_extraction_seconds: float = 0.0
    ai_processing_seconds: float = 0.0
    model: str | None = None
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float | None = None


class AIExtractionResult(BaseModel):
    """Structured invoice data and measurements returned by the AI boundary."""

    invoice: InvoiceData
    metrics: ProcessingMetrics


class ExtractedInvoice(BaseModel):
    """Local PDF text waiting for review before it is sent to the AI."""

    source_filename: str
    text: str
    extraction_method: str = "digital"
    local_extraction_seconds: float = 0.0


class ProcessedInvoice(BaseModel):
    """An invoice plus local processing metadata."""

    source_filename: str
    invoice: InvoiceData
    customer_profile_key: str = "standard"
    source_text: str = Field(default="", exclude=True)
    processing_metrics: ProcessingMetrics = Field(
        default_factory=ProcessingMetrics
    )
