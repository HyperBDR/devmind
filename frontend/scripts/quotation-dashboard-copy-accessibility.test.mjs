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
  assert.equal(copy.monthSummaryTitle, 'Monthly quotes')
  assert.equal(copy.recentOverviewTitle, 'Recently updated quotes')
  assert.match(dashboard, /id="dashboard-month-summary"/)
  assert.match(dashboard, /test-id="dashboard-period"/)
  assert.match(dashboard, /availablePeriodOptions/)
  assert.match(dashboard, /selectedPeriod/)
  assert.match(dashboard, /getDashboardSummary\(period\)/)
  assert.match(dashboard, /getDashboardAnalytics\(currency\)/)
  assert.match(dashboard, /function openSelectedMonthQuotes/)
  assert.match(dashboard, /createdFrom/)
  assert.match(dashboard, /createdTo/)
  assert.match(dashboard, /tab: 'list'/)
  assert.match(dashboard, /openSelectedMonthQuotes/)
  assert.match(dashboard, /summary\?\.monthQuoteCount/)
  assert.match(dashboard, /monthQuoteDeltaLabel/)
  assert.match(dashboard, /previousMonthCount/)
  assert.doesNotMatch(dashboard, /monthSummarySubtitle/)
  assert.doesNotMatch(dashboard, /previousMonthAmount/)
  assert.doesNotMatch(dashboard, /monthSummaryFormula/)
  assert.doesNotMatch(dashboard, /monthQuoteAmountLabel/)
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
  assert.match(dashboard, /EURO/)
  assert.match(dashboard, /new Set/)
  assert.match(
    dashboard,
    /\['USD', 'CNY', 'EUR', 'GBP', 'MYR', 'HKD'\]/
  )
  assert.match(dashboard, /currencyShortLabel/)
  assert.match(dashboard, /currencyOptionLabel/)
  assert.match(dashboard, /CURRENCY_ORDER\.map/)
  assert.match(dashboard, /class-name="w-\[4\.5rem\] shrink-0"/)
  assert.match(dashboard, /compact/)
  assert.match(dashboard, /'RM'/)
  assert.doesNotMatch(dashboard, /currencyUsd/)
  assert.doesNotMatch(dashboard, /currencyGbp/)
  assert.equal(english.quotation.common.currencyGbp, '£')
  assert.match(dashboard, /let analyticsRequestId = 0/)
  assert.match(dashboard, /requestId !== analyticsRequestId/)
  assert.match(dashboard, /analytics\.value = null/)
  assert.match(
    dashboard,
    /normalizeDashboardCurrency\(data\.currency\)/
  )
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
