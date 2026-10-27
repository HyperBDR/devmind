import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createAgioneController } from '../src/utils/agioneOpsController.js'
import { createAgioneWorkspaceController } from '../src/utils/agioneWorkspaceController.js'
import { originalFinanceDTO, readonlyWorkspaceMarkup } from '../src/utils/agioneOriginalWorkspace.js'
import { dashboardFinance } from '../src/components/agione-demo/dashboard-finance.mjs'
const now = () => new Date('2026-10-26T05:00:00Z')
const window = { start: '2026-10-25T00:00:00+08:00', endExclusive: '2026-10-26T00:00:00+08:00', timezone: 'Asia/Shanghai' }
const response = data => ({ data: { code: 0, data } })
const native = { id: 'native-1', sourceKind: 'native', platform: 'pro', principalKind: 'provider', enabled: true, hasCredentials: true, readyForLive: true }
const live = (operation, data = {}) => ({ operation, data, window, coverage: { mode: 'live', fetchedAt: now().toISOString() }, provenance: { mode: 'live', fetchedAt: now().toISOString() }, capabilities: { directUpstream: true, readOnly: true } })
function harness(rows = [native]) {
  const calls = []
  const api = { connections: async () => response({ results: rows, next: null, capabilities: { canManageConnections: true } }), liveQuery: async (id, body) => { calls.push([id, body]); return response(live(body.operation, body.operation === 'customers' ? { items: [], total: 0 } : { summary: {}, rows: [] })) }, dashboard: () => { throw Error('legacy dashboard forbidden') }, snapshotQuery: () => { throw Error('snapshot forbidden') }, submitSync: () => { throw Error('legacy sync forbidden') } }
  return { api, calls }
}
test('native-only default never falls back to old snapshots or synthetic sources', async () => {
  const h = harness([{ ...native, sourceKind: 'demo_snapshot' }, { ...native, sourceKind: 'synthetic' }])
  const c = createAgioneController(h.api, () => {}, { now }); c.reset('user:1'); await c.load()
  assert.equal(c.snapshot().connectionId, ''); assert.equal(c.snapshot().error, 'nativeNotConfigured'); assert.equal(h.calls.length, 0); assert.equal(c.snapshot().canManageConnections, true)
})
test('native dashboard queries direct upstream without dataset versions or sync', async () => {
  const h = harness(); const c = createAgioneController(h.api, () => {}, { now }); c.reset('user:1'); await c.load()
  assert.equal(c.snapshot().isLive, true); assert.equal(c.snapshot().readOnly, true); assert.equal(c.snapshot().dashboard.dataVersion, ''); assert.equal(h.calls[0][1].operation, 'dashboard'); assert(!('dataVersion' in h.calls[0][1]))
  assert(c.setWindow('2026-10-20', '2026-10-25')); await c.sync(); assert.equal(h.calls.length, 2)
})
test('local native mode reads a published snapshot and refreshes through sync', async () => {
  const calls = []
  const snapshot = {
    operation: 'dashboard',
    dataVersion: 'native-version-1',
    data: { summary: { requestCount: 3 } },
    window,
    provenance: { mode: 'snapshot', kind: 'native_snapshot' },
    capabilities: { directUpstream: false, readOnly: true }
  }
  const api = {
    connections: async () => response({ results: [native], next: null }),
    dashboard: async () => response({
      state: 'ready',
      dataVersion: snapshot.dataVersion,
      summary: snapshot.data.summary,
      window,
      provenance: snapshot.provenance,
      snapshotResponse: snapshot
    }),
    submitSync: async (id, selected) => {
      calls.push([id, selected])
      return response({
        runId: 'native-run-1',
        status: 'succeeded',
        dataVersion: snapshot.dataVersion
      })
    }
  }
  const c = createAgioneController(api, () => {}, {
    now,
    localNative: true,
    keyFactory: () => 'native-sync-key'
  })
  c.reset('user:1')
  await c.load()
  assert.equal(c.snapshot().isLive, false)
  assert.equal(c.snapshot().readOnly, true)
  assert.equal(c.snapshot().dashboard.provenance.kind, 'native_snapshot')
  assert.equal(c.snapshot().startDate, '2026-10-19')
  assert.equal(c.snapshot().endDate, '2026-10-25')
  assert(c.setWindow('2026-10-20', '2026-10-25'))
  await c.sync()
  assert.equal(calls.length, 1)
  assert.equal(calls[0][1].start, '2026-10-20T00:00:00+08:00')
  assert.equal(c.snapshot().startDate, '2026-10-20')
  assert.equal(c.snapshot().endDate, '2026-10-25')
})
test('unconfigured native connection is explicit and never performs a request', async () => {
  const h = harness([{ ...native, readyForLive: false }]); const c = createAgioneController(h.api, () => {}, { now }); c.reset('user:1'); await c.load()
  assert.equal(c.snapshot().error, 'connectionNotConfigured'); assert.equal(h.calls.length, 0)
})
test('all native workspaces and evidence use live API without snapshot version', async () => {
  const h = harness(); const w = createAgioneWorkspaceController(h.api); w.reset('user:1')
  await w.attach({ isLive: true, requestId: 'request-1', window, provenance: { mode: 'live' } }, native.id)
  await w.setView('aggregate'); await w.setView('portrait'); await w.openRequests({ customerTenantId: '123' }); await w.openEvidence('1')
  for (const [, body] of h.calls) assert(!('dataVersion' in body))
  for (const op of ['dashboard', 'analysis', 'trend', 'customers', 'requests', 'evidence']) assert(h.calls.some(([, body]) => body.operation === op), op)
  assert.equal(w.snapshot().cachedWindow, null)
})
test('native workspace rejects old cache masquerading as live', async () => {
  const h = harness(); h.api.liveQuery = async (_, body) => response({ operation: body.operation, data: {}, provenance: { mode: 'snapshot' }, capabilities: { directUpstream: false } })
  const w = createAgioneWorkspaceController(h.api); w.reset('user:1'); await w.attach({ isLive: true, requestId: 'request-1', window, provenance: { mode: 'live' } }, native.id)
  assert.equal(w.snapshot().dashboard, null); assert(w.snapshot().error)
})
test('native configuration is write-only and never persisted in browser storage', () => {
  const code = readFileSync(new URL('../src/components/agione-demo/NativeConnectionDialog.vue', import.meta.url), 'utf8')
  assert(!/localStorage|sessionStorage|console\.|\.env/.test(code)); assert.match(code, /type="password"/); assert.match(code, /clearSecrets\(\)/); assert.match(code, /grantSelf/); assert.match(code, /canView: true, canSync: false/)
})

