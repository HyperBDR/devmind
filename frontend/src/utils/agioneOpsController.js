const DAY = 86400000
const MAX_POLL_ATTEMPTS = 400
const POLL_DELAYS = [500, 1000, 2000, 3000, 5000, 8000, 10000]
const ACTIVE = new Set(['queued', 'running', 'retrying'])
const TERMINAL = new Set([
  'succeeded',
  'failed',
  'revoked',
  'interrupted',
  'dispatch_failed'
])

export function shanghaiDate(now = new Date()) {
  const parts = new Intl.DateTimeFormat('en', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  }).formatToParts(now)
  const value = (name) => parts.find((part) => part.type === name).value
  return `${value('year')}-${value('month')}-${value('day')}`
}

function dateEpoch(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value || '')) return NaN
  const parsed = Date.parse(`${value}T00:00:00Z`)
  return Number.isFinite(parsed) &&
    new Date(parsed).toISOString().slice(0, 10) === value
    ? parsed
    : NaN
}

export function previousCompleteDay(now = new Date()) {
  const yesterday = new Date(dateEpoch(shanghaiDate(now)) - DAY)
    .toISOString()
    .slice(0, 10)
  return { startDate: yesterday, endDate: yesterday }
}

export function previousCompleteWeek(now = new Date()) {
  const { endDate } = previousCompleteDay(now)
  const startDate = new Date(dateEpoch(endDate) - 6 * DAY)
    .toISOString()
    .slice(0, 10)
  return { startDate, endDate }
}

export function syncWindow(startDate, endDate, now = new Date()) {
  const start = dateEpoch(startDate)
  const end = dateEpoch(endDate)
  const today = dateEpoch(shanghaiDate(now))
  const days = (end - start) / DAY + 1
  if (!Number.isFinite(days) || days < 1 || days > 31 || end >= today) {
    throw new Error('invalidWindow')
  }
  return {
    start: `${startDate}T00:00:00+08:00`,
    endExclusive: `${new Date(end + DAY).toISOString().slice(0, 10)}T00:00:00+08:00`,
    timezone: 'Asia/Shanghai'
  }
}

function initial(now) {
  return {
    connections: [],
    connectionId: '',
    sourceKind: '',
    readOnly: false,
    isLive: false,
    canManageConnections: false,
    configurableConnections: [],
    connectionConfigured: false,
    dashboard: null,
    windowMissing: false,
    run: null,
    loading: false,
    listLoading: false,
    syncing: false,
    previousLoading: false,
    error: '',
    errorCode: '',
    ...previousCompleteWeek(now)
  }
}

export function snapshotWindowDates(data) {
  const window = data?.window
  const aware = (value) =>
    typeof value === 'string' && /T.*(?:Z|[+-]\d{2}:\d{2})$/.test(value)
  if (!aware(window?.start) || !aware(window?.endExclusive)) {
    throw new Error('invalidResponse')
  }
  const start = Date.parse(window?.start)
  const end = Date.parse(window?.endExclusive)
  if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) {
    throw new Error('invalidResponse')
  }
  return {
    startDate: shanghaiDate(new Date(start)),
    endDate: shanghaiDate(new Date(end - 1))
  }
}

function visibleConnections(rows, nativeOnly) {
  const native = rows.filter((row) => row.sourceKind === 'native')
  if (nativeOnly) return native.sort((a, b) =>
    (a.platform === 'pro' ? 0 : 2) +
    (a.principalKind === 'provider' ? 0 : 1) -
    ((b.platform === 'pro' ? 0 : 2) +
      (b.principalKind === 'provider' ? 0 : 1)))
  const available = rows.filter((row) =>
    ['demo_snapshot', 'native'].includes(row.sourceKind))
  if (!available.length) return rows
  const rank = (row) =>
    (row.sourceKind === 'demo_snapshot' ? 0 : 4) +
    (row.platform === 'pro' ? 0 : 2) +
    (row.principalKind === 'provider' ? 0 : 1)
  return available.sort((a, b) => rank(a) - rank(b))
}

function unwrap(response) {
  if (response?.data?.code && response.data.code !== 0) {
    throw new Error('invalidResponse')
  }
  return response?.data?.data
}

function safeError(error) {
  const status = error?.response?.status
  const code = error?.response?.data?.data?.errorCode || ''
  return {
    error: [401, 403, 404].includes(status)
      ? 'accessDenied'
      : status === 409
        ? 'conflict'
        : 'networkError',
    errorCode: /^[A-Z_0-9]{1,80}$/.test(code) ? code : ''
  }
}

