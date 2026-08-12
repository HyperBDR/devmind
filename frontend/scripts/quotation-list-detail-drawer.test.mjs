import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const list = await readFile(
  new URL(
    '../src/modules/quotation/components/QuotationList.vue',
    import.meta.url
  ),
  'utf8'
)
const drawer = await readFile(
  new URL(
    '../src/modules/quotation/components/QuotationDetailsDrawer.vue',
    import.meta.url
  ),
  'utf8'
)
const details = await readFile(
  new URL(
    '../src/modules/quotation/components/QuotationDetails.vue',
    import.meta.url
  ),
  'utf8'
)
const app = await readFile(
  new URL('../src/modules/quotation/App.vue', import.meta.url),
  'utf8'
)
const page = await readFile(
  new URL(
    '../src/modules/quotation/pages/QuotationListPage.vue',
    import.meta.url
  ),
  'utf8'
)
const api = await readFile(
  new URL('../src/modules/quotation/api/quotations.ts', import.meta.url),
  'utf8'
)
const enLocale = await readFile(
  new URL('../src/modules/quotation/locales/en.json', import.meta.url),
  'utf8'
)

test('quotation rows open the detail drawer without routing', () => {
  assert.match(list, /openDetailDrawer: \[id: string\]/)
  assert.match(list, /emit\('openDetailDrawer', quote\.id\)/)
  assert.match(list, /@click="handleRowClick\(quote, \$event\)"/)
  assert.match(list, /event\.currentTarget\.focus\(\)/)
  assert.match(list, /@keydown\.enter="handleRowKeydown/)
  assert.match(list, /@keydown\.space="handleRowKeydown/)
  assert.doesNotMatch(list, /data-view-details/)
  assert.match(app, /@open-detail-drawer="handleOpenDetailDrawer"/)
  assert.match(app, /:quote-id="drawerQuoteId"/)
})

test('nested actions cannot trigger the row drawer', () => {
  assert.match(list, /function isNestedRowAction/)
  for (const selector of ['button', 'a', 'input', 'select', 'textarea']) {
    assert.match(list, new RegExp(selector))
  }
  assert.match(list, /if \(isNestedRowAction\(event\.target\)\) return/)
})

test('drawer loads full details and supports accessible close paths', () => {
  assert.match(drawer, /getQuotation\(quoteId\)/)
  assert.match(drawer, /requestId === detailRequestId/)
  assert.match(drawer, /<Dialog/)
  assert.match(drawer, /:initial-focus="closeButton"/)
  assert.match(drawer, /returnFocusElement = document\.activeElement/)
  assert.match(drawer, /returnFocusTimer = window\.setTimeout/)
  assert.match(drawer, /returnFocusElement\.focus\(\{ preventScroll: true \}\)/)
  assert.match(drawer, /@close="close"/)
  assert.match(drawer, /role="status"/)
  assert.match(drawer, /role="alert"/)
  assert.match(drawer, /@click="loadQuote"/)
  assert.match(drawer, /overflow-y-auto/)
  assert.match(drawer, /data-quotation-drawer-scroll/)
  assert.match(drawer, /scrollbar-width: none/)
  assert.match(details, /embedded\?: boolean/)
  assert.match(details, /v-if="!embedded"/)
  assert.match(details, /data-embedded-quotation-preview/)
  assert.match(details, /data-quotation-details-sidebar/)
  assert.match(details, /v-if="!embedded"[\s\S]*?data-quotation-details-sidebar/)
  assert.doesNotMatch(
    details,
    /data-embedded-quotation-preview[\s\S]{0,220}overflow-y-auto/
  )
})

test('quotation columns expose pointer and keyboard resize controls', () => {
  assert.match(list, /<colgroup>/)
  assert.match(list, /data-column-resizer/)
  assert.match(list, /data-column-header="column\.key"/)
  assert.match(list, /role="separator"/)
  assert.match(list, /startColumnResize\(column\.key, \$event\)/)
  assert.match(list, /@pointermove\.stop\.prevent="handleColumnResize"/)
  assert.match(list, /resizeColumnBy\(column\.key, -COLUMN_RESIZE_STEP\)/)
  assert.match(list, /resizeColumnBy\(column\.key, COLUMN_RESIZE_STEP\)/)
  assert.match(list, /visibleTableWidth/)
  assert.match(list, /:style="tableUsesHorizontalScroll/)
  assert.match(list, /data-quotation-table-scroller/)
  assert.match(list, /tableUsesHorizontalScroll \? 'overflow-x-auto' : 'overflow-hidden'/)
  assert.doesNotMatch(list, /data-quotation-top-scrollbar/)
})

test('total, source and quote date use the requested order', () => {
  const totalColumn = list.indexOf(
    "labelKey: 'quotation.pages.list.tableTotal'"
  )
  const sourceColumn = list.indexOf(
    "labelKey: 'quotation.pages.list.tableSource'"
  )
  const dateColumn = list.indexOf(
    "labelKey: 'quotation.pages.list.tableQuoteDate'"
  )
  assert.ok(totalColumn >= 0)
  assert.ok(sourceColumn > totalColumn)
  assert.ok(dateColumn > sourceColumn)
  assert.match(api, /quote_date\?: string \| null/)
  assert.match(api, /quoteDate: api\.quote_date \|\| undefined/)
})

test('page-size menu is outside the clipped table wrapper', () => {
  const tableWrapperEnd = list.indexOf(
    '<div\n        class="flex flex-col gap-2 border-t'
  )
  assert.ok(tableWrapperEnd >= 0)
  const clippedWrapper = list.slice(
    list.indexOf('<div class="flex flex-1 overflow-hidden rounded-t-xl">'),
    tableWrapperEnd
  )
  assert.doesNotMatch(clippedWrapper, /test-id="quotation-page-size"/)
  assert.match(
    list,
    /panel-class-name="!bottom-full !top-auto !mb-1 !mt-0"/
  )
})

test('long contact names cannot expand compact quotation rows', () => {
  assert.match(
    list,
    /class="truncate whitespace-nowrap px-3 py-1 text-dm-text-secondary/
  )
  assert.match(list, /class="min-w-0"[\s\S]*?quote\.projectName/)
  assert.match(list, /class="min-w-0"[\s\S]*?quote\.clientCompany/)
})

test('quotation list removes the user hint and page-level horizontal scroll', () => {
  assert.doesNotMatch(list, /quotation\.pages\.list\.userHint/)
  assert.match(list, /xl:grid-cols-\[minmax\(0,1\.35fr\)_repeat\(3,minmax\(0,\.7fr\)\)_minmax\(0,1\.4fr\)\]/)
  assert.match(app, /overflow-x-hidden overflow-y-auto/)
  assert.match(app, /v-if="currentTab === 'list'"\s+class="flex flex-col"/)
})

test('ten-row quotation pages fill the available viewport height', () => {
  assert.match(
    list,
    /class="flex h-full min-h-\[calc\(100dvh-7\.0625rem\)\] flex-col gap-3"/
  )
  assert.match(list, /class="flex flex-1 flex-col rounded-xl/)
  assert.match(
    list,
    /'h-full': pageSize === 10 && quotations\.length === 10/
  )
  assert.match(page, /<div class="h-full">/)
  assert.match(page, /class="flex h-full flex-col gap-5"/)
  assert.match(page, /<QuotationList[\s\S]*?class="flex-1"/)
})

test('English quotation labels use concise CRM terminology', () => {
  for (const copy of [
    '"tableQuoteNo": "Quote number"',
    '"tableSalesperson": "Sales owner"',
    '"tableQuoteDate": "Quote date"',
    '"sourceDocumentImport": "Imported from Feishu"',
    '"feishuSync": "Sync from Feishu"',
    '"drawerTitle": "Quote details"',
  ]) {
    assert.match(enLocale, new RegExp(copy))
  }
  assert.doesNotMatch(enLocale, /"tableSalesperson": "Sales rep"/)
  assert.doesNotMatch(enLocale, /"tableQuoteDate": "Date created"/)
})
