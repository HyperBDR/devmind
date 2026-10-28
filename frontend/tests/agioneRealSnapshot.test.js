import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { createAgioneController as createLegacyController } from '../src/utils/agioneOpsController.js'

const createAgioneController = (api, changed, options = {}) => createLegacyController(api, changed, { ...options, nativeOnly: false })

const response = (data) => ({ data: { code: 0, data } })
const source = (id, platform = 'pro', principalKind = 'provider') => ({
  id,
  platform,
  principalKind,
  sourceKind: 'demo_snapshot',
  enabled: true,
  verifiedAt: null
})
const synthetic = { ...source('fake'), sourceKind: 'synthetic' }
const real = (
  version = 'demo-cache-v1',
  start = '2026-10-01',
  end = '2026-10-14'
) => ({
  state: 'ready',
  dataVersion: `bff-${version}`,
  window: {
    start: `${start}T00:00:00+08:00`,
    endExclusive: `${end}T10:53:09+08:00`,
    timezone: 'Asia/Shanghai'
  },
  publishedAt: '2026-10-14T02:53:09Z',
  provenance: {
    kind: 'demo_snapshot',
    readOnly: true,
    isRealData: true,
    sourceVersion: version,
    collectedAt: '2026-10-14T02:53:09Z',
    stale: true
  },
  summary: { requests: 12431, success: 12300, failure: 131, unknown: 0 },
  trend: [],
  modelDistribution: []
})
const deferred = () => {
  let resolve
  const promise = new Promise((done) => {
    resolve = done
  })
  return { promise, resolve }
}
function setup(overrides = {}, options = {}) {
  const calls = []
  const api = {
    connections: async () =>
      response({ results: [source('real')], next: null }),
    dashboard: async (id) => {
      calls.push(['read', id])
      return response(real())
    },
    submitSync: async () => {
      calls.push(['submit'])
      throw new Error('No collection allowed')
    },
    run: async () => {
      calls.push(['poll'])
      throw new Error('No task allowed')
    },
    ...overrides
  }
  const controller = createAgioneController(api, () => {}, {
    now: () => new Date('2026-10-25T12:00:00Z'),
    keyFactory: () => {
      throw new Error('Read-only needs no idempotency key')
    },
    schedule: () => {
      throw new Error('Read-only needs no task timer')
    },
    ...options
  })
  controller.reset('admin-session')
  return { controller, calls, api }
}

test('real sources exclude synthetic sources and use original Pro/provider order', async () => {
  const { controller, calls } = setup({
    connections: async () =>
      response({
        results: [
          synthetic,
          source('cc-op', 'cc', 'operator'),
          source('pro-op', 'pro', 'operator'),
          source('cc-provider', 'cc'),
          source('pro-provider')
        ],
        next: null
      })
  })
  await controller.load()
  assert.deepEqual(
    controller.snapshot().connections.map((x) => x.id),
    ['pro-provider', 'pro-op', 'cc-provider', 'cc-op']
  )
  assert.equal(controller.snapshot().connectionId, 'pro-provider')
  assert.equal(controller.snapshot().readOnly, true)
  assert.deepEqual(calls, [['read', 'pro-provider']])
})

test('snapshot is preferred while native verification remains selectable', async () => {
  const native = {
    ...source('pro-provider-native'),
    sourceKind: 'native',
    hasCredentials: true,
    readyForLive: true
  }
  const { controller } = setup({
    connections: async () => response({
      results: [native, source('pro-provider-snapshot')],
      next: null
    })
  })
  await controller.load()
  assert.deepEqual(
    controller.snapshot().connections.map((x) => x.id),
    ['pro-provider-snapshot', 'pro-provider-native']
  )
  assert.equal(controller.snapshot().connectionId, 'pro-provider-snapshot')
})

test('real sources found on later list pages never briefly query synthetic data', async () => {
  const { controller, calls } = setup({
    connections: async ({ offset }) =>
      response({
        results: offset ? [source('real')] : [synthetic],
        next: offset ? null : '/next'
      })
  })
  await controller.load()
  assert.deepEqual(
    controller.snapshot().connections.map((x) => x.id),
    ['real']
  )
  assert.deepEqual(calls, [['read', 'real']])
})

