import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import assert from 'node:assert/strict'

const dashboard = readFileSync(
  new URL('../src/modules/quotation/components/Dashboard.vue', import.meta.url),
  'utf8'
)
const catalog = readFileSync(
  new URL(
    '../src/modules/quotation/components/ProductServiceManager.vue',
    import.meta.url
  ),
  'utf8'
)
const english = JSON.parse(
  readFileSync(
    new URL('../src/modules/quotation/locales/en.json', import.meta.url),
    'utf8'
  )
)

test('dashboard uses quotation-only overview copy and stable recent fields', () => {
  const copy = english.quotation.pages.dashboard
  assert.equal(copy.overviewTitle, 'Quote overview')
  assert.equal(copy.monthSummaryTitle, 'Quotes this month')
  assert.equal(copy.recentOverviewTitle, 'Recently updated quotes')
  assert.match(dashboard, /id="dashboard-month-summary"/)
  assert.match(dashboard, /summary\?\.monthQuoteCount/)
  assert.match(dashboard, /summary\.value\?\.monthQuoteAmount/)
  assert.doesNotMatch(dashboard, /monthSummarySubtitle/)
  assert.doesNotMatch(dashboard, /previousMonthCount/)
  assert.doesNotMatch(dashboard, /previousMonthAmount/)
  assert.doesNotMatch(dashboard, /monthSummaryFormula/)
  assert.match(dashboard, /quote\.updatedAt/)
  assert.match(dashboard, /id="dashboard-recent-overview"/)
  assert.doesNotMatch(dashboard, /id="kpi-card-/)
  assert.doesNotMatch(dashboard, /successRate/)
  assert.doesNotMatch(dashboard, /expiringSoonCount/)
})

test('dashboard currency selector deduplicates aliases and formats symbols', () => {
  assert.match(dashboard, /<FormSelect/)
  assert.match(dashboard, /test-id="dashboard-currency"/)
  assert.doesNotMatch(dashboard, /<select\s+id="dashboard-currency"/)
  assert.match(dashboard, /currency === 'RMB' \? 'CNY' : currency/)
  assert.match(dashboard, /new Set/)
  assert.match(dashboard, /\['USD', 'CNY', 'EUR', 'HKD', 'MYR'\]/)
  assert.match(dashboard, /if \(currency === 'HKD'\) return 'HK\$'/)
  assert.match(dashboard, /if \(currency === 'MYR'\) return 'RM'/)
})

test('catalog delete icons expose item-specific names and tooltips', () => {
  assert.match(
    catalog,
    /:aria-label="t\('quotation\.pages\.catalog\.deleteProduct'/
  )
  assert.match(
    catalog,
    /:aria-label="t\('quotation\.pages\.catalog\.deleteService'/
  )
  assert.match(
    catalog,
    /:aria-label="t\('quotation\.pages\.catalog\.deleteDiscount'/
  )
  assert.match(catalog, /:title="t\('quotation\.pages\.catalog\.deleteProduct'/)
  assert.match(catalog, /:title="t\('quotation\.pages\.catalog\.deleteService'/)
  assert.match(
    catalog,
    /:title="t\('quotation\.pages\.catalog\.deleteDiscount'/
  )
})
