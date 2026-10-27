import test from 'node:test'
import assert from 'node:assert/strict'
import {
  createAgioneWorkspaceController,
  viewFromHash
} from '../src/utils/agioneWorkspaceController.js'

const frame = {
  dataVersion: 'version-1',
  window: {
    start: '2026-10-18T00:00:00+08:00',
    endExclusive: '2026-10-25T00:00:00+08:00',
    timezone: 'Asia/Shanghai'
  }
}
const wrap = (body, data = {}) => ({
  data: {
    code: 0,
    data: {
      operation: body.operation,
      dataVersion: body.dataVersion,
      window: body.window,
      data,
      overview:
        body.operation === 'dashboard'
          ? { summary: { requests: 42 } }
          : undefined,
      coverage: {
        directoryTotal: 149,
        confirmedDirectoryCustomers: 148,
        excludedUnconfirmedCustomers: 1
      }
    }
  }
})
function setup(handler) {
  const calls = []
  const api = {
    snapshotQuery: async (id, body, config) => {
      calls.push({ id, body, config })
      if (handler) return handler(id, body, config)
      if (body.operation === 'customers')
        return wrap(body, {
          items: [{ customerTenantId: '10', name: 'Organization' }],
          total: 27,
          page: body.payload.page,
          pageSize: 25
        })
      return wrap(body)
    }
  }
  const c = createAgioneWorkspaceController(api)
  c.reset('user-1')
  return { c, calls, api }
}

test('new snapshot retains selected range and queries that range', async () => {
  const { c, calls } = setup()
  const selected = { ...frame.window, start: '2026-10-20T00:00:00+08:00' }
  await c.attach(frame, 'a', selected)
  assert.deepEqual(c.snapshot().window, selected)
  assert.deepEqual(c.snapshot().cachedWindow, frame.window)
  assert.equal(calls[0].body.window.start, selected.start)
  await c.attach({ ...frame, dataVersion: 'version-2' }, 'a', selected)
  assert.equal(c.snapshot().window.start, selected.start)
  assert.equal(calls.filter((call) => call.body.operation === 'dashboard')
    .at(-1).body.window.start, selected.start)
})

