import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const dashboard = fs.readFileSync(
  new URL(
    '../src/modules/quotation/components/sales/SalesDashboard.vue',
    import.meta.url,
  ),
  'utf8',
)
const salesPage = fs.readFileSync(
  new URL('../src/pages/QuotationSales.vue', import.meta.url),
  'utf8',
)
const sidebar = fs.readFileSync(
  new URL('../src/components/layout/AppSidebar.vue', import.meta.url),
  'utf8',
)
const en = JSON.parse(fs.readFileSync(
  new URL('../src/modules/quotation/locales/en.json', import.meta.url),
  'utf8',
))
const zh = JSON.parse(fs.readFileSync(
  new URL('../src/modules/quotation/locales/zh-CN.json', import.meta.url),
  'utf8',
))

test('Sales dashboard exposes the executive overview layout', () => {
  for (const marker of [
    'data-sales-dashboard',
    'data-sales-kpis',
    'data-sales-trend',
    'data-sales-period-comparison',
    'data-sales-region',
    'data-sales-product',
    'data-sales-customers',
    'quotation.sales.totalSales',
    'quotation.sales.yearOverYear',
  ]) {
    assert.match(dashboard, new RegExp(marker))
  }
})

test('Sales dashboard keeps the primary controls actionable', () => {
  assert.match(dashboard, /@click="setGranularity/)
  assert.match(dashboard, /v-model="currency"/)
  assert.match(dashboard, /v-model="startDate"/)
  assert.match(dashboard, /v-model="endDate"/)
  assert.match(dashboard, /@update:model-value="setComparisonYears"/)
  assert.match(dashboard, /@update:model-value="setComparisonGranularity"/)
  assert.match(dashboard, /start_date: `\$\{startDate\.value\}-01`/)
  assert.match(dashboard, /end_date: monthEndDate\(endDate\.value\)/)
  assert.match(dashboard, /comparison_years: comparisonYears\.value/)
  assert.match(dashboard, /<Line/)
  assert.match(dashboard, /<Bar/)
  assert.doesNotMatch(dashboard, />\s*Apply\s*</)
  assert.match(dashboard, /watch\(/)
  assert.match(dashboard, /available_currencies/)
  assert.match(dashboard, /quarter_to_date_amount/)
  assert.match(dashboard, /year_to_date_amount/)
  assert.match(dashboard, /period_amount/)
  assert.match(dashboard, /year_over_year/)
})

test('Sales dashboard keeps the existing application navigation', () => {
  assert.match(dashboard, /class="sales-analytics-shell"/)
  assert.doesNotMatch(dashboard, /class="sales-sidebar"/)
  assert.doesNotMatch(dashboard, /Sales Analytics/)
  assert.doesNotMatch(salesPage, /:show-header="!isDashboard"/)
  assert.doesNotMatch(salesPage, /:show-sidebar="!isDashboard"/)
  assert.match(dashboard, /class="dashboard-kpi-grid"/)
  assert.match(dashboard, /class="dashboard-chart-grid"/)
  assert.match(dashboard, /class="dashboard-breakdown-grid"/)
  assert.doesNotMatch(dashboard, /<svg/)
})

test('Sales dashboard exposes real customer regions and customer navigation', () => {
  assert.match(dashboard, /row\.region/)
  assert.match(dashboard, /['"]\/quotation\/customers['"]/)
})

test('Quotation secondary navigation uses concise labels', () => {
  assert.match(sidebar, /t\('quotation\.list'\)/)
  assert.match(sidebar, /t\('quotation\.create'\)/)
  assert.match(
    fs.readFileSync(
      new URL('../src/locales/zh-CN.json', import.meta.url),
      'utf8',
    ),
    /"list": "报价",[\s\S]*"create": "新建报价"/,
  )
  assert.doesNotMatch(
    JSON.stringify(zh),
    /在线创建报价单|报价查询中心/,
  )
})

test('Sales product labels clip without an ellipsis', () => {
  assert.match(dashboard, /product-rank-name/)
  assert.match(dashboard, /productDisplayName\(row\.name\)/)
  assert.match(dashboard, /maxCharacters = 28/)
  assert.match(dashboard, /\.product-rank-name[\s\S]*text-overflow:\s*clip/)
  assert.match(
    dashboard,
    /\.product-list \.rank-row[\s\S]*grid-template-columns:\s*minmax\(0,/,
  )
})

test('Sales breakdown period controls are functional selects', () => {
  assert.match(dashboard, /setBreakdownYear\('region', \$event\)/)
  assert.match(dashboard, /setBreakdownYear\('product', \$event\)/)
  assert.match(dashboard, /setBreakdownYear\('customer', \$event\)/)
  assert.match(dashboard, /loadBreakdown/)
  assert.doesNotMatch(dashboard, /static-select/)
})

test('Sales breakdown cards keep independent full-year ranges', () => {
  assert.match(dashboard, /end_date: `\$\{year\}-12-31`/)
  assert.doesNotMatch(dashboard, /regionYear\.value = selectedYear\.value/)
  assert.doesNotMatch(dashboard, /productYear\.value = selectedYear\.value/)
  assert.doesNotMatch(dashboard, /customerYear\.value = selectedYear\.value/)
})

test('Sales dropdowns reuse the Quote Desk form select', () => {
  assert.match(dashboard, /import FormSelect/)
  assert.match(dashboard, /<FormSelect/g)
  assert.doesNotMatch(dashboard, /<select/)
})

test('Sales dashboard follows the workspace language', () => {
  assert.match(dashboard, /useQuotationI18n/)
  assert.match(dashboard, /t\('quotation\.sales\./)
  for (const key of [
    'dashboardTitle',
    'dashboardSubtitle',
    'totalSales',
    'salesTrend',
    'periodComparison',
    'byRegion',
    'byProduct',
    'topCustomers',
    'annualSales',
    'invoiceValue',
    'shareOfTotal',
  ]) {
    assert.equal(typeof en.quotation.sales[key], 'string')
    assert.equal(typeof zh.quotation.sales[key], 'string')
  }
  assert.doesNotMatch(dashboard, />Sales Dashboard</)
  assert.doesNotMatch(dashboard, />Sales Trend</)
})

test('Yearly trend connects totals across the parsed invoice years', () => {
  assert.match(dashboard, /yearlyTrendData/)
  assert.match(dashboard, /filter\(\(point\) => point\.hasData\)/)
  assert.match(dashboard, /labels: yearlyTrendData\.value\.labels/)
  assert.match(dashboard, /data: yearlyTrendData\.value\.values/)
})

test('Historical comparisons use full years', () => {
  assert.match(
    dashboard,
    /data: valuesFor\(rows, granularity\.value\),/,
  )
  assert.match(
    dashboard,
    /value: sumRows\(rowsForYear\(comparison\.series, comparison\.year\)\)/,
  )
  assert.match(
    dashboard,
    /data: valuesFor\(\s*rowsForYear\(comparison\.series, comparison\.year\),\s*granularity\.value,\s*true,/,
  )
  assert.match(
    dashboard,
    /data: valuesFor\(\s*rowsForYear\(comparison\.series, comparison\.year\),\s*comparisonGranularity\.value,\s*true,/,
  )
  assert.match(dashboard, /if \(!startDate\.value \|\| !endDate\.value\)/)
  assert.match(dashboard, /if \(!value\) return '—'/)
})

test('Total comparison uses the exact historical date range', () => {
  assert.match(
    dashboard,
    /Number\(data\.value\?\.comparison\[0\]\?\.period_amount \|\| 0\)/,
  )
})

test('Sales KPI values share one aligned single-line title row', () => {
  assert.doesNotMatch(dashboard, /class="kpi-detail"/)
  assert.doesNotMatch(dashboard, /\bdetail:/)
  assert.match(
    dashboard,
    /\.kpi-label\s*\{[\s\S]*?white-space:\s*nowrap;/,
  )
})

test('Invoice dashboard uses invoice terminology and readable small text', () => {
  assert.equal(en.quotation.sales.dashboardTitle, 'Invoice overview')
  assert.equal(en.quotation.sales.salesTrend, 'Invoice value trend')
  assert.equal(en.quotation.sales.periodComparison, 'Invoice value by period')
  assert.equal(zh.quotation.sales.dashboardTitle, '发票看板')
  assert.equal(zh.quotation.sales.salesTrend, '发票金额趋势')
  assert.equal(en.quotation.sales.yearToDateOption, '{year}')
  assert.equal(zh.quotation.sales.yearToDateOption, '{year}')
  assert.match(dashboard, /\.kpi-label\s*\{[\s\S]*?font-size:\s*13px;/)
  assert.match(dashboard, /\.customer-table\s*\{[\s\S]*?font-size:\s*12px;/)
  assert.match(
    dashboard,
    /\.date-range-button span\s*\{[^}]*white-space:\s*nowrap;/,
  )
})

test('Customer invoice values have enough room and stay left aligned', () => {
  assert.match(
    dashboard,
    /\.customer-table th:nth-child\(4\),[\s\S]*?width:\s*26%;/,
  )
  assert.match(
    dashboard,
    /\.customer-table th:nth-child\(5\),[\s\S]*?width:\s*15%;/,
  )
  assert.match(
    dashboard,
    /\.customer-table td:nth-child\(4\)[^{]*\{[^}]*text-align:\s*left;/,
  )
  assert.match(
    dashboard,
    /\.customer-table td:nth-child\(5\)[^{]*\{[^}]*text-align:\s*right;/,
  )
})

test('KPI comparison copy stays concise enough for a single line', () => {
  assert.equal(en.quotation.sales.samePeriodComparison, 'vs {year}')
  assert.equal(en.quotation.sales.rollingComparison, 'vs prior 12 months')
  assert.equal(zh.quotation.sales.rollingComparison, '较前12个月')
})
