import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const quotationsApi = await readFile(
  new URL('../src/modules/quotation/api/quotations.ts', import.meta.url),
  'utf8',
)
const quotationList = await readFile(
  new URL(
    '../src/modules/quotation/components/QuotationList.vue',
    import.meta.url,
  ),
  'utf8',
)
const quotationApp = await readFile(
  new URL('../src/modules/quotation/App.vue', import.meta.url),
  'utf8',
)
const quotationListPage = await readFile(
  new URL(
    '../src/modules/quotation/pages/QuotationListPage.vue',
    import.meta.url,
  ),
  'utf8',
)
const quotationDetailPage = await readFile(
  new URL(
    '../src/modules/quotation/pages/QuotationDetailPage.vue',
    import.meta.url,
  ),
  'utf8',
)
const quotationCreatePage = await readFile(
  new URL(
    '../src/modules/quotation/pages/QuotationCreatePage.vue',
    import.meta.url,
  ),
  'utf8',
)
const quotationI18n = await readFile(
  new URL(
    '../src/modules/quotation/composables/useQuotationI18n.ts',
    import.meta.url,
  ),
  'utf8',
)

test('quotation API defaults to ten and supports allowed page sizes', () => {
  assert.match(quotationsApi, /params\.page \|\| 1/)
  assert.match(quotationsApi, /params\.pageSize \|\| 10/)
  assert.match(quotationsApi, /pageSize\?: 10 \| 20 \| 50/)
  assert.match(quotationsApi, /page_size/)
  assert.match(quotationsApi, /total_pages/)
})

test('list sends all search and source filter values to the server', () => {
  for (const parameter of [
    'search',
    'product_line_name',
    'source_type',
    'created_from',
    'created_to',
  ]) {
    assert.match(quotationsApi, new RegExp(`query\\.set\\('${parameter}'`))
  }
  assert.doesNotMatch(quotationList, /filteredQuotations/)
})

test('list maps business metadata and server product-line facets', () => {
  assert.match(quotationsApi, /quote_date: string/)
  assert.match(quotationsApi, /issuer_contact_name: string/)
  assert.match(quotationsApi, /salesperson: api\.issuer_contact_name/)
  assert.match(quotationsApi, /quoteDate: api\.quote_date/)
  assert.match(quotationsApi, /facets\?\.product_lines/)
  assert.match(quotationList, /props\.productLines\.map/)
  assert.doesNotMatch(quotationList, /loadProductLineOptions/)
})

test('list presents quote dates, salespeople and source labels', () => {
  assert.match(quotationList, /tableQuoteDate/)
  assert.match(quotationList, /function displayQuoteDate/)
  assert.match(quotationList, /quote\.quoteDate \? quote\.quoteDate\.substring\(0, 10\) : '—'/)
  assert.match(quotationList, /tableSalesperson/)
  assert.match(quotationList, /quote\.salesperson \|\| '—'/)
  assert.match(quotationList, /tableSource/)
  assert.match(quotationList, /sourceLocalCreated/)
  assert.match(quotationList, /sourceDocumentImport/)
  assert.doesNotMatch(quotationList, /tableStatusSource/)
  assert.doesNotMatch(quotationList, /const tableStatusValues/)
  assert.doesNotMatch(quotationI18n, /statusFilterOptions/)
})

test('pagination controls expose ranges, totals, pages and sizes', () => {
  assert.match(quotationList, /const pageNumbers = computed/)
  assert.match(quotationList, /!\[10, 20, 50\]\.includes\(value\)/)
  assert.match(quotationList, /const pageSizeOptions = \[10, 20, 50\]/)
  assert.match(quotationList, /test-id="quotation-page-size"/)
  assert.match(
    quotationList,
    /panel-class-name="!bottom-full !top-auto !mb-1 !mt-0"/,
  )
  assert.doesNotMatch(quotationList, /<select[\s\S]*?:value="pageSize"/)
  assert.match(quotationList, /rangeStart/)
  assert.match(quotationList, /rangeEnd/)
  assert.match(quotationList, /totalPages/)
  assert.match(quotationList, /requestPage\(page - 1\)/)
  assert.match(quotationList, /requestPage\(page \+ 1\)/)
})

