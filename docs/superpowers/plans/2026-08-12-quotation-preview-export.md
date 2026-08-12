# Quotation Preview Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make locally created quotation Excel and PDF exports match the
right-side creation preview while preserving imported originals and every
non-rendering behavior.

**Architecture:** `render_quotation_xlsx()` is the only server-side layout
implementation. The export pipeline passes those exact XLSX bytes to the
existing LibreOffice converter for PDF, so both formats share one layout.
Imported first revisions continue to use their untouched source XLSX.

**Tech Stack:** Django 5.1, openpyxl, Pillow, LibreOffice headless, unittest,
Node test runner.

## Global Constraints

- The visual source of truth is `QuotationPreview.vue` in compact mode.
- Only locally created quotation rendering may change.
- Imported Excel and PDF files retain their original bytes and layout.
- Do not change Feishu, API, permissions, models, migrations, queues, storage
  routing, Dockerfiles, Compose files, images, dependencies, or containers.
- Use existing `backend-api-dev` and `backend-worker-dev` containers and port
  `18000`.
- Stop for renewed approval if implementation requires a file outside the
  explicit file list below.

## File Map

- Modify `backend/quotation/services/export_renderer.py`: implement the one
  preview-layout XLSX renderer and retain the existing LibreOffice converter.
- Modify `backend/quotation/services/export_pipeline.py`: convert the exact
  rendered XLSX bytes to PDF and keep pinned renderer versions immutable.
- Create `backend/quotation/assets/onepro-logo.png`: backend copy of the
  existing frontend logo; no image build changes.
- Modify `backend/quotation/test_exports.py`: behavioral renderer and pipeline
  regression tests.
- Modify `frontend/scripts/quotation-export-completeness.test.mjs`: static
  cross-layer guard for unlimited rows and the single-layout PDF path.

---

### Task 1: Lock the single-layout export behavior

**Files:**
- Modify: `backend/quotation/test_exports.py`
- Modify: `frontend/scripts/quotation-export-completeness.test.mjs`

**Interfaces:**
- Consumes: `render_quotation_xlsx(template, snapshot) -> bytes` and
  `convert_xlsx_to_pdf(excel_bytes, *, job_id) -> bytes`.
- Produces: failing regression tests that require PDF conversion to receive the
  exact XLSX bytes and reject silent renderer-version mutation.

- [ ] **Step 1: Update the imported-original PDF test**

Keep `test_imported_first_revision_uses_untouched_source_excel` and require:

```python
convert_pdf.assert_called_once_with(source_bytes, job_id=job.id)
```

This protects imported source preservation and should already describe the
desired behavior.

- [ ] **Step 2: Add a local-render exact-byte test**

```python
@patch(
    "quotation.services.export_pipeline.convert_xlsx_to_pdf",
    return_value=b"%PDF-preview",
)
@patch(
    "quotation.services.export_pipeline.render_quotation_xlsx",
    return_value=b"PK\x03\x04-preview-layout",
)
def test_local_pdf_converts_the_exact_preview_excel(
    self,
    render_xlsx,
    convert_pdf,
):
    job = self.create_job(["xlsx", "pdf"])

    result = render_quotation_export_task.run(job.id)

    self.assertEqual(result["status"], ExportJobStatus.COMPLETED)
    render_xlsx.assert_called_once_with(
        job.template,
        job.quotation_version.snapshot_json,
    )
    convert_pdf.assert_called_once_with(
        b"PK\x03\x04-preview-layout",
        job_id=job.id,
    )
```

- [ ] **Step 3: Change the legacy renderer test to immutable failure**

Rename it to
`test_queued_job_rejects_unsupported_pinned_renderer` and assert:

```python
job.refresh_from_db()
self.assertEqual(result["status"], ExportJobStatus.RENDER_FAILED)
self.assertEqual(job.renderer_version, "openpyxl-libreoffice-v1")
self.assertEqual(job.error_code, "renderer_version_unsupported")
self.assertEqual(job.assets.count(), 0)
```

- [ ] **Step 4: Replace the obsolete frontend source-regex guard**

