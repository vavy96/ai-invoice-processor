"""Validation rules for extracted and human-edited invoice data."""

from dataclasses import dataclass
import math
import re

from .models import InvoiceData


@dataclass(frozen=True)
class ValidationIssue:
    """A human-readable problem found in an invoice."""

    field: str
    message: str
    severity: str = "warning"


def _close(left: float, right: float, tolerance: float = 0.02) -> bool:
    return math.isclose(left, right, abs_tol=tolerance)


def _appears_to_be_credit_note(source_text: str) -> bool:
    """Recognize common, explicit credit-note labels in the PDF text."""

    return bool(
        re.search(
            r"\b(?:credit\s+(?:note|memo(?:randum)?)|nota\s+de\s+credit)\b",
            source_text,
            flags=re.IGNORECASE,
        )
    )


def validate_invoice(
    invoice: InvoiceData,
    source_text: str = "",
) -> list[ValidationIssue]:
    """Apply simple, explainable checks without changing the extracted values."""

    issues: list[ValidationIssue] = []
    required_text = {
        "supplier_name": invoice.supplier_name,
        "invoice_number": invoice.invoice_number,
        "currency": invoice.currency,
    }
    for field, value in required_text.items():
        if not value or not value.strip():
            issues.append(ValidationIssue(field, "This important field is missing."))

    if invoice.currency and not re.fullmatch(r"[A-Z]{3}", invoice.currency):
        issues.append(
            ValidationIssue("currency", "Use a three-letter currency code, such as USD or EUR.")
        )

    if invoice.total_amount is None:
        issues.append(ValidationIssue("total_amount", "The invoice total is missing.", "error"))

    if (
        invoice.total_amount is not None
        and invoice.total_amount < 0
        and not _appears_to_be_credit_note(source_text)
    ):
        issues.append(
            ValidationIssue(
                "total_amount",
                "A negative total is allowed only when the PDF is clearly a credit note.",
                "error",
            )
        )

    if invoice.invoice_date and invoice.due_date and invoice.due_date < invoice.invoice_date:
        issues.append(
            ValidationIssue("due_date", "The due date is before the issue date.", "error")
        )

    if (
        invoice.net_amount is not None
        and invoice.tax_amount is not None
        and invoice.total_amount is not None
    ):
        expected_total = invoice.net_amount + invoice.tax_amount
        if not _close(expected_total, invoice.total_amount):
            issues.append(
                ValidationIssue(
                    "total_amount",
                    f"Net amount plus tax is {expected_total:.2f}, not "
                    f"{invoice.total_amount:.2f}.",
                    "error",
                )
            )
    return issues
