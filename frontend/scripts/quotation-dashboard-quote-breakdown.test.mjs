import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import assert from 'node:assert/strict'

const dashboardSource = readFileSync(
  new URL('../src/modules/quotation/components/Dashboard.vue', import.meta.url),
  'utf8',
)
const enLocale = readFileSync(
  new URL('../src/modules/quotation/locales/en.json', import.meta.url),
  'utf8',
)

test('dashboard pie chart shows quote-level breakdown with native English copy', () => {
  assert.match(dashboardSource, /quoteBreakdownData/)
  assert.match(dashboardSource, /quoteBreakdownChartRows/)
  assert.match(dashboardSource, /quoteNo/)
  assert.match(dashboardSource, /label: `\$\{quote\.quoteNo\} · \$\{amountLabel\}`/)
  assert.match(dashboardSource, /labels: quoteBreakdownChartRows\.value\.map\(\(row\) => row\.label\)/)
  assert.match(dashboardSource, /<Pie/)
  assert.doesNotMatch(dashboardSource, /cutout:/)
  assert.match(dashboardSource, /quotePieLeaderLabelPlugin/)
  assert.doesNotMatch(dashboardSource, /setChartMode/)
  assert.doesNotMatch(dashboardSource, /chartAmountToggleProductLine/)
  assert.doesNotMatch(dashboardSource, /chartAmountToggleStatus/)

  assert.match(enLocale, /"chartAmountTitle": "Quote Breakdown"/)
  assert.match(
    enLocale,
    /"chartAmountSubtitle": "Slices reflect each quote amount; small-value quotes are hidden\."/,
  )
  assert.doesNotMatch(enLocale, /chartAmountMixedCurrency/)
  assert.doesNotMatch(enLocale, /chartAmountTotalLabel/)
  assert.doesNotMatch(enLocale, /ranked list shows value and share/)
  assert.doesNotMatch(enLocale, /Leader lines show quote no\. and total/)
})

