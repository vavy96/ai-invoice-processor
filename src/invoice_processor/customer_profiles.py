"""Configurable invoice-field profiles for different customers."""

from dataclasses import dataclass

from .models import InvoiceData


@dataclass(frozen=True)
class CustomerProfile:
    """Invoice fields required by one customer profile."""

    key: str
    display_name: str
    description: str
    required_fields: tuple[str, ...]

    def __post_init__(self) -> None:
        unknown_fields = set(self.required_fields) - set(
            InvoiceData.model_fields
        )

        if unknown_fields:
            unknown_list = ", ".join(sorted(unknown_fields))
            raise ValueError(
                f"Unknown invoice fields in profile: {unknown_list}"
            )


DEFAULT_PROFILE_KEY = "standard"


CUSTOMER_PROFILES = {
    "standard": CustomerProfile(
        key="standard",
        display_name="Standard invoice",
        description=(
            "Requires the main supplier, invoice, date, currency, "
            "and total fields."
        ),
        required_fields=(
            "supplier_name",
            "invoice_number",
            "invoice_date",
            "currency",
            "total_amount",
        ),
    ),
    "services": CustomerProfile(
        key="services",
        display_name="Services invoice",
        description=(
            "Requires the standard fields plus a summary of the "
            "services and any stated service period."
        ),
        required_fields=(
            "supplier_name",
            "invoice_number",
            "invoice_date",
            "currency",
            "total_amount",
            "products_services_summary",
        ),
    ),
    "purchase_order": CustomerProfile(
        key="purchase_order",
        display_name="Purchase-order invoice",
        description=(
            "Requires the standard fields plus a purchase-order number."
        ),
        required_fields=(
            "supplier_name",
            "invoice_number",
            "invoice_date",
            "currency",
            "total_amount",
            "purchase_order_number",
        ),
    ),
    "vat": CustomerProfile(
        key="vat",
        display_name="VAT invoice",
        description=(
            "Requires the standard fields plus net and tax amounts."
        ),
        required_fields=(
            "supplier_name",
            "invoice_number",
            "invoice_date",
            "currency",
            "net_amount",
            "tax_amount",
            "total_amount",
        ),
    ),
}


def get_customer_profile(profile_key: str) -> CustomerProfile:
    """Return a configured profile or reject an unknown key."""

    profile = CUSTOMER_PROFILES.get(profile_key)

    if profile is None:
        raise ValueError(f"Unknown customer profile: {profile_key}")

    return profile