"""Conservative duplicate-invoice detection."""

from dataclasses import dataclass

from .models import ProcessedInvoice


@dataclass(frozen=True)
class DuplicateInvoice:
    """A duplicate invoice and the earlier invoice it matches."""

    duplicate_index: int
    original_index: int
    duplicate_filename: str
    original_filename: str


def _normalize_identifier(value: str | None) -> str | None:
    """Normalize identifiers for reliable comparisons."""

    if not value:
        return None

    normalized = "".join(
        character.casefold()
        for character in value
        if character.isalnum()
    )

    return normalized or None


def _invoice_identity(
    result: ProcessedInvoice,
) -> tuple[str, str] | None:
    """Build a conservative supplier-and-invoice-number identity."""

    invoice = result.invoice
    invoice_number = _normalize_identifier(invoice.invoice_number)

    supplier_tax_id = _normalize_identifier(invoice.supplier_tax_id)
    supplier_name = _normalize_identifier(invoice.supplier_name)

    if invoice_number is None:
        return None

    if supplier_tax_id is not None:
        supplier_identity = f"tax:{supplier_tax_id}"
    elif supplier_name is not None:
        supplier_identity = f"name:{supplier_name}"
    else:
        return None

    return supplier_identity, invoice_number


def find_duplicate_invoices(
    results: list[ProcessedInvoice],
) -> list[DuplicateInvoice]:
    """Find repeated supplier and invoice-number combinations."""

    first_seen: dict[tuple[str, str], int] = {}
    duplicates: list[DuplicateInvoice] = []

    for index, result in enumerate(results):
        identity = _invoice_identity(result)

        if identity is None:
            continue

        original_index = first_seen.get(identity)

        if original_index is None:
            first_seen[identity] = index
            continue

        original = results[original_index]
        duplicates.append(
            DuplicateInvoice(
                duplicate_index=index,
                original_index=original_index,
                duplicate_filename=result.source_filename,
                original_filename=original.source_filename,
            )
        )

    return duplicates