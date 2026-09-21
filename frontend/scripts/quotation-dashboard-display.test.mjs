import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { test } from 'node:test'

const salesDashboard = await readFile(
  new URL('../src/modules/quotation/components/sales/SalesDashboard.vue', import.meta.url),
  'utf8',
)
const quotationDashboard = await readFile(
  new URL('../src/modules/quotation/components/Dashboard.vue', import.meta.url),
  'utf8',
)

test('sales dashboard uses month filters and year-specific comparison series', () => {
  assert.match(salesDashboard, /v-model="startDate"[\s\S]*type="month"/)
  assert.match(salesDashboard, /v-model="endDate"[\s\S]*type="month"/)
  assert.match(salesDashboard, /function rowsForYear\(/)
  assert.match(
    salesDashboard,
    /rowsForSelectedMonths\(\s*source\?\.series \|\| \[\],\s*selectedYear\.value,/,
  )
  assert.match(
    salesDashboard,
    /rowsForYear\(comparison\.series, comparison\.year\)/,
  )
  assert.match(salesDashboard, /function rowsForSelectedMonths\(/)
  assert.match(salesDashboard, /return monthLabels\.value/)
  assert.match(salesDashboard, /values\[month - 1\] = 0/)
  assert.match(salesDashboard, /start_date: `\$\{startDate\.value\}-01`/)
  assert.match(salesDashboard, /end_date: monthEndDate\(endDate\.value\)/)
  assert.match(salesDashboard, /@change="showDatePicker = false"/)
  assert.match(salesDashboard, /bindClickOutside\(dateRangeControlRef/)
})

test('quotation dashboard does not truncate monetary KPI values', () => {
  assert.doesNotMatch(
    quotationDashboard,
    /<p class="mt-4 truncate font-mono text-3xl font-bold text-dm-text">/,
  )
})

test('quotation dashboard calculates year-over-year change from both values', () => {
  assert.match(
    quotationDashboard,
    /const current = summary\.value\?\.monthQuoteAmount \|\| 0[\s\S]*const previous = summary\.value\?\.previousYearQuoteAmount \|\| 0[\s\S]*return \(\(current - previous\) \/ previous\) \* 100/,
  )
})

test('sales breakdown cards align content bottoms and use a smaller map', () => {
  assert.match(
    salesDashboard,
    /\.breakdown-card \{[\s\S]*display: flex;[\s\S]*flex-direction: column;/,
  )
  assert.match(salesDashboard, /\.world-map \{[\s\S]*height: 85px;/)
  assert.match(salesDashboard, /\.region-breakdown-content \{[\s\S]*flex: 1;/)
  assert.match(salesDashboard, /\.region-list \{[\s\S]*margin-top: 0;/)
  assert.match(salesDashboard, /\.product-list \{[\s\S]*align-content: space-between;/)
  assert.match(
    salesDashboard,
    /\.product-list \.rank-row \{[\s\S]*grid-template-rows: 20px 12px;/,
  )
  assert.match(
    salesDashboard,
    /\.region-list \.rank-row[\s\S]*grid-template-rows: 20px 12px;/,
  )
  assert.match(salesDashboard, /\.product-list \{[\s\S]*margin-bottom: 20px;/)
  assert.match(
    salesDashboard,
    /\.customer-table-wrap \{[\s\S]*flex: 0 0 auto;[\s\S]*margin-top: 12px;/,
  )
  assert.match(
    salesDashboard,
    /\.view-all-link \{[\s\S]*margin-top: auto;[\s\S]*margin-bottom: 20px;/,
  )
})
