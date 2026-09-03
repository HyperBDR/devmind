import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import assert from 'node:assert/strict'

const preview = readFileSync(
  new URL('../src/modules/quotation/components/QuotationPreview.vue', import.meta.url),
  'utf8',
)
const createPage = readFileSync(
  new URL(
    '../src/modules/quotation/components/QuotationCreate.vue',
    import.meta.url,
  ),
  'utf8',
)
const enLocale = readFileSync(
  new URL('../src/modules/quotation/locales/en.json', import.meta.url),
  'utf8',
)
const zhLocale = readFileSync(
  new URL('../src/modules/quotation/locales/zh-CN.json', import.meta.url),
  'utf8',
)
const historyInput = readFileSync(
  new URL('../src/modules/quotation/components/HistoryTextInput.vue', import.meta.url),
  'utf8',
)

test('quotation preview lets long English table headings wrap inside fixed columns', () => {
  assert.match(preview, /const headerCellClass =\s*\n\s*'whitespace-normal break-normal/)
  assert.doesNotMatch(preview, /const headerCellClass =\s*\n\s*'whitespace-nowrap/)
  assert.match(preview, /class="whitespace-normal break-normal border border-slate-300 px-1\.5 py-1 align-middle">\s*Contact Person/)
  assert.match(preview, /class="whitespace-normal break-normal border border-slate-300 px-1\.5 py-1 align-middle">\s*Payment Terms/)
  assert.match(preview, /props\.scale === 'compact' \? 'text-\[9px\]' : 'text-\[11px\]'/)
})

test('quotation line items respond to the available form pane width', () => {
  assert.match(createPage, /container: quotation-line-items \/ inline-size/)
  assert.match(createPage, /@container quotation-line-items \(min-width: 400px\)/)
  assert.match(createPage, /@container quotation-line-items \(min-width: 560px\)/)
  assert.match(createPage, /quotation-line-item-description/)
  assert.doesNotMatch(createPage, /2xl:grid-cols-5/)
})

test('email placeholders escape vue-i18n linked-message syntax', () => {
  for (const locale of [enLocale, zhLocale]) {
    assert.match(locale, /"customerEmailPlaceholder": "client\{'@'\}company\.com"/)
    assert.doesNotMatch(locale, /"customerEmailPlaceholder": "client@company\.com"/)
  }
})

test('history controls expose a localized accessible name', () => {
  assert.match(historyInput, /:aria-label="t\('quotation\.common\.showHistory'\)"/)
  assert.doesNotMatch(historyInput, /aria-label="展开历史记录"/)
  assert.match(enLocale, /"showHistory": "Show history"/)
  assert.match(zhLocale, /"showHistory": "展开历史记录"/)
})