test('search is debounced and filters reset the first page', () => {
  assert.match(quotationList, /window\.setTimeout\(\(\) => \{/)
  assert.match(quotationList, /}, 300\)/)
  assert.match(quotationList, /listQuery\(1\)/)
  assert.match(quotationList, /selectedProductLine/)
  assert.match(quotationList, /selectedSource/)
  assert.match(quotationList, /createdFrom/)
  assert.match(quotationList, /createdTo/)
  assert.doesNotMatch(quotationList, /selectedStatus/)
})

test('empty, loading and failed request states stay inside the list panel', () => {
  assert.match(quotationList, /<tr v-if="loading">/)
  assert.match(quotationList, /emptyResults/)
  assert.match(quotationApp, /triggerToast\(message, 'error'\)/)
  assert.match(quotationListPage, /showToast\(.*'error'\)/s)
  assert.doesNotMatch(quotationListPage, /v-if="loading && !quotations\.length"/)
  assert.doesNotMatch(quotationListPage, /<QuotationList\s+v-else/)
})

test('rows open the details drawer without a separate view-details button', () => {
  assert.match(quotationList, /function openQuoteDetails\(quote: Quotation\)/)
  assert.match(quotationList, /emit\('openDetailDrawer', quote\.id\)/)
  assert.match(quotationList, /tabindex="0"/)
  assert.match(quotationList, /cursor-pointer/)
  assert.doesNotMatch(quotationList, /openImportedQuote/)
  assert.doesNotMatch(quotationList, /data-view-details/)
  assert.doesNotMatch(quotationList, /emit\('viewQuote', quote\.id\)/)
})

test('list column widths reserve stable space for longer headers and actions', () => {
  assert.match(quotationList, /project:\s*\{[\s\S]*?defaultWidth:\s*260/)
  assert.match(quotationList, /customer:\s*\{[\s\S]*?defaultWidth:\s*200/)
  assert.match(quotationList, /contact:\s*\{[\s\S]*?defaultWidth:\s*180/)
  assert.match(quotationList, /salesperson:\s*\{[\s\S]*?defaultWidth:\s*170/)
  assert.match(quotationList, /source:\s*\{[\s\S]*?defaultWidth:\s*170/)
  assert.match(quotationList, /const ACTIONS_COLUMN_WIDTH = 152/)
})

test('older list requests cannot overwrite newer results', () => {
  assert.match(quotationApp, /requestId !== quotationListRequestId/)
  assert.match(quotationListPage, /currentRequest !== requestId/)
})

test('page requests do not wait for remote Feishu link checks', () => {
  const appListLoad = quotationApp.slice(
    quotationApp.indexOf('async function refreshQuotations'),
    quotationApp.indexOf('async function loadActiveQuote'),
  )
  const routedListLoad = quotationListPage.slice(
    quotationListPage.indexOf('async function load('),
    quotationListPage.indexOf('async function handleFeishuUploadDone'),
  )
  assert.doesNotMatch(appListLoad, /reconcileFeishuQuotationLinks/)
  assert.doesNotMatch(routedListLoad, /reconcileFeishuQuotationLinks/)
  assert.match(
    quotationApp,
    /handleReconcileFeishuLinks[\s\S]*?reconcileFeishuQuotationLinks/,
  )
})

test('deleting the last row moves back one page', () => {
  assert.match(quotationApp, /quotations\.value\.length === 1/)
  assert.match(quotationApp, /currentPage - 1/)
  assert.match(quotationListPage, /quotations\.value\.length === 1/)
  assert.match(quotationListPage, /currentPage - 1/)
})

test('detail and edit pages request quotations by ID', () => {
  assert.match(
    quotationDetailPage,
    /getQuotation\(String\(route\.params\.id\)\)/,
  )
  assert.match(quotationCreatePage, /getQuotation\(editId\)/)
  assert.doesNotMatch(quotationDetailPage, /listQuotations/)
  assert.doesNotMatch(quotationCreatePage, /listQuotations/)
})
