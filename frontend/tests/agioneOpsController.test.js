import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import {
  createAgioneController as createLegacyController,
  previousCompleteDay,
  previousCompleteWeek,
  shanghaiDate,
  syncWindow
} from '../src/utils/agioneOpsController.js'
import {
  getAvailablePlatforms,
  getCurrentPlatformKey,
  hasFeature
} from '../src/utils/platformAccess.js'

const createAgioneController = (api, changed, options = {}) => createLegacyController(api, changed, { ...options, nativeOnly: false })

const now = () => new Date('2026-10-25T04:00:00Z')
const response = (data) => ({ data: { code: 0, data } })
const connection = (id = 'connection-1') => ({
  id,
  name: id,
  platform: 'pro',
  principalKind: 'provider',
  enabled: true,
  verifiedAt: '2026-10-24T00:00:00Z',
  sourceKind: 'synthetic'
})
const dashboard = (id = 'version-1') => ({
  state: 'ready',
  dataVersion: id,
  summary: {
    requests: 4,
    success: 2,
    failure: 1,
    unknown: 1,
    successRate: 50
  },
  trend: [],
  modelDistribution: []
})
const deferred = () => {
  let resolve
  let reject
  const promise = new Promise((done, fail) => {
    resolve = done
    reject = fail
  })
  return { promise, resolve, reject }
}
function harness(overrides = {}) {
  const calls = []
  const queue = new Map()
  let timer = 0
  const api = {
    connections: async (options) => {
      calls.push(['connections', options])
      return response({ results: [connection()], count: 1, next: null })
    },
    dashboard: async (id, version) => {
      calls.push(['dashboard', id, version])
      return response(dashboard(version))
    },
    submitSync: async (id, window, key) => {
      calls.push(['submit', id, window, key])
      return response({ runId: 'run-1', status: 'queued', totalCount: null })
    },
    run: async (id, runId) => {
      calls.push(['run', id, runId])
      return response({
        runId,
        status: 'succeeded',
        dataVersion: 'published-1'
      })
    },
    ...overrides
  }
  const controller = createAgioneController(api, () => {}, {
    now,
    keyFactory: () => 'synthetic-idempotency-key',
    schedule: (callback) => {
      queue.set(++timer, callback)
      return timer
    },
    cancel: (id) => queue.delete(id)
  })
  controller.reset('synthetic-account-session')
  return {
    controller,
    calls,
    queue,
    api,
    async tick() {
      const [id, fn] = queue.entries().next().value || []
      if (fn) {
        queue.delete(id)
        await fn()
      }
    }
  }
}

test('Shanghai dates use complete local days, not browser UTC defaults', () => {
  assert.equal(shanghaiDate(new Date('2026-10-24T20:00:00Z')), '2026-10-25')
  assert.deepEqual(previousCompleteDay(now()), {
    startDate: '2026-10-24',
    endDate: '2026-10-24'
  })
  assert.deepEqual(previousCompleteWeek(now()), {
    startDate: '2026-10-18',
    endDate: '2026-10-24'
  })
  assert.deepEqual(syncWindow('2026-09-30', '2026-10-01', now()), {
    start: '2026-09-30T00:00:00+08:00',
    endExclusive: '2026-10-02T00:00:00+08:00',
    timezone: 'Asia/Shanghai'
  })
  for (const [start, end] of [
    ['2026-02-30', '2026-03-01'],
    ['2026-10-25', '2026-10-25'],
    ['2026-10-24', '2026-10-23'],
    ['2026-09-01', '2026-10-24']
  ])
    assert.throws(() => syncWindow(start, end, now()), /invalidWindow/)
})

test('authorized load reads actual dashboard without any automatic sync', async () => {
  const { controller, calls } = harness()
  await controller.load()
  assert.equal(controller.snapshot().dashboard.summary.requests, 4)
  assert.deepEqual(
    calls.map((x) => x[0]),
    ['connections', 'dashboard']
  )
  assert.equal(controller.snapshot().connectionId, 'connection-1')
})

test('pagination uses offsets, never follows an external next URL', async () => {
  const offsets = []
  const { controller } = harness({
    connections: async ({ offset }) => {
      offsets.push(offset)
      return response({
        results: [connection(`connection-${offset}`)],
        next: offset ? null : 'https://untrusted.example/credentials'
      })
    }
  })
  await controller.load()
  assert.deepEqual(offsets, [0, 1])
  assert.equal(controller.snapshot().connections.length, 2)
})

test('disabled connections are not offered as executable sources', async () => {
  const { controller } = harness({
    connections: async () =>
      response({
        results: [{ ...connection(), enabled: false }],
        next: null
      })
  })
  await controller.load()
  assert.equal(controller.snapshot().connectionId, '')
  assert.deepEqual(controller.snapshot().connections, [])
})

test('a new session clears data and ignores an old connections response', async () => {
  const late = deferred()
  const { controller } = harness({ connections: () => late.promise })
  const pending = controller.load()
  controller.reset('different-account')
  late.resolve(response({ results: [connection()], next: null }))
  await pending
  assert.equal(controller.snapshot().dashboard, null)
  assert.deepEqual(controller.snapshot().connections, [])
})

