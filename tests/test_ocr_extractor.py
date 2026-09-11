"""Tests for local OCR extraction."""

from pathlib import Path

import pytest

from invoice_processor.ocr_extractor import (
    OCRExtractionError,
    extract_text_with_ocr,
)


class FakePage:
    """A simulated PDF page used without running real OCR."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.ocr_settings: dict[str, object] = {}
        self.text_page = object()

    def get_textpage_ocr(
        self,
        *,
        language: str,
        dpi: int,
        full: bool,
        tessdata: str,
    ) -> object:
        self.ocr_settings = {
            "language": language,
            "dpi": dpi,
            "full": full,
            "tessdata": tessdata,
        }
        return self.text_page

    def get_text(
        self,
        mode: str,
        *,
        textpage: object,
    ) -> str:
        assert mode == "text"
        assert textpage is self.text_page
        return self.text


class FakeDocument:
    """A simulated multi-page PDF document."""

    def __init__(self, pages: list[FakePage]) -> None:
        self.pages = pages
        self.page_count = len(pages)

    def __enter__(self) -> "FakeDocument":
        return self

    def __exit__(
        self,
        exception_type: object,
        exception: object,
        traceback: object,
    ) -> None:
        return None

    def __iter__(self):
        return iter(self.pages)


def test_extracts_text_from_every_page(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pages = [
        FakePage("Supplier: Example SRL"),
        FakePage("Total: 100.00 RON"),
    ]

    monkeypatch.setattr(
        "invoice_processor.ocr_extractor.pymupdf.open",
        lambda *, stream, filetype: FakeDocument(pages),
    )

    text = extract_text_with_ocr(
        b"fake scanned PDF",
        tessdata_path=tmp_path,
    )

    assert "--- Page 1 ---" in text
    assert "Supplier: Example SRL" in text
    assert "--- Page 2 ---" in text
    assert "Total: 100.00 RON" in text

    for page in pages:
        assert page.ocr_settings["language"] == "eng+ron"
        assert page.ocr_settings["dpi"] == 300
        assert page.ocr_settings["full"] is True
        assert page.ocr_settings["tessdata"] == str(tmp_path)


def test_rejects_empty_upload() -> None:
    with pytest.raises(OCRExtractionError, match="empty"):
        extract_text_with_ocr(b"")


def test_rejects_missing_tessdata_folder(tmp_path: Path) -> None:
    missing_folder = tmp_path / "missing-tessdata"

    with pytest.raises(OCRExtractionError, match="language data"):
        extract_text_with_ocr(
            b"fake scanned PDF",
            tessdata_path=missing_folder,
        )


def test_rejects_ocr_with_no_readable_text(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pages = [FakePage("   ")]

    monkeypatch.setattr(
        "invoice_processor.ocr_extractor.pymupdf.open",
        lambda *, stream, filetype: FakeDocument(pages),
    )

    with pytest.raises(OCRExtractionError, match="no readable text"):
        extract_text_with_ocr(
            b"fake scanned PDF",
            tessdata_path=tmp_path,
        )