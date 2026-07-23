import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const documentsApi = await readFile(
  new URL('../src/modules/quotation/api/documents.ts', import.meta.url),
  'utf8',
)
const importedDocumentsPage = await readFile(
  new URL(
    '../src/modules/quotation/components/ImportedDocumentsPage.vue',
    import.meta.url,
  ),
  'utf8',
)
const quotationList = await readFile(
  new URL('../src/modules/quotation/components/QuotationList.vue', import.meta.url),
  'utf8',
)
const quotationListPage = await readFile(
  new URL('../src/modules/quotation/pages/QuotationListPage.vue', import.meta.url),
  'utf8',
)
const quotationsApi = await readFile(
  new URL('../src/modules/quotation/api/quotations.ts', import.meta.url),
  'utf8',
)
const quotationPage = await readFile(
  new URL('../src/pages/Quotation.vue', import.meta.url),
  'utf8',
)
const appLayout = await readFile(
  new URL('../src/components/layout/AppLayout.vue', import.meta.url),
  'utf8',
)
const zhCnLocale = await readFile(
  new URL('../src/modules/quotation/locales/zh-CN.json', import.meta.url),
  'utf8',
)

test('document parsing API exposes automatic parse and fallback confirm operations', () => {
  assert.match(documentsApi, /parseImportedDocument/)
  assert.match(documentsApi, /getDocumentParseResult/)
  assert.match(documentsApi, /confirmDocumentParseResult/)
  assert.match(documentsApi, /document-parse-results\/.*\/confirm/)
})

