"""Tests for the processing workflow."""

from invoice_processor.models import ExtractedInvoice, InvoiceData
from invoice_processor.workflow import (
    extract_invoice_text,
    process_extracted_invoice,
    process_invoice,
)


def test_workflow_passes_pdf_text_to_ai(monkeypatch) -> None:
    monkeypatch.setattr(
        "invoice_processor.workflow.extract_text_from_pdf",
        lambda _pdf: "Invoice text from the PDF",
    )
    seen: list[str] = []

    def fake_ai_extractor(text: str) -> InvoiceData:
        seen.append(text)
        return InvoiceData(
            supplier_name="Vendor",
            invoice_number="1",
            currency="EUR",
            total_amount=25,
        )

    result = process_invoice(b"pdf", "invoice.pdf", fake_ai_extractor)

    assert seen == ["Invoice text from the PDF"]
    assert result.source_filename == "invoice.pdf"
    assert result.invoice.total_amount == 25


def test_extraction_stage_does_not_need_an_ai_extractor(monkeypatch) -> None:
    monkeypatch.setattr(
        "invoice_processor.workflow.extract_text_from_pdf",
        lambda _pdf: "Locally extracted invoice text",
    )

    extracted = extract_invoice_text(b"pdf", "local.pdf")

    assert extracted.source_filename == "local.pdf"
    assert extracted.text == "Locally extracted invoice text"


def test_ai_stage_uses_already_previewed_text(monkeypatch) -> None:
    monkeypatch.setattr(
        "invoice_processor.workflow.extract_text_from_pdf",
        lambda _pdf: (_ for _ in ()).throw(AssertionError("PDF should not be read again")),
    )
    extracted = ExtractedInvoice(
        source_filename="previewed.pdf",
        text="Text that the person already previewed",
    )

    result = process_extracted_invoice(
        extracted,
        lambda text: InvoiceData(
            supplier_name="Vendor",
            invoice_number="2",
            currency="USD",
            total_amount=10 if "previewed" in text else 0,
        ),
    )

    assert result.invoice.total_amount == 10
