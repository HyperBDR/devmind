# Quotation Preview Export Design

## Goal

For locally created quotations, make the Excel and PDF files uploaded to
Feishu match the right-side creation preview. Preserve original files for
document-import quotations. Do not rebuild or modify the existing Docker
images.

## Scope

- The visual source of truth is `QuotationPreview.vue` in compact mode.
- Locally created quotations are rendered into the preview layout.
- Imported Excel and PDF files retain their original bytes and layout.
- Existing API, worker, database, and Docker images remain in place.
- The current bind-mounted backend source is the only runtime change.

## Non-goals

The implementation must not change behavior outside locally created
quotation rendering. In particular, it must not modify:

- quotation create, edit, delete, list, permissions, or audit behavior;
- Feishu authentication, folder browsing, upload, retry, or open-link logic;
- export job models, API contracts, idempotency, queues, or replica routing;
- document-import parsing or original-file preservation;
- database schemas or migrations;
- Dockerfiles, Compose files, images, dependencies, or container topology.

Production edits are limited to the quotation renderer and its renderer tests,
plus the backend copy of the existing logo asset. Any required change outside
that boundary stops implementation for renewed approval.

## Rendering Architecture

Excel is the only server-side layout implementation. The renderer maps the
preview structure to one worksheet using the existing `openpyxl` and Pillow
dependencies. PDF output is produced from those exact Excel bytes with the
existing headless LibreOffice binary.

The independent HTML/PyMuPDF preview renderer is removed from the export
pipeline. This prevents Excel and PDF from drifting into separate layouts.

## Visual Contract

The generated worksheet must reproduce the preview's observable structure:

- OnePro logo position and scale;
- seven fixed columns with `12/24/8/12/10/17/17` proportions;
- white page, slate text, slate borders, gray section headers;
- issuer heading, underlined Quotation title, and matching vertical spacing;
- Ship to, Bill to, quote metadata, and contact metadata blocks;
- Software and Others sections with minimum three and five rows;
- all real line items without truncation;
- identical labels, number formatting, percentage formatting, and totals;
- disclaimer block, acceptance text, signature image, and signer details.

Excel features that do not exist in HTML, such as cells and print areas, are
configured only to preserve the preview appearance when opened or printed.

## Assets

The existing OnePro logo is copied into a backend quotation asset directory
and loaded from the bind-mounted source tree. Signature images continue to be
decoded from the quotation snapshot with the existing validation limits.
Neither asset requires a Docker image change.

## Data Flow

1. Pin the quotation version and template metadata as today.
2. For a locally created quotation, render one preview-layout XLSX.
3. Return that XLSX when Excel is requested.
4. Convert the same XLSX bytes through LibreOffice when PDF is requested.
5. Persist and upload the resulting assets through the existing Feishu replica
   workflow and selected archive folder.
6. For an imported quotation's original revision, keep the existing original
   byte preservation behavior.

Pinned renderer versions remain immutable. An unsupported old renderer fails
explicitly instead of being silently rewritten while a job is running.

## Error Handling

- Invalid or oversized signatures fail with the existing validation codes.
- Missing logo or invalid generated workbook fails before asset persistence.
- PDF conversion keeps the existing capacity, timeout, and cleanup behavior.
- No partial Excel asset is persisted when requested PDF conversion fails.
- Feishu failures remain upload failures and do not affect local output bytes.

## Verification

Automated tests cover:

- preview column proportions, row heights, fonts, colors, borders, and labels;
- embedded logo and optional signature;
- minimum blank rows and unlimited real line items;
- preserved imported source bytes;
- PDF conversion receives the exact generated Excel bytes;
- failure atomicity and immutable renderer versions;
- existing Feishu folder selection, upload, and open-link behavior;
- the complete frontend quotation suite and backend quotation suite.

Manual verification uses port `18000` and the existing containers: create a
quotation, compare the right-side preview with downloaded Excel and PDF,
upload both to Feishu, and open both links successfully.