The Node test must assert the new invariant without depending on the removed
template-row insertion implementation:

```javascript
test('backend preview export keeps every item and uses one PDF layout', () => {
  assert.match(renderer, /items = list\(snapshot\.get\("items"\) or \[\]\)/)
  assert.match(renderer, /max\(minimum - len\(section_items\), 0\)/)
  assert.match(pipeline, /convert_xlsx_to_pdf\(\s*excel_bytes,/)
  assert.doesNotMatch(pipeline, /render_preview_pdf/)
})
```

Read `export_pipeline.py` into `pipeline` beside the existing `renderer`
fixture.

- [ ] **Step 5: Run tests and verify RED**

Run:

```bash
cd frontend && node --test scripts/quotation-export-completeness.test.mjs
docker exec backend-api-dev /opt/venv/bin/python manage.py test \
  quotation.test_exports.QuotationExportTaskTests.test_local_pdf_converts_the_exact_preview_excel \
  quotation.test_exports.QuotationExportTaskTests.test_queued_job_rejects_unsupported_pinned_renderer \
  --verbosity 1
```

Expected: the Node test fails because `render_preview_pdf` is still used; the
backend tests fail because PDF does not receive `excel_bytes` and renderer
versions are silently replaced.

- [ ] **Step 6: Commit tests**

```bash
git add backend/quotation/test_exports.py \
  frontend/scripts/quotation-export-completeness.test.mjs
git commit -m "test: lock quotation preview export contract"
```

### Task 2: Match the preview in the XLSX renderer

**Files:**
- Create: `backend/quotation/assets/onepro-logo.png`
- Modify: `backend/quotation/services/export_renderer.py`
- Modify: `backend/quotation/test_exports.py`

**Interfaces:**
- Consumes: a pinned `QuotationTemplate` and immutable quotation snapshot.
- Produces: `render_quotation_xlsx(template, snapshot) -> bytes` containing one
  worksheet named `Quotation`, the preview layout, logo, and optional
  signature.

- [ ] **Step 1: Copy the existing logo without changing it**

Copy
`frontend/src/modules/quotation/assets/onepro-logo.png` byte-for-byte to
`backend/quotation/assets/onepro-logo.png`, then verify identical hashes:

```bash
shasum -a 256 frontend/src/modules/quotation/assets/onepro-logo.png \
  backend/quotation/assets/onepro-logo.png
```

Expected: both SHA-256 hashes are identical.

- [ ] **Step 2: Add a workbook visual-contract test**

Create a local quotation snapshot with four Software items, six Other items,
and a small valid PNG signature. Render and load the workbook with openpyxl,
then assert:

```python
self.assertEqual(sheet.title, "Quotation")
self.assertEqual(
    [sheet.column_dimensions[column].width for column in "ABCDEFG"],
    [12, 24, 8, 12, 10, 17, 17],
)
self.assertEqual(sheet["A2"].value, self.quotation.issuer_company_name)
self.assertEqual(sheet["A3"].value, "Quotation")
self.assertEqual(sheet["A19"].value, "Software")
self.assertEqual(sheet["A27"].value, "Others")
self.assertEqual(len(sheet._images), 2)
self.assertEqual(sheet["A20"].fill.fgColor.rgb, "00F8FAFC")
self.assertEqual(sheet["A19"].fill.fgColor.rgb, "00E2E8F0")
```

Also gather non-empty descriptions from column B and assert every supplied
description appears. Use exactly four Software and six Other items in this
test so the fixed section assertions remain deterministic.

- [ ] **Step 3: Run the visual-contract test and verify RED**

Run:

```bash
docker exec backend-api-dev /opt/venv/bin/python manage.py test \
  quotation.test_exports.QuotationExportTaskTests.test_xlsx_matches_creation_preview_layout \
  --verbosity 1
```

Expected: FAIL because the current workbook has no logo or signature and its
title spacing does not match the preview.

- [ ] **Step 4: Implement exact preview constants**

In `export_renderer.py`, define only the constants used by both renderer code
and tests:

