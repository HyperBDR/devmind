const VIEWS = new Set(['focus', 'aggregate', 'portrait'])
const empty = () => ({
  view: 'focus',
  connectionId: '',
  dataVersion: '',
  isLive: false,
  requestId: '',
  provenance: null,
  window: null,
  cachedWindow: null,
  overview: null,
  customerIds: [],
  filters: { modelIds: [], statuses: [], failureTypes: [] },
  loading: false,
  refreshing: false,
  stale: false,
  error: '',
  analysis: null,
  trend: null,
  customers: null,
  profile: null,
  selectedCustomerId: '',
  memberOptions: [],
  customerOptions: [],
  directory: null, directoryLoading: false, directoryError: '',
  modelOptions: [],
  finance: null,
  dashboard: null,
  capabilities: {},
  coverage: null,
  forceSelected: false,
  drawer: null,
  drawerLoading: false,
  drawerError: '',
  evidence: null,
  groupBy: 'customerTenantId',
  secondary: '',
  metric: 'requestCount',
  userId: '',
  analysisPage: 1,
  customerPage: 1,
  search: '',
  signal: ''
})
const unwrap = (response) => response?.data?.data
const denied = (error) => [401, 403, 404].includes(error?.response?.status)
const failure = (error) => {
  const code = error?.response?.data?.data?.errorCode
  const messages = {
    WINDOW_NOT_CACHED: '所选日期未采集，不会自动补采。',
    DEMO_WINDOW_OUTSIDE_SNAPSHOT: '所选日期超出已缓存范围。',
    DATA_VERSION_EXPIRED: '指定快照已不可用，请显式刷新连接。',
    DEMO_SOURCE_CHANGED: '原 Demo 来源身份已变化，需要重新核验。',
    SOURCE_TIMEOUT: '上游读取超时，请稍后重试。',
    SOURCE_UNREACHABLE: '暂时无法连接上游，请稍后重试。'
  }
  if (typeof code === 'string' && /^[A-Z_0-9]{1,100}$/.test(code))
    return `${messages[code] || '当前页面读取失败，请重试。'} (${code})`
  return error?.message === '快照版本发生变化，请刷新后重试'
    ? error.message
    : '当前接口读取失败，请检查连接配置和读取权限。'
}

