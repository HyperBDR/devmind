import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import assert from 'node:assert/strict'

const dashboard = readFileSync(
  new URL('../src/modules/quotation/components/Dashboard.vue', import.meta.url),
  'utf8',
)
const catalog = readFileSync(
  new URL('../src/modules/quotation/components/ProductServiceManager.vue', import.meta.url),
  'utf8',
)
const english = JSON.parse(
  readFileSync(new URL('../src/modules/quotation/locales/en.json', import.meta.url), 'utf8'),
)

test('dashboard explains the win-rate denominator and labels both quote counts', () => {
  const copy = english.quotation.pages.dashboard
  assert.equal(copy.kpiSuccessRateHint, 'Won out of won and open quotes')
  assert.equal(copy.kpiActiveDraftsLabel, 'Open quotes and drafts')
  assert.equal(copy.kpiActiveDraftsValue, '{open} open · {drafts} drafts')
  assert.match(dashboard, /kpiActiveDraftsValue/)
  assert.doesNotMatch(dashboard, /\{\{ activeCount \}\} \/ \{\{ draftCount \}\}/)
})

test('catalog delete icons expose item-specific names and tooltips', () => {
  assert.match(catalog, /:aria-label="t\('quotation\.pages\.catalog\.deleteProduct'/)
  assert.match(catalog, /:aria-label="t\('quotation\.pages\.catalog\.deleteService'/)
  assert.match(catalog, /:aria-label="t\('quotation\.pages\.catalog\.deleteDiscount'/)
  assert.match(catalog, /:title="t\('quotation\.pages\.catalog\.deleteProduct'/)
  assert.match(catalog, /:title="t\('quotation\.pages\.catalog\.deleteService'/)
  assert.match(catalog, /:title="t\('quotation\.pages\.catalog\.deleteDiscount'/)
})