test('switching connections ignores the previous dashboard response', async () => {
  const late = deferred()
  const { controller } = harness({
    connections: async () =>
      response({ results: [connection('a'), connection('b')], next: null }),
    dashboard: (id) =>
      id === 'a' ? late.promise : response(dashboard('version-b'))
  })
  const pending = controller.load()
  await Promise.resolve()
  await controller.selectConnection('b')
  late.resolve(response(dashboard('version-a')))
  await pending
  assert.equal(controller.snapshot().connectionId, 'b')
  assert.equal(controller.snapshot().dashboard.dataVersion, 'version-b')
})

test('latest refresh wins over an earlier slow request', async () => {
  const h = harness()
  await h.controller.load()
  const late = deferred()
  h.api.dashboard = (id, version) =>
    version === 'old' ? late.promise : response(dashboard(version))
  const old = h.controller.refresh('old')
  await h.controller.refresh('new')
  late.resolve(response(dashboard('old')))
  await old
  assert.equal(h.controller.snapshot().dashboard.dataVersion, 'new')
})

test('manual sync sends a real exclusive window and an idempotency key', async () => {
  const h = harness()
  await h.controller.load()
  await h.controller.sync()
  assert.equal(h.controller.snapshot().syncing, true)
  const sent = h.calls.find((x) => x[0] === 'submit')
  assert.equal(sent[1], 'connection-1')
  assert.equal(sent[2].start, '2026-10-18T00:00:00+08:00')
  assert.equal(sent[2].endExclusive, '2026-10-25T00:00:00+08:00')
  assert.equal(sent[3], 'synthetic-idempotency-key')
  await h.tick()
  assert.equal(h.controller.snapshot().syncing, false)
  assert.equal(h.controller.snapshot().dashboard.dataVersion, 'published-1')
  assert.equal(h.queue.size, 0)
})

test('an eager completed run loads its exact version without polling', async () => {
  const h = harness({
    submitSync: async () =>
      response({
        runId: 'run-eager',
        status: 'succeeded',
        dataVersion: 'eager-version'
      })
  })
  await h.controller.load()
  await h.controller.sync()
  assert.equal(h.controller.snapshot().dashboard.dataVersion, 'eager-version')
  assert.equal(
    h.calls.some((x) => x[0] === 'run'),
    false
  )
  assert.equal(h.queue.size, 0)
})

for (const status of ['failed', 'revoked', 'interrupted', 'dispatch_failed']) {
  test(`terminal ${status} stops polling without inventing a successful snapshot`, async () => {
    const h = harness({
      run: async () =>
        response({
          runId: 'run-1',
          status,
          errorCode: 'SOURCE_IDENTITY_MISMATCH'
        })
    })
    await h.controller.load()
    await h.controller.sync()
    await h.tick()
    assert.equal(h.controller.snapshot().error, 'syncFailed')
    assert.equal(h.controller.snapshot().run.status, status)
    assert.equal(h.controller.snapshot().syncing, false)
    assert.equal(h.controller.snapshot().dashboard.dataVersion, 'version-1')
    assert.equal(h.queue.size, 0)
  })
}

test('access rejection clears displayed data and does not reveal raw error text', async () => {
  const h = harness({
    run: async () => {
      throw {
        response: {
          status: 403,
          data: { data: { errorCode: '<private>', detail: 'secret response' } }
        }
      }
    }
  })
  await h.controller.load()
  await h.controller.sync()
  await h.tick()
  assert.equal(h.controller.snapshot().dashboard, null)
  assert.equal(h.controller.snapshot().run, null)
  assert.equal(h.controller.snapshot().error, 'accessDenied')
  assert.equal(h.controller.snapshot().errorCode, '')
  assert.equal(
    JSON.stringify(h.controller.snapshot()).includes('secret response'),
    false
  )
})

test('logout cancels timers and suppresses an in-flight progress result', async () => {
  const late = deferred()
  const h = harness({ run: () => late.promise })
  await h.controller.load()
  await h.controller.sync()
  const checking = h.tick()
  h.controller.reset()
  late.resolve(
    response({
      runId: 'run-1',
      status: 'succeeded',
      dataVersion: 'private-old-version'
    })
  )
  await checking
  assert.equal(h.controller.snapshot().dashboard, null)
  assert.equal(h.controller.snapshot().run, null)
  assert.equal(h.queue.size, 0)
})

test('changing dates keeps the last usable data while a new sync is pending', async () => {
  const h = harness()
  await h.controller.load()
  await h.controller.sync()
  const previous = h.controller.snapshot().dashboard
  assert.equal(h.controller.setWindow('2026-10-22', '2026-10-23'), true)
  assert.deepEqual(h.controller.snapshot().dashboard, previous)
  assert.equal(h.controller.snapshot().run, null)
  assert.equal(h.queue.size, 0)
  assert.equal(h.controller.setWindow('2026-10-26', '2026-10-26'), false)
  await h.controller.sync()
  assert.equal(h.calls.filter((x) => x[0] === 'submit').length, 1)
})

