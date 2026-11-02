import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { renderOriginalWorkspace, renderOriginalScopeDialog } from '../src/components/agione-demo/original-workspace-renderers.mjs'
import { dashboardFinance } from '../src/components/agione-demo/dashboard-finance.mjs'
import { localizeWorkspaceHtml, protectWorkspaceData, workspaceText } from '../src/utils/agioneWorkspaceLocale.js'
import { originalWorkspaceState } from '../src/utils/agioneOriginalWorkspace.js'

const metrics = { requestCount: 3, successCount: 2, failureCount: 1, unknownCount: 0, successRate: 66.67, distinctCustomers: 1, totalTokens: null, inputTokens: null, outputTokens: null }
function state() {
  return originalWorkspaceState({
    window: { start: '2026-10-18T00:00:00+08:00', endExclusive: '2026-10-25T00:00:00+08:00' },
    analysis: { rows: [{ label: '失败客户 <A>&"', groupKey: { customerTenantId: '123' }, metrics }], topRows: [], globalSummary: metrics, summary: metrics, total: 1, page: 1, pageSize: 20, reconciliation: { groupedRequestCount: 3 } },
    groupBy: 'customerTenantId', secondary: '', metric: 'requestCount', userId: '', memberOptions: [],
    customerOptions: [{ id: '123', label: '失败客户 <A>&"' }], modelOptions: [], customers: { items: [], total: 0, page: 1, pageSize: 25 },
    customerIds: [], filters: { modelIds: [], statuses: [], failureTypes: [] },
    profile: { customerTenantId: '123', name: '客户', identity: { organizationName: '失败公司' }, summary: metrics, signals: { signals: [] }, rhythm: { trend: [] }, members: [], models: [], value: {}, participation: {} }
  })
}

test('English analytics uses product terminology and has no untranslated UI', () => {
  const html = renderOriginalWorkspace(state(), 'aggregate', { locale: 'en-US' })
  for (const text of ['Requests', 'Success rate', 'Reported tokens', 'Group by', 'Grouped results', 'Caller']) assert(html.includes(text), text)
  assert(html.includes('失败客户 &lt;A&gt;&amp;&quot;'))
  assert(!html.includes('Invocation subject'))
  assert.doesNotMatch(html.replaceAll('失败客户 &lt;A&gt;&amp;&quot;', 'Business'), /[\u3400-\u9fff]/)
})

test('English customer insights preserves Chinese customer and organization names', () => {
  const input = state()
  const html = renderOriginalWorkspace(input, 'portrait', { locale: 'en' })
  assert(html.includes('<h2>客户</h2>'))
  assert(html.includes('失败公司'))
  assert(html.includes('Customer profile'))
  assert(html.includes('Token usage over time'))
  assert(html.includes('Shanghai time (UTC+8)'))
  assert.doesNotMatch(html.replaceAll('失败公司', 'Business').replaceAll('客户', 'Business').replaceAll('>客<','>B<'), /[\u3400-\u9fff]/)
})

test('locale is explicit, immutable, and does not leak between render calls', () => {
  const input = state(), before = JSON.stringify(input)
  const zh = renderOriginalWorkspace(input, 'aggregate')
  const en = renderOriginalWorkspace(input, 'aggregate', { locale: 'en' })
  assert(zh.includes('聚合结果'))
  assert(en.includes('Grouped results'))
  assert.equal(renderOriginalWorkspace(input, 'aggregate'), zh)
  assert.equal(JSON.stringify(input), before)
})

test('UI classification labels translate, entity labels and chart names do not', () => {
  const protectedData = protectWorkspaceData({
    rows: [{ label: '失败', groupKey: { status: 'FAILURE' } }, { label: '失败', groupKey: { customerTenantId: '123' } }],
    series: [{ label: '客户', seriesKey: '123' }, { label: '全部', seriesKey: 'ALL' }]
  })
  const data = protectedData.value
  const html = `<span>${data.rows[0].label}</span><span>${data.rows[1].label}</span><span>${data.series[0].label}</span><span>${data.series[1].label}</span>`
  assert.equal(protectedData.restore(localizeWorkspaceHtml(html, 'en')), '<span>Failed</span><span>失败</span><span>客户</span><span>All</span>')
})