test('dashboard chart cards use laptop-safe balanced desktop proportions', () => {
  assert.match(dashboardSource, /2xl:grid-cols-\[minmax\(0,1\.18fr\)_minmax\(480px,0\.82fr\)\]/)
  assert.match(dashboardSource, /id="chart-quote-amount" class="dm-card flex h-full flex-col p-5"/)
  assert.doesNotMatch(dashboardSource, /chartAmountSummaryLabel/)
  assert.doesNotMatch(dashboardSource, /quoteBreakdownSummaryRows/)
  assert.match(dashboardSource, /class="relative flex min-h-\[16rem\] flex-1 items-center justify-center/)
  assert.match(dashboardSource, /id="dashboard-recent-grid"[^>]*2xl:grid-cols-\[minmax\(0,1\.18fr\)_minmax\(480px,0\.82fr\)\]/)
  assert.match(dashboardSource, /class="dm-card flex h-full flex-col justify-between p-5"/)
  assert.doesNotMatch(enLocale, /chartAmountSummaryLabel/)
  assert.doesNotMatch(enLocale, /chartAmountQuoteCount/)
})

test('dashboard quote breakdown uses one centered filtered pie', () => {
  assert.match(dashboardSource, /QUOTE_BREAKDOWN_MIN_SHARE = 2/)
  assert.match(dashboardSource, /QUOTE_BREAKDOWN_MAX_SLICES = 8/)
  assert.match(dashboardSource, /row\.share >= QUOTE_BREAKDOWN_MIN_SHARE/)
  assert.match(
    dashboardSource,
    /const quoteBreakdownData = computed\(\(\) =>\s*props\.quotations/,
  )
  assert.doesNotMatch(dashboardSource, /const chartQuotes/)
  assert.doesNotMatch(dashboardSource, /selectedBreakdownCurrency/)
  assert.doesNotMatch(dashboardSource, /quoteBreakdownCurrencies/)
  assert.doesNotMatch(dashboardSource, /v-for="currency in quoteBreakdownCurrencies"/)
  assert.doesNotMatch(dashboardSource, /chartAmountCurrencyToggleAria/)
  assert.match(dashboardSource, /id="quote-breakdown-layout"/)
  assert.match(dashboardSource, /class="flex w-full min-w-0 items-center justify-center"/)
  assert.match(dashboardSource, /min-h-\[16rem\]/)
  assert.match(dashboardSource, /min-h-\[320px\] w-full/)
  assert.match(dashboardSource, /relative h-80/)
  assert.match(dashboardSource, /w-\[min\(100%,700px\)\]/)
  assert.match(dashboardSource, /radius: '92%'/)
  assert.doesNotMatch(dashboardSource, /quote-breakdown-scroll/)
  assert.doesNotMatch(dashboardSource, /v-for="row in quoteBreakdownRows"/)
  assert.doesNotMatch(dashboardSource, /quoteBreakdownSingleCurrency/)
  assert.doesNotMatch(dashboardSource, /hasMixedQuoteBreakdownCurrencies/)
  assert.doesNotMatch(dashboardSource, /chartAmountMixedCurrencyLabel/)
  assert.doesNotMatch(dashboardSource, /chartAmountMixedCurrencyValue/)
  assert.doesNotMatch(dashboardSource, /formatCompactChartAmount/)
  assert.doesNotMatch(
    dashboardSource,
    /absolute inset-0 flex flex-col items-center justify-center text-center/,
  )
  assert.doesNotMatch(dashboardSource, /chartAmountRankingTitle/)
  assert.doesNotMatch(dashboardSource, /chartAmountTotalLabel/)
  assert.doesNotMatch(dashboardSource, /quoteBreakdownRemainingCount/)
  assert.doesNotMatch(dashboardSource, /chartAmountMoreQuotes/)
  assert.doesNotMatch(dashboardSource, /\.slice\(0, QUOTE_BREAKDOWN_RANK_LIMIT\)/)
})

test('dashboard pie labels use balanced reference-style leader lines', () => {
  assert.match(dashboardSource, /arrangePieLineLabels/)
  assert.match(dashboardSource, /entries\.filter\(\(entry\) => entry\.side === -1\)/)
  assert.match(dashboardSource, /entries\.filter\(\(entry\) => entry\.side === 1\)/)
  assert.match(dashboardSource, /quoteBreakdownRotation/)
  assert.match(dashboardSource, /rotation: quoteBreakdownRotation\.value/)
  assert.doesNotMatch(dashboardSource, /ctx\.lineTo\(bendX, entry\.anchorY\)/)
  assert.match(dashboardSource, /ctx\.lineTo\(bendX, entry\.labelY\)/)
  assert.match(dashboardSource, /lineEndX = bendX \+ entry\.side \* 44/)
  assert.match(dashboardSource, /ctx\.lineTo\(lineEndX, entry\.labelY\)/)
  assert.match(dashboardSource, /ctx\.strokeStyle = row\.color/)
  assert.match(dashboardSource, /600 12px ui-monospace/)
  assert.match(dashboardSource, /11px ui-sans-serif/)
  assert.doesNotMatch(dashboardSource, /ctx\.arc\(entry\.anchorX/)
  assert.match(dashboardSource, /ctx\.fillText\(\s*row\.amountLabel,/)
  assert.doesNotMatch(dashboardSource, /formatShare/)
  assert.doesNotMatch(dashboardSource, /chartAmountPieTooltip/)
  assert.match(dashboardSource, /:plugins="\[quotePieLeaderLabelPlugin\]"/)
})

test('dashboard recent quotes use a responsive, low-noise hierarchy', () => {
  assert.match(dashboardSource, /id="dashboard-recent-quotes"/)
  assert.match(
    dashboardSource,
    /sm:grid-cols-\[minmax\(0,1fr\)_auto\]/,
  )
  assert.match(dashboardSource, /formatRecentQuoteTime/)
  assert.match(dashboardSource, /flex min-w-0 flex-wrap items-center/)
  assert.match(dashboardSource, /bg-blue-50 px-2 py-1 font-mono text-xs/)
  assert.doesNotMatch(dashboardSource, /quote\.createdAt\.substring\(5, 16\)/)
  assert.doesNotMatch(dashboardSource, /quotation\.common\.separator/)
  assert.match(
    dashboardSource,
    /class="flex justify-center"[\s\S]*<StatusBadge :status="quote\.status" \/>/,
  )
})