test('CONNECTION_BUSY keeps the previous dashboard and exposes the conflict', async () => {
  const h = harness({
    submitSync: async () => {
      throw { response: { status: 409, data: { data: {
        errorCode: 'CONNECTION_BUSY'
      } } } }
    }
  })
  await h.controller.load()
  const previous = h.controller.snapshot().dashboard
  await h.controller.sync()
  assert.deepEqual(h.controller.snapshot().dashboard, previous)
  assert.equal(h.controller.snapshot().error, 'conflict')
  assert.equal(h.controller.snapshot().errorCode, 'CONNECTION_BUSY')
  assert.equal(h.controller.snapshot().syncing, false)
})

test('CONNECTION_BUSY attaches to the returned active run', async () => {
  const h = harness({
    submitSync: async () => {
      throw { response: { status: 409, data: { data: {
        runId: 'existing-run', status: 'running', phase: 'finance'
      } } } }
    },
    run: async (_, runId) => response({
      runId, status: 'succeeded', dataVersion: 'published-existing'
    })
  })
  await h.controller.load()
  await h.controller.sync()
  assert.equal(h.controller.snapshot().run.runId, 'existing-run')
  assert.equal(h.controller.snapshot().syncing, true)
  await h.tick()
  assert.equal(h.controller.snapshot().dashboard.dataVersion, 'published-existing')
})

test('polling is bounded, and resume checks the same task without resubmitting', async () => {
  const h = harness({
    run: async () => response({ runId: 'run-1', status: 'running' })
  })
  await h.controller.load()
  await h.controller.sync()
  for (let i = 0; i < 401; i += 1) await h.tick()
  assert.equal(h.controller.snapshot().error, 'pollTimeout')
  assert.equal(h.queue.size, 0)
  await h.controller.resume()
  assert.equal(h.controller.snapshot().syncing, true)
  assert.equal(h.calls.filter((x) => x[0] === 'submit').length, 1)
  h.controller.dispose()
  assert.equal(h.queue.size, 0)
})

test('AGIOne occupies the old position without inheriting the old permission', () => {
  const user = {
    access_profile: { visible_features: ['llm_ops'], available_platforms: [] }
  }
  assert.equal(hasFeature(user, 'agione_ops'), false)
  assert.equal(
    getAvailablePlatforms(user).some((x) => x.key === 'agione_ops'),
    false
  )
  user.access_profile.visible_features.push('agione_ops')
  const entry = getAvailablePlatforms(user).find((x) => x.key === 'agione_ops')
  assert.equal(entry.defaultPath, '/agione')
  assert.equal(getCurrentPlatformKey('/agione'), 'agione_ops')
  assert.equal(getCurrentPlatformKey('/llm-ops'), 'agione_ops')
  assert.equal(getCurrentPlatformKey('/llm-ops/archive'), 'agione_ops')
  const source = readFileSync(
    new URL('../src/router/index.js', import.meta.url),
    'utf8'
  )
  const root = source.split("path: '/agione'")[1].split('path:')[0]
  assert.match(root, /requiredFeature: 'agione_ops'/)
  assert.match(root, /pages\/AgioneOps\.vue/)
  assert.doesNotMatch(root, /appKey/)
})

test('visible page uses the backend and real versions, never static business fixtures', () => {
  const source = readFileSync(
    new URL('../src/pages/AgioneOps.vue', import.meta.url),
    'utf8'
  )
  assert.match(source, /data-testid="agione-operations"/)
  assert.match(source, /createAgioneController\(agioneOpsApi/)
  assert.match(source, /state\.dashboard\?\.dataVersion/)
  assert.match(source, /data-demo-origin="AGIone\/static\/index.html"/)
  assert.match(source, /class="shell"/)
  assert.match(source, /class="sidebar"/)
  assert.match(source, /class="dashboard-columns"/)
  assert.match(source, /agione-demo\/demo-scoped.css/)
  assert.doesNotMatch(source, /AppLayout|llm-ops\/archive|agione-kpi/)
  assert.match(source, /agione\.syntheticNotice/)
  assert.match(source, /createAgioneController\(agioneOpsApi, \(next\) => \{/)
  assert.doesNotMatch(source, /v-html|localStorage|8011|iframe|Math\.random/)
  const en = JSON.parse(
    readFileSync(new URL('../src/locales/en.json', import.meta.url))
  ).agione
  const zh = JSON.parse(
    readFileSync(new URL('../src/locales/zh-CN.json', import.meta.url))
  ).agione
  assert.deepEqual(Object.keys(en).sort(), Object.keys(zh).sort())
  assert.deepEqual(
    Object.keys(en.errors).sort(),
    Object.keys(zh.errors).sort()
  )
  assert.deepEqual(
    Object.keys(en.status).sort(),
    Object.keys(zh.status).sort()
  )
})