test('default scope omits empty customer ids instead of sending a forbidden empty array', async () => {
  const { c, calls } = setup()
  await c.attach(frame, 'a')
  assert(calls.every((x) => !('customerIds' in x.body)))
  await c.setView('aggregate')
  assert(calls.every((x) => !('customerIds' in x.body)))
})
test('dashboard finance payload is reused without a duplicate independent read', async () => {
  const { c, calls } = setup((id, b) =>
    Promise.resolve(
      wrap(
        b,
        b.operation === 'dashboard'
          ? { finance: { available: true, finance: { balances: [] } } }
          : {}
      )
    )
  )
  await c.attach(frame, 'a')
  await Promise.resolve()
  assert.equal(calls.filter((x) => x.body.operation === 'finance').length, 0)
  assert.equal(c.snapshot().finance.available, true)
})
test('live frame renders once and reads finance independently', async () => {
  const calls = []
  const api = {
    liveQuery: async (id, body) => {
      calls.push({ id, body })
      return {
        data: {
          code: 0,
          data: {
            operation: 'finance',
            data: { available: false, reason: 'NO_USABLE_FINANCE_OBSERVATIONS' },
            provenance: { mode: 'live' },
            capabilities: { directUpstream: true }
          }
        }
      }
    }
  }
  const c = createAgioneWorkspaceController(api)
  c.reset('user-1')
  await c.attach({
    ...frame,
    isLive: true,
    requestId: 'live:1',
    provenance: { mode: 'live' },
    liveResponse: {
      operation: 'dashboard',
      data: { summary: { requestCount: 42 }, trend: [] },
      overview: { summary: { requestCount: 42 } },
      coverage: { mode: 'live' },
      capabilities: { directUpstream: true }
    }
  }, 'native-1')
  await Promise.resolve()
  assert.equal(c.snapshot().dashboard.summary.requestCount, 42)
  assert.equal(calls.filter((x) => x.body.operation === 'dashboard').length, 0)
  assert.equal(calls.filter((x) => x.body.operation === 'trend').length, 0)
  assert.equal(calls.filter((x) => x.body.operation === 'finance').length, 1)
})
test('safe operation errors show stable code and never raw backend failed text', async () => {
  const { c } = setup(() =>
    Promise.reject({
      response: {
        status: 400,
        data: { message: 'failed', data: { errorCode: 'WINDOW_NOT_CACHED' } }
      }
    })
  )
  await c.attach(frame, 'a')
  assert.match(c.snapshot().error, /WINDOW_NOT_CACHED/)
  assert.match(c.snapshot().error, /未采集/)
  assert(!c.snapshot().error.includes('failed'))
})
test('group row retains label and metrics through drawer pagination and evidence',async()=>{const row={groupKey:{modelId:'99'},label:'Model 99',metrics:{requestCount:71,successRate:95,inputTokens:123,outputTokens:456}};const {c,calls}=setup((id,b)=>Promise.resolve(wrap(b,b.operation==='analysis'?{rows:[row]}:{})));await c.attach(frame,'a');await c.setView('aggregate');await c.openGroupDrawer(row);assert.deepEqual(c.snapshot().drawer.groupMeta,{label:'Model 99',summary:row.metrics});await c.openRequests(row.groupKey,2);assert.equal(c.snapshot().drawer.groupMeta.summary.requestCount,71);await c.openEvidence('123');await c.openRequests(row.groupKey,2);assert.equal(c.snapshot().drawer.groupMeta.label,'Model 99');assert(calls.every(x=>x.body.dataVersion==='version-1'));const count=calls.length;c.openGroupDrawer({...row,groupKey:{modelId:'foreign'}});assert.equal(calls.length,count)})
test('restores only three supported copyable navigation hashes', () => {
  assert.equal(viewFromHash('#aggregate'), 'aggregate')
  assert.equal(viewFromHash('#portrait'), 'portrait')
  assert.equal(viewFromHash('#pricing'), 'focus')
})
test('three navigation pages issue distinct real operations without changing pinned version', async () => {
  const { c, calls } = setup()
  await c.attach(frame, 'source-a')
  await c.setView('aggregate')
  await c.setView('portrait')
  assert(calls.some((x) => x.body.operation === 'analysis'))
  assert(calls.some((x) => x.body.operation === 'trend'))
  assert(calls.some((x) => x.body.operation === 'customers'))
  assert(calls.some((x) => x.body.operation === 'profile'))
  assert(calls.every((x) => x.body.dataVersion === 'version-1'))
  assert.equal(c.snapshot().profile?.customerId, undefined)
})
test('analysis controls and pagination are server query payloads', async () => {
  const { c, calls } = setup()
  await c.attach(frame, 'a')
  await c.setView('aggregate')
  await c.configure({
    groupBy: 'modelId',
    secondary: 'status',
    metric: 'outputTokens',
    userId: 'subject-1',
    analysisPage: 2
  })
  const b = calls.filter((x) => x.body.operation === 'analysis').at(-1).body
  assert.deepEqual(b.payload.groupBy, ['modelId', 'status'])
  assert.deepEqual(b.payload.userIds, ['subject-1'])
  assert.equal(b.payload.page, 2)
  assert.equal(b.dataVersion, 'version-1')
})
test('customer search, filter, pagination and selection query actual profile', async () => {
  const { c, calls } = setup()
  await c.attach(frame, 'a')
  await c.setView('portrait')
  await c.configure({
    search: 'Organization',
    signal: 'decline',
    customerPage: 2
  })
  const list = calls.filter((x) => x.body.operation === 'customers').at(-1).body
  assert.equal(list.payload.page, 2)
  assert.equal(list.payload.search, 'Organization')
  assert.equal(list.payload.signal, 'decline')
  assert.equal(
    calls.filter((x) => x.body.operation === 'profile').at(-1).body.payload
      .customerId,
    '10'
  )
})
test('drilldown pins group scope/page then loads only requested evidence', async () => {
  const { c, calls } = setup()
  await c.attach(frame, 'a')
  await c.openRequests({ modelId: '99' }, 2, '10')
  await c.openEvidence('123')
  const request = calls
    .filter((x) => x.body.operation === 'requests')
    .at(-1).body
  assert.deepEqual(request.customerIds, ['10'])
  assert.equal(request.payload.page, 2)
  assert.deepEqual(request.payload.groupKey, { modelId: '99' })
  assert.equal(calls.at(-1).body.payload.evidenceId, '123')
  assert.equal(calls.at(-1).body.dataVersion, 'version-1')
})
test('scope filters and cached date subsets apply without status or sync calls', async () => {
  const { c, calls } = setup()
  await c.attach(frame, 'a')
  await c.setFilters(['10'], {
    modelIds: ['99'],
    statuses: ['FAILURE'],
    failureTypes: []
  })
  await c.setWindow({ ...frame.window, start: '2026-10-20T00:00:00+08:00' })
  const b = calls.filter((x) => x.body.operation === 'dashboard').at(-1).body
  assert.deepEqual(b.customerIds, ['10'])
  assert.equal(b.window.start, '2026-10-20T00:00:00+08:00')
  assert.throws(
    () => c.setWindow({ ...frame.window, start: '2026-10-01T00:00:00+08:00' }),
    /缓存范围/
  )
  assert(
    calls.every(
      (x) => !['sync', 'status', 'collect'].includes(x.body.operation)
    )
  )
})
test('portrait caches each customer profile without rereading the directory', async () => {
  const { c, calls } = setup((id, body) => Promise.resolve(
    wrap(body, body.operation === 'customers'
      ? { items: [
          { customerTenantId: '10', name: 'A' },
          { customerTenantId: '11', name: 'B' }
        ], total: 2, page: 1, pageSize: 25 }
      : { customerTenantId: body.payload?.customerId, members: [] })
  ))
  await c.attach(frame, 'a')
  await c.setView('portrait')
  await c.selectCustomer('11')
  await c.selectCustomer('10')
  assert.equal(calls.filter((x) => x.body.operation === 'customers').length, 1)
  assert.equal(calls.filter((x) => x.body.operation === 'profile').length, 3)
  assert.equal(c.snapshot().selectedCustomerId, '10')
})
test('finance follows dates without applying customer and model filters', async () => {
  const { c, calls } = setup()
  await c.attach(frame, 'a')
  await c.setFilters(['10'], {
    modelIds: ['99'],
    statuses: [],
    failureTypes: []
  })
  await Promise.resolve()
  const b = calls.filter((x) => x.body.operation === 'finance').at(-1).body
  assert.deepEqual(b, {
    operation: 'finance',
    dataVersion: 'version-1',
    window: frame.window,
    payload: {}
  })
})
test('late page result cannot overwrite newly selected view', async () => {
  let finish
  const { c } = setup((id, b) =>
    b.operation === 'analysis'
      ? new Promise((r) => {
          finish = () => r(wrap(b, { rows: [{ label: 'old' }] }))
        })
      : Promise.resolve(
          wrap(b, b.operation === 'customers' ? { items: [], total: 0 } : {})
        )
  )
  await c.attach(frame, 'a')
  const pending = c.setView('aggregate')
  await c.setView('portrait')
  finish()
  await pending
  assert.equal(c.snapshot().view, 'portrait')
  assert.equal(c.snapshot().analysis, null)
})
test('account reset clears profile, version and drawer and drops late requests', async () => {
  let finish
  const { c } = setup((id, b) =>
    b.operation === 'requests'
      ? new Promise((r) => {
          finish = () => r(wrap(b, { items: [{ recordId: '1' }] }))
        })
      : Promise.resolve(wrap(b))
  )
  await c.attach(frame, 'a')
  const pending = c.openRequests()
  c.reset('user-2')
  finish()
  await pending
  assert.equal(c.snapshot().dataVersion, '')
  assert.equal(c.snapshot().drawer, null)
})
test('permission failure clears all old business content', async () => {
  let forbidden = false
  const { c } = setup((id, b) => {
    if (forbidden) return Promise.reject({ response: { status: 403 } })
    return Promise.resolve(wrap(b, { rows: [{ label: 'old' }] }))
  })
  await c.attach(frame, 'a')
  await c.setView('aggregate')
  forbidden = true
  await c.load()
  assert.equal(c.snapshot().analysis, null)
  assert.equal(c.snapshot().dataVersion, '')
  assert.match(c.snapshot().error, /权限/)
})
test('explicit refresh invalidates old dependent views even if source version is unchanged', async () => {
  const { c, calls } = setup()
  await c.attach(frame, 'a')
  await c.setView('aggregate')
  const n = calls.length
  c.invalidate()
  await c.attach(frame, 'a')
  assert(calls.length > n)
  assert.equal(c.snapshot().view, 'aggregate')
  assert.equal(c.snapshot().dataVersion, 'version-1')
})

