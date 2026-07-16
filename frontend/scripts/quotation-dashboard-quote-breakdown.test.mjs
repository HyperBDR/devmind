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
  assert.match(dashboardSource, /quotePieLeaderLinePlugin/)
  assert.match(dashboardSource, /quoteNo/)
  assert.match(dashboardSource, /label: `\$\{quote\.quoteNo\} · \$\{amountLabel\}`/)
  assert.match(dashboardSource, /labels: quoteBreakdownData\.value\.map\(\(row\) => row\.label\)/)
  assert.match(dashboardSource, /:plugins="\[quotePieLeaderLinePlugin\]"/)
  assert.doesNotMatch(dashboardSource, /setChartMode/)
  assert.doesNotMatch(dashboardSource, /chartAmountToggleProductLine/)
  assert.doesNotMatch(dashboardSource, /chartAmountToggleStatus/)

  assert.match(enLocale, /"chartAmountTitle": "Quote Breakdown"/)
  assert.match(
    enLocale,
    /"chartAmountSubtitle": "Each slice represents one quote\. Labels show the quote number and total value\."/,
  )
  assert.doesNotMatch(enLocale, /Leader lines show quote no\. and total/)
})

test('dashboard chart cards use the approved balanced desktop proportions', () => {
  assert.match(dashboardSource, /xl:grid-cols-\[minmax\(0,1\.18fr\)_minmax\(480px,0\.82fr\)\]/)
  assert.match(dashboardSource, /id="chart-quote-amount" class="dm-card flex h-full flex-col p-5"/)
  assert.doesNotMatch(dashboardSource, /chartAmountSummaryLabel/)
  assert.doesNotMatch(dashboardSource, /quoteBreakdownSummaryRows/)
  assert.match(dashboardSource, /class="relative flex h-64 flex-1 items-center justify-center/)
  assert.match(dashboardSource, /id="dashboard-recent-grid"[^>]*xl:grid-cols-\[minmax\(0,1\.18fr\)_minmax\(480px,0\.82fr\)\]/)
  assert.match(dashboardSource, /class="dm-card flex h-full flex-col justify-between p-5"/)
  assert.doesNotMatch(enLocale, /chartAmountSummaryLabel/)
  assert.doesNotMatch(enLocale, /chartAmountQuoteCount/)
})

test('dashboard pie leader lines keep a readable horizontal length', () => {
  assert.match(dashboardSource, /const minLeaderLineLength =/)
  assert.match(dashboardSource, /const preferredEndX =/)
  assert.match(dashboardSource, /startX \+ minLeaderLineLength/)
  assert.match(dashboardSource, /startX - minLeaderLineLength/)
  assert.doesNotMatch(dashboardSource, /chart\.width \* 0\.32/)
})
