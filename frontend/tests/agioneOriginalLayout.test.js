import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { renderOriginalWorkspace, renderOriginalScopeDialog } from '../src/components/agione-demo/original-workspace-renderers.mjs'
import { originalWorkspaceState, originalFinanceDTO, readonlyWorkspaceMarkup } from '../src/utils/agioneOriginalWorkspace.js'
import { dashboardFinance } from '../src/components/agione-demo/dashboard-finance.mjs'
import { tokenAxis, trendPlot } from '../src/components/agione-demo/core.mjs'
import { profileTrendView } from '../src/components/agione-demo/profile-charts.mjs'

test('profile trend uses readable ticks and retains every day and exact values', () => {
  const plot = trendPlot([{ value: 83281000 }, { value: 10 }, { value: null }], [], 'value', true)
  assert.deepEqual(plot.ticks, [0, 25000000, 50000000, 75000000, 100000000])
  assert.equal(plot.current[0][0].value, 83281000)
  assert.equal(plot.current[0][1].value, 10)
  assert.deepEqual(tokenAxis(plot.max), { unit: 1000000, label: 'Token (M)' })
  assert.deepEqual(tokenAxis(2000), { unit: 1000, label: 'Token (K)' })
  assert.deepEqual(tokenAxis(2000000000), { unit: 1000000000, label: 'Token (B)' })
  const points = Array.from({ length: 7 }, (_, i) => ({
    bucketStart: `2026-10-${String(21 + i).padStart(2, '0')}T00:00:00+08:00`,
    bucketEndExclusive: `2026-10-${String(22 + i).padStart(2, '0')}T00:00:00+08:00`,
    requestCount: 1, totalTokensSampleCount: 1, totalTokens: i ? 10 : 83281000,
  }))
  const html = profileTrendView({ rhythm: { trend: [{ points }] } }, {
    start: points[0].bucketStart, endExclusive: points.at(-1).bucketEndExclusive,
  }, { grain: 'day' })
  for (let i = 21; i <= 27; i++) assert(html.includes(`10/${i}`))
  assert(html.includes('83,281,000 Token'))
  assert(html.includes('Token (M)'))
})

