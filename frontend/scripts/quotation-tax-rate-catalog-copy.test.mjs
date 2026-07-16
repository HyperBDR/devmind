import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import assert from 'node:assert/strict'

const createQuote = readFileSync(
  new URL('../src/modules/quotation/components/QuotationCreate.vue', import.meta.url),
  'utf8',
)
const english = JSON.parse(
  readFileSync(new URL('../src/modules/quotation/locales/en.json', import.meta.url), 'utf8'),
)

test('tax rate input accepts only a decimal percentage from 0 to 100', () => {
  assert.match(createQuote, /@input="handleVatRateInput"/)
  assert.match(createQuote, /inputmode="decimal"/)
  assert.match(createQuote, /function sanitizeVatRateInput/)
  assert.match(createQuote, /Math\.min\(100,/)
})

test('catalog uses concise table headings for English users', () => {
  const copy = english.quotation.pages.catalog
  assert.equal(copy.tableProductName, 'Product')
  assert.equal(copy.tableListPrice, 'Price')
  assert.equal(copy.tableServiceName, 'Description')
  assert.equal(copy.tableRefPrice, 'Price')
})
