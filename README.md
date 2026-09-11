# AI Invoice Processor

AI Invoice Processor is a beginner-friendly local Streamlit app. It reads the
embedded text in digital PDF invoices, asks an OpenAI model to turn that text into
structured fields, checks the values, lets a person correct them, and exports the
reviewed results.

## Version 1 scope

Included:

- Runs locally with a simple Streamlit interface.
- Accepts one or more PDF invoices.
- Extracts embedded text from digital PDFs.
- Requests typed, structured output from an OpenAI model.
- Checks required fields, dates, currencies, and totals.
- Lets a person edit every extracted value before export.
- Downloads invoice summaries as CSV.
- Downloads the fixed invoice schema as an XLSX workbook.
- Includes modular code and basic automated tests.

Intentionally not included yet: OCR, a database, authentication, Docker, or cloud
deployment. Scanned and image-only PDFs therefore produce a clear error.

## Screenshot

![AI Invoice Processor review screen](docs/images/ai-invoice-processor-review.png)

## Project structure

```text
invoice-processor/
├── app.py                         # Streamlit interface and review screen
├── src/invoice_processor/
│   ├── ai_extractor.py            # OpenAI structured extraction
│   ├── config.py                  # .env and environment settings
│   ├── exporters.py               # CSV and XLSX creation
│   ├── models.py                  # Fixed invoice schema from the guideline
│   ├── pdf_extractor.py           # Digital PDF text extraction
│   ├── validation.py              # Explainable business checks
│   └── workflow.py                # PDF-to-invoice coordinator
├── tests/                         # Automated unit tests
├── .env.example                   # Safe configuration example
├── requirements.txt               # Python dependencies
└── pyproject.toml                  # Package and test configuration
```

The Streamlit UI depends on the workflow, but the workflow does not depend on
Streamlit. This keeps the important logic easy to test and reuse.

## Invoice schema

Version 1 uses the guideline's invoice fields and adds one reviewed summary field
for billed products and services:

```text
supplier_name
supplier_tax_id
invoice_number
invoice_date
due_date
currency
net_amount
tax_amount
total_amount
purchase_order_number
products_services_summary
confidence_notes
```

Using one agreed schema keeps AI extraction, review, validation, CSV, and Excel
exports consistent. When the invoice does not contain a field, its structured
value is `null`; the application does not ask the model to guess it.

`products_services_summary` lists the billed products and services in a single
export column. Multiple entries are separated with semicolons. A service period
is included beside the service name only when the invoice states it.

## Requirements

- Python 3.11 or newer
- An OpenAI API key with API billing configured
- A digital (text-based) PDF invoice for real extraction

## Setup on Windows PowerShell

Open PowerShell in this folder, then run:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Copy the example settings file:

```powershell
Copy-Item .env.example .env
```

Open `.env` in a text editor and replace `your_api_key_here`:

```dotenv
OPENAI_API_KEY=your_real_api_key
OPENAI_MODEL=gpt-4.1-mini
```

The model can also be changed in the app sidebar. Use a model available to your
OpenAI project that supports Structured Outputs.

## Run the app

With the virtual environment active:

```powershell
streamlit run app.py
```

Streamlit opens a local browser page. Upload PDFs, select **Extract and preview
text**, and check that key invoice details are readable. Nothing is sent to AI in
this first stage. When the text looks correct, select **Continue with AI
extraction**, review or edit the structured fields, and use the CSV or Excel
download buttons.

## Run the tests

```powershell
pytest
```

The tests do not call the OpenAI API. They use small fakes so that PDF handling,
validation, exports, and the workflow can be checked quickly and without cost.

## How the processing flow works

1. `pdf_extractor.py` reads embedded PDF text with pypdf and the app shows a local
   preview for human verification.
2. After the user continues, `ai_extractor.py` sends that text to the Responses API and requests an
   `InvoiceData` structured result.
3. `validation.py` reports suspicious or missing values without silently fixing
   them.
4. `app.py` presents editable summary and line-item tables for human review.
5. `exporters.py` creates downloads in memory; it does not create a database.

## Privacy and limitations

- The app runs locally, but extracted invoice text is sent to the configured
  OpenAI model API. Do not upload documents you are not permitted to process.
- API response storage is disabled in the request (`store=False`). See the
  [official Responses API documentation](https://developers.openai.com/api/reference/python/resources/responses/methods/create)
  for current API behavior and data controls. This prevents the response from
  being stored for later API retrieval, but it does not by itself provide or
  claim Zero Data Retention.
- The application processes uploaded PDFs and generated downloads in memory; it
  does not intentionally save them to the project. Remove confidential source
  files and downloaded exports when they are no longer needed.
- Use only synthetic or properly anonymised invoices in a public repository,
  demonstration, screenshot, or portfolio.
- This prototype does not claim GDPR compliance. Real client use requires an
  appropriate legal and security review, including the chosen API provider's
  current privacy and retention terms.
- AI extraction can be wrong. Validation is intentionally simple, and human review
  is required before relying on or exporting the data.
- Version 1 has no OCR. If text cannot be selected in a PDF viewer, the app will
  probably reject the file as scanned/image-only.

## Common problems

**“No usable digital text was found”**  
The file is likely scanned or image-only. OCR is outside version 1's scope.

**“An OpenAI API key is required”**  
Add the key in `.env` or paste it into the app sidebar for the current session.

**The model name is unavailable**  
Choose a Structured Outputs-capable model available in your OpenAI project and
enter its exact name in the sidebar.

**PowerShell blocks virtual-environment activation**  
You can run commands without activation, for example:

```powershell
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m streamlit run app.py
```