test('cached source dates and original provenance replace yesterday defaults', async () => {
  const { controller } = setup()
  await controller.load()
  const state = controller.snapshot()
  assert.equal(state.startDate, '2026-10-01')
  assert.equal(state.endDate, '2026-10-14')
  assert.equal(state.dashboard.summary.requests, 12431)
  assert.equal(state.dashboard.publishedAt, '2026-10-14T02:53:09Z')
  assert.equal(state.dashboard.provenance.sourceVersion, 'demo-cache-v1')
  assert.equal(state.dashboard.provenance.stale, true)
})

test('refresh, accidental sync and resume only read the existing snapshot', async () => {
  const { controller, calls } = setup()
  await controller.load()
  await controller.refresh()
  await controller.sync()
  await controller.resume()
  assert.deepEqual(
    calls.map((x) => x[0]),
    ['read', 'read', 'read', 'read']
  )
  assert.equal(controller.snapshot().run, null)
  assert.equal(controller.snapshot().syncing, false)
})

test('read-only dates cannot be changed or used to request backfill', async () => {
  const { controller, calls } = setup()
  await controller.load()
  assert.equal(controller.setWindow('2026-10-18', '2026-10-24'), false)
  assert.equal(controller.snapshot().startDate, '2026-10-01')
  assert.equal(controller.snapshot().endDate, '2026-10-14')
  assert.equal(controller.snapshot().error, '')
  await controller.sync()
  assert.deepEqual(
    calls.map((x) => x[0]),
    ['read', 'read']
  )
})

test('switching real sources uses their own dates rather than a unified window', async () => {
  const { controller } = setup({
    connections: async () =>
      response({ results: [source('a'), source('b')], next: null }),
    dashboard: async (id) =>
      response(id === 'a' ? real('a') : real('b', '2026-09-20', '2026-09-29'))
  })
  await controller.load()
  await controller.selectConnection('b')
  assert.equal(controller.snapshot().startDate, '2026-09-20')
  assert.equal(controller.snapshot().endDate, '2026-09-29')
  assert.equal(controller.snapshot().dashboard.provenance.sourceVersion, 'b')
})

test('a failed real request does not fall back to synthetic data', async () => {
  const { controller, calls } = setup({
    connections: async () =>
      response({ results: [synthetic, source('real')], next: null }),
    dashboard: async (id) => {
      calls.push(['read', id])
      throw { response: { status: 503 } }
    }
  })
  await controller.load()
  assert.equal(controller.snapshot().connectionId, 'real')
  assert.equal(controller.snapshot().readOnly, true)
  assert.equal(controller.snapshot().dashboard, null)
  assert.equal(controller.snapshot().startDate, '')
  assert.equal(controller.snapshot().endDate, '')
  assert.equal(controller.snapshot().error, 'networkError')
  assert.deepEqual(calls, [['read', 'real']])
})

for (const status of [401, 403, 404]) {
  test(`real ${status} clears cached metrics, version and dates`, async () => {
    const h = setup()
    await h.controller.load()
    h.api.dashboard = async () => {
      throw { response: { status } }
    }
    await h.controller.refresh()
    assert.equal(h.controller.snapshot().dashboard, null)
    assert.equal(h.controller.snapshot().run, null)
    assert.equal(h.controller.snapshot().startDate, '')
    assert.equal(h.controller.snapshot().endDate, '')
    assert.equal(h.controller.snapshot().error, 'accessDenied')
  })
}