test('Vue-like deep proxies use trusted raw group metrics and reject old scope origins',async()=>{const row={groupKey:{modelId:'99'},label:'Trusted Model',metrics:{requestCount:71}};const {c,calls}=setup((id,b)=>Promise.resolve(wrap(b,b.operation==='analysis'?{rows:[row]}:{})));await c.attach(frame,'a');await c.setView('aggregate');const origin={connectionId:c.snapshot().connectionId,dataVersion:c.snapshot().dataVersion,contextKey:c.snapshot().contextKey};const proxy=new Proxy(row,{get(target,key){if(key==='metrics')return {requestCount:999};if(key==='label')return 'Untrusted';if(key==='groupKey')return new Proxy(target.groupKey,{});return target[key]}});await c.openGroupDrawer(proxy,null,origin);assert.equal(c.snapshot().drawer.groupMeta.label,'Trusted Model');assert.equal(c.snapshot().drawer.groupMeta.summary.requestCount,71);await c.configure({metric:'outputTokens'});const n=calls.length;c.openGroupDrawer(proxy,null,origin);assert.equal(calls.length,n)})

const deferred = () => {
  let resolve, reject
  const promise = new Promise((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}
const tick = async () => {
  for (let i = 0; i < 12; i++) await Promise.resolve()
}
const dashboardData = (tag) => ({
  summary: { requestCount: tag }, trend: [{ tag }], finance: null
})

test('focus uses dashboard trend without a second trend or finance query', async () => {
  const { c, calls } = setup((id, b) => wrap(b, dashboardData(42)))
  await c.attach(frame, 'a')
  assert.deepEqual(calls.map((x) => x.body.operation), ['dashboard'])
  assert.equal(c.snapshot().trend.summary.requestCount, 42)
  assert.deepEqual(c.snapshot().trend.series, [{ tag: 42 }])
})

test('returning page renders immediately and rechecks ACL in background', async () => {
  let pending = null
  const { c, calls } = setup((id, b) => {
    if (b.operation === 'dashboard' && pending) return pending.promise
    return wrap(b, dashboardData(7))
  })
  await c.attach(frame, 'a')
  await c.setView('aggregate')
  pending = deferred()
  const returning = c.setView('focus')
  assert.equal(c.snapshot().dashboard.summary.requestCount, 7)
  assert.equal(c.snapshot().loading, false)
  assert.equal(c.snapshot().refreshing, true)
  assert.equal(calls.filter((x) => x.body.operation === 'dashboard').length, 2)
  pending.reject({ response: { status: 403 } })
  await returning
  assert.equal(c.snapshot().dashboard, null)
  assert.equal(c.snapshot().dataVersion, '')
  assert.equal(c.snapshot().refreshing, false)
})

test('identical load shares the same Promise and operation request', async () => {
  let pending = null
  const { c, calls } = setup((id, b) => pending ? pending.promise :
    wrap(b, dashboardData(1)))
  await c.attach(frame, 'a')
  pending = deferred()
  const first = c.load()
  const second = c.load()
  assert.equal(first, second)
  assert.equal(calls.filter((x) => x.body.operation === 'dashboard').length, 2)
  pending.resolve(wrap(calls.at(-1).body, dashboardData(2)))
  await first
  assert.equal(c.snapshot().dashboard.summary.requestCount, 2)
})

test('A-B-A aborts obsolete work and starts a fresh needed request', async () => {
  const pending = deferred()
  let wait = false
  const { c, calls } = setup((id, b) => {
    if (wait && b.operation === 'dashboard') return pending.promise
    return wrap(b, dashboardData(1))
  })
  await c.attach(frame, 'a')
  wait = true
  const first = c.load()
  await c.setView('aggregate')
  const returning = c.setView('focus')
  const dashboards = calls.filter((x) => x.body.operation === 'dashboard')
  assert.equal(dashboards.length, 3)
  assert.equal(dashboards[1].config.signal.aborted, true)
  assert.equal(dashboards[2].config.signal.aborted, false)
  pending.resolve(wrap(calls.findLast((x) =>
    x.body.operation === 'dashboard').body, dashboardData(2)))
  await Promise.all([first, returning])
  assert.equal(c.snapshot().dashboard.summary.requestCount, 2)
})

test('stale successful page is not inserted into navigation cache', async () => {
  const pending = deferred()
  let wait = true
  const { c, calls } = setup((id, b) => b.operation === 'analysis' && wait
    ? pending.promise : wrap(b, dashboardData(1)))
  await c.attach(frame, 'a')
  const old = c.setView('aggregate')
  await c.setView('focus')
  const analysisBody = calls.find((x) => x.body.operation === 'analysis').body
  pending.resolve(wrap(analysisBody, { rows: [{ label: 'stale' }] }))
  await old
  wait = false
  const next = c.setView('aggregate')
  assert.equal(c.snapshot().analysis, null)
  assert.equal(c.snapshot().loading, true)
  await next
  assert.equal(c.snapshot().analysis.rows, undefined)
})

for (const status of [401, 403, 404]) {
  test(`late same-domain ${status} clears data after navigating away`, async () => {
    const pending = deferred()
    const { c } = setup((id, b) => b.operation === 'analysis'
      ? pending.promise : wrap(b, dashboardData(1)))
    await c.attach(frame, 'a')
    const old = c.setView('aggregate')
    await c.setView('focus')
    pending.reject({ response: { status } })
    await old
    assert.equal(c.snapshot().dashboard, null)
    assert.equal(c.snapshot().dataVersion, '')
    assert.equal(c.snapshot().finance, null)
    assert.equal(c.snapshot().directory, null)
    assert.equal(c.snapshot().memberOptions.length, 0)
  })
}

test('old connection denial cannot clear the newly attached connection', async () => {
  const pending = deferred()
  const { c } = setup((id, b) => id === 'a' && b.operation === 'analysis'
    ? pending.promise : wrap(b, dashboardData(id)))
  await c.attach(frame, 'a')
  const old = c.setView('aggregate')
  await c.attach(frame, 'b')
  await c.setView('focus')
  pending.reject({ response: { status: 403 } })
  await old
  assert.equal(c.snapshot().connectionId, 'b')
  assert.equal(c.snapshot().dashboard.summary.requestCount, 'b')
  assert.equal(c.snapshot().error, '')
})

test('same-connection denial remains authoritative after version change', async () => {
  const pending = deferred()
  let wait = true
  const { c } = setup((id, b) => wait && b.operation === 'analysis'
    ? pending.promise : wrap(b, dashboardData(1)))
  await c.attach(frame, 'a')
  const old = c.setView('aggregate')
  wait = false
  await c.attach({ ...frame, dataVersion: 'version-2' }, 'a')
  pending.reject({ response: { status: 403 } })
  await old
  assert.equal(c.snapshot().dataVersion, '')
  assert.match(c.snapshot().error, /权限/)
})

test('scope, window and configure changes label previous results while loading', async () => {
  const { c } = setup((id, b) => wrap(b, dashboardData(1)))
  await c.attach(frame, 'a')
  const filtered = c.setFilters(['10'], {
    modelIds: ['99'], statuses: [], failureTypes: []
  })
  assert.notEqual(c.snapshot().dashboard, null)
  assert.equal(c.snapshot().stale, true)
  assert.equal(c.snapshot().loading, false)
  await filtered
  assert.equal(c.snapshot().stale, false)
  const windowed = c.setWindow({ ...frame.window,
    start: '2026-10-20T00:00:00+08:00' })
  assert.equal(c.snapshot().stale, true)
  await windowed
  assert.equal(c.snapshot().stale, false)
  await c.setView('aggregate')
  const configured = c.configure({ metric: 'outputTokens', analysisPage: 2 })
  assert.equal(c.snapshot().stale, true)
  assert.equal(c.snapshot().loading, false)
  await configured
  assert.equal(c.snapshot().stale, false)
})

test('LRU page cache is bounded and evicts the least recently used page', async () => {
  const { c } = setup((id, b) => wrap(b, dashboardData(1)))
  await c.attach(frame, 'a')
  await c.setView('aggregate')
  for (let page = 2; page <= 27; page++)
    await c.configure({ analysisPage: page })
  const old = c.configure({ analysisPage: 1 })
  assert.equal(c.snapshot().stale, true)
  assert.equal(c.snapshot().loading, false)
  await old
  const recent = c.configure({ analysisPage: 26 })
  assert.notEqual(c.snapshot().analysis, null)
  assert.equal(c.snapshot().loading, false)
  await recent
})

test('reset and dispose abort pending calls and clear all cached pages', async () => {
  for (const method of ['reset', 'dispose']) {
    const pending = deferred()
    const calls = []
    let wait = false
    const c = createAgioneWorkspaceController({
      snapshotQuery(id, body, config) {
        calls.push({ body, config })
        return wait ? pending.promise : Promise.resolve(wrap(body,
          dashboardData(1)))
      }
    })
    c.reset('one')
    await c.attach(frame, 'a')
    wait = true
    const old = c.load()
    const signal = calls.at(-1).config.signal
    assert.equal(signal.aborted, false)
    c[method]('two')
    assert.equal(signal.aborted, true)
    pending.reject({ name: 'CanceledError', code: 'ERR_CANCELED' })
    await old
    assert.equal(c.snapshot().dashboard, null)
    assert.equal(c.snapshot().error, '')
    if (method === 'reset') {
      wait = false
      const fresh = c.attach(frame, 'a')
      assert.equal(c.snapshot().loading, true)
      await fresh
    }
  }
})

test('current cancelled query is silent', async () => {
  const { c } = setup(() => Promise.reject({ code: 'ERR_CANCELED' }))
  await c.attach(frame, 'a')
  assert.equal(c.snapshot().error, '')
  assert.equal(c.snapshot().loading, false)
})

test('old account denial cannot clear a new authenticated session', async () => {
  const pending = deferred()
  let wait = true
  const { c } = setup((id, b) => wait && b.operation === 'analysis'
    ? pending.promise : wrap(b, dashboardData(1)))
  await c.attach(frame, 'a')
  const old = c.setView('aggregate')
  c.reset('user-2')
  wait = false
  await c.attach(frame, 'a')
  pending.reject({ response: { status: 401 } })
  await old
  assert.equal(c.snapshot().dataVersion, 'version-1')
  assert.equal(c.snapshot().dashboard.summary.requestCount, 1)
})

for (const operation of ['requests', 'evidence', 'schema', 'finance',
  'profile', 'customers']) {
  test(`late ${operation} denial clears the current business domain`, async () => {
    const pending = deferred()
    let wait = false
    const { c } = setup((id, b) => wait && b.operation === operation
      ? pending.promise : wrap(b, b.operation === 'customers'
        ? { items: [{ customerTenantId: '10' }] } : dashboardData(1)))
    await c.attach(frame, 'a')
    if (operation === 'profile') await c.setView('portrait')
    wait = true
    let old
    if (operation === 'requests') old = c.openRequests()
    if (operation === 'evidence') old = c.openEvidence('one')
    if (operation === 'schema') old = c.options('modelId')
    if (operation === 'customers') old = c.queryDirectory()
    if (operation === 'profile') old = c.selectCustomer('10')
    if (operation === 'finance') {
      // Trigger the fallback without a dashboard finance field.
      wait = false
      c.reset('user-1')
      const financeApi = {
        snapshotQuery: (id, b) => b.operation === 'finance'
          ? pending.promise : Promise.resolve(wrap(b, {}))
      }
      const other = createAgioneWorkspaceController(financeApi)
      other.reset('user-1')
      await other.attach(frame, 'a')
      await other.setView('portrait')
      pending.reject({ response: { status: 403 } })
      await tick()
      assert.equal(other.snapshot().dataVersion, '')
      assert.equal(other.snapshot().profile, null)
      return
    }
    wait = false
    await c.setView('aggregate')
    pending.reject({ response: { status: 403 } })
    await old
    assert.equal(c.snapshot().dataVersion, '')
    assert.equal(c.snapshot().analysis, null)
  })
}

import { readFile } from 'node:fs/promises'

for (const kind of ['demo_snapshot', 'native_snapshot']) {
  test(`${kind} frame reuses pinned complete dashboard without extra calls`, async () => {
    const { c, calls } = setup()
    const response = {
      operation: 'dashboard', dataVersion: frame.dataVersion,
      data: dashboardData(42),
      provenance: { mode: 'snapshot', kind },
      capabilities: { directUpstream: false }
    }
    await c.attach({ ...frame, snapshotResponse: response }, 'a')
    assert.equal(calls.length, 0)
    assert.equal(c.snapshot().dashboard.summary.requestCount, 42)
    assert.deepEqual(c.snapshot().trend.series, [{ tag: 42 }])
  })
}

for (const patch of [
  { dataVersion: 'wrong-version' },
  { provenance: { mode: 'live', kind: 'native_snapshot' } },
  { provenance: { kind: 'unknown_source' } },
  { capabilities: { directUpstream: true } },
  { operation: 'analysis' }
]) {
  test('snapshot frame rejects unpinned or nonlocal embedded response ' +
    JSON.stringify(patch), async () => {
    const { c, calls } = setup((id, b) => wrap(b, dashboardData(7)))
    await c.attach({ ...frame, snapshotResponse: {
      operation: 'dashboard', dataVersion: frame.dataVersion,
      data: dashboardData(42),
      provenance: { mode: 'snapshot', kind: 'native_snapshot' },
      capabilities: { directUpstream: false }, ...patch
    } }, 'a')
    assert.equal(calls.length, 1)
    assert.equal(c.snapshot().dashboard.summary.requestCount, 7)
  })
}

test('snapshot frame liveResponse alias remains compatible', async () => {
  const { c, calls } = setup()
  await c.attach({ ...frame, liveResponse: {
    operation: 'dashboard', dataVersion: frame.dataVersion,
    data: dashboardData(42), provenance: { kind: 'demo_snapshot' }
  } }, 'a')
  assert.equal(calls.length, 0)
  assert.equal(c.snapshot().dashboard.summary.requestCount, 42)
})

test('configure keeps needed same-key pending operation and aborts stale payload', async () => {
  const pending = []
  const { c, calls } = setup((id, b, config) => {
    if (b.operation === 'analysis' || b.operation === 'trend') {
      const item = { ...deferred(), body: b, signal: config.signal }
      pending.push(item)
      return item.promise
    }
    return wrap(b, dashboardData(1))
  })
  await c.attach(frame, 'a')
  const first = c.setView('aggregate')
  const second = c.configure({ metric: 'outputTokens' })
  assert.equal(calls.filter((x) => x.body.operation === 'analysis').length, 2)
  assert.equal(calls.filter((x) => x.body.operation === 'trend').length, 1)
  assert.equal(pending[0].signal.aborted, true)
  assert.equal(pending[1].signal.aborted, false)
  assert.equal(pending[2].signal.aborted, false)
  for (const item of pending) item.resolve(wrap(item.body, { rows: [] }))
  await Promise.all([first, second])
  assert.equal(c.snapshot().loading, false)
  assert.deepEqual(c.snapshot().analysis.rows, [])
})

test('cancelled drawer queries stop loading without an error', async () => {
  let cancel = false
  const { c } = setup((id, b) => cancel
    ? Promise.reject({ code: 'ERR_CANCELED' }) : wrap(b, dashboardData(1)))
  await c.attach(frame, 'a')
  cancel = true
  await c.openRequests()
  assert.equal(c.snapshot().drawerLoading, false)
  assert.equal(c.snapshot().drawerError, '')
  await c.openEvidence('one')
  assert.equal(c.snapshot().drawerLoading, false)
  assert.equal(c.snapshot().drawerError, '')
})

test('inflight requests are bounded and cancel oldest pending work', async () => {
  const pending = []
  const c = createAgioneWorkspaceController({
    snapshotQuery(id, body, config) {
      if (body.operation !== 'evidence')
        return Promise.resolve(wrap(body, dashboardData(1)))
      const item = { ...deferred(), body, signal: config.signal }
      pending.push(item)
      return item.promise
    }
  })
  c.reset('user-1')
  await c.attach(frame, 'a')
  const reads = Array.from({ length: 55 }, (_, index) =>
    c.openEvidence(String(index)))
  assert.equal(pending.filter((item) => item.signal.aborted).length, 7)
  for (const item of pending)
    item.resolve(wrap(item.body, { evidenceId: item.body.payload.evidenceId }))
  await Promise.all(reads)
  assert.equal(c.snapshot().evidence.evidenceId, '54')
})

test('irrelevant aggregate controls do not discard cached focus page', async () => {
  const { c } = setup((id, b) => wrap(b, dashboardData(1)))
  await c.attach(frame, 'a')
  await c.setView('aggregate')
  await c.configure({ groupBy: 'modelId', analysisPage: 2 })
  const returning = c.setView('focus')
  assert.equal(c.snapshot().loading, false)
  assert.equal(c.snapshot().dashboard.summary.requestCount, 1)
  await returning
})

test('returning portrait retains cached profile while profile is rechecked', async () => {
  const pending = deferred()
  let wait = false
  const { c } = setup((id, b) => {
    if (b.operation === 'profile' && wait) return pending.promise
    return wrap(b, b.operation === 'customers'
      ? { items: [{ customerTenantId: '10' }] }
      : b.operation === 'profile' ? { customerId: '10', tag: 7 }
        : dashboardData(1))
  })
  await c.attach(frame, 'a')
  await c.setView('portrait')
  await c.setView('focus')
  wait = true
  const returning = c.setView('portrait')
  assert.equal(c.snapshot().profile.tag, 7)
  await tick()
  assert.equal(c.snapshot().profile.tag, 7)
  pending.reject({ response: { status: 403 } })
  await returning
  assert.equal(c.snapshot().profile, null)
})

test('schema candidates do not survive configure or filter scope change', async () => {
  const pending = deferred()
  let wait = false
  const { c } = setup((id, b) => {
    if (wait && b.operation === 'dashboard') return pending.promise
    return wrap(b, b.operation === 'schema'
      ? { options: { items: [{ id: 'one' }] } } : dashboardData(1))
  })
  await c.attach(frame, 'a')
  await c.options('modelId')
  assert.equal(c.snapshot().modelOptions.length, 1)
  wait = true
  const filtered = c.setFilters(['10'], {
    modelIds: [], statuses: [], failureTypes: []
  })
  assert.equal(c.snapshot().modelOptions.length, 0)
  pending.reject({ code: 'ERR_CANCELED' })
  await filtered
})

test('snapshot version and live request id prevent cache reuse', async () => {
  const { c } = setup((id, b) => wrap(b, dashboardData(1)))
  await c.attach(frame, 'a')
  const changed = c.attach({ ...frame, dataVersion: 'version-2' }, 'a')
  assert.equal(c.snapshot().stale, true)
  assert.notEqual(c.snapshot().dashboard, null)
  await changed
  assert.equal(c.snapshot().stale, false)
  const api = { liveQuery: async (id, b) => ({ data: { data: {
    operation: b.operation, data: dashboardData(2),
    provenance: { mode: 'live' }, capabilities: { directUpstream: true }
  } } }) }
  const live = createAgioneWorkspaceController(api)
  live.reset('user-1')
  const liveFrame = { ...frame, isLive: true,
    provenance: { mode: 'live' }, requestId: 'request-one' }
  await live.attach(liveFrame, 'a')
  const next = live.attach({ ...liveFrame, requestId: 'request-two' }, 'a')
  assert.equal(live.snapshot().dashboard, null)
  assert.equal(live.snapshot().loading, true)
  await next
})

test('optional AbortController absence still queries successfully', async () => {
  const original = globalThis.AbortController
  try {
    globalThis.AbortController = undefined
    const { c } = setup((id, b) => wrap(b, dashboardData(1)))
    await c.attach(frame, 'a')
    assert.equal(c.snapshot().dashboard.summary.requestCount, 1)
    c.dispose()
  } finally {
    globalThis.AbortController = original
  }
})

test('API methods forward optional signal config without changing body', async () => {
  const source = await readFile(new URL('../src/api/agioneOps.js',
    import.meta.url), 'utf8')
  const calls = []
  globalThis.__agioneApiTestClient = {
    post: (...args) => { calls.push(args); return Promise.resolve({}) }
  }
  try {
    const patched = source.replace("import apiClient from './index'",
      'const apiClient = globalThis.__agioneApiTestClient')
    const { agioneOpsApi } = await import('data:text/javascript,' +
      encodeURIComponent(patched))
    const config = { signal: new AbortController().signal }
    const body = { operation: 'dashboard' }
    await agioneOpsApi.snapshotQuery('a b', body, config)
    await agioneOpsApi.liveQuery('a b', body, config)
    assert(calls.every(([, sent, options]) =>
      sent === body && options === config))
    assert(calls[0][0].includes('a%20b'))
  } finally {
    delete globalThis.__agioneApiTestClient
  }
})

test('Vue watcher observes busy completion and clears empty or failed frames', async () => {
  const source = await readFile(new URL('../src/pages/AgioneOps.vue',
    import.meta.url), 'utf8')
  const start = source.indexOf('watch(\n  () => [state.value.connectionId')
  assert(start >= 0)
  const end = source.indexOf("  { flush: 'sync' }", start)
  const watcher = source.slice(start, end)
  assert.match(watcher, /state\.value\.loading/)
  assert.match(watcher, /state\.value\.listLoading/)
  assert.match(watcher, /state\.value\.error/)
  const callback = watcher.slice(watcher.indexOf('  ([id,'),
    watcher.lastIndexOf('},') + 1).trim()
  const attached = []
  const work = { value: { connectionId: 'a' } }
  const workspace = { attach: (...args) => attached.push(args) }
  const state = { value: { sourceKind: 'synthetic' } }
  const invoke = new Function('work', 'workspace', 'state', `return ${callback}`)(
    work, workspace, state)
  invoke(['', null, false, false, true, ''])
  assert.deepEqual(attached.at(-1), [null, ''])
  invoke(['b', null, true, true, true, ''])
  assert.deepEqual(attached.at(-1), [null, ''])
  work.value.connectionId = 'b'
  const readyFrame = { dataVersion: 'v' }
  invoke(['b', readyFrame, false, false, true, ''])
  assert.deepEqual(attached.at(-1), [readyFrame, 'b', null])
  invoke(['b', null, false, false, true, 'accessDenied'])
  assert.deepEqual(attached.at(-1), [null, ''])
})

test('finance refresh keeps the dashboard and updates after background completion', async () => {
  const { c, calls } = setup((id, body) => Promise.resolve(wrap(body,
    body.operation === 'dashboard'
      ? { summary: { requestCount: 42 }, finance: {
          available: false, refreshState: 'queued'
        } }
      : body.operation === 'finance'
        ? { available: true, refreshState: 'ready', balances: [{ value: '5' }] }
        : {}
  )))
  await c.attach(frame, 'a')
  assert.equal(c.snapshot().dashboard.summary.requestCount, 42)
  assert.equal(c.snapshot().finance.refreshState, 'queued')
  await new Promise(resolve => setTimeout(resolve, 5200))
  assert.equal(calls.filter(x => x.body.operation === 'finance').length, 1)
  assert.equal(c.snapshot().dashboard.summary.requestCount, 42)
  assert.equal(c.snapshot().dashboard.finance.refreshState, 'ready')
  c.dispose()
})

test('aggregate export reads all pages with the selected grouping', async () => {
  const { c, calls } = setup((id, body) => {
    if (body.operation !== 'analysis') return Promise.resolve(wrap(body))
    const page = body.payload.page
    return Promise.resolve(wrap(body, {
      rows: Array.from({ length: page === 1 ? 200 : 1 }, (_, i) => ({ label: `row-${(page - 1) * 200 + i + 1}`, metrics: { requestCount: i } })),
      total: 201,
      page,
      pageSize: body.payload.pageSize
    }))
  })
  await c.attach(frame, 'a')
  await c.setView('aggregate')
  const rows = await c.exportAnalysis()
  assert.equal(rows.length, 201)
  assert.equal(rows[200].label, 'row-201')
  const pages = calls.filter(x => x.body.operation === 'analysis' && x.body.payload.pageSize === 200)
  assert.deepEqual(pages.map(x => x.body.payload.page), [1, 2])
  assert.deepEqual(pages[0].body.window, frame.window)
})

test('returning to a previously viewed snapshot shows cached data immediately', async () => {
  let resolveRead
  let block = false
  const { c } = setup((id, body) => {
    if (block && body.operation === 'dashboard') return new Promise(resolve => { resolveRead = resolve })
    return Promise.resolve(wrap(body, { summary: { requestCount: 42 }, customers: [] }))
  })
  await c.attach(frame, 'a')
  await c.attach({ ...frame, dataVersion: 'version-2' }, 'a')
  block = true
  const pending = c.attach(frame, 'a')
  assert.equal(c.snapshot().loading, false)
  assert.equal(c.snapshot().refreshing, true)
  assert.equal(c.snapshot().dashboard.summary.requestCount, 42)
  resolveRead(wrap({ operation: 'dashboard', dataVersion: 'version-1' }, { summary: {}, customers: [] }))
  await pending
})

test('reload reads updated comparison even when snapshot version is unchanged', async () => {
  let comparison = 'UNAVAILABLE'
  const { c, calls } = setup((id, body) => wrap(body, {
    comparison: { state: comparison }, finance: null
  }))
  await c.attach(frame, 'a')
  assert.equal(c.snapshot().dashboard.comparison.state, 'UNAVAILABLE')
  comparison = 'READY'
  await c.reload()
  assert.equal(c.snapshot().dashboard.comparison.state, 'READY')
  assert.equal(calls.filter(x => x.body.operation === 'dashboard').length, 2)
})

test('same snapshot can attach a wider composite window', async () => {
  const { c, calls } = setup((id, body) => wrap(body, dashboardData(1)))
  await c.attach(frame, 'a')
  const wider = { ...frame.window, start: '2026-10-11T00:00:00+08:00' }
  await c.attach({ ...frame, window: wider }, 'a', wider)
  assert.equal(c.snapshot().window.start, wider.start)
  assert.equal(calls.at(-1).body.window.start, wider.start)
})


test('waits for a covering frame when a larger window is selected', async () => {
  const { c } = setup((id, body) => wrap(body, dashboardData(1)))
  await c.attach(frame, 'a')
  const wider = { ...frame.window, start: '2026-10-11T00:00:00+08:00' }
  assert.doesNotThrow(() => c.attach(frame, 'a', wider))
  assert.deepEqual(c.snapshot().window, frame.window)
  await c.attach({ ...frame, window: wider }, 'a', wider)
  assert.deepEqual(c.snapshot().window, wider)
})
