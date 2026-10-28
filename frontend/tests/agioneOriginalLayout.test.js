import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { renderOriginalWorkspace, renderOriginalScopeDialog } from '../src/components/agione-demo/original-workspace-renderers.mjs'
import { originalWorkspaceState, originalFinanceDTO, readonlyWorkspaceMarkup } from '../src/utils/agioneOriginalWorkspace.js'
import { dashboardFinance } from '../src/components/agione-demo/dashboard-finance.mjs'

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
  assert.match(html, /入账日数据覆盖：2026-09-01、2026-09-04/)
  assert.match(html, /消耗日数据覆盖：2026-09-01 — 2026-09-02、2026-09-04/)
  assert.match(html, /所选日期消耗数据尚未完整采集/)
})
import { finiteFinance } from '../src/utils/agioneFinancePresentation.js'
const summary={requestCount:0,successCount:0,failureCount:0,unknownCount:0,distinctCustomers:0,totalTokens:null}
const state={window:{start:'2026-10-18T00:00:00+08:00',endExclusive:'2026-10-25T00:00:00+08:00'},analysis:{rows:[],topRows:[],globalSummary:summary,summary,total:0,page:1,pageSize:20,reconciliation:{groupedRequestCount:0}},groupBy:'customerTenantId',secondary:'',metric:'requestCount',userId:'',memberOptions:[],customerOptions:[],modelOptions:[],customers:{items:[],total:0,page:1,pageSize:25},customerIds:[],filters:{modelIds:[],statuses:[],failureTypes:[]},profile:null}
test('analysis preserves original baseline details, metric p slots, table and footer',()=>{const html=renderOriginalWorkspace(originalWorkspaceState(state),'aggregate');assert.match(html,/workspace-baseline-details/);assert.match(html,/<small>请求量<\/small><strong>0<\/strong><p>/);assert.match(html,/workspace-trend-scroll/);assert.match(html,/workspace-table-footer/);assert.match(html,/data-export-analysis/)})
test('portrait uses 8011 account layout, recharge, charts, composition and member identities without a customer chooser',()=>{const p={customerTenantId:'123',name:'Organization',summary,identity:{organizationName:'Organization'},signals:{signals:[]},rhythm:{trend:[]},members:[],models:[],value:{},participation:{}};const html=renderOriginalWorkspace(originalWorkspaceState({...state,profile:p}),'portrait');for(const marker of ['profile-account-layout','profile-recharge-card','profile-financial-overview','profile-call-overview','profile-token-chart','profile-composition-card','profile-members-compact'])assert(html.includes(marker),marker);assert(!html.includes('profile-customer-toolbar'));assert(!html.includes('customerSearch'))})
test('scope preserves original checkbox columns, radios, drafts and modal footer',()=>{const html=renderOriginalScopeDialog({catalog:{customers:[],models:[]},customerIds:[],modelIds:[],result:'ALL'});for(const marker of ['scope-modal-content','scope-choice-panel','scope-option-list','scope-result-options','scope-modal-footer','scopeDraftSummary'])assert(html.includes(marker),marker);assert(!html.includes('multiple'))})
test('finance uses latest distribution and period summary DOM with readonly navigation',()=>{assert.equal(finiteFinance('12.34'),12.34);assert.equal(finiteFinance(null),null);assert.equal(finiteFinance(''),null);const value={available:true,coverageBasis:'pinned_confirmed_finance',latestObservations:false,totalCustomers:108,balanceCustomers:2,periodSummaries:[{period:'2026-10',unit:'Credit',topUp:'12.34',consumed:'1.50',consumingCustomers:1,coveredCustomers:2,topUpCustomers:1}],balanceDistributions:[{unit:'Credit',threshold:'100',healthyCustomers:1,lowCustomers:0,zeroCustomers:0,negativeCustomers:1,belowThresholdCustomers:1,negativeTotal:'3.50'}],balances:[{value:'12.34',unit:'Credit'}],cycles:[],trend:[]};const html=readonlyWorkspaceMarkup(dashboardFinance(originalFinanceDTO(value)),{finance:value});for(const marker of ['df-balance-section','df-period-section','df-balance-bar','df-summary-grid','查看客户账户','分析客户消耗'])assert(html.includes(marker),marker);assert(html.includes('12.34'));assert(html.includes('不代表最新独立账本全量'));assert.doesNotMatch(html,/更新全部财务/);assert.match(html,/data-view="portrait"/);assert.match(html,/data-view="aggregate"/)})
test('render adapter imports no application bootstrap and contains no collection or transport code',()=>{const code=readFileSync(new URL('../src/components/agione-demo/original-workspace-renderers.mjs',import.meta.url),'utf8');assert(!/import[^\n]+['"]\.\/app\.mjs/.test(code));assert(!/\bfetch\(|localStorage|setInterval\(|async function/.test(code))})