test('scope supports string and options locales, keeps customer labels escaped', () => {
  const scope = { catalog: { customers: [{ id: '123', label: '客户', requestCount: 1 }], models: [] }, customerIds: [], modelIds: [], result: 'ALL' }
  const html = renderOriginalScopeDialog(scope, { locale: 'en' })
  assert(html.includes('<strong>客户</strong>'))
  assert(html.includes('Apply filters'))
  assert(html.includes('1 request'))
  assert.equal(renderOriginalScopeDialog(scope, 'en'), html)
})

test('finance distinguishes platform credits from cash revenue and preserves unknown amounts', () => {
  const finance = { mode: 'live', available: true, fetchedAt: '2026-10-26T08:00:00Z', requestedMonth: '2026-10', totalCustomers: 4, balanceCustomers: 4, coveredCustomers: 4,
    balanceDistributions: [{ unit: 'Credit', threshold: '100', healthyCustomers: 1, lowCustomers: 1, zeroCustomers: 1, negativeCustomers: 1, belowThresholdCustomers: 3, negativeTotal: '12.34' }],
    periodSummaries: [{ period: '2026-10', unit: 'Credit', topUp: '1234.50', consumed: null, adjustment: null, roundOff: null, consumingCustomers: 1, coveredCustomers: 4, topUpCustomers: 1 }] }
  const html = dashboardFinance(finance, { locale: 'en' })
  for (const text of ['Available balance breakdown', 'Credits added', 'Credits used', 'Adjustments &amp; rounding', 'Total owed', 'Customers with usage', 'Shanghai time (UTC+8)']) assert(html.includes(text) || html.includes(text.replace('&amp;', '&')), text)
  assert(html.includes('1,234.50'))
  assert.match(html, /Credits used<\/span><strong>—<\/strong>/)
  assert.doesNotMatch(html, /[\u3400-\u9fff]/)
  assert(!html.includes('Credits revenue'))
  assert(!html.includes('data-collect-finance'))
})

test('HTML token localization updates visible hints but never action attributes', () => {
  const html = `<button data-view="客户" data-code="失败" title='请求成功率' aria-label="可用余额分层" data-help="未返回的数值显示为 —。">请求量</button>`
  const en = localizeWorkspaceHtml(html, 'en')
  assert(en.includes('data-view="客户" data-code="失败"'))
  assert(en.includes("title='Success rate'"))
  assert(en.includes('data-help="Values not returned by the source are shown as —."'))
  assert(en.includes('>Requests</button>'))
})

test('attribute quotes remain valid and business HTML cannot become markup', () => {
  const p = protectWorkspaceData({ name: '<img src=x onerror=alert(1)>失败' })
  const html = p.restore(localizeWorkspaceHtml(`<span title='平台耗时单位尚未确认，暂不展示 P95 和首 Token 耗时。'>${p.value.name}</span>`, 'en'))
  assert(html.includes('platform&#39;s latency'))
  assert(html.includes('&lt;img src=x onerror=alert(1)&gt;失败'))
  assert(!html.includes('<img'))
})

test('dynamic counts, pagination and semantic metric labels are natural English', () => {
  assert.equal(workspaceText('2,731 次请求', 'en'), '2,731 requests')
  assert.equal(workspaceText('第 1 / 3 页 · 每页 2 位', 'en'), 'Page 1 of 3 · 2 customers per page')
  assert.equal(workspaceText('Credit 入账', 'zh-CN'), 'Credit 入账')
})

test('business terminology stays consistent across finance and diagnostics', () => {
  const dictionary = readFileSync(new URL('../src/utils/agioneWorkspaceLocale.js', import.meta.url), 'utf8')
  for (const phrase of [
    'Credits added', 'Credits used', 'Total owed', 'Integration issues',
    'Customers with integration issues', 'Top-up summary',
    "You are not authorized to view this customer's financial data"
  ]) assert(dictionary.includes(`|${phrase}`), phrase)
  assert(!dictionary.includes('|Credits revenue'))
  assert(!dictionary.includes('|Access blocked'))
})

test('all three workspace components subscribe to DevMind global locale', () => {
  for (const name of ['FocusWorkspace.vue', 'AnalysisWorkspace.vue', 'CustomerWorkspace.vue']) {
    const code = readFileSync(new URL(`../src/components/agione-demo/${name}`, import.meta.url), 'utf8')
    assert.match(code, /useI18n\(\{ useScope: 'global' \}\)/)
    assert.match(code, /locale:locale\.value/)
  }
})