test('live finance keeps original sections without cache labels or fabricated null amounts', () => {
  const state = { isLive: true, provenance: { mode: 'live', fetchedAt: now().toISOString() } }
  const finance = { available: true, totalCustomers: 2, balanceCustomers: 2, coveredCustomers: 2, balances: [], cycles: [], periodSummaries: [{ period: '2026-10', unit: 'Credit', topUp: null, consumed: '12.34', adjustment: null, roundOff: null, consumingCustomers: 1, coveredCustomers: 2, topUpCustomers: 0 }] }
  const html = readonlyWorkspaceMarkup(dashboardFinance(originalFinanceDTO(finance, state)), { ...state, finance })
  assert.match(html, /df-balance-section/); assert.match(html, /df-period-section/); assert.doesNotMatch(html, /更新全部财务|按需直连读取/); assert.match(html, /读取于/); assert.match(html, /12.34/); assert.match(html, /<strong>—<\/strong>/)
  assert.doesNotMatch(html, /历史快照|已有缓存|非实时|已授权缓存汇总/)
})
test('business page has no connection configuration or credential entry', () => {
  const page = readFileSync(new URL('../src/pages/AgioneOps.vue', import.meta.url), 'utf8')
  assert.doesNotMatch(page, /<NativeConnectionDialog|nativeConfig\.open|原生连接配置/)
  assert.match(page, /const isLive = computed/)
  assert.match(page, /nativeOnly: true, localNative: true/)
  assert.match(page, /'agione\.noConnections'/)
  const zh = JSON.parse(readFileSync(new URL('../src/locales/zh-CN.json', import.meta.url), 'utf8')).agione
  assert.equal(zh.live.noConnections, '连接尚未就绪')
})

