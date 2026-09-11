"""Text extraction for digital PDF invoices."""

from io import BytesIO

from pypdf import PdfReader


class PDFExtractionError(ValueError):
    """Raised when a PDF cannot provide usable digital text."""


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Return embedded text from a PDF.

    This intentionally does not perform OCR. Scanned/image-only invoices receive a
    helpful error so that the limitation is obvious to the user.
    """

    if not pdf_bytes:
        raise PDFExtractionError("The uploaded PDF is empty.")

    try:
        reader = PdfReader(BytesIO(pdf_bytes))
        if reader.is_encrypted and reader.decrypt("") == 0:
            raise PDFExtractionError("The PDF is password protected.")
        pages = [page.extract_text() or "" for page in reader.pages]
    except PDFExtractionError:
        raise
    except Exception as exc:
        raise PDFExtractionError("The file could not be read as a PDF.") from exc

    text = "\n\n".join(page.strip() for page in pages if page.strip()).strip()
    if len(text) < 20:
        raise PDFExtractionError(
            "No usable digital text was found. Version 1 does not support scanned "
            "or image-only PDFs (OCR is not included)."
        )
    return text
