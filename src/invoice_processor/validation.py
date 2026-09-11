"""Validation rules for extracted and human-edited invoice data."""

from dataclasses import dataclass
import math
import re

from .customer_profiles import (
    DEFAULT_PROFILE_KEY,
    CustomerProfile,
    get_customer_profile,
)
from .models import InvoiceData


@dataclass(frozen=True)
class ValidationIssue:
    """A human-readable problem found in an invoice."""

    field: str
    message: str
    severity: str = "warning"


def _close(
    left: float,
    right: float,
    tolerance: float = 0.02,
) -> bool:
    return math.isclose(left, right, abs_tol=tolerance)


def _is_missing(value: object) -> bool:
    """Return whether a required invoice value is empty."""

    if value is None:
        return True

    return isinstance(value, str) and not value.strip()


def _appears_to_be_credit_note(source_text: str) -> bool:
    """Recognize common, explicit credit-note labels in PDF text."""

    return bool(
        re.search(
            (
                r"\b(?:credit\s+(?:note|memo(?:randum)?)|"
                r"nota\s+de\s+credit)\b"
            ),
            source_text,
            flags=re.IGNORECASE,
        )
    )


def validate_invoice(
    invoice: InvoiceData,
    source_text: str = "",
    *,
    profile: CustomerProfile | None = None,
) -> list[ValidationIssue]:
    """Apply general and customer-profile validation checks."""

    active_profile = profile or get_customer_profile(
        DEFAULT_PROFILE_KEY
    )
    issues: list[ValidationIssue] = []

    for field in active_profile.required_fields:
        value = getattr(invoice, field)

        if not _is_missing(value):
            continue

        if field == "total_amount":
            message = "The invoice total is missing."
            severity = "error"
        else:
            message = (
                f"This field is required by the "
                f"{active_profile.display_name} profile."
            )
            severity = "warning"

        issues.append(
            ValidationIssue(
                field=field,
                message=message,
                severity=severity,
            )
        )

    if invoice.currency and not re.fullmatch(
        r"[A-Z]{3}",
        invoice.currency,
    ):
        issues.append(
            ValidationIssue(
                "currency",
                "Use a three-letter currency code, such as USD or EUR.",
            )
        )

    if (
        invoice.total_amount is not None
        and invoice.total_amount < 0
        and not _appears_to_be_credit_note(source_text)
    ):
        issues.append(
            ValidationIssue(
                "total_amount",
                (
                    "A negative total is allowed only when the PDF "
                    "is clearly a credit note."
                ),
                "error",
            )
        )

    if (
        invoice.invoice_date
        and invoice.due_date
        and invoice.due_date < invoice.invoice_date
    ):
        issues.append(
            ValidationIssue(
                "due_date",
                "The due date is before the invoice date.",
                "error",
            )
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
                    (
                        f"Net amount plus tax is "
                        f"{expected_total:.2f}, not "
                        f"{invoice.total_amount:.2f}."
                    ),
                    "error",
                )
            )

    return issues