const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')

const demoPath = path.join(__dirname, 'channel-price-matrix-demo.html')
const html = fs.readFileSync(demoPath, 'utf8')
const scriptMatch = html.match(/<script>\n([\s\S]*?)\n<\/script>/)

test('demo JavaScript parses without syntax errors', () => {
  assert.ok(scriptMatch, 'inline application script must exist')
  assert.doesNotThrow(() => new Function(scriptMatch[1]))
})

test('workspace exposes dashboard and channel matrix as primary views', () => {
  assert.match(html, /data-component="operations-dashboard"/)
  assert.match(html, /data-component="channel-price-matrix"/)
  assert.match(html, /activeWorkspace === 'dashboard'/)
  assert.match(html, /activeWorkspace === 'matrix'/)
})

test('matrix comparisons include effective contract context', () => {
  for (const field of [
    'price_version',
    'effective_window',
    'pricing_rule',
    'updated_at',
    'contract_fx'
  ]) {
    assert.match(html, new RegExp(`\\b${field}\\b`))
  }
  assert.match(html, /data-component="channel-price-matrix"/)
  assert.match(html, /class="compare-offers"/)
  assert.match(html, /v-if="compareOpen" v-model="compareOpen"/)
})

test('price mocks are normalized to the declared per-million-token unit', () => {
  assert.match(html, /input_price_per_million:\s*Number\([^)]+\) \* 1000/)
  assert.match(html, /retail_input_price_per_million:\s*4\.8/)
  assert.match(html, /CNY \/ 1M Tokens/)
})

test('normal, stale-price, and empty operational scenarios are available', () => {
  assert.match(html, /scenarioMode = ref\('normal'\)/)
  assert.match(html, /command="stale"/)
  assert.match(html, /command="empty"/)
  assert.match(html, /scenarioMode\.value === 'empty' \? \[\]/)
})

test('priority queue excludes ready rows and stale prices block decisions', () => {
  assert.match(html, /\.filter\(\(row\) => effectiveAction\(row\) !== 'keep'\)/)
  assert.match(html, /return 'refresh_prices'/)
  assert.match(html, /refresh_prices: \{ label: '刷新价格'/)
})

test('dashboard health metrics are derived from effective offers', () => {
  assert.match(html, /const dataHealth = computed/)
  assert.match(html, /freshness: `\$\{percentage\(freshOffers, offers\.length\)\}%`/)
  assert.doesNotMatch(html, /health-row__value">92\.3%/)
})

test('primary view and dimension switches expose selection state', () => {
  assert.match(html, /role="tablist"/)
  assert.match(html, /:aria-selected="activeWorkspace === 'dashboard'"/)
  assert.match(html, /:aria-pressed="priceDimension === 'input'"/)
  assert.match(html, /:aria-label="priceCellLabel\(row, channel\)"/)
})

test('customer workspace does not expose implementation mapping copy', () => {
  const mainMatch = html.match(/<main class="main">([\s\S]*?)<\/main>/)
  assert.ok(mainMatch, 'main workspace must exist')
  assert.doesNotMatch(mainMatch[1], /字段映射|本 Demo 数据字段|decision_action mapping/)
})
