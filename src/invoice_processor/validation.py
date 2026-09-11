"""Validation rules for extracted and human-edited invoice data."""

from dataclasses import dataclass
import math
import re

from .customer_profiles import (
    DEFAULT_PROFILE_KEY,
    CustomerProfile,
    get_customer_profile,
)
from .models import InvoiceData, InvoiceLineItem


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


def validate_line_item(
    item: InvoiceLineItem,
    index: int,
) -> list[ValidationIssue]:
    """Validate one product or service line."""

    issues: list[ValidationIssue] = []
    line_number = index + 1
    field_prefix = f"line_items[{index}]"

    if not item.description.strip():
        issues.append(
            ValidationIssue(
                f"{field_prefix}.description",
                f"Line {line_number} description is missing.",
            )
        )

    if (
        item.quantity is not None
        and item.unit_price is not None
        and item.net_amount is not None
    ):
        expected_net = item.quantity * item.unit_price

        if not _close(expected_net, item.net_amount):
            issues.append(
                ValidationIssue(
                    f"{field_prefix}.net_amount",
                    (
                        f"Line {line_number} quantity multiplied by "
                        f"unit price is {expected_net:.2f}, not "
                        f"{item.net_amount:.2f}."
                    ),
                    "error",
                )
            )

    if (
        item.net_amount is not None
        and item.tax_amount is not None
        and item.total_amount is not None
    ):
        expected_total = item.net_amount + item.tax_amount

        if not _close(expected_total, item.total_amount):
            issues.append(
                ValidationIssue(
                    f"{field_prefix}.total_amount",
                    (
                        f"Line {line_number} net amount plus tax is "
                        f"{expected_total:.2f}, not "
                        f"{item.total_amount:.2f}."
                    ),
                    "error",
                )
            )

    if (
        item.net_amount is not None
        and item.tax_rate_percent is not None
        and item.tax_amount is not None
    ):
        expected_tax = (
            item.net_amount * item.tax_rate_percent / 100
        )

        if not _close(expected_tax, item.tax_amount):
            issues.append(
                ValidationIssue(
                    f"{field_prefix}.tax_amount",
                    (
                        f"Line {line_number} tax calculated from the "
                        f"stated rate is {expected_tax:.2f}, not "
                        f"{item.tax_amount:.2f}."
                    ),
                    "error",
                )
            )

    period_start = item.service_period_start
    period_end = item.service_period_end

    if period_start is not None and period_end is None:
        issues.append(
            ValidationIssue(
                f"{field_prefix}.service_period_end",
                (
                    f"Line {line_number} has a service-period start "
                    "but no end date."
                ),
            )
        )
    elif period_start is None and period_end is not None:
        issues.append(
            ValidationIssue(
                f"{field_prefix}.service_period_start",
                (
                    f"Line {line_number} has a service-period end "
                    "but no start date."
                ),
            )
        )
    elif (
        period_start is not None
        and period_end is not None
        and period_end < period_start
    ):
        issues.append(
            ValidationIssue(
                f"{field_prefix}.service_period_end",
                (
                    f"Line {line_number} service-period end date is "
                    "before its start date."
                ),
                "error",
            )
        )

    return issues


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

    for index, item in enumerate(invoice.line_items):
        issues.extend(validate_line_item(item, index))

    return issues
