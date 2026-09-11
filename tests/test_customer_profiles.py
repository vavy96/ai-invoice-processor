"""Tests for configurable customer profiles."""

import pytest

from invoice_processor.customer_profiles import (
    CUSTOMER_PROFILES,
    DEFAULT_PROFILE_KEY,
    CustomerProfile,
    get_customer_profile,
)
from invoice_processor.models import InvoiceData


def test_default_profile_is_standard() -> None:
    profile = get_customer_profile(DEFAULT_PROFILE_KEY)

    assert profile.key == "standard"
    assert profile.display_name == "Standard invoice"


def test_standard_profile_requires_core_fields() -> None:
    required = set(
        get_customer_profile("standard").required_fields
    )

    assert {
        "supplier_name",
        "invoice_number",
        "invoice_date",
        "currency",
        "total_amount",
    } <= required


def test_services_profile_requires_summary() -> None:
    profile = get_customer_profile("services")

    assert "products_services_summary" in profile.required_fields


def test_purchase_order_profile_requires_po_number() -> None:
    profile = get_customer_profile("purchase_order")

    assert "purchase_order_number" in profile.required_fields


def test_vat_profile_requires_amount_breakdown() -> None:
    required = set(get_customer_profile("vat").required_fields)

    assert {"net_amount", "tax_amount", "total_amount"} <= required


def test_every_required_field_exists_in_invoice_model() -> None:
    valid_fields = set(InvoiceData.model_fields)

    for profile in CUSTOMER_PROFILES.values():
        assert set(profile.required_fields) <= valid_fields


def test_rejects_unknown_profile_and_field() -> None:
    with pytest.raises(ValueError, match="Unknown customer profile"):
        get_customer_profile("missing-profile")

    with pytest.raises(ValueError, match="Unknown invoice fields"):
        CustomerProfile(
            key="invalid",
            display_name="Invalid",
            description="Invalid test profile.",
            required_fields=("field_that_does_not_exist",),
        )