test('finance shows actual coverage without hiding gaps or missing deposits', () => {
  const html = dashboardFinance({
    available: true, totalCustomers: 1, requestedMonth: '2026-08',
    periodSummaries: [{ period: '2026-08', consumed: null, topUp: null }],
    trend: [
      { date: '2026-09-01', value: '1', topUp: '2' },
      { date: '2026-09-02', value: '0', topUp: null },
      { date: '2026-09-04', value: '3', topUp: '4' },
    ],
  })
  assert.match(html, /入账覆盖：2026-09-01、2026-09-04/)
  assert.match(html, /消耗覆盖：2026-09-01 — 2026-09-02、2026-09-04/)
  assert.match(html, /df-head-main[\s\S]*财务与额度[\s\S]*df-head-period[\s\S]*入账覆盖：[\s\S]*消耗覆盖：[\s\S]*账期覆盖[\s\S]*df-actions/)
  assert.doesNotMatch(html, /df-summary-note/)
  assert.match(html, /消耗数据未完整采集/)
})
import { finiteFinance } from '../src/utils/agioneFinancePresentation.js'
const summary={requestCount:0,successCount:0,failureCount:0,unknownCount:0,distinctCustomers:0,totalTokens:null}
const state={window:{start:'2026-10-18T00:00:00+08:00',endExclusive:'2026-10-25T00:00:00+08:00'},analysis:{rows:[],topRows:[],globalSummary:summary,summary,total:0,page:1,pageSize:20,reconciliation:{groupedRequestCount:0}},groupBy:'customerTenantId',secondary:'',metric:'requestCount',userId:'',memberOptions:[],customerOptions:[],modelOptions:[],customers:{items:[],total:0,page:1,pageSize:25},customerIds:[],filters:{modelIds:[],statuses:[],failureTypes:[]},profile:null}
test('analysis preserves original baseline details, metric p slots, table and footer',()=>{const html=renderOriginalWorkspace(originalWorkspaceState(state),'aggregate');assert.match(html,/workspace-baseline-details/);assert.match(html,/<small>请求量<\/small><strong>0<\/strong><p>/);assert.match(html,/workspace-trend-scroll/);assert.match(html,/workspace-table-footer/);assert.match(html,/data-export-analysis/)})
test('portrait uses 8011 account layout, recharge, charts, composition and member identities without a customer chooser',()=>{const p={customerTenantId:'123',name:'Organization',summary,identity:{organizationName:'Organization'},signals:{signals:[]},rhythm:{trend:[]},members:[],models:[],value:{},participation:{}};const html=renderOriginalWorkspace(originalWorkspaceState({...state,profile:p}),'portrait');for(const marker of ['profile-account-layout','profile-recharge-card','profile-financial-overview','profile-call-overview','profile-token-chart','profile-composition-card','profile-members-compact'])assert(html.includes(marker),marker);assert(!html.includes('profile-customer-toolbar'));assert(!html.includes('customerSearch'))})
test('scope preserves original checkbox columns, radios, drafts and modal footer',()=>{const html=renderOriginalScopeDialog({catalog:{customers:[],models:[]},customerIds:[],modelIds:[],result:'ALL'});for(const marker of ['scope-modal-content','scope-choice-panel','scope-option-list','scope-result-options','scope-modal-footer','scopeDraftSummary'])assert(html.includes(marker),marker);assert(!html.includes('multiple'))})
test('finance uses latest distribution and period summary DOM with readonly navigation',()=>{assert.equal(finiteFinance('12.34'),12.34);assert.equal(finiteFinance(null),null);assert.equal(finiteFinance(''),null);const value={available:true,coverageBasis:'pinned_confirmed_finance',latestObservations:false,totalCustomers:108,balanceCustomers:2,periodSummaries:[{period:'2026-10',unit:'Credit',topUp:'12.34',consumed:'1.50',consumingCustomers:1,coveredCustomers:2,topUpCustomers:1}],balanceDistributions:[{unit:'Credit',threshold:'100',healthyCustomers:1,lowCustomers:0,zeroCustomers:0,negativeCustomers:1,belowThresholdCustomers:1,negativeTotal:'3.50'}],balances:[{value:'12.34',unit:'Credit'}],cycles:[],trend:[]};const html=readonlyWorkspaceMarkup(dashboardFinance(originalFinanceDTO(value)),{finance:value});for(const marker of ['df-balance-section','df-period-section','df-balance-bar','df-summary-grid','查看客户账户','分析客户消耗'])assert(html.includes(marker),marker);assert(html.includes('12.34'));assert(html.includes('不代表最新独立账本全量'));assert.doesNotMatch(html,/更新全部财务/);assert.match(html,/data-view="portrait"/);assert.match(html,/data-view="aggregate"/)})
test('render adapter imports no application bootstrap and contains no collection or transport code',()=>{const code=readFileSync(new URL('../src/components/agione-demo/original-workspace-renderers.mjs',import.meta.url),'utf8');assert(!/import[^\n]+['"]\.\/app\.mjs/.test(code));assert(!/\bfetch\(|localStorage|setInterval\(|async function/.test(code))})

test('caller drawer separates caller and tenant IDs and keeps missing names explicit', () => {
  const input = originalWorkspaceState(state)
  input.catalog.customers = [{ id: '123456789012345678', label: '示例客户' }]
  const options = { drawer: true, body: { window: state.window, groupKey: { userId: '123456789012345678:987654321098765432' } }, groupLabel: '123456789012345678:987654321098765432' }
  const html = renderOriginalWorkspace(input, 'groupHeader', options)
  assert(!html.includes('<h3>123456789012345678:987654321098765432</h3>'))
  assert.match(html, /调用用户 ID/)
  assert.match(html, /所属客户/)
  assert.match(html, /示例客户/)
  assert.match(html, /data-copy-id="987654321098765432"/)
  assert.match(html, /data-copy-id="123456789012345678"/)
  const english = renderOriginalWorkspace(input, 'groupHeader', { ...options, locale: 'en' })
  assert.match(english, /API user ID/)
  assert.match(english, /示例客户/)
  assert.match(english, />Copy<\/button>/)
  input.catalog.customers = []
  assert.match(renderOriginalWorkspace(input, 'groupHeader', options), /所属客户<\/span><strong>123456789012345678<\/strong>/)
  assert.match(renderOriginalWorkspace(input, 'groupHeader', { ...options, groupLabel: '张三' }), /<h3>张三<\/h3>/)
  const project = { ...options, body: { ...options.body, groupKey: { userId: '123456789012345678:PROJECT:project-1' } } }
  assert.match(renderOriginalWorkspace(input, 'groupHeader', project), /项目 ID/)
})

test('profile callers show a useful name or caller type instead of a composite identifier', () => {
  const caller = '123456789012345678:987654321098765432'
  const profile = { customerTenantId: '123456789012345678', name: '客户', summary, identity: {}, signals: { signals: [] }, rhythm: { trend: [] }, models: [], value: {}, participation: {}, members: [{ label: caller, groupKey: { userId: caller }, metrics: { requestCount: 2 } }, { label: 'Alice', groupKey: { userId: '123456789012345678:alice' }, metrics: { requestCount: 1 } }] }
  for (const locale of ['zh-CN', 'en']) {
    const html = renderOriginalWorkspace(originalWorkspaceState({ ...state, profile }), 'portrait', { locale })
    assert(!html.includes(`<b>${caller}</b>`))
    assert.match(html, /987654321098765432/)
    assert.match(html, /Alice/)
  }
})

test('saved filters use the shared accessible listbox styling', () => {
  const page = readFileSync(new URL('../src/pages/AgioneOps.vue', import.meta.url), 'utf8')
  assert.match(page, /<Listbox\b/)
  assert.match(page, /<ListboxButton[^>]*ui-select-trigger/)
  assert.match(page, /<ListboxOptions[^>]*ui-select-menu/)
  assert.match(page, /<ListboxOption[\s\S]*savedFilters/)
  assert.match(page, /@update:model-value="selectSavedFilter"/)
  assert.doesNotMatch(page, /<select v-model="selectedSavedFilter"/)
})


test('finance combines matching coverage dates', () => {
  const html = dashboardFinance({available:true, totalCustomers:1, requestedMonth:'2026-10', periodSummaries:[{period:'2026-10', topUp:'1', consumed:'2', coveredCustomers:1}], trend:[{date:'2026-10-01', value:'2', topUp:'1'}]})
  assert.match(html, /入账 \/ 消耗覆盖：2026-10-01/)
  assert.doesNotMatch(html, /有入账记录 — 位客户/)
})


test('drawer uses verified caller and customer names for multidimensional groups', () => {
  const input = originalWorkspaceState(state)
  const html = renderOriginalWorkspace(input, 'groupHeader', { drawer:true, body:{window:state.window,groupKey:{userId:'123:456',modelId:'789'}}, groupLabel:'客户 / Onepro', callerName:'provider_onepro', customerName:'客户名称' })
  assert.match(html, /<h3>provider_onepro<\/h3>/)
  assert.match(html, /所属客户<\/span><strong>客户名称<\/strong>/)
  assert.match(html, /调用用户 ID<\/span><strong>456<\/strong>/)
  assert.match(html, /租户 ID<\/span><strong>123<\/strong>/)
  const english = renderOriginalWorkspace(input, 'groupHeader', {locale:'en', drawer:true, body:{window:state.window,groupKey:{userId:'123:456'}}, callerName:'客户', customerName:'模型'})
  assert.match(english, /<h3>客户<\/h3>/)
  assert.match(english, /<strong>模型<\/strong>/)
})
