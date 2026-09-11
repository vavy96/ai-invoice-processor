"""PDF text extraction with a local OCR fallback."""

from io import BytesIO

from pypdf import PdfReader

from .ocr_extractor import OCRExtractionError, extract_text_with_ocr


class PDFExtractionError(ValueError):
    """Raised when neither digital extraction nor OCR returns useful text."""


MIN_DIGITAL_CHARACTERS = 10


def _has_enough_digital_text(text: str) -> bool:
    """Return True when extracted text is substantial enough to use."""

    readable_characters = sum(character.isalnum() for character in text)
    return readable_characters >= MIN_DIGITAL_CHARACTERS


def extract_text_from_pdf_with_method(
    pdf_bytes: bytes,
) -> tuple[str, str]:
    """Extract PDF text and report whether digital extraction or OCR was used."""

    if not pdf_bytes:
        raise PDFExtractionError("The uploaded PDF is empty.")

    try:
        reader = PdfReader(BytesIO(pdf_bytes))
        page_text = [
            (page.extract_text() or "").strip()
            for page in reader.pages
        ]
    except Exception as exc:
        raise PDFExtractionError(f"The PDF could not be read: {exc}") from exc

    combined_text = "\n\n".join(
        text for text in page_text if text
    ).strip()

    if _has_enough_digital_text(combined_text):
        return combined_text, "digital"

    try:
        ocr_text = extract_text_with_ocr(pdf_bytes)
        return ocr_text, "ocr"
    except OCRExtractionError as exc:
        raise PDFExtractionError(
            "The PDF appears scanned or image-only. "
            f"Local OCR could not extract readable text: {exc}"
        ) from exc


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract text while preserving the original text-only interface."""

    text, _method = extract_text_from_pdf_with_method(pdf_bytes)
    return text