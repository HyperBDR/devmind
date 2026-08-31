import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const app = readFileSync(
  new URL('../src/modules/quotation/App.vue', import.meta.url),
  'utf8',
)
const create = readFileSync(
  new URL(
    '../src/modules/quotation/components/QuotationCreate.vue',
    import.meta.url,
  ),
  'utf8',
)
const api = readFileSync(
  new URL('../src/modules/quotation/api/quotations.ts', import.meta.url),
  'utf8',
)
const numbering = readFileSync(
  new URL(
    '../src/modules/quotation/utils/quotationNumbering.ts',
    import.meta.url,
  ),
  'utf8',
)

test('formal revision numbering is delegated to the backend', () => {
  assert.doesNotMatch(app, /skipVersion/)
  assert.doesNotMatch(app, /usesQuoteRevisions/)
  assert.doesNotMatch(create, /getNextRevisionQuoteNumber/)
  assert.doesNotMatch(numbering, /getNextRevisionQuoteNumber/)
  assert.doesNotMatch(api, /skip_version/)
  assert.match(create, /editingQuoteIsFormal/)
  assert.match(app, /activeQuote\.value = saved/)
})