for (const invalid of [
  (data) => {
    delete data.provenance
  },
  (data) => {
    data.provenance.kind = 'synthetic'
  },
  (data) => {
    data.provenance.isRealData = false
  },
  (data) => {
    data.provenance.readOnly = false
  },
  (data) => {
    data.provenance.sourceVersion = null
  },
  (data) => {
    delete data.window
  },
  (data) => {
    data.window.start = '2026-10-01T00:00:00'
  }
]) {
  test(`real response fails closed for invalid metadata #${invalid.toString()}`, async () => {
    const data = real()
    invalid(data)
    const { controller } = setup({ dashboard: async () => response(data) })
    await controller.load()
    assert.equal(controller.snapshot().dashboard, null)
    assert.equal(controller.snapshot().readOnly, true)
    assert.equal(controller.snapshot().startDate, '')
    assert.equal(controller.snapshot().error, 'networkError')
  })
}

test('a late response cannot replace the current real source or its dates', async () => {
  const late = deferred()
  const { controller } = setup({
    connections: async () =>
      response({ results: [source('a'), source('b')], next: null }),
    dashboard: (id) =>
      id === 'a'
        ? late.promise
        : response(real('b', '2026-09-20', '2026-09-29'))
  })
  const loading = controller.load()
  await Promise.resolve()
  await controller.selectConnection('b')
  late.resolve(response(real('a')))
  await loading
  assert.equal(controller.snapshot().connectionId, 'b')
  assert.equal(controller.snapshot().startDate, '2026-09-20')
  assert.equal(controller.snapshot().dashboard.provenance.sourceVersion, 'b')
})

test('account change clears real data and ignores old-account response', async () => {
  const h = setup()
  await h.controller.load()
  const late = deferred()
  h.api.dashboard = () => late.promise
  const previous = h.controller.refresh()
  h.controller.reset('different-account')
  assert.equal(h.controller.snapshot().readOnly, false)
  assert.equal(h.controller.snapshot().dashboard, null)
  late.resolve(response(real('private-old')))
  await previous
  assert.equal(h.controller.snapshot().dashboard, null)
  assert.deepEqual(h.controller.snapshot().connections, [])
})

test('synthetic-only users retain explicit synthetic mode and existing sync support', async () => {
  let submitted = false
  const { controller } = setup(
    {
      connections: async () => response({ results: [synthetic], next: null }),
      dashboard: async () =>
        response({
          state: 'ready',
          dataVersion: 'fixture-v1',
          summary: { requests: 4 }
        }),
      submitSync: async () => {
        submitted = true
        return response({
          runId: 'fixture-run',
          status: 'succeeded',
          dataVersion: 'fixture-v1'
        })
      }
    },
    { keyFactory: () => 'synthetic-only-key' }
  )
  await controller.load()
  assert.equal(controller.snapshot().readOnly, false)
  assert.equal(controller.snapshot().connectionId, 'fake')
  assert.equal(controller.setWindow('2026-10-20', '2026-10-24'), true)
  await controller.sync()
  assert.equal(controller.snapshot().error, '')
  assert.equal(controller.snapshot().run.status, 'succeeded')
  assert.equal(submitted, true)
})

test('original Demo source exposes truthful read-only controls and metadata', () => {
  const page = readFileSync(
    new URL('../src/pages/AgioneOps.vue', import.meta.url),
    'utf8'
  )
  const zh = JSON.parse(
    readFileSync(new URL('../src/locales/zh-CN.json', import.meta.url), 'utf8')
  ).agione
  assert.match(
    page,
    /if \(readOnly\.value\)\s*return controller\.refresh\(\)/
  )
  assert.match(page, /v-if="state\.run && !readOnly"/)
  assert.match(page, /workspace\.setWindow\(queryWindow\)/)
  assert.match(page, /navigateWorkspace\('aggregate'\)/)
  assert.match(page, /navigateWorkspace\('portrait'\)/)
  assert.match(page, /provenance\?\.sourceVersion/)
  assert.equal(zh.realSnapshotBadge, '真实历史快照 · 只读 · 非实时')
  assert.equal(zh.refreshSnapshot, '刷新数据')
  assert.equal(zh.previousNotIntegrated, '前期比较尚未接入')
  assert.equal(zh.readOnlyRangeHelp, '北京时间，含起止当天，不含今天')
  assert.match(zh.staleSnapshot, /截至时间/)
})