test('opening an uncollected native connection never starts a sync', async () => {
  let syncs = 0
  const api = {
    connections: async () => response({ results: [native], next: null }),
    dashboard: async () => response({ state: 'not_collected' }),
    submitSync: async () => { syncs++; return response({}) }
  }
  const c = createAgioneController(api, () => {}, { now, localNative: true })
  c.reset('user:1')
  await c.load()
  assert.equal(syncs, 0)
  assert.equal(c.snapshot().dashboard.state, 'not_collected')
  assert.equal(c.snapshot().syncing, false)
})

test('selecting a date reuses a matching native snapshot before collecting', async () => {
  let syncs = 0
  const api = {
    connections: async () => response({ results: [native], next: null }),
    dashboard: async () => response({ state: 'ready', dataVersion: 'cached',
      summary: {}, window, provenance: { kind: 'native_snapshot' } }),
    submitSync: async () => { syncs++; return response({}) }
  }
  const c = createAgioneController(api, () => {}, { now, localNative: true })
  c.reset('user:1')
  await c.load()
  await c.loadWindow('2026-10-25', '2026-10-25')
  assert.equal(c.snapshot().dashboard.dataVersion, 'cached')
  assert.equal(syncs, 0)
})

test('selecting an uncollected date starts one background collection', async () => {
  let syncs = 0
  const api = {
    connections: async () => response({ results: [native], next: null }),
    dashboard: async () => response({ state: 'not_collected' }),
    submitSync: async () => {
      syncs++
      return response({ runId: 'run', status: 'failed' })
    }
  }
  const c = createAgioneController(api, () => {}, { now, localNative: true })
  c.reset('user:1')
  await c.load()
  await c.loadWindow('2026-10-20', '2026-10-22')
  assert.equal(syncs, 1)
})


test('an uncollected date retains the previous dashboard during collection', async () => {
  let calls = 0
  const api = {
    connections: async () => response({ results: [native], next: null }),
    dashboard: async () => response(++calls === 1
      ? { state: 'ready', dataVersion: 'cached', summary: {}, window,
          provenance: { kind: 'native_snapshot' } }
      : { state: 'not_collected' }),
    submitSync: async () => response({ runId: 'run', status: 'failed' })
  }
  const c = createAgioneController(api, () => {}, { now, localNative: true })
  c.reset('user:1')
  await c.load()
  await c.loadWindow('2026-10-20', '2026-10-22')
  assert.equal(c.snapshot().dashboard.dataVersion, 'cached')
  assert.equal(c.snapshot().windowMissing, true)
})

test('collecting the previous period keeps the selected dates and refreshes them', async () => {
  let submitted
  const versions = []
  const loadingStates = []
  const api = {
    connections: async () => response({results:[native],next:null}),
    dashboard: async (_id, version) => {
      versions.push(version)
      return response({state:'ready',dataVersion:'current',summary:{},window,
        provenance:{kind:'native_snapshot'}})
    },
    submitSync: async (_id, period) => {
      submitted = period
      return response({runId:'previous',status:'succeeded',dataVersion:'prior'})
    }
  }
  const c = createAgioneController(api, state => loadingStates.push(state.previousLoading), {now,localNative:true})
  c.reset('user:1')
  await c.load()
  await c.syncPrevious()
  assert(loadingStates.includes(true))
  assert.equal(c.snapshot().previousLoading, false)
  assert.equal(submitted.start, '2026-10-12T00:00:00+08:00')
  assert.equal(submitted.endExclusive, '2026-10-19T00:00:00+08:00')
  assert.equal(versions.at(-1), undefined)
  assert.equal(c.snapshot().dashboard.dataVersion, 'current')
})

test('partial cached range is displayed and triggers background collection', async () => {
  let syncs = 0
  const partial = { state: 'ready', dataVersion: 'cached', summary: {}, window,
    coverage: { partial: true, missingDays: ['2026-10-21'] },
    provenance: { kind: 'native_snapshot' } }
  const api = {
    connections: async () => response({ results: [native], next: null }),
    dashboard: async () => response(partial),
    submitSync: async () => { syncs++; return response({ runId: 'run', status: 'failed' }) }
  }
  const c = createAgioneController(api, () => {}, { now, localNative: true })
  c.reset('user:1')
  await c.load()
  await c.loadWindow('2026-10-20', '2026-10-22')
  assert.equal(syncs, 1)
  assert.equal(c.snapshot().dashboard.coverage.partial, true)
  assert.equal(c.snapshot().windowMissing, true)
})
