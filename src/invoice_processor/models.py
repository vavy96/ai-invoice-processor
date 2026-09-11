"""Typed data models shared across the application."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    source_text: str = Field(default="", exclude=True)
    processing_metrics: ProcessingMetrics = Field(
        default_factory=ProcessingMetrics
    )