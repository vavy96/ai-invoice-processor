"""Streamlit entry point for the AI Invoice Processor."""

from functools import partial
from pathlib import Path
import sys

import pandas as pd
import streamlit as st

# Keep `streamlit run app.py` beginner-friendly without requiring package installation.
sys.path.insert(0, str(Path(__file__).parent / "src"))

from invoice_processor.ai_extractor import extract_invoice_with_ai  # noqa: E402
from invoice_processor.config import load_settings  # noqa: E402
from invoice_processor.exporters import to_csv_bytes, to_xlsx_bytes  # noqa: E402
from invoice_processor.models import (  # noqa: E402
    ExtractedInvoice,
    InvoiceData,
    ProcessedInvoice,
)
from invoice_processor.validation import validate_invoice  # noqa: E402
from invoice_processor.workflow import (  # noqa: E402
    extract_invoice_text,
    process_extracted_invoice,
)


SUMMARY_COLUMNS = [
    "supplier_name",
    "supplier_tax_id",
    "invoice_number",
    "invoice_date",
    "due_date",
    "currency",
    "net_amount",
    "tax_amount",
    "total_amount",
    "purchase_order_number",
    "products_services_summary",
    "confidence_notes",
]
NUMBER_FIELDS = {"net_amount", "tax_amount", "total_amount"}


def _display_value(value: object) -> object:
    """Convert typed values into editable table-friendly values."""

    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()  # type: ignore[union-attr]
    return value


def _clean(value: object, *, numeric: bool = False) -> object:
    """Turn blank/NaN editor cells into None and coerce numeric cells."""

    if value is None or (not isinstance(value, (list, dict)) and pd.isna(value)):
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return float(value) if numeric else value


def review_invoice(
    result: ProcessedInvoice,
    index: int,
    fallback_source_text: str = "",
) -> ProcessedInvoice | None:
    """Render editable fields and return the current reviewed invoice."""

    invoice = result.invoice
    # Streamlit can retain objects created before a code reload. Fall back to the
    # text stored by the earlier PDF-preview stage for those existing sessions.
    source_text = getattr(result, "source_text", fallback_source_text)
    st.subheader(result.source_filename)
    summary = pd.DataFrame(
        [
            {
                field: _display_value(getattr(invoice, field, None))
                for field in SUMMARY_COLUMNS
            }
        ]
    )
    edited_summary = st.data_editor(
        summary,
        key=f"summary_{index}",
        hide_index=True,
        use_container_width=True,
        column_config={
            "net_amount": st.column_config.NumberColumn(format="%.2f"),
            "tax_amount": st.column_config.NumberColumn(format="%.2f"),
            "total_amount": st.column_config.NumberColumn(format="%.2f"),
        },
    )

    try:
        row = edited_summary.iloc[0].to_dict()
        cleaned_summary = {
            field: _clean(row.get(field), numeric=field in NUMBER_FIELDS)
            for field in SUMMARY_COLUMNS
        }
        reviewed = InvoiceData.model_validate(cleaned_summary)
    except (ValueError, TypeError) as exc:
        st.error(f"Please correct an invalid value: {exc}")
        return None

    issues = validate_invoice(reviewed, source_text)
    if not issues:
        st.success("Validation passed.")
    else:
        for issue in issues:
            message = f"{issue.field}: {issue.message}"
            st.error(message) if issue.severity == "error" else st.warning(message)
    return ProcessedInvoice(
        source_filename=result.source_filename,
        invoice=reviewed,
        source_text=source_text,
    )


