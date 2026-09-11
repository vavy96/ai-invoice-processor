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
from invoice_processor.customer_profiles import (  # noqa: E402
    CUSTOMER_PROFILES,
    CustomerProfile,
)
from invoice_processor.duplicate_detector import (  # noqa: E402
    find_duplicate_invoices,
)
from invoice_processor.exporters import (  # noqa: E402
    to_accuracy_csv_bytes,
    to_csv_bytes,
    to_line_items_csv_bytes,
    to_xlsx_bytes,
)
from invoice_processor.metrics import (  # noqa: E402
    compare_invoice_fields,
    field_accuracy_percent,
)
from invoice_processor.models import (  # noqa: E402
    ExtractedInvoice,
    InvoiceData,
    InvoiceLineItem,
    ProcessedInvoice,
    ProcessingMetrics,
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

LINE_ITEM_COLUMNS = [
    "description",
    "item_type",
    "quantity",
    "unit",
    "unit_price",
    "net_amount",
    "tax_rate_percent",
    "tax_amount",
    "total_amount",
    "service_period_start",
    "service_period_end",
]

LINE_ITEM_NUMBER_FIELDS = {
    "quantity",
    "unit_price",
    "net_amount",
    "tax_rate_percent",
    "tax_amount",
    "total_amount",
}


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
def display_processing_metrics(
    result: ProcessedInvoice,
    reviewed: InvoiceData,
) -> None:
    """Display timing, token, cost and review-agreement measurements."""

    metrics = getattr(
        result,
        "processing_metrics",
        ProcessingMetrics(),
    )
    comparisons = compare_invoice_fields(result.invoice, reviewed)
    agreement = field_accuracy_percent(comparisons)
    corrected_fields = [
        comparison.field_name
        for comparison in comparisons
        if not comparison.correct
    ]

    total_seconds = (
        metrics.local_extraction_seconds
        + metrics.ai_processing_seconds
    )

    if metrics.estimated_cost_usd is None:
        cost_display = "Unavailable"
    else:
        cost_display = f"${metrics.estimated_cost_usd:.6f}"

    if metrics.extraction_method == "ocr":
        method_display = "Local OCR (Tesseract)"
    else:
        method_display = "Digital text extraction"

    with st.expander("Processing measurements"):
        st.caption(
            "Review agreement assumes every displayed field has been "
            "checked against the original invoice."
        )

        agreement_column, time_column, cost_column = st.columns(3)

        with agreement_column:
            st.metric(
                "Field agreement after review",
                f"{agreement:.2f}%",
            )

        with time_column:
            st.metric(
                "Total processing time",
                f"{total_seconds:.2f} seconds",
            )

        with cost_column:
            st.metric(
                "Estimated API cost",
                cost_display,
            )

        st.write(f"**Reading method:** {method_display}")
        st.write(
            f"**Local extraction time:** "
            f"{metrics.local_extraction_seconds:.4f} seconds"
        )
        st.write(
            f"**AI processing time:** "
            f"{metrics.ai_processing_seconds:.4f} seconds"
        )
        st.write(f"**Model:** {metrics.model or 'Not recorded'}")
        st.write(f"**Input tokens:** {metrics.input_tokens:,}")
        st.write(
            f"**Cached input tokens:** "
            f"{metrics.cached_input_tokens:,}"
        )
        st.write(f"**Output tokens:** {metrics.output_tokens:,}")
        st.write(f"**Total tokens:** {metrics.total_tokens:,}")

        if corrected_fields:
            st.warning(
                "Fields corrected during review: "
                + ", ".join(corrected_fields)
            )
        else:
            st.success("No fields have been corrected during review.")


def review_invoice(
    result: ProcessedInvoice,
    index: int,
    fallback_source_text: str = "",
    *,
    profile: CustomerProfile,
) -> ProcessedInvoice | None:
    """Render editable fields and return the current reviewed invoice."""

    invoice = result.invoice
    # Streamlit can retain objects created before a code reload. Fall back to the
    # text stored by the earlier PDF-preview stage for those existing sessions.
    source_text = getattr(result, "source_text", fallback_source_text)
    st.subheader(result.source_filename)
    st.caption(
        f"Validation profile: {profile.display_name}"
    )
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

    st.markdown("**Invoice line items**")
    st.caption(
        "Review the extracted products and services. "
        "You can add or remove rows."
    )

    line_item_rows = [
        {
            field: getattr(item, field, None)
            for field in LINE_ITEM_COLUMNS
        }
        for item in getattr(invoice, "line_items", [])
    ]
    line_items_dataframe = pd.DataFrame(
        line_item_rows,
        columns=LINE_ITEM_COLUMNS,
    )

    edited_line_items = st.data_editor(
        line_items_dataframe,
        key=f"line_items_{index}",
        hide_index=True,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "description": st.column_config.TextColumn(
                "Description",
                required=False,
            ),
            "item_type": st.column_config.SelectboxColumn(
                "Type",
                options=["product", "service", "other"],
                required=False,
            ),
            "quantity": st.column_config.NumberColumn(
                "Quantity",
                format="%.2f",
            ),
            "unit": st.column_config.TextColumn("Unit"),
            "unit_price": st.column_config.NumberColumn(
                "Unit price",
                format="%.2f",
            ),
            "net_amount": st.column_config.NumberColumn(
                "Net amount",
                format="%.2f",
            ),
            "tax_rate_percent": st.column_config.NumberColumn(
                "Tax rate %",
                format="%.2f",
            ),
            "tax_amount": st.column_config.NumberColumn(
                "Tax amount",
                format="%.2f",
            ),
            "total_amount": st.column_config.NumberColumn(
                "Total amount",
                format="%.2f",
            ),
            "service_period_start": st.column_config.DateColumn(
                "Service start",
                format="YYYY-MM-DD",
            ),
            "service_period_end": st.column_config.DateColumn(
                "Service end",
                format="YYYY-MM-DD",
            ),
        },
    )

    try:
        row = edited_summary.iloc[0].to_dict()
        cleaned_summary = {
            field: _clean(
                row.get(field),
                numeric=field in NUMBER_FIELDS,
            )
            for field in SUMMARY_COLUMNS
        }

        cleaned_line_items: list[InvoiceLineItem] = []

        for _, item_row in edited_line_items.iterrows():
            item_values = {
                field: _clean(
                    item_row.get(field),
                    numeric=field in LINE_ITEM_NUMBER_FIELDS,
                )
                for field in LINE_ITEM_COLUMNS
            }

            if all(
                value is None
                for value in item_values.values()
            ):
                continue

            if item_values["description"] is None:
                item_values["description"] = ""

            cleaned_line_items.append(
                InvoiceLineItem.model_validate(item_values)
            )

        cleaned_summary["line_items"] = cleaned_line_items
        reviewed = InvoiceData.model_validate(cleaned_summary)
    except (ValueError, TypeError) as exc:
        st.error(f"Please correct an invalid value: {exc}")
        return None

    issues = validate_invoice(
        reviewed,
        source_text,
        profile=profile,
    )
    if not issues:
        st.success("Validation passed.")
    else:
        for issue in issues:
            message = f"{issue.field}: {issue.message}"
            st.error(message) if issue.severity == "error" else st.warning(message)
    display_processing_metrics(result, reviewed)


    return ProcessedInvoice(
        source_filename=result.source_filename,
        invoice=reviewed,
        customer_profile_key=profile.key,
        source_text=source_text,
        processing_metrics=getattr(
            result,
            "processing_metrics",
            ProcessingMetrics(),
        ),
    )


