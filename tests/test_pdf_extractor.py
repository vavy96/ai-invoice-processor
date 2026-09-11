"""Tests for digital PDF text extraction."""

import pytest

from invoice_processor.pdf_extractor import PDFExtractionError, extract_text_from_pdf


class FakePage:
    def __init__(self, text: str | None) -> None:
        self.text = text

    def extract_text(self) -> str | None:
        return self.text


class FakeReader:
    is_encrypted = False

    def __init__(self, _stream: object, pages: list[FakePage]) -> None:
        self.pages = pages


def test_extracts_and_joins_digital_text(monkeypatch: pytest.MonkeyPatch) -> None:
    pages = [FakePage("Invoice 100\nVendor Ltd"), FakePage("Total: EUR 42.00")]
    monkeypatch.setattr(
        "invoice_processor.pdf_extractor.PdfReader",
        lambda stream: FakeReader(stream, pages),
    )

    text = extract_text_from_pdf(b"fake pdf bytes")

    assert "Invoice 100" in text
    assert "Total: EUR 42.00" in text


def test_rejects_image_only_pdf(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "invoice_processor.pdf_extractor.PdfReader",
        lambda stream: FakeReader(stream, [FakePage(None)]),
    )

    with pytest.raises(PDFExtractionError, match="does not support scanned"):
        extract_text_from_pdf(b"fake pdf bytes")


def test_rejects_empty_upload() -> None:
    with pytest.raises(PDFExtractionError, match="empty"):
        extract_text_from_pdf(b"")