def main() -> None:
    st.set_page_config(page_title="AI Invoice Processor", page_icon="🧾", layout="wide")
    st.title("🧾 AI Invoice Processor")
    st.write(
        "Upload digital PDF invoices, extract structured fields with AI, review the "
        "values, and download the results. Scanned PDFs are not supported in version 1."
    )

    settings = load_settings()
    with st.sidebar:
        st.header("Settings")
        api_key = st.text_input(
            "OpenAI API key",
            value=settings.openai_api_key,
            type="password",
            help="Used for this local session. You can also set OPENAI_API_KEY in .env.",
        )
        model = st.text_input("Model", value=settings.openai_model)
        st.caption("Invoice text is sent to the selected OpenAI model. API response storage is disabled.")

    uploads = st.file_uploader(
        "Choose one or more PDF invoices",
        type=["pdf"],
        accept_multiple_files=True,
    )

    if st.button("1. Extract and preview text", type="primary", disabled=not uploads):
        extracted_documents: list[ExtractedInvoice] = []
        errors: list[str] = []
        with st.spinner("Reading embedded PDF text locally..."):
            for upload in uploads:
                try:
                    extracted_documents.append(
                        extract_invoice_text(upload.getvalue(), upload.name)
                    )
                except Exception as exc:
                    errors.append(f"{upload.name}: {exc}")
        st.session_state["extracted_documents"] = extracted_documents
        st.session_state["extraction_errors"] = errors
        st.session_state.pop("processed_invoices", None)
        st.session_state.pop("processing_errors", None)

    for error in st.session_state.get("extraction_errors", []):
        st.error(error)

    extracted_documents = st.session_state.get("extracted_documents", [])
    if extracted_documents:
        st.divider()
        st.header("Check the extracted text")
        st.info(
            "This text was read locally and has not been sent to AI. Confirm that "
            "supplier names, invoice numbers, dates, currencies, and totals are readable."
        )
        for index, document in enumerate(extracted_documents):
            with st.expander(document.source_filename, expanded=index == 0):
                preview_limit = 4_000
                preview = document.text[:preview_limit]
                st.text_area(
                    "Extracted text preview",
                    value=preview,
                    height=260,
                    disabled=True,
                    key=f"preview_{index}",
                )
                if len(document.text) > preview_limit:
                    st.caption(
                        f"Showing the first {preview_limit:,} of "
                        f"{len(document.text):,} characters."
                    )
                else:
                    st.caption(f"Showing all {len(document.text):,} extracted characters.")

        if st.button("2. Continue with AI extraction"):
            if not api_key:
                st.error("Add an OpenAI API key in the sidebar before using AI extraction.")
            else:
                results: list[ProcessedInvoice] = []
                errors: list[str] = []
                ai_extractor = partial(extract_invoice_with_ai, api_key=api_key, model=model)
                with st.spinner("Extracting structured invoice fields with AI..."):
                    for document in extracted_documents:
                        try:
                            results.append(process_extracted_invoice(document, ai_extractor))
                        except Exception as exc:
                            errors.append(f"{document.source_filename}: {exc}")
                st.session_state["processed_invoices"] = results
                st.session_state["processing_errors"] = errors

    for error in st.session_state.get("processing_errors", []):
        st.error(error)

    results = st.session_state.get("processed_invoices", [])
    if results:
        st.divider()
        st.header("Review extracted values")
        st.info("Edit any field that needs correction. Validation updates automatically.")
        reviewed_results = []
        source_text_by_filename = {
            document.source_filename: document.text for document in extracted_documents
        }
        for index, result in enumerate(results):
            with st.container(border=True):
                reviewed = review_invoice(
                    result,
                    index,
                    source_text_by_filename.get(result.source_filename, ""),
                )
                if reviewed is not None:
                    reviewed_results.append(reviewed)

        if len(reviewed_results) == len(results):
            st.subheader("Export reviewed results")
            csv_column, xlsx_column = st.columns(2)
            with csv_column:
                st.download_button(
                    "Download CSV",
                    data=to_csv_bytes(reviewed_results),
                    file_name="invoice_results.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            with xlsx_column:
                st.download_button(
                    "Download Excel",
                    data=to_xlsx_bytes(reviewed_results),
                    file_name="invoice_results.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )


if __name__ == "__main__":
    main()