test('archive sync imports Excel and PDF files into normal quotations', () => {
  assert.match(importedDocumentsPage, /syncResult\.created_quotation_ids/)
  assert.match(importedDocumentsPage, /created_quotation_count/)
  assert.match(importedDocumentsPage, /autoImportComplete/)
  assert.match(importedDocumentsPage, /emit\('quotationCreated'/)
  assert.doesNotMatch(importedDocumentsPage, /parseDocuments\(candidates\)/)
  assert.doesNotMatch(importedDocumentsPage, /DocumentParseReviewModal/)
  assert.doesNotMatch(importedDocumentsPage, /confirmDocumentParseResult/)
})

test('imported document controls stay mounted while their panel is hidden', () => {
  assert.match(
    quotationListPage,
    /<div class="hidden" aria-hidden="true">\s*<ImportedDocumentsPage/,
  )
  assert.match(quotationListPage, /@quotation-created="handleImportedQuotationCreated"/)
  assert.doesNotMatch(quotationListPage, /v-if="false"/)
})

test('imported documents page keeps only fallback parse states in the list', () => {
  assert.match(importedDocumentsPage, /canParse\(row\.doc\)/)
  assert.match(importedDocumentsPage, /\['excel', 'pdf'\]/)
  assert.match(importedDocumentsPage, /statusParseReady/)
  assert.match(importedDocumentsPage, /statusParseReview/)
  assert.match(importedDocumentsPage, /statusParseConfirmed/)
  assert.match(importedDocumentsPage, /statusNotQuotation/)
  assert.match(importedDocumentsPage, /not_quotation/)
  assert.match(importedDocumentsPage, /parseCreated/)
  assert.match(importedDocumentsPage, /parseNeedsAttention/)
  assert.match(importedDocumentsPage, /viewQuotation/)
})

test('temporary Office files stay visible without a parse action', () => {
  assert.match(importedDocumentsPage, /function isTemporaryFile/)
  assert.match(importedDocumentsPage, /startsWith\('\~\$'\)/)
  assert.match(importedDocumentsPage, /!isTemporaryFile\(doc\)/)
  assert.match(importedDocumentsPage, /statusTemporary/)
  assert.match(zhCnLocale, /"statusTemporary": "临时文件"/)
})

test('quotation searches support quote numbers and one-click clearing', () => {
  assert.match(documentsApi, /parsed_quote_no/)
  assert.match(importedDocumentsPage, /doc\.parsed_quote_no/)
  assert.match(importedDocumentsPage, /search = ''/)
  assert.match(quotationList, /searchText = ''/)
  assert.match(importedDocumentsPage, /clearSearch/)
  assert.match(quotationList, /clearSearch/)
})

test('imported documents cannot be deleted from the list', () => {
  assert.doesNotMatch(importedDocumentsPage, /deleteImportedDocuments/)
  assert.doesNotMatch(importedDocumentsPage, /handleBatchDelete/)
  assert.doesNotMatch(importedDocumentsPage, /type="checkbox"/)
})

test('quotation list shows one source or status indicator per quotation', () => {
  assert.match(quotationsApi, /source_type/)
  assert.match(quotationsApi, /versionCurrent/)
  assert.match(quotationList, /sourceDocumentImport/)
  assert.match(quotationList, /bg-fuchsia-100/)
  assert.match(quotationList, /selectedSource/)
  assert.doesNotMatch(quotationList, /V\{\{ quote\.versionCurrent \}\}/)
  assert.match(quotationList, /quote\.sourceType !== 'document_import'/)
  assert.match(
    quotationList,
    /v-if="quote\.sourceType === 'document_import'"/,
  )
  assert.match(quotationList, /v-else-if="quote\.status === 'Cancelled'"/)
})

test('quotation number is constrained and exposes its full value on hover', () => {
  assert.match(quotationList, /max-w-\[220px\]/)
  assert.match(quotationList, /truncate whitespace-nowrap/)
  assert.match(quotationList, /:title="quote\.quoteNo"/)
})

test('quotation metadata has hover details and Feishu opens instead of downloading', () => {
  assert.match(quotationList, /:title="quote\.projectName"/)
  assert.match(quotationList, /:title="quote\.clientCompany"/)
  assert.match(quotationList, /:title="displayContact\(quote\)/)
  assert.match(quotationList, /popup\.location\.replace\(directUrl\)/)
  assert.doesNotMatch(quotationList, /downloadRemoteDocument/)
})

test('imported quotations only expose their original download format', () => {
  assert.match(quotationsApi, /source_document_type/)
  assert.match(quotationsApi, /sourceDocumentType/)
  assert.match(
    quotationList,
    /sourceDocumentType !== format/,
  )
  assert.match(
    quotationList,
    /sourceDocumentType === 'excel'/,
  )
  assert.match(
    quotationList,
    /sourceDocumentType === 'pdf'/,
  )
})

test('missing imported contact and amount placeholders are not displayed', () => {
  assert.match(quotationList, /displayContact/)
  assert.match(quotationList, /Not specified/)
  assert.match(quotationList, /displayTotal/)
  assert.match(quotationList, /sourceType === 'document_import'/)
})

test('quotation page owns the only vertical content scroller', () => {
  assert.match(quotationPage, /:content-scrollable="false"/)
  assert.match(quotationPage, /quotation-page-scroll-locked/)
  assert.match(quotationPage, /#app-scroll-stage/)
  assert.match(quotationPage, /overflow-y: auto/)
  assert.match(appLayout, /contentScrollable \? 'overflow-y-auto' : 'overflow-hidden'/)
})

test('quotation navigation preserves the mounted workspace', () => {
  assert.match(appLayout, /:key="contentKey"/)
  assert.match(appLayout, /route\.path\.startsWith\('\/quotation'\)/)
  assert.doesNotMatch(appLayout, /:key="route\.path"/)
})

test('imported documents render cached data before remote synchronization', () => {
  const cachedLoad = importedDocumentsPage.indexOf(
    'const cachedItems = await listImportedFeishuDocuments()',
  )
  const remoteSync = importedDocumentsPage.indexOf(
    'let syncResult = await syncFeishuArchiveFolder',
  )
  assert.ok(cachedLoad >= 0)
  assert.ok(remoteSync > cachedLoad)
})

test('confirmed document parse status is presented as parsed', () => {
  assert.match(zhCnLocale, /"statusParseConfirmed": "已解析"/)
  assert.doesNotMatch(zhCnLocale, /"statusParseConfirmed": "已生成报价"/)
})