export function createAgioneController(api, onChange = () => {}, options = {}) {
  const nativeOnly = options.nativeOnly !== false
  const localNative = options.localNative === true
  const now = options.now || (() => new Date())
  const schedule = options.schedule || ((fn, delay) => setTimeout(fn, delay))
  const cancel = options.cancel || clearTimeout
  const keyFactory =
    options.keyFactory || (() => globalThis.crypto.randomUUID())
  let state = initial(now())
  let session = ''
  let revision = 0
  let queryRevision = 0
  let pollRevision = 0
  let timer = null
  let disposed = false
  let previousRun = false

  function publish(patch) {
    state = { ...state, ...patch }
    if (!disposed) onChange(state)
  }
  const current = (version) => !disposed && !!session && version === revision
  const polling = (version, poll) => current(version) && poll === pollRevision

  function stopPolling() {
    pollRevision += 1
    if (timer !== null) cancel(timer)
    timer = null
  }

  function reset(sessionKey = '') {
    revision += 1
    queryRevision += 1
    stopPolling()
    session = sessionKey
    state = initial(now())
    if (!disposed) onChange(state)
  }

  async function refresh(dataVersion) {
    if (!session || !state.connectionId || disposed) return
    const version = revision
    const query = ++queryRevision
    const id = state.connectionId
    publish({ loading: true, error: '', errorCode: '' })
    try {
      if (localNative && state.sourceKind === 'native') {
        const data = unwrap(await api.dashboard(id, dataVersion,
          syncWindow(state.startDate, state.endDate, now())))
        if (!current(version) || query !== queryRevision) return
        if (!['ready', 'not_collected'].includes(data?.state))
          throw new Error('invalidResponse')
        if (data.state === 'ready' && (
          !data.dataVersion || !data.summary ||
          data.provenance?.kind !== 'native_snapshot'
        )) throw new Error('invalidResponse')
        if (data.window) snapshotWindowDates(data)
        const missing = data.state === 'not_collected' || data.coverage?.partial === true
        publish({ dashboard: data.state === 'not_collected' && state.dashboard?.state === 'ready'
          ? state.dashboard : data, windowMissing: missing,
          loading: false, run: null, syncing: false })
        return
      }
      if (state.isLive) {
        const response = unwrap(await api.liveQuery(id, {
          operation: 'dashboard',
          window: syncWindow(state.startDate, state.endDate, now())
        }))
        if (!current(version) || query !== queryRevision) return
        if (response?.operation !== 'dashboard' ||
            response.provenance?.mode !== 'live' ||
            response.capabilities?.directUpstream !== true ||
            !response.data || !response.window) {
          throw new Error('invalidResponse')
        }
        const frame = {
          ...(response.overview || {}),
          state: 'ready', isLive: true, dataVersion: '',
          requestId: `live:${version}:${query}`,
          window: response.window,
          summary: response.overview?.summary || response.data.summary ||
            response.data.globalSummary || {},
          provenance: response.provenance,
          coverage: response.coverage,
          capabilities: response.capabilities,
          liveResponse: response
        }
        publish({ dashboard: frame, loading: false, run: null,
          syncing: false, ...snapshotWindowDates(frame) })
        return
      }
      const data = unwrap(await api.dashboard(id, dataVersion))
      if (!current(version) || query !== queryRevision) return
      if (!['ready', 'not_collected'].includes(data?.state)) {
        throw new Error('invalidResponse')
      }
      if (data.state === 'ready' && (!data.dataVersion || !data.summary)) {
        throw new Error('invalidResponse')
      }
      let dates = {}
      if (state.readOnly && data.state === 'ready') {
        const source = data.provenance
        if (
          source?.kind !== 'demo_snapshot' ||
          source.readOnly !== true ||
          source.isRealData !== true ||
          source.sourceVersion == null ||
          source.sourceVersion === ''
        )
          throw new Error('invalidResponse')
        dates = snapshotWindowDates(data)
      }
      publish({
        dashboard: data,
        loading: false,
        ...dates,
        ...(state.readOnly ? { run: null, syncing: false } : {})
      })
    } catch (error) {
      if (!current(version) || query !== queryRevision) return
      const failure = safeError(error)
      if (failure.error === 'accessDenied') stopPolling()
      publish({
        ...(state.readOnly && failure.error === 'accessDenied'
          ? { dashboard: null, startDate: '', endDate: '' }
          : {}),
        loading: false,
        ...(failure.error === 'accessDenied'
          ? { run: null, syncing: false }
          : {}),
        ...failure
      })
    }
  }

  async function selectConnection(id) {
    if (!state.connections.some((connection) => connection.id === id)) return
    revision += 1
    queryRevision += 1
    stopPolling()
    const selected = state.connections.find((connection) => connection.id === id)
    const isNative = selected.sourceKind === 'native'
    const isLive = isNative && !localNative
    const readOnly = isNative || selected.sourceKind === 'demo_snapshot'
    const configured = isNative ? selected.readyForLive !== false &&
      selected.hasCredentials !== false : true
    publish({
      connectionId: id,
      sourceKind: selected.sourceKind || '',
      readOnly,
      isLive,
      connectionConfigured: configured,
      ...(readOnly && !isLive && !(localNative && isNative)
        ? { startDate: '', endDate: '' }
        : !state.startDate
          ? previousCompleteWeek(now())
          : {}),
      dashboard: null,
      run: null,
      syncing: false,
      error: '',
      errorCode: '',
      loading: false
    })
    if (isNative && !configured) {
      publish({ error: 'connectionNotConfigured',
        errorCode: 'NATIVE_CONNECTION_NOT_CONFIGURED' })
      return
    }
    await refresh()
  }

  async function load() {
    if (!session || disposed) return
    const version = ++revision
    queryRevision += 1
    stopPolling()
    publish({
      connections: [],
      connectionId: '',
      ...(state.readOnly ? { startDate: '', endDate: '' } : {}),
      readOnly: false,
      dashboard: null,
      run: null,
      listLoading: true,
      loading: false,
      syncing: false,
      error: '',
      errorCode: ''
    })
    try {
      const connections = []
      let canManageConnections = false
      for (let offset = 0, page = 0; page < 20; page += 1) {
        const data = unwrap(await api.connections({ offset }))
        if (!current(version)) return
        if (!Array.isArray(data?.results)) throw new Error('invalidResponse')
        canManageConnections ||= data.capabilities?.canManageConnections === true
        connections.push(
          ...data.results.filter((row) => typeof row?.id === 'string')
        )
        offset += data.results.length
        if (!data.next) break
        if (!data.results.length || page === 19)
          throw new Error('invalidResponse')
      }
      const available = visibleConnections(
        connections.filter((row) => row.enabled === true), nativeOnly)
      publish({ connections: available, listLoading: false,
        canManageConnections,
        configurableConnections: connections.filter((row) =>
          row.sourceKind === 'native'),
        isLive: !localNative &&
          (nativeOnly || available[0]?.sourceKind === 'native'),
        ...(!available.length && nativeOnly ? {
          error: 'nativeNotConfigured',
          errorCode: 'NATIVE_CONNECTION_NOT_CONFIGURED'
        } : {}) })
      if (available.length) await selectConnection(available[0].id)
    } catch (error) {
      if (!current(version)) return
      publish({
        connections: [],
        connectionId: '',
        listLoading: false,
        dashboard: null,
        ...safeError(error)
      })
    }
  }

  function setWindow(startDate, endDate) {
    if (
      state.readOnly &&
      !state.isLive &&
      !(localNative && state.sourceKind === 'native')
    ) return false
    try {
      syncWindow(startDate, endDate, now())
    } catch (_) {
      publish({ error: 'invalidWindow', errorCode: '' })
      return false
    }
    if (state.startDate === startDate && state.endDate === endDate) {
      publish({ error: '', errorCode: '' })
      return true
    }
    revision += 1
    queryRevision += 1
    stopPolling()
    publish({
      startDate,
      endDate,
      previousLoading: false,
      windowMissing: false,
      run: null,
      syncing: false,
      loading: false,
      error: '',
      errorCode: ''
    })
    return true
  }

  async function loadWindow(startDate, endDate) {
    if (!setWindow(startDate, endDate)) return
    const version = revision
    await refresh()
    if (current(version) && state.startDate === startDate &&
        state.endDate === endDate && !state.error &&
        state.windowMissing) await sync()
  }

  async function acceptRun(data, version, poll) {
    if (!polling(version, poll)) return
    if (!data?.runId || ![...ACTIVE, ...TERMINAL].includes(data.status)) {
      throw new Error('invalidResponse')
    }
    publish({ run: data })
    if (data.status === 'succeeded') {
      publish({ syncing: false })
      if (!data.dataVersion) throw new Error('invalidResponse')
      await refresh(previousRun ? undefined : data.dataVersion)
      previousRun = false
      publish({ previousLoading: false })
      return true
    }
    if (TERMINAL.has(data.status)) {
      publish({
        syncing: false,
        previousLoading: false,
        error: 'syncFailed',
        errorCode: /^[A-Z_0-9]{1,80}$/.test(data.errorCode || '')
          ? data.errorCode
          : ''
      })
      return true
    }
    return false
  }

  async function pollRun(id, runId, version, poll, attempts = 0) {
    if (!polling(version, poll)) return
    if (attempts >= MAX_POLL_ATTEMPTS) {
      publish({ syncing: false, previousLoading: false, error: 'pollTimeout', errorCode: '' })
      return
    }
    try {
      const data = unwrap(await api.run(id, runId))
      if (!polling(version, poll)) return
      if (data?.runId !== runId) throw new Error('invalidResponse')
      if (await acceptRun(data, version, poll)) return
      if (!polling(version, poll)) return
      timer = schedule(
        () => pollRun(id, runId, version, poll, attempts + 1),
        POLL_DELAYS[Math.min(attempts + 1, POLL_DELAYS.length - 1)]
      )
    } catch (error) {
      if (!polling(version, poll)) return
      stopPolling()
      const failure = safeError(error)
      publish({
        syncing: false, previousLoading: false,
        ...failure,
        ...(failure.error === 'accessDenied'
          ? { run: null, dashboard: null }
          : {})
      })
    }
  }

  async function sync(previousWindow = null) {
    if (
      state.readOnly &&
      !(localNative && state.sourceKind === 'native')
    ) return refresh()
    if (
      !session ||
      !state.connectionId ||
      state.syncing ||
      disposed ||
      state.error === 'invalidWindow'
    )
      return
    let window
    try {
      window = previousWindow || syncWindow(state.startDate, state.endDate, now())
    } catch (_) {
      publish({ error: 'invalidWindow', errorCode: '' })
      return
    }
    const version = revision
    stopPolling()
    const poll = pollRevision
    const id = state.connectionId
    previousRun = !!previousWindow
    publish({ syncing: true, previousLoading: previousRun, run: null, error: '', errorCode: '' })
    try {
      const data = unwrap(await api.submitSync(id, window, keyFactory()))
      if (!polling(version, poll)) return
      if (!(await acceptRun(data, version, poll)) && polling(version, poll)) {
        timer = schedule(() => pollRun(id, data.runId, version, poll), 500)
      }
    } catch (error) {
      if (!polling(version, poll)) return
      const activeRun = error?.response?.status === 409
        ? error.response.data?.data
        : null
      if (!previousRun && activeRun?.runId && ACTIVE.has(activeRun.status)) {
        publish({ run: activeRun, syncing: true, error: '', errorCode: '' })
        timer = schedule(
          () => pollRun(id, activeRun.runId, version, poll),
          POLL_DELAYS[0]
        )
        return
      }
      const failure = safeError(error)
      publish({
        syncing: false, previousLoading: false,
        ...failure,
        ...(failure.error === 'accessDenied'
          ? { dashboard: null, run: null }
          : {})
      })
    }
  }

  function syncPrevious() {
    const start = dateEpoch(state.startDate)
    const end = dateEpoch(state.endDate)
    const days = (end - start) / DAY + 1
    if (!Number.isInteger(days) || days < 1 || days > 31) return
    const previousEnd = new Date(start - DAY).toISOString().slice(0, 10)
    const previousStart = new Date(start - days * DAY).toISOString().slice(0, 10)
    return sync(syncWindow(previousStart, previousEnd, now()))
  }

  function resume() {
    if (state.readOnly) return refresh()
    if (!session || !state.run || !ACTIVE.has(state.run.status)) return
    stopPolling()
    publish({ syncing: true, error: '', errorCode: '' })
    return pollRun(state.connectionId, state.run.runId, revision, pollRevision)
  }

  function dispose() {
    reset()
    disposed = true
  }

  return {
    snapshot: () => state,
    reset,
    load,
    selectConnection,
    setWindow,
    loadWindow,
    refresh,
    sync,
    syncPrevious,
    resume,
    dispose
  }
}
