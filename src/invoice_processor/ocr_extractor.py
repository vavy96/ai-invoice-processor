"""Local OCR extraction for scanned PDF invoices."""

import os
from pathlib import Path

import pymupdf


class OCRExtractionError(ValueError):
    """Raised when local OCR cannot extract usable text."""


def _find_tessdata() -> Path:
    """Find the folder containing Tesseract language files."""

    possible_locations = [
        os.getenv("TESSDATA_PREFIX"),
        r"C:\Program Files\Tesseract-OCR\tessdata",
    ]

    for location in possible_locations:
        if location:
            path = Path(location)
            if path.is_dir():
                return path

    raise OCRExtractionError(
        "Tesseract language data was not found. "
        "Expected it in C:\\Program Files\\Tesseract-OCR\\tessdata."
    )


def extract_text_with_ocr(
    pdf_bytes: bytes,
    *,
    languages: str = "eng+ron",
    dpi: int = 300,
    tessdata_path: str | Path | None = None,
) -> str:
    """Extract text from every PDF page using local Tesseract OCR."""

    if not pdf_bytes:
        raise OCRExtractionError("The uploaded PDF is empty.")

    tessdata = Path(tessdata_path) if tessdata_path else _find_tessdata()

    if not tessdata.is_dir():
        raise OCRExtractionError(
            f"Tesseract language data was not found at: {tessdata}"
        )

    extracted_pages: list[str] = []

    try:
        with pymupdf.open(stream=pdf_bytes, filetype="pdf") as document:
            if document.page_count == 0:
                raise OCRExtractionError("The PDF contains no pages.")

            for page_number, page in enumerate(document, start=1):
                text_page = page.get_textpage_ocr(
                    language=languages,
                    dpi=dpi,
                    full=True,
                    tessdata=str(tessdata),
                )
                page_text = page.get_text(
                    "text",
                    textpage=text_page,
                ).strip()

                if page_text:
                    extracted_pages.append(
                        f"--- Page {page_number} ---\n{page_text}"
                    )

    except OCRExtractionError:
        raise
    except Exception as exc:
        raise OCRExtractionError(f"Local OCR failed: {exc}") from exc

    combined_text = "\n\n".join(extracted_pages).strip()

    if not combined_text:
        raise OCRExtractionError(
            "Local OCR finished, but no readable text was found."
        )

    return combined_text