```python
PREVIEW_COLUMN_WIDTHS = (12, 24, 8, 12, 10, 17, 17)
PREVIEW_TEXT_COLOR = "0F172A"
PREVIEW_BORDER_COLOR = "CBD5E1"
PREVIEW_SECTION_FILL = "E2E8F0"
PREVIEW_HEADER_FILL = "F8FAFC"
PREVIEW_SOFTWARE_ROWS = 3
PREVIEW_OTHER_ROWS = 5
PREVIEW_LOGO_PATH = (
    Path(__file__).resolve().parent.parent / "assets" / "onepro-logo.png"
)
```

- [ ] **Step 5: Implement the minimal worksheet mapping**

Keep `render_quotation_xlsx()` in the existing file and map the Vue preview in
the same order:

```python
items = list(snapshot.get("items") or [])
groups = (
    (
        "Software",
        [item for item in items if item.get("type") == "Software"],
        PREVIEW_SOFTWARE_ROWS,
        snapshot.get("software_subtotal"),
    ),
    (
        "Others",
        [item for item in items if item.get("type") != "Software"],
        PREVIEW_OTHER_ROWS,
        snapshot.get("others_subtotal"),
    ),
)

for section, section_items, minimum, subtotal in groups:
    rows = section_items + [
        {} for _ in range(max(minimum - len(section_items), 0))
    ]
```

The worksheet order must be logo spacer, issuer, title, Ship to, Bill to,
metadata, Software, Others, totals, disclaimers, acceptance, and signatures.
Use the same labels and blank-row minima as `QuotationPreview.vue`. Preserve
every real item by extending beyond the minimum rather than slicing.

- [ ] **Step 6: Embed logo and signature**

Use the already-installed openpyxl/Pillow path:

```python
logo = SpreadsheetImage(PREVIEW_LOGO_PATH)
logo.width = 132
logo.height = round(logo.height * (132 / logo.width))
logo.anchor = "A1"
sheet.add_image(logo)

signature = _signature_image(snapshot.get("issuer_signature", ""))
if signature is not None:
    signature.anchor = sheet.cell(row=signature_row, column=5).coordinate
    sheet.add_image(signature)
```

Store the original logo aspect ratio before assigning `logo.width` so the
height calculation uses the source dimensions.

- [ ] **Step 7: Set print behavior and validate output**

```python
sheet.sheet_view.showGridLines = False
sheet.print_area = f"A1:G{last_row}"
sheet.page_setup.orientation = "portrait"
sheet.page_setup.fitToWidth = 1
sheet.page_setup.fitToHeight = 0
sheet.sheet_properties.pageSetUpPr.fitToPage = True
```

Retain deterministic workbook timestamps and the existing generated-workbook
validation.

- [ ] **Step 8: Run renderer tests and verify GREEN**

Run:

```bash
docker exec backend-api-dev /opt/venv/bin/python manage.py test \
  quotation.test_exports.QuotationExportTaskTests.test_xlsx_matches_creation_preview_layout \
  --verbosity 1
cd frontend && node --test scripts/quotation-export-completeness.test.mjs
```

Expected: the workbook test passes; the Node test remains RED only on the
pipeline's independent PDF path.

- [ ] **Step 9: Commit the XLSX renderer**

```bash
git add backend/quotation/assets/onepro-logo.png \
  backend/quotation/services/export_renderer.py \
  backend/quotation/test_exports.py
git commit -m "fix: match quotation export to creation preview"
```

### Task 3: Generate PDF from the exact XLSX bytes

**Files:**
- Modify: `backend/quotation/services/export_pipeline.py`
- Modify: `backend/quotation/services/export_renderer.py`
- Modify: `backend/quotation/test_exports.py`

**Interfaces:**
- Consumes: `excel_bytes` from the local renderer or imported original.
- Produces: PDF bytes from
  `convert_xlsx_to_pdf(excel_bytes, job_id=job.id)`.

- [ ] **Step 1: Restore immutable renderer-version validation**

Replace silent mutation with the existing typed error:

```python
if job.renderer_version != CURRENT_RENDERER_VERSION:
    raise TemplateValidationError(
        "Pinned quotation renderer is no longer supported",
        code="renderer_version_unsupported",
    )
```