def main() -> None:
    st.set_page_config(page_title="AI Invoice Processor", page_icon="🧾", layout="wide")
    st.title("🧾 AI Invoice Processor")
    st.write(
    "Upload PDF invoices, extract structured fields with AI, review the values, "
    "and download the results. Scanned PDFs are processed locally with OCR when needed."
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
        model = st.text_input(
            "Model",
            value=settings.openai_model,
        )

        selected_profile_key = st.selectbox(
            "Customer profile",
            options=list(CUSTOMER_PROFILES),
            format_func=lambda profile_key: (
                CUSTOMER_PROFILES[profile_key].display_name
            ),
            help=(
                "Controls which invoice fields are required "
                "during validation."
            ),
        )
        selected_profile = CUSTOMER_PROFILES[
            selected_profile_key
        ]

        st.caption(selected_profile.description)
        st.caption(
            "Invoice text is sent to the selected OpenAI model. "
            "API response storage is disabled."
        )

    uploads = st.file_uploader(
        "Choose one or more PDF invoices",
        type=["pdf"],
        accept_multiple_files=True,
    )

    if st.button("1. Extract and preview text", type="primary", disabled=not uploads):
        extracted_documents: list[ExtractedInvoice] = []
        errors: list[str] = []
        with st.spinner("Reading PDF text locally..."):
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
                if document.extraction_method == "ocr":
                    st.caption("Reading method: Local OCR (Tesseract)")
                else:
                    st.caption("Reading method: Digital text extraction")
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
                    source_text_by_filename.get(
                        result.source_filename,
                        "",
                    ),
                    profile=selected_profile,
                )
                if reviewed is not None:
                    reviewed_results.append(reviewed)

        if len(reviewed_results) == len(results):
            duplicates = find_duplicate_invoices(reviewed_results)

            st.subheader("Duplicate invoice check")

            if duplicates:
                for duplicate in duplicates:
                    st.warning(
                        f"Possible duplicate: "
                        f"{duplicate.duplicate_filename} matches "
                        f"{duplicate.original_filename}. "
                        "They have the same supplier identity and "
                        "invoice number."
                    )
            else:
                st.success(
                    "No duplicate invoices were detected in this batch."
                )

            st.subheader("Export reviewed results")

            (
                csv_column,
                line_items_column,
                xlsx_column,
                accuracy_column,
            ) = st.columns(4)

            with csv_column:
                st.download_button(
                    "Download invoice CSV",
                    data=to_csv_bytes(reviewed_results),
                    file_name="invoice_results.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

            with line_items_column:
                st.download_button(
                    "Download line-item CSV",
                    data=to_line_items_csv_bytes(
                        reviewed_results
                    ),
                    file_name="invoice_line_items.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

            with xlsx_column:
                st.download_button(
                    "Download Excel report",
                    data=to_xlsx_bytes(
                        reviewed_results,
                        original_results=results,
                    ),
                    file_name="invoice_results.xlsx",
                    mime=(
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    ),
                    use_container_width=True,
                )

            with accuracy_column:
                st.download_button(
                    "Download accuracy CSV",
                    data=to_accuracy_csv_bytes(
                        results,
                        reviewed_results,
                    ),
                    file_name="invoice_accuracy.csv",
                    mime="text/csv",
                    use_container_width=True,
                )


if __name__ == "__main__":
    main()