export function viewFromHash(hash = '') {
  const view = hash.replace(/^#/, '')
  return VIEWS.has(view) ? view : 'focus'
}

export async function requestPreviousComparison(workspace, controller) {
  const before = workspace.snapshot()
  const selection = controller.snapshot()
  const context = JSON.stringify([
    before.view, before.connectionId, before.filters, before.customerIds,
    selection.startDate, selection.endDate
  ])
  const unchanged = () => {
    const view = workspace.snapshot()
    const current = controller.snapshot()
    return JSON.stringify([
      view.view, view.connectionId, view.filters, view.customerIds,
      current.startDate, current.endDate
    ]) === context
  }
  if (before.view !== 'focus' || selection.syncing) return
  await controller.refresh()
  if (!unchanged() || controller.snapshot().error ||
      controller.snapshot().syncing) return
  if (controller.snapshot().windowMissing) return 'current_required'
  await workspace.reload()
  const after = workspace.snapshot()
  if (!unchanged() || after.error || controller.snapshot().syncing) return
  if (after.coverage?.partial) return 'current_required'
  if (after.dashboard?.comparison?.state !== 'READY')
    await controller.syncPrevious()
}

export function createAgioneWorkspaceController(api, onChange = () => {}) {
  let state = empty(),
    session = '',
    epoch = 0,
    request = 0,
    detail = 0,
    directoryRevision = 0,
    disposed = false
  const pageCache = new Map()
  const profileCache = new Map()
  const optionsCache = new Map()
  const inFlight = new Map()
  let authEpoch = 0
  let activeLoad = null
  let financeTimer = null
  const canonical = (value) => JSON.stringify(value, (_, item) => {
    if (!item || typeof item !== 'object' || Array.isArray(item)) return item
    return Object.fromEntries(Object.entries(item).sort(([a], [b]) =>
      a.localeCompare(b)))
  })
  const cancelled = (error) => error?.name === 'AbortError' ||
    error?.name === 'CanceledError' || error?.code === 'ERR_CANCELED'
  const domain = () => canonical([session, authEpoch, state.connectionId])
  function clearWork(keepPages = false) {
    clearTimeout(financeTimer)
    financeTimer = null
    if (!keepPages) pageCache.clear()
    profileCache.clear()
    optionsCache.clear()
    activeLoad = null
    for (const entry of inFlight.values()) entry.controller?.abort()
    inFlight.clear()
  }
  const pageFields = [
    'analysis', 'trend', 'customers', 'profile', 'dashboard', 'overview',
    'finance', 'capabilities', 'coverage', 'selectedCustomerId'
  ]
  function pageKey() {
    const payload = state.view === 'aggregate'
      ? [state.groupBy, state.secondary, state.metric, state.userId,
        state.analysisPage]
      : state.view === 'portrait'
        ? [state.customerPage, state.search, state.signal,
          state.forceSelected ? state.selectedCustomerId : ''] : {}
    return canonical([domain(), state.dataVersion, state.requestId,
      state.isLive, state.window, state.customerIds, state.filters, state.view,
      payload])
  }
  function profileKey(customerId) {
    return canonical([
      domain(), state.connectionId, state.dataVersion, state.requestId,
      state.isLive, state.window, state.customerIds, state.filters,
      customerId
    ])
  }
  function rememberProfile(key, value) {
    profileCache.delete(key)
    profileCache.set(key, value)
    while (profileCache.size > 48)
      profileCache.delete(profileCache.keys().next().value)
  }
  function remember(key, generation, seq) {
    if (!valid(generation, seq)) return
    const page = Object.fromEntries(pageFields.map((key) => [key, state[key]]))
    pageCache.delete(key)
    pageCache.set(key, page)
    while (pageCache.size > 24) pageCache.delete(pageCache.keys().next().value)
  }
  const dashboardTrend = (data = {}) => ({
    summary: data.summary || {},
    globalSummary: data.globalSummary || data.summary || {},
    series: data.trend || [],
    previousSeries: data.previousTrend || null,
    comparisonReason: data.comparison?.reason || '前期尚未读取',
    comparisonBasis: data.comparison?.basis || 'CURRENT_WINDOW'
  })
  const publish = (patch) => {
    state = { ...state, ...patch, contextKey: `${epoch}:${request}` }
    if (!disposed) onChange(state)
  }
  const valid = (generation, seq) =>
    !disposed && !!session && epoch === generation && request === seq
  const body = (operation, payload = {}, extra = {}) => ({
    operation,
    ...(!state.isLive ? { dataVersion: state.dataVersion } : {}),
    ...(state.window ? { window: state.window } : {}),
    ...(state.customerIds.length ? { customerIds: state.customerIds } : {}),
    filters: state.filters,
    payload,
    ...extra
  })
  function call(operation, payload = {}, extra = {}) {
    const live = state.isLive
    const version = state.dataVersion
    const connectionId = state.connectionId
    const authorizationDomain = domain()
    const generation = epoch
    const query = operation === 'finance'
      ? { operation, ...(!live ? { dataVersion: version } : {}),
          ...(state.window ? { window: state.window } : {}), payload }
      : body(operation, payload, extra)
    const key = canonical([authorizationDomain, generation, state.view,
      state.requestId, live, query])
    if (inFlight.has(key)) {
      const pending = inFlight.get(key)
      pending.seq = request
      return pending.promise
    }
    const controller = typeof AbortController === 'function'
      ? new AbortController() : null
    const entry = { controller, promise: null, seq: request }
    entry.promise = (async () => {
      try {
        const response = unwrap(await (live ? api.liveQuery : api.snapshotQuery)(
          connectionId, query, controller ? { signal: controller.signal } : {}
        ))
        if (!response || response.operation !== operation)
          throw new Error('接口响应不符合当前操作')
        if (live) {
          if (response.provenance?.mode !== 'live' ||
              response.capabilities?.directUpstream !== true)
            throw new Error('原生直连接口返回了非实时数据')
        } else if (response.dataVersion !== version) {
          throw new Error('快照版本发生变化，请刷新后重试')
        }
        return response
      } catch (error) {
        if (!cancelled(error) && authorizationDomain === domain() && !disposed)
          authorizationFailure(error)
        throw error
      } finally {
        if (inFlight.get(key) === entry) inFlight.delete(key)
      }
    })()
    inFlight.set(key, entry)
    while (inFlight.size > 48) {
      const oldest = inFlight.keys().next().value
      inFlight.get(oldest).controller?.abort()
      inFlight.delete(oldest)
    }
    return entry.promise
  }
  function authorizationFailure(error) {
    if (denied(error)) {
      epoch++
      request++
      detail++
      clearWork()
      directoryRevision++
      publish({ ...empty(), view: state.view,
        connectionId: state.connectionId,
        error: '权限已变化，旧数据已清空，请重新读取连接。'
      })
      return true
    }
    return false
  }
  function reset(key = '') {
    clearWork()
    authEpoch++
    epoch++
    request++
    detail++
    session = key
    state = empty()
    if (!disposed) onChange(state)
  }
  function attach(frame, connectionId, selectedWindow = null) {
    const live = frame?.isLive === true && frame?.provenance?.mode === 'live'
    const frameKey = live ? frame.requestId : frame?.dataVersion
    if (!frameKey || !connectionId) {
      if (state.connectionId) {
        clearWork()
        authEpoch++
        epoch++
        request++
        detail++
        publish({ ...empty(), view: state.view })
      }
      return
    }
    if (
      state.connectionId === connectionId &&
      (live ? state.requestId === frameKey : state.dataVersion === frameKey)
    ) {
      if (selectedWindow && frame.window &&
          Date.parse(selectedWindow.start) >= Date.parse(frame.window.start) &&
          Date.parse(selectedWindow.endExclusive) <= Date.parse(frame.window.endExclusive) &&
          canonical(selectedWindow) !== canonical(state.window)) {
        publish({ cachedWindow: frame.window })
        return setWindow(selectedWindow)
      }
      return
    }
    const view = state.view
    const retain = state.connectionId === connectionId && !live &&
      (view === 'focus' ? state.dashboard :
        view === 'aggregate' ? state.analysis : state.customers)
    const retained = retain
      ? Object.fromEntries(pageFields.map((key) => [key, state[key]])) : {}
    clearWork(state.connectionId === connectionId && !live)
    if (state.connectionId !== connectionId) authEpoch++
    epoch++
    request++
    detail++
    const selectedFits = !live && selectedWindow && frame.window &&
      Date.parse(selectedWindow.start) >= Date.parse(frame.window.start) &&
      Date.parse(selectedWindow.endExclusive) <= Date.parse(frame.window.endExclusive)
    const effectiveWindow = selectedFits ? selectedWindow : frame.window
    publish({
      ...empty(),
      ...retained,
      stale: !!retain,
      view,
      connectionId,
      dataVersion: live ? '' : frame.dataVersion,
      isLive: live,
      requestId: live ? frameKey : '',
      provenance: frame.provenance || null,
      window: effectiveWindow,
      cachedWindow: live ? null : frame.window
    })
    const response = live ? frame.liveResponse
      : frame.snapshotResponse || frame.liveResponse
    const snapshotResponse = !live &&
      Date.parse(effectiveWindow?.start) === Date.parse(frame.window?.start) &&
      Date.parse(effectiveWindow?.endExclusive) === Date.parse(frame.window?.endExclusive) &&
      response?.dataVersion === frame.dataVersion &&
      response.capabilities?.directUpstream !== true &&
      response.provenance?.mode !== 'live' &&
      (response.provenance?.mode === 'snapshot' ||
        ['demo_snapshot', 'native_snapshot'].includes(
          response.provenance?.kind))
    if (
      (live || snapshotResponse) &&
      view === 'focus' &&
      response?.operation === 'dashboard' &&
      response?.data
    ) {
      const generation = epoch
      const seq = request
      publish({
        dashboard: response.data,
        trend: dashboardTrend(response.data),
        overview: response.overview || null,
        capabilities: response.capabilities || {},
        coverage: response.coverage || null,
        finance: response.data.finance || null,
        loading: false, stale: false
      })
      const key = pageKey()
      remember(key, generation, seq)
      if (!Object.prototype.hasOwnProperty.call(response.data, 'finance'))
        void loadFinance(generation, seq, key)
      else scheduleFinance(response.data.finance, generation, seq, key)
      return
    }
    return load()
  }
  function load() {
    if (!session || !state.connectionId ||
        (!state.isLive && !state.dataVersion) || disposed) return
    const key = pageKey()
    if (activeLoad?.key === key && activeLoad.generation === epoch &&
        activeLoad.seq === request) return activeLoad.promise
    const generation = epoch
    const seq = ++request
    const cached = pageCache.get(key)
    if (cached) {
      pageCache.delete(key)
      pageCache.set(key, cached)
    }
    const retain = !cached && (state.view === 'focus' ? state.dashboard :
      state.view === 'aggregate' ? state.analysis : state.customers)
    publish({
      ...(retain ? {} : {
        analysis: null, trend: null, customers: null, profile: null,
        dashboard: null, overview: null, finance: null,
        capabilities: {}, coverage: null
      }),
      memberOptions: [], customerOptions: [], modelOptions: [],
      ...cached, loading: !cached && !retain,
      refreshing: !!cached || !!retain, stale: !!retain, error: '',
      drawerLoading: false, drawerError: '',
      directory: null, directoryLoading: false, directoryError: ''
    })
    const entry = { key, generation, seq, promise: null }
    activeLoad = entry
    entry.promise = readPage(generation, seq, key).finally(() => {
      if (activeLoad === entry) activeLoad = null
    })
    if (valid(generation, seq)) {
      for (const [key, pending] of inFlight) {
        if (pending.seq === seq) continue
        pending.controller?.abort()
        inFlight.delete(key)
      }
    }
    return entry.promise
  }
  async function readPage(generation, seq, key) {
    try {
      if (state.view === 'aggregate') {
        const payload = {
          groupBy: [state.groupBy, state.secondary].filter(Boolean),
          metrics: [...new Set([state.metric, 'requestCount', 'successRate',
            'inputTokens', 'outputTokens'])],
          userIds: state.userId ? [state.userId] : [],
          page: state.analysisPage, pageSize: 20
        }
        const [analysis, trend] = await Promise.all([
          call('analysis', payload),
          call('trend', { granularity: 'day', userIds: payload.userIds })
        ])
        if (!valid(generation, seq)) return
        publish({ analysis: analysis.data, trend: trend.data,
          capabilities: analysis.capabilities || {},
          coverage: analysis.coverage || null,
          loading: false, refreshing: false, stale: false })
        remember(key, generation, seq)
        void options('userId')
      } else if (state.view === 'portrait') {
        const customers = await call('customers', {
          search: state.search,
          ...(state.signal ? { signal: state.signal } : {}),
          page: state.customerPage, pageSize: 25
        })
        if (!valid(generation, seq)) return
        const items = customers.data?.items || []
        const id = state.forceSelected || items.some((row) =>
          row.customerTenantId === state.selectedCustomerId)
          ? state.selectedCustomerId : items[0]?.customerTenantId || ''
        publish({ customers: customers.data, selectedCustomerId: id,
          capabilities: customers.capabilities || {},
          loading: false, refreshing: false, stale: false })
        if (id) await selectCustomer(id)
        remember(key, generation, seq)
        void loadFinance(generation, seq, key)
      } else {
        const dashboard = await call('dashboard')
        if (!valid(generation, seq)) return
        publish({ dashboard: dashboard.data,
          trend: dashboardTrend(dashboard.data),
          overview: dashboard.overview || null,
          capabilities: dashboard.capabilities || {},
          coverage: dashboard.coverage || null,
          finance: dashboard.data?.finance || null,
          loading: false, refreshing: false, stale: false })
        remember(key, generation, seq)
        if (!Object.prototype.hasOwnProperty.call(
          dashboard.data || {}, 'finance'))
          void loadFinance(generation, seq, key)
        else scheduleFinance(dashboard.data.finance, generation, seq, key)
      }
    } catch (error) {
      if (valid(generation, seq)) {
        if (cancelled(error)) {
          publish({ loading: false, refreshing: false, stale: false })
          return
        }
        publish({ loading: false, refreshing: false, error: failure(error) })
      }
    }
  }
  async function loadFinance(generation, seq, key = pageKey()) {
    try {
      const result = await call('finance')
      if (valid(generation, seq)) {
        const previous = state.finance?.refreshState
        publish({ finance: result.data, ...(state.dashboard ? {
          dashboard: { ...state.dashboard, finance: result.data }
        } : {}) })
        remember(key, generation, seq)
        if (previous !== 'ready' &&
            result.data?.refreshState === 'ready' && state.view === 'portrait' &&
            state.selectedCustomerId) void selectCustomer(state.selectedCustomerId)
        scheduleFinance(result.data, generation, seq, key)
      }
    } catch (error) {
      if (valid(generation, seq) && !cancelled(error)) {
        publish({ finance: { available: false, reason: failure(error) } })
        remember(key, generation, seq)
      }
    }
  }
  async function refreshFinance() {
    const generation = epoch, seq = request
    publish({ financeRefreshError: '', finance: { ...state.finance, refreshState: 'queued' } })
    try {
      await api.refreshFinance(state.connectionId)
      if (valid(generation, seq)) await loadFinance(generation, seq)
    } catch (error) {
      if (valid(generation, seq)) publish({
        financeRefreshError: failure(error),
        finance: { ...state.finance, refreshState: 'failed' }
      })
    }
  }
  function scheduleFinance(finance, generation, seq, key) {
    clearTimeout(financeTimer)
    financeTimer = null
    if (!valid(generation, seq) ||
        !['queued', 'running'].includes(finance?.refreshState)) return
    financeTimer = setTimeout(() => loadFinance(generation, seq, key), 5000)
    financeTimer?.unref?.()
  }
  function setView(view) {
    if (!VIEWS.has(view)) return
    if (view === state.view) return load()
    request++
    detail++
    publish({
      view,
      drawer: null,
      evidence: null,
      error: '',
      profile: null,
      analysis: null,
      customers: null
    })
    return load()
  }
  function configure(patch) {
    request++
    detail++
    publish({
      ...patch,
      analysisPage: patch.analysisPage || 1,
      drawer: null,
      evidence: null
    })
    return load()
  }
  async function options(dimension) {
    if (!state.connectionId || (!state.isLive && !state.dataVersion)) return
    const cacheKey = canonical([
      domain(), state.dataVersion, state.requestId, state.isLive, dimension
    ])
    const cached = optionsCache.get(cacheKey)
    if (cached) {
      publish({ [cached.key]: cached.rows })
      return cached.rows
    }
    const generation = epoch,
      seq = request
    try {
      const rows = []
      for (let page = 1; page <= 10; page++) {
        const response = await call('schema', {
          optionDimension: dimension,
          page,
          pageSize: 200
        })
        if (!valid(generation, seq)) return
        const options = response.data?.options || response.data || {}
        const items = options.items || []
        rows.push(...items)
        if (
          items.length < 200 ||
          (typeof options.total === 'number' && rows.length >= options.total) ||
          options.total === null
        )
          break
        if (page === 10) throw new Error('候选分页超过保护上限')
      }
      const key =
        dimension === 'customerTenantId'
          ? 'customerOptions'
          : dimension === 'modelId'
            ? 'modelOptions'
            : 'memberOptions'
      optionsCache.set(cacheKey, { key, rows })
      publish({ [key]: rows })
      return rows
    } catch (error) {
      if (valid(generation, seq) && !cancelled(error)) {
        publish({
          memberOptions: dimension === 'userId' ? [] : state.memberOptions
        })
      }
    }
  }
  function setFilters(customerIds, filters) {
    request++
    detail++
    publish({
      customerIds,
      filters,
      analysisPage: 1,
      customerPage: 1,
      drawer: null,
      evidence: null,
      selectedCustomerId: '',
      forceSelected: false
    })
    return load()
  }
  function setWindow(window) {
    if (
      !window ||
      !Number.isFinite(Date.parse(window.start)) ||
      !Number.isFinite(Date.parse(window.endExclusive)) ||
      Date.parse(window.endExclusive) <= Date.parse(window.start)
    )
      throw new Error('日期范围无效')
    if (
      state.cachedWindow &&
      (Date.parse(window.start) < Date.parse(state.cachedWindow.start) ||
        Date.parse(window.endExclusive) >
          Date.parse(state.cachedWindow.endExclusive))
    )
      throw new Error('所选日期超出已缓存范围，不会触发补采')
    request++
    detail++
    publish({
      window,
      analysisPage: 1,
      customerPage: 1,
      drawer: null,
      evidence: null
    })
    return load()
  }
  async function queryDirectory({ search = '', signal = '', page = 1 } = {}) {
    const generation = epoch
    const seq = ++directoryRevision
    const viewGeneration = request
    const current = () => valid(generation, viewGeneration) &&
      seq === directoryRevision
    publish({ directoryLoading: true, directoryError: '' })
    try {
      const response = await call('customers', {
        search, ...(signal ? { signal } : {}), page, pageSize: 25
      }, { customerIds: undefined })
      if (current())
        publish({ directory: response.data, directoryLoading: false })
    } catch (error) {
      if (current()) publish({
        directory: cancelled(error) ? state.directory : null,
        directoryLoading: false,
        directoryError: cancelled(error) ? '' : failure(error)
      })
    }
  }
  async function selectCustomer(id) {
    if (
      !(state.customers?.items || []).some(
        (row) => row.customerTenantId === id
      ) &&
      !(state.forceSelected && state.selectedCustomerId === id)
    )
      return
    const generation = epoch,
      seq = ++detail,
      version = request,
      key = profileKey(id),
      cached = profileCache.get(key)
    if (cached) profileCache.delete(key), profileCache.set(key, cached)
    publish({ selectedCustomerId: id,
      profile: cached || (state.selectedCustomerId === id ? state.profile : null),
      error: '' })
    try {
      const result = await call('profile', { customerId: id })
      if (
        disposed ||
        generation !== epoch ||
        seq !== detail ||
        version !== request
      )
        return
      publish({ profile: result.data })
      rememberProfile(key, result.data)
      remember(pageKey(), generation, version)
    } catch (error) {
      if (
        generation === epoch &&
        seq === detail &&
        version === request &&
        !cancelled(error)
      )
        publish({ profile: null, error: failure(error) })
    }
  }
  async function openRequests(groupKey = {}, page = 1, customerId = null, captured = null) {
    const previous=state.drawer
    const groupMeta=captured || (previous && previous.customerId===customerId && JSON.stringify(previous.groupKey)===JSON.stringify(groupKey) ? previous.groupMeta : null)
    const generation = epoch,
      seq = ++detail,
      version = request
    publish({
      drawer: { groupKey, page, customerId, groupMeta, items: [], total: 0 },
      evidence: null,
      drawerLoading: true,
      drawerError: ''
    })
    try {
      const response = await call(
        'requests',
        {
          groupKey,
          userIds: state.userId ? [state.userId] : [],
          page,
          pageSize: 20
        },
        customerId ? { customerIds: [customerId] } : {}
      )
      if (
        disposed ||
        generation !== epoch ||
        seq !== detail ||
        version !== request
      )
        return
      publish({
        drawer: { ...response.data, groupKey, customerId, page, groupMeta },
        drawerLoading: false
      })
    } catch (error) {
      if (
        generation === epoch &&
        seq === detail &&
        version === request
      )
        publish({ drawerLoading: false,
          drawerError: cancelled(error) ? '' : failure(error) })
    }
  }
  function openGroupDrawer(row, customerId=null, origin=null) {
    if(origin && (origin.connectionId!==state.connectionId || origin.dataVersion!==state.dataVersion || origin.contextKey!==state.contextKey))return
    const canonical=key=>{if(!key || Array.isArray(key))return null;const entries=Object.entries(key);if(!entries.length || entries.length>2 || entries.some(([name,value])=>!['date','customerTenantId','modelId','userId','status','failureType'].includes(name)||typeof value!=='string'))return null;return JSON.stringify(entries.sort(([a],[b])=>a.localeCompare(b)))}
    const key=canonical(row?.groupKey)
    if(!key)return
    const rows=state.view==='aggregate'?(state.analysis?.rows||[]):(state.profile?.members||[])
    const trusted=rows.find(item=>canonical(item.groupKey)===key)
    if(!trusted)return
    return openRequests({...trusted.groupKey},1,customerId,{label:trusted.label || Object.values(trusted.groupKey).join(' / '),summary:{...trusted.metrics}})
  }
  async function openEvidence(evidenceId) {
    if (!evidenceId) return
    const generation = epoch,
      seq = ++detail,
      version = request
    publish({ drawerLoading: true, drawerError: '', evidence: null })
    try {
      const response = await call('evidence', {
        evidenceId: String(evidenceId)
      })
      if (
        generation === epoch &&
        seq === detail &&
        version === request &&
        !disposed
      )
        publish({ evidence: response.data, drawerLoading: false })
    } catch (error) {
      if (
        generation === epoch &&
        seq === detail &&
        version === request
      )
        publish({ drawerLoading: false,
          drawerError: cancelled(error) ? '' : failure(error) })
    }
  }
  async function exportAnalysis() {
    const generation = epoch, seq = request
    const payload = {
      groupBy: [state.groupBy, state.secondary].filter(Boolean),
      metrics: [...new Set([state.metric, 'requestCount', 'successRate',
        'inputTokens', 'outputTokens'])],
      userIds: state.userId ? [state.userId] : [],
      page: 1, pageSize: 200
    }
    const rows = []
    let total
    do {
      const response = await call('analysis', { ...payload })
      if (!valid(generation, seq)) throw new Error('筛选条件已变化，请重新导出')
      const data = response.data
      if (!Array.isArray(data?.rows) || !Number.isInteger(data.total) ||
          data.rows.length !== Math.min(payload.pageSize, data.total - rows.length))
        throw new Error('导出数据不完整，请重试')
      total = data.total
      rows.push(...data.rows)
      payload.page++
    } while (rows.length < total)
    if (rows.length !== total) throw new Error('导出数据不完整，请重试')
    return rows
  }
  function openCustomer(id) {
    request++
    detail++
    publish({
      view: 'portrait',
      selectedCustomerId: id,
      forceSelected: true,
      search: '',
      signal: '',
      customerPage: 1,
      drawer: null
    })
    return load()
  }
  function closeDrawer() {
    detail++
    publish({
      drawer: null,
      evidence: null,
      drawerLoading: false,
      drawerError: ''
    })
  }
  function invalidate() {
    clearWork()
    const view = state.view
    epoch++
    request++
    detail++
    state = { ...empty(), view }
    if (!disposed) onChange(state)
  }
  function dispose() {
    reset()
    disposed = true
  }
  return {
    snapshot: () => state,
    reset,
    attach,
    load,
    reload: () => { clearWork(true); request++; return load() },
    setView,
    configure,
    options,
    setFilters,
    setWindow,
    selectCustomer,
    refreshFinance,
    queryDirectory,
    openRequests,
    openGroupDrawer,
    openEvidence,
    openCustomer,
    exportAnalysis,
    closeDrawer,
    invalidate,
    dispose
  }
}