Remove `renderer_version` from this status transition's `update_fields`.

- [ ] **Step 2: Convert the exact Excel output**

Replace the independent PDF call with:

```python
if "pdf" in job.formats:
    ExportJob.objects.filter(pk=job.id).update(
        status=ExportJobStatus.CONVERTING_PDF
    )
    outputs[DocumentType.PDF] = convert_xlsx_to_pdf(
        excel_bytes,
        job_id=job.id,
    )
```

Remove the `render_preview_pdf` import.

- [ ] **Step 3: Delete the duplicate PDF layout**

Delete `_pdf_text`, `_pdf_money`, `_preview_pdf_html`, and
`render_preview_pdf` from `export_renderer.py`, then remove imports used only
by those functions. Keep `convert_xlsx_to_pdf()` and
`_convert_xlsx_to_pdf_unlocked()` unchanged.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run:

```bash
docker exec backend-api-dev /opt/venv/bin/python manage.py test \
  quotation.test_exports.QuotationExportTaskTests.test_imported_first_revision_uses_untouched_source_excel \
  quotation.test_exports.QuotationExportTaskTests.test_local_pdf_converts_the_exact_preview_excel \
  quotation.test_exports.QuotationExportTaskTests.test_pdf_failure_creates_no_partial_excel_asset \
  quotation.test_exports.QuotationExportTaskTests.test_queued_job_rejects_unsupported_pinned_renderer \
  --verbosity 1
cd frontend && node --test scripts/quotation-export-completeness.test.mjs
```

Expected: all focused tests pass.

- [ ] **Step 5: Commit the pipeline change**

```bash
git add backend/quotation/services/export_pipeline.py \
  backend/quotation/services/export_renderer.py \
  backend/quotation/test_exports.py
git commit -m "fix: derive quotation PDF from preview Excel"
```

### Task 4: Full regression and live verification

**Files:**
- No production file changes.

**Interfaces:**
- Consumes: the completed renderer and existing port `18000` runtime.
- Produces: test evidence and visual evidence without rebuilding images.

- [ ] **Step 1: Record existing image identities**

```bash
docker inspect backend-api-dev backend-worker-dev \
  --format '{{.Name}} {{.Image}} {{.Config.Image}}'
```

Save the output for comparison after verification.

- [ ] **Step 2: Run all quotation tests**

```bash
docker exec backend-api-dev /opt/venv/bin/python manage.py test quotation \
  --verbosity 1
cd frontend && npm run test:quotation
```

Expected: all backend quotation tests and all 100 frontend quotation tests
pass.

- [ ] **Step 3: Run static checks**

```bash
git diff --check
cd frontend && npm run build
```

Expected: both commands succeed.

- [ ] **Step 4: Verify existing images are unchanged**

Repeat:

```bash
docker inspect backend-api-dev backend-worker-dev \
  --format '{{.Name}} {{.Image}} {{.Config.Image}}'
```

Expected: output is byte-for-byte identical to Step 1. Do not run any Docker
build, pull, recreate, or Compose command.

- [ ] **Step 5: Verify local-create Excel and PDF on port 18000**

Using ego lite, open an existing locally created quotation and capture the
right-side preview. Export Excel and PDF through the UI. Render the first PDF
page and the XLSX print output for visual comparison. Verify Logo, columns,
spacing, all lines, totals, disclaimer, and signature match the preview.

- [ ] **Step 6: Verify Feishu upload and links**

Upload both formats to the configured folder. Confirm the quotation record has
new Excel and PDF document IDs, then open both buttons and verify the two files
load in Feishu.

- [ ] **Step 7: Confirm imported originals remain untouched**

Export an imported first revision and compare its downloaded XLSX SHA-256 with
the source document SHA-256. Expected: identical hashes.

- [ ] **Step 8: Final scope audit**

```bash
git diff --name-only HEAD~3..HEAD
```

Expected names are limited to the five files in this plan plus the design and
plan documents. If any unrelated path appears, stop and remove that unrelated
change before completion.
