<template>
  <div
    ref="root"
    class="agione-demo integrated-controls"
    :class="{
      dark,
      'dashboard-home': work.view === 'focus' && diagnosis === 'all',
      'workspace-compact': work.view !== 'focus',
      'analysis-page': work.view === 'aggregate',
      'portrait-page': work.view === 'portrait'
    }"
    :data-ui-language="locale"
    data-testid="agione-operations"
    data-demo-origin="AGIone/static/index.html"
  >
    <div class="shell">
      <aside class="sidebar">
        <div class="brand">
          AGIOne<span>Ops</span><small>CUSTOMER OPERATIONS</small>
        </div>
        <div class="nav-label">{{ t('agione.demoNavLabel') }}</div>
        <nav
          id="nav"
          :aria-label="t('agione.demoNavigation')"
          @keydown="workspaceNavKeys"
        >
          <button
            :class="{ active: work.view === 'focus' }"
            :aria-current="work.view === 'focus' ? 'page' : undefined"
            @click="navigateWorkspace('focus')"
          >
            <span class="nav-num">01</span>{{ t('agione.demoDashboard') }}
          </button>
          <button
            :class="{ active: work.view === 'aggregate' }"
            :aria-current="work.view === 'aggregate' ? 'page' : undefined"
            @click="navigateWorkspace('aggregate')"
          >
            <span class="nav-num">02</span>{{ t('agione.demoAnalysis') }}
          </button>
          <button
            :class="{ active: work.view === 'portrait' }"
            :aria-current="work.view === 'portrait' ? 'page' : undefined"
            @click="navigateWorkspace('portrait')"
          >
            <span class="nav-num">03</span>{{ t('agione.demoPortrait') }}
          </button>
        </nav>
        <div class="nav-bottom">
          AGIOne · {{ t('agione.demoCustomerOps') }}<br /><RouterLink
            to="/dashboard"
            >{{ t('agione.returnDevmind') }} ↗</RouterLink
          >
        </div>
      </aside>
      <div class="workspace">
        <header class="topbar">
          <div class="header-context">
            <div class="crumb">
              {{ t('agione.demoCustomerOps') }}
              <span aria-hidden="true"> / </span
              ><b id="crumb">{{ workspaceTitle }}</b>
            </div>
            <div ref="connectionControl" class="connection-control">
              <span class="connection-divider" aria-hidden="true"></span>
              <button
                id="connectionTrigger"
                ref="connectionTrigger"
                class="connection-trigger"
                aria-haspopup="menu"
                :aria-expanded="menuOpen"
                aria-controls="connectionMenu"
                :disabled="!state.connections.length"
                @click="toggleMenu()"
                @keydown.down.prevent="toggleMenu(true, true)"
                @keydown.up.prevent="toggleMenu(true, true)"
              >
                <b>{{
                  connection?.platform === 'cc'
                    ? 'CC'
                    : connection?.platform === 'pro'
                      ? 'Pro'
                      : '—'
                }}</b
                ><span class="connection-slash">/</span
                ><span>{{
                  connection
                    ? accountLabel(connection.principalKind)
                    : t('agione.connection')
                }}</span
                ><svg
                  class="connection-chevron"
                  viewBox="0 0 20 20"
                  fill="none"
                  aria-hidden="true"
                >
                  <path
                    d="m6 8 4 4 4-4"
                    stroke="currentColor"
                    stroke-width="1.6"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  />
                </svg>
              </button>
              <div
                id="connectionMenu"
                ref="connectionMenu"
                class="connection-menu"
                role="menu"
                :aria-label="t('agione.connectionAndWindow')"
                :hidden="!menuOpen"
                :style="menuPosition"
                @keydown="menuKeys"
              >
                <div
                  v-for="platform in platforms"
                  :key="platform"
                  class="connection-group"
                  role="group"
                  :aria-label="platform === 'pro' ? 'Pro' : 'CC'"
                >
                  <div class="connection-menu-label">
                    <b>{{ platform === 'pro' ? 'Pro' : 'CC' }}</b
                    ><span>{{
                      t(
                        readOnly
                          ? 'agione.realSnapshotShort'
                          : 'agione.localDemo'
                      )
                    }}</span>
                  </div>
                  <button
                    v-for="item in state.connections.filter(
                      (x) => x.platform === platform
                    )"
                    :key="item.id"
                    role="menuitemradio"
                    :aria-checked="item.id === state.connectionId"
                    @click="selectConnection(item.id)"
                  >
                    <b>{{ accountLabel(item.principalKind) }}</b
                    ><span>{{ item.name }}</span
                    ><span class="connection-check" aria-hidden="true"
                      ><svg
                        v-if="item.id === state.connectionId"
                        viewBox="0 0 20 20"
                        fill="none"
                      >
                        <path
                          d="m5 10 3 3 7-7"
                          stroke="currentColor"
                          stroke-width="1.8"
                          stroke-linecap="round"
                          stroke-linejoin="round"
                        /></svg
                    ></span>
                  </button>
                </div>
              </div>
            </div>
          </div>
          <div
            id="notice"
            class="notice"
            role="status"
            aria-live="polite"
          ></div>
          <AppHeader inline :show-menu-button="false" />
        </header>
        <main class="main">
          <div v-if="connection && !readOnly" class="notice" role="note">
            <b>{{ sourceBadge }}</b>
            {{
              t(
                readOnly
                  ? 'agione.realSnapshotNotice'
                  : 'agione.syntheticNotice'
              )
            }}
            <span v-if="readOnly && state.dashboard?.provenance?.stale">
              · {{ t('agione.staleSnapshot') }}
            </span>
          </div>
          <div v-if="state.error" id="error" role="alert">
            <b>{{ t('agione.operationIncomplete') }}</b>
            <p>
              {{ state.errorCode === 'NATIVE_SYNC_DEADLINE' ? t('agione.errors.syncDeadline') : t(`agione.errors.${state.error}`) }}
              <span v-if="state.errorCode">({{ state.errorCode }})</span>
            </p>
            <div class="button-line">
              <button
                v-if="state.error === 'pollTimeout'"
                @click="controller.resume()"
              >
                {{ t('agione.resumeProgress') }}</button
              ><button
                v-else
                @click="
                  state.connectionId ? controller.refresh() : controller.load()
                "
              >
                {{ t('agione.retry') }}</button
              ><button :disabled="refreshDisabled" @click="refreshCurrent">
                {{ refreshLabel }}
              </button>
            </div>
          </div>
          <div
            v-if="state.run && !readOnly"
            class="callout"
            role="status"
            aria-live="polite"
          >
            <b>{{ t(`agione.status.${state.run.status}`) }}</b>
            <p>
              {{ state.run.phase }} ·
              {{ formatNumber(state.run.processedCount) }} /
              {{
                state.run.totalCount == null
                  ? t('agione.unknown')
                  : formatNumber(state.run.totalCount)
              }}
            </p>
          </div>
          <div id="content" :aria-busy="state.listLoading || state.loading || work.loading"><div id="diagnosticNav" hidden></div><div id="scopeHost">
            <section class="panel" data-panel="scope">
              <div class="panel-head">
                <div class="panel-title">
                  <h2>{{ t('agione.demoScope') }}</h2>
                  <p>
                    {{
                      t(
                        readOnly
                          ? 'agione.readOnlyRangeHelp'
                          : 'agione.windowHelp'
                      )
                    }}
                  </p>
                </div>
              </div>
              <div class="scope-toolbar">
                <div
                  class="date-segments"
                  role="group"
                  :aria-label="t('agione.demoDateRange')"
                >
                  <button
                    :aria-pressed="isLastSeven"
                    :disabled="
                      state.syncing ||
                      state.loading ||
                      work.loading ||
                      (readOnly && !isLive && !work.dataVersion)
                    "
                    :title="
                      readOnly ? t('agione.readOnlyRangeHelp') : undefined
                    "
                    @click="recentSeven"
                  >
                    {{ t('agione.lastSeven') }}</button
                  ><button
                    :aria-pressed="!isLastSeven"
                    :disabled="
                      state.syncing ||
                      state.loading ||
                      work.loading ||
                      (readOnly && !isLive && !work.dataVersion)
                    "
                    :title="
                      readOnly ? t('agione.readOnlyRangeHelp') : undefined
                    "
                    @click="openDates"
                  >
                    {{
                      isLastSeven
                        ? t('agione.customDates')
                        : `${displayStart} — ${displayEnd}`
                    }}
                    <svg
                      class="ui-chevron"
                      viewBox="0 0 20 20"
                      fill="none"
                      aria-hidden="true"
                    >
                      <path
                        d="m5 7.5 5 5 5-5"
                        stroke="currentColor"
                        stroke-width="1.6"
                        stroke-linecap="round"
                      />
                    </svg>
                  </button>
                </div>
                <div
                  class="scope-filter-field"
                  role="group"
                  :aria-label="t('agione.scopeFilterPlaceholder')"
                >
                  <button
                    class="scope-filter"
                    :disabled="!readOnly || (!isLive && !work.dataVersion)"
                    aria-haspopup="dialog"
                    :aria-label="t('agione.scopeFilterPlaceholder')"
                    @click="openScope"
                  >
                    <span class="scope-filter-placeholder">{{
                      t('agione.scopeFilterPlaceholder')
                    }}</span
                    ><svg
                      class="ui-chevron"
                      viewBox="0 0 20 20"
                      fill="none"
                      aria-hidden="true"
                    >
                      <path
                        d="m5 7.5 5 5 5-5"
                        stroke="currentColor"
                        stroke-width="1.6"
                        stroke-linecap="round"
                      />
                    </svg>
                  </button>
                  <div
                    id="appliedFilters"
                    class="applied-filters"
                    role="region"
                    :aria-label="t('agione.scopeTitle')"
                    aria-live="polite"
                    v-if="
                      work.customerIds.length ||
                      work.filters.modelIds.length ||
                      work.filters.statuses.length
                    "
                  >
                    <span
                      v-for="id in work.customerIds"
                      :key="`customer-${id}`"
                      class="applied-filter"
                    >
                      {{ t('agione.selectedCustomers', { count: 1 }) }}
                      <button type="button" :aria-label="`${t('agione.clear')} ${id}`" @click.stop="removeFilter('customer', id)">×</button>
                    </span>
                    <span
                      v-for="id in work.filters.modelIds"
                      :key="`model-${id}`"
                      class="applied-filter"
                    >
                      {{ t('agione.selectedModels', { count: 1 }) }}
                      <button type="button" :aria-label="`${t('agione.clear')} ${id}`" @click.stop="removeFilter('model', id)">×</button>
                    </span>
                    <span
                      v-for="status in work.filters.statuses"
                      :key="`status-${status}`"
                      class="applied-filter"
                    >
                      {{ t(`agione.${status === 'SUCCESS' ? 'success' : status === 'FAILURE' ? 'failure' : 'unknown'}`) }}
                      <button type="button" :aria-label="`${t('agione.clear')} ${status}`" @click.stop="removeFilter('status', status)">×</button>
                    </span>
                    <button type="button" class="applied-clear" @click="clearScope">{{ t('agione.clear') }}</button>
                  </div>
                </div>
                <button
                  class="scope-reset"
                  :disabled="
                    state.syncing ||
                    state.loading ||
                    work.loading ||
                    (readOnly && !isLive && !work.dataVersion)
                  "
                  :title="readOnly ? t('agione.readOnlyRangeHelp') : undefined"
                  @click="recentSeven"
                >
                  {{ t('agione.resetScope') }}
                </button>
                <div class="scope-groups" :aria-label="t('agione.savedFilters')">
                  <label class="saved-select">
                    <span class="sr-only">{{ t('agione.savedFilters') }}</span>
                    <select v-model="selectedSavedFilter" @change="applySavedFilter">
                      <option value="">{{ t('agione.noSavedFilters') }}</option>
                      <option v-for="item in savedFilters" :key="item.name" :value="item.name">{{ item.name }}</option>
                    </select>
                    <svg class="ui-chevron" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                      <path d="m5 7.5 5 5 5-5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
                    </svg>
                  </label>
                  <button class="save-group-button" type="button" @click="saveCurrentFilter">
                    {{ t('agione.saveFilters') }}
                  </button>
                </div>
                <div id="scopeRefreshActions" class="scope-refresh-actions">
                  <span id="scopeUpdatedAt"
                    >{{
                      t(readOnly ? 'agione.originalAsOf' : 'agione.updatedAt')
                    }}
                    {{ updatedTime(sourceTime) }}</span
                  ><button
                    id="refresh"
                    :disabled="refreshDisabled"
                    @click="refreshCurrent"
                  >
                    {{ refreshLabel }}
                  </button>
                </div>
              </div>
              <div class="scope-bottom">
                <span class="scope-summary" aria-live="polite">
                  <template v-if="work.customerIds.length || work.filters.modelIds.length || work.filters.statuses.length">
                    {{ t('agione.selectedCustomers', { count: work.customerIds.length }) }} ·
                    {{ t('agione.selectedModels', { count: work.filters.modelIds.length }) }} ·
                    {{ work.filters.statuses.map(value => t(`agione.${value === 'SUCCESS' ? 'success' : value === 'FAILURE' ? 'failure' : 'unknown'}`)).join(' / ') || t('agione.allResults') }}
                  </template>
                  <template v-else>
                    {{ t('agione.allCustomers') }} · {{ t('agione.allModels') }} · {{ t('agione.allResults') }}
                  </template>
                  <span class="scope-dot">·</span>
                  {{ t(readOnly ? 'agione.readOnlyRangeHelp' : 'agione.completeDays') }}
                  <template v-if="state.dashboard?.coverage?.partial && !pendingRange">
                    <span class="scope-dot">·</span>
                    {{ t('agione.partialRangeNotice') }}
                    <template v-if="state.dashboard.coverage.missingDays?.length">
                      {{ t('agione.missingDates', { dates: state.dashboard.coverage.missingDays.join('、') }) }}
                    </template>
                  </template>
                  <template v-if="pendingRange">
                    <span class="scope-dot">·</span>
                    {{ state.dashboard?.coverage?.partial ? t(state.error ? 'agione.pendingRangePartialFailed' : 'agione.pendingRangePartial', pendingRange) : ready && work.window ? t(state.error ? 'agione.pendingRangeFailed' : 'agione.pendingRange', pendingRange) : t('agione.pendingRangeEmpty', pendingRange) }}
                    <template v-if="state.dashboard?.coverage?.missingDays?.length">
                      {{ t('agione.missingDates', { dates: state.dashboard.coverage.missingDays.join('、') }) }}
                    </template>
                    <template v-if="ready && work.window">
                      {{ t('agione.currentDisplayedRange', { start: shanghaiDate(new Date(work.window.start)), end: shanghaiDate(new Date(Date.parse(work.window.endExclusive) - 1)) }) }}
                    </template>
                  </template>
                </span>
                <details class="scope-help">
                  <summary>
                    {{ t('agione.dataDetails') }}
                    <span aria-hidden="true">⌄</span>
                  </summary>
                  <div class="scope-version">
                    {{ t('agione.dataVersion') }}
                    <span class="version">{{
                      isLive ? (state.dashboard?.provenance?.fetchedAt || '—') : (state.dashboard?.dataVersion || '—')
                    }}</span
                    ><br />{{ t('agione.snapshotWindow') }} {{ actualWindow
                    }}<br />{{
                      t(readOnly ? 'agione.originalAsOf' : 'agione.publishedAt')
                    }}
                    {{ formatTime(sourceTime) }}
                    <template v-if="readOnly"><br /><b>{{ sourceBadge }}</b> {{ t('agione.realSnapshotNotice') }}<span v-if="state.dashboard?.provenance?.stale"> · {{ t('agione.staleSnapshot') }}</span></template>
          <div v-if="readOnly && directoryCoverage">
            {{ t('agione.directoryCoverage', { total: directoryCoverage.directoryTotal ?? '—', confirmed: directoryCoverage.confirmedDirectoryCustomers ?? '—', excluded: directoryCoverage.excludedUnconfirmedCustomers ?? '—' }) }}
          </div>
                    <template v-if="connection?.sourceKind === 'demo_snapshot'"
                      ><br />{{ t('agione.sourceVersion') }}
                      <span class="version">{{
                        state.dashboard?.provenance?.sourceVersion || '—'
                      }}</span>
                    </template>
                  </div>
                </details>
              </div>
            </section>
            </div><div class="results-shell"><div id="results"><div
              v-if="state.listLoading || (state.loading && !ready)"
              class="loading"
              role="status"
            >
              {{ t('agione.loading') }}
            </div>
            <div
              v-else-if="!state.connectionId && !state.error"
              class="empty"
              role="status"
            >
              <h2>{{ t('agione.noConnections') }}</h2>
              <p>{{ t('agione.noConnectionsHelp') }}</p>
            </div>
            <div v-else-if="!ready && !state.error" class="empty" role="status">
              <h2>
                {{
                  pendingRange && state.syncing ? t('agione.collectingRange') :
                    t(readOnly ? 'agione.snapshotUnavailable' : 'agione.noData')
                }}
              </h2>
              <p>
                {{
                  pendingRange && state.syncing
                    ? t('agione.pendingRangeEmpty', pendingRange)
                    : readOnly
                    ? t('agione.snapshotUnavailableHelp')
                    : connection?.verifiedAt
                      ? t('agione.noDataHelp')
                      : t('agione.notVerified')
                }}
              </p>
              <button
                v-if="!state.syncing && (connection?.sourceKind === 'native' || (!readOnly && connection?.verifiedAt))"
                class="primary"
                :disabled="state.syncing"
                @click="refreshCurrent"
              >
                {{ t('agione.firstSync') }}
              </button>
            </div>
            <div v-if="readOnly && work.error" class="callout" role="alert">
              <p>{{ t(work.error.includes('(DATA_VERSION_EXPIRED)') ? 'agione.errors.snapshotExpired' : 'agione.errors.networkError') }}</p>
              <button @click="work.error.includes('(DATA_VERSION_EXPIRED)') ? controller.loadWindow(state.startDate, state.endDate) : workspace.load()">{{ t('agione.retryPage') }}</button>
            </div>
            <div v-if="readOnly && work.loading" class="loading" role="status">
              {{ t('agione.workspaceLoading') }}
            </div>
            <div v-if="!readOnly && work.view !== 'focus'" class="panel empty">
              {{ t('agione.unsupportedSource') }}
            </div>
            <div v-if="readOnly && work.stale" role="status" class="workspace-refresh-status">
              {{ t('agione.staleRefreshing') }}
            </div>
            <div :inert="work.stale || null">
            <AnalysisWorkspace
              v-if="
                readOnly &&
                work.view === 'aggregate' &&
                !work.loading &&
                !work.error
              "
              :state="work"
              :export-rows="workspace.exportAnalysis"
              @change="workspace.configure"
              @drill="workspace.openGroupDrawer"
              @clear="clearScope"
            />
            <CustomerWorkspace
              v-if="
                readOnly &&
                work.view === 'portrait' &&
                !work.loading &&
                !work.error
              "
              :state="work"
              :finance-refresh-disabled="refreshDisabled || state.sourceKind !== 'native'"
              @refresh-finance="workspace.refreshFinance"
              @change="workspace.configure"
              @select="workspace.selectCustomer"
              @clear="clearScope"
              @analyze-model="analyzeModel"
              @requests="(id) => workspace.openRequests({}, 1, id)"
              @drill="
                (item) =>
                  workspace.openGroupDrawer(item.row, item.customerId, item.origin)
              "
            />
            <FocusWorkspace v-if="readOnly && work.view === 'focus' && !work.loading && !work.error && work.dashboard" :state="work" :previous-loading="state.previousLoading || previousChecking || previousAfterCurrent" @customer="openWorkspaceCustomer" @requests="id=>workspace.openRequests({},1,id)" @analyze-model="analyzeModel" @clear="clearScope" @diagnosis="diagnosis=$event" @view="navigateWorkspace" @previous="retryPreviousComparison" />
            </div>
            <template
              v-if="
                !readOnly && ready && !state.loading && work.view === 'focus' && !work.error && (!readOnly || (!work.loading && !!work.overview))
              "
            >
              <div
                v-if="windowMismatch && !readOnly"
                class="callout"
                role="note"
              >
                {{ t('agione.windowMismatch') }} {{ actualWindow }}
              </div>
              <FinancePanel v-if="readOnly" :value="work.finance" :is-live="isLive" :provenance="work.provenance" />
              <section
                v-else
                class="panel dashboard-finance"
                data-panel="dashboard-finance"
                :aria-label="t('agione.demoFinance')"
              >
                <div class="df-head">
                  <div>
                    <h2>
                      {{ t('agione.demoFinance') }}
                      <span class="df-scope">{{
                        t('agione.notConnected')
                      }}</span>
                    </h2>
                    <p>{{ t('agione.financeScope') }}</p>
                  </div>
                  <div class="df-actions">
                    <span class="df-badge" role="status">{{
                      t('agione.notConnected')
                    }}</span
                    ><button disabled :title="t('agione.financeMissing')">
                      {{ t('agione.fillFinance') }}
                    </button>
                  </div>
                </div>
                <div class="df-body">
                  <div>
                    <div class="df-metrics">
                      <div>
                        <p class="df-label">{{ t('agione.balanceTotal') }}</p>
                        <strong class="df-number">—</strong>
                        <p class="df-note">{{ t('agione.financeMissing') }}</p>
                      </div>
                      <div>
                        <p class="df-label">{{ t('agione.cycleConsumed') }}</p>
                        <strong class="df-number">—</strong>
                        <p class="df-note">{{ t('agione.financeMissing') }}</p>
                      </div>
                    </div>
                    <div class="df-pending">
                      <span
                        >{{ t('agione.cashRevenue')
                        }}<small>— {{ t('agione.notConnected') }}</small></span
                      ><span
                        >{{ t('agione.modelCost')
                        }}<small>— {{ t('agione.notConnected') }}</small></span
                      ><span
                        >{{ t('agione.margin')
                        }}<small>— {{ t('agione.notConnected') }}</small></span
                      >
                    </div>
                    <p class="df-note">{{ t('agione.financeMissing') }}</p>
                  </div>
                  <div class="df-chart">
                    <div class="df-chart-head">
                      <h3>{{ t('agione.creditTrend') }}</h3>
                      <small>{{ t('agione.notConnected') }}</small>
                    </div>
                    <p class="df-note">{{ t('agione.financeScope') }}</p>
                    <div class="df-empty">
                      {{ t('agione.financeMissing')
                      }}<small>{{ t('agione.noInventedMoney') }}</small>
                    </div>
                  </div>
                </div>
              </section>
              <div class="dashboard-columns">
                <div class="dashboard-data">
                  <section
                    class="panel dashboard-overview"
                    data-panel="summary"
                  >
                    <div class="panel-head">
                      <div class="panel-title">
                        <h2>{{ t('agione.overview') }}</h2>
                      </div>
                    </div>
                    <div class="dashboard-metrics">
                      <div>
                        <small>{{ t('agione.activeCustomers') }}</small
                        ><strong>{{
                          formatNumber(summary.activeCustomers)
                        }}</strong>
                        <p></p>
                      </div>
                      <div>
                        <small>{{ t('agione.requests') }}</small
                        ><strong>{{ formatNumber(summary.requests) }}</strong>
                        <p>
                          {{ formatNumber(summary.success) }}
                          {{ t('agione.success') }} /
                          {{ formatNumber(summary.failure) }}
                          {{ t('agione.failure') }} /
                          {{ formatNumber(summary.unknown) }}
                          {{ t('agione.unknown') }}
                        </p>
                      </div>
                      <div>
                        <small>{{ t('agione.successRate') }}</small
                        ><strong>{{
                          formatPercent(summary.successRate)
                        }}</strong>
                        <p></p>
                      </div>
                      <div>
                        <small>{{ t('agione.knownTokens') }}</small
                        ><strong>{{
                          formatNumber(summary.totalTokens)
                        }}</strong>
                        <p>
                          {{ formatNumber(summary.totalTokensSampleCount) }}/{{
                            formatNumber(summary.requests)
                          }}
                          {{ t('agione.knownSamples') }}
                        </p>
                      </div>
                    </div>
                  </section>
                  <section class="panel dashboard-trend" data-panel="trend">
                    <div class="panel-head">
                      <div class="panel-title">
                        <h2>{{ t('agione.trend') }}</h2>
                        <p>
                          {{
                            t(
                              readOnly
                                ? 'agione.readOnlyTrendSubtitle'
                                : 'agione.demoTrendSubtitle'
                            )
                          }}
                        </p>
                      </div>
                    </div>
                    <div class="trend-chart">
                      <div class="trend-toolbar">
                        <b
                          >{{ t('agione.allResults') }} ·
                          {{ t('agione.requests') }}</b
                        >
                        <div class="trend-legend">
                          <span class="trend-key">{{
                            t('agione.current')
                          }}</span
                          ><span>{{ previousLabel }}</span>
                        </div>
                      </div>
                      <div class="trend-layout">
                        <div class="trend-yaxis" aria-hidden="true">
                          <span
                            v-for="tick in plot.ticks"
                            :key="tick"
                            :style="{
                              top: `${100 - (100 * tick) / plot.max}%`
                            }"
                            >{{ formatNumber(tick) }}</span
                          >
                        </div>
                        <div
                          class="trend-visual"
                          role="group"
                          :aria-label="
                            t('agione.trendAccessible', {
                              count: formatNumber(summary.requests)
                            })
                          "
                        >
                          <svg
                            viewBox="0 0 600 180"
                            preserveAspectRatio="none"
                            aria-hidden="true"
                          >
                            <path
                              v-for="tick in plot.ticks"
                              :key="tick"
                              class="plot-grid"
                              :d="`M0 ${180 - (180 * tick) / plot.max}H600`"
                            />
                            <polyline
                              v-for="(segment, index) in plot.current"
                              :key="index"
                              class="plot-current"
                              :points="
                                segment
                                  .map((p) => `${p.x * 6},${p.y * 1.8}`)
                                  .join(' ')
                              "
                            /></svg
                          ><span
                            v-for="point in plot.current.flat()"
                            :key="point.index"
                            class="trend-dot"
                            :style="{
                              left: `${point.x}%`,
                              top: `${point.y}%`
                            }"
                            tabindex="0"
                            role="img"
                            :aria-label="`${trend[point.index]?.date}: ${point.value}`"
                            :title="`${trend[point.index]?.date}: ${point.value}`"
                          ></span>
                        </div>
                      </div>
                      <div class="trend-xaxis" aria-hidden="true">
                        <span
                          v-for="(index, i) in trendIndexes"
                          :key="index"
                          :class="{
                            'first-tick': i === 0,
                            'last-tick': i === trendIndexes.length - 1
                          }"
                          :style="{
                            left: `${trend.length === 1 ? 50 : (100 * index) / (trend.length - 1)}%`
                          }"
                          >{{
                            trend[index]?.date?.slice(5).replace('-', '/')
                          }}</span
                        >
                      </div>
                      <div class="trend-footnote">
                        <span>{{ actualWindow }} · Asia/Shanghai</span
                        ><span>{{
                          readOnly ? previousLabel : t('agione.noPreviousLine')
                        }}</span>
                      </div>
                    </div>
                  </section>
                  <section
                    class="panel dashboard-models"
                    data-panel="model-use"
                  >
                    <div class="panel-head">
                      <div class="panel-title">
                        <h2>{{ t('agione.demoModels') }}</h2>
                        <p>
                          {{
                            t('agione.demoModelCount', {
                              count: models.length
                            })
                          }}
                        </p>
                      </div>
                    </div>
                    <div
                      class="model-list"
                      tabindex="0"
                      role="region"
                      :aria-label="t('agione.demoModels')"
                    >
                      <div
                        v-for="model in models"
                        :key="model.modelId"
                        class="model-item"
                      >
                        <div class="model-row">
                          <button
                            class="model-analysis-link"
                            :disabled="!readOnly || (!isLive && !work.dataVersion)"
                            :title="t('agione.analyzeModel')"
                            @click="analyzeModel(model.modelId)"
                          >
                            {{ model.modelId }}
                            <span aria-hidden="true">↗</span></button
                          ><span
                            ><b>{{ formatNumber(model.requests) }}</b>
                            {{ t('agione.requestUnit') }}</span
                          >
                        </div>
                        <small class="model-id">ID {{ model.modelId }}</small>
                        <p class="model-outcomes">
                          {{ t('agione.success') }}
                          {{ formatNumber(model.success) }} ·
                          {{ t('agione.failure') }}
                          {{ formatNumber(model.failure) }} ·
                          {{ t('agione.unknown') }}
                          {{ formatNumber(model.unknown) }}
                        </p>
                        <div class="model-share">
                          <div class="model-track" aria-hidden="true">
                            <span
                              :style="{
                                width: `${summary.requests ? (model.requests / summary.requests) * 100 : 0}%`
                              }"
                            ></span>
                          </div>
                          <span>{{
                            formatPercent(
                              summary.requests
                                ? (model.requests / summary.requests) * 100
                                : null
                            )
                          }}</span>
                        </div>
                      </div>
                    </div>
                    <p class="model-note">
                      {{ t('agione.requestShare') }} ·
                      {{ t('agione.modelHelp') }}
                    </p>
                  </section>
                </div>
                <DashboardSignals
                  v-if="readOnly"
                  :data="work.dashboard"
                  @customer="openWorkspaceCustomer"
                  @requests="(id) => workspace.openRequests({}, 1, id)"
                />
                <section v-else class="panel event-column" data-panel="events">
                  <div class="event-heading">
                    <div class="event-title-group">
                      <h2>{{ t('agione.demoLeads') }}</h2>
                      <small>{{ t('agione.notConnected') }}</small>
                    </div>
                    <button
                      class="event-rule-settings"
                      disabled
                      :title="t('agione.notConnected')"
                    >
                      ⚙ {{ t('agione.demoRules') }}
                    </button>
                  </div>
                  <div class="event-rule-warning" role="status">
                    <b>{{ previousLabel }}</b>
                    <p>{{ previousHelp }}</p>
                    <small>{{ t('agione.leadsMissing') }}</small>
                  </div>
                  <div class="event-priority">
                    <div class="event-eyebrow">
                      {{ t('agione.notConnected') }}
                    </div>
                    <h3>{{ t('agione.noLeadsInvented') }}</h3>
                    <p>{{ t('agione.leadsMissing') }}</p>
                  </div>
                  <div
                    class="event-tabs"
                    role="group"
                    :aria-label="t('agione.demoLeads')"
                  >
                    <button
                      v-for="label in [
                        t('agione.allCustomers'),
                        t('agione.inactive'),
                        t('agione.requestFailure'),
                        t('agione.blocked'),
                        t('agione.declining')
                      ]"
                      :key="label"
                      disabled
                    >
                      {{ label }} · —
                    </button>
                  </div>
                  <div class="event-list">
                    <div class="empty">{{ t('agione.leadsMissing') }}</div>
                  </div>
                  <div class="event-bottom">
                    <div class="event-diagnostics">
                      <button class="link" disabled>
                        {{ t('agione.declining') }} →</button
                      ><button class="link" disabled>
                        {{ t('agione.blocked') }} →</button
                      ><button class="link" disabled>
                        {{ t('agione.failureReason') }} →
                      </button>
                    </div>
                    <details class="event-help">
                      <summary>{{ t('agione.dataDetails') }}</summary>
                      <p>{{ t('agione.qualityHelp') }}</p>
                      <p>
                        {{ t('agione.quarantined') }}
                        {{
                          formatNumber(
                            state.dashboard.coverage?.excludedUnknownCustomers
                          )
                        }}
                        · {{ t('agione.quarantinedHelp') }}
                      </p>
                      <p>
                        {{ t('agione.inputTokens') }}
                        {{ formatNumber(summary.inputTokens) }} ·
                        {{ t('agione.outputTokens') }}
                        {{ formatNumber(summary.outputTokens) }}
                      </p>
                    </details>
                  </div>
                </section>
              </div>
            </template>
            </div></div>
          </div>
          <footer class="footer">
            <span>AGIOne · {{ t('agione.demoCustomerOps') }}</span
            ><span
              >{{ t('agione.dataVersion') }}
              <span class="version">{{
                isLive ? (state.dashboard?.provenance?.fetchedAt || '—') : (state.dashboard?.dataVersion || '—')
              }}</span>
              <template v-if="connection"
                >·
                {{
                  t(readOnly ? 'agione.realSnapshotShort' : 'agione.synthetic')
                }}
              </template></span
            >
          </footer>
        </main>
      </div>
    </div>
    <ScopeDialog ref="scopeDialog" :state="work" @apply="({customerIds,filters})=>workspace.setFilters(customerIds,filters)" @directory="workspace.queryDirectory" />
    <RequestDrawer
      :state="work"
      @close="workspace.closeDrawer"
      @page="
        (page) =>
          workspace.openRequests(
            work.drawer.groupKey,
            page,
            work.drawer.customerId
          )
      "
      @evidence="workspace.openEvidence"
      @back="
        workspace.openRequests(
          work.drawer.groupKey,
          work.drawer.page,
          work.drawer.customerId
        )
      "
    />
    <dialog
      id="agione-save-filter-dialog"
      ref="saveFilterDialog"
      class="save-filter-dialog"
      aria-labelledby="saveFilterTitle"
      @cancel="closeSaveFilter"
      @close="releaseOriginalDialog(saveFilterDialog)"
    >
      <form @submit.prevent="confirmSaveFilter">
        <div class="dialog-head">
          <h2 id="saveFilterTitle">{{ t('agione.saveFilters') }}</h2>
          <button type="button" :aria-label="t('agione.close')" @click="closeSaveFilter">×</button>
        </div>
        <p class="save-filter-help">{{ t('agione.saveFiltersPrompt') }}</p>
        <label class="save-filter-label" for="saveFilterName">{{ t('agione.savedFilters') }}</label>
        <input
          id="saveFilterName"
          ref="saveFilterNameInput"
          v-model.trim="saveFilterName"
          maxlength="80"
          autocomplete="off"
          required
        />
        <div class="save-filter-actions">
          <button type="button" @click="closeSaveFilter">{{ t('agione.cancel') }}</button>
          <button class="primary" type="submit">{{ t('agione.saveFilters') }}</button>
        </div>
      </form>
    </dialog>
    <dialog
      id="agione-date-dialog"
      data-agione-dialog-id="agione-date-dialog"
      @close="releaseOriginalDialog(dateDialog)"
      ref="dateDialog"
      class="date-dialog"
      aria-labelledby="dialogTitle"
      @cancel="closeDates"
    >
      <div class="dialog-head">
        <h2 id="dialogTitle">{{ t('agione.demoDateRange') }}</h2>
        <button id="closeDialog" @click="closeDates">
          {{ t('agione.close') }}
        </button>
      </div>
      <div id="dialogBody">
        <form id="dateForm" @submit.prevent="applyDates">
          <p class="calendar-hint">{{ t('agione.calendarHint') }}</p>
          <div class="range-readout" aria-live="polite">
            <span :class="{ choosing: !dateDraft.end }"
              ><small>{{ t('agione.startDate') }}</small
              ><b>{{ dateDraft.start }}</b></span
            ><i aria-hidden="true">→</i
            ><span :class="{ 'choosing-end': !dateDraft.end }"
              ><small>{{ t('agione.endDate') }}</small
              ><b>{{ dateDraft.end || t('agione.chooseDate') }}</b></span
            >
          </div>
          <div class="calendar-nav">
            <button
              type="button"
              :aria-label="t('agione.previousMonth')"
              @click="dateDraft.month = shiftMonth(dateDraft.month, -1)"
            >
              ‹</button
            ><span>{{
              dateDraft.end
                ? t('agione.reselectDates')
                : t('agione.chooseEndDate')
            }}</span
            ><button
              type="button"
              :aria-label="t('agione.nextMonth')"
              :disabled="calendarMonths.at(-1) >= latestDay.slice(0, 7)"
              @click="dateDraft.month = shiftMonth(dateDraft.month, 1)"
            >
              ›
            </button>
          </div>
          <div class="calendar-months">
            <section
              v-for="month in calendarMonths"
              :key="month"
              class="calendar-month"
              :aria-label="calendarMonth(month, locale).title"
            >
              <h3>{{ calendarMonth(month, locale).title }}</h3>
              <div class="calendar-week" aria-hidden="true">
                <span v-for="(weekday, dayIndex) in weekdays" :key="dayIndex">{{
                  weekday
                }}</span>
              </div>
              <div class="calendar-days">
                <template
                  v-for="(day, index) in calendarMonth(month, locale).days"
                  :key="index"
                  ><span v-if="!day"></span
                  ><button
                    v-else
                    type="button"
                    :data-day="day"
                    :aria-label="day"
                    :aria-pressed="
                      day === dateDraft.start || day === dateDraft.end
                    "
                    :class="{
                      endpoint:
                        day === dateDraft.start || day === dateDraft.end,
                      'in-range':
                        dateDraft.end &&
                        day > dateDraft.start &&
                        day < dateDraft.end
                    }"
                    :disabled="
                      day > latestDay ||
                      (!dateDraft.end && day > shiftDay(dateDraft.start, 30))
                    "
                    @click="pickDay(day)"
                  >
                    {{ Number(day.slice(-2)) }}
                  </button></template
                >
              </div>
            </section>
          </div>
          <p v-if="dateError" class="form-error" role="alert">
            {{ t('agione.errors.invalidWindow') }}
          </p>
          <div class="calendar-footer">
            <span>{{
              t(readOnly ? 'agione.readOnlyRangeHelp' : 'agione.completeDays')
            }}</span>
            <div>
              <button type="button" @click="closeDates">
                {{ t('agione.cancel') }}</button
              ><button class="primary" type="submit" :disabled="!dateDraft.end">
                {{ t('agione.applyDates') }}
              </button>
            </div>
          </div>
        </form>
      </div>
    </dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import AppHeader from '@/components/layout/AppHeader.vue'
import { useI18n } from 'vue-i18n'
import { agioneOpsApi } from '@/api/agioneOps'
import { useUserStore } from '@/store/user'
import {
  createAgioneController,
  previousCompleteDay,
  shanghaiDate,
  syncWindow
} from '@/utils/agioneOpsController'
import {
  calendarMonth,
  selectRange,
  shiftDay,
  shiftMonth,
  trendPlot
} from '@/components/agione-demo/core.mjs'
import {
  createAgioneWorkspaceController,
  requestPreviousComparison,
  viewFromHash
} from '@/utils/agioneWorkspaceController'
import AnalysisWorkspace from '@/components/agione-demo/AnalysisWorkspace.vue'
import CustomerWorkspace from '@/components/agione-demo/CustomerWorkspace.vue'
import RequestDrawer from '@/components/agione-demo/RequestDrawer.vue'
import FinancePanel from '@/components/agione-demo/FinancePanel.vue'
import FocusWorkspace from '@/components/agione-demo/FocusWorkspace.vue'
import { claimOriginalDialog, releaseOriginalDialog } from '@/utils/agioneDialog'
import ScopeDialog from '@/components/agione-demo/ScopeDialog.vue'
import DashboardSignals from '@/components/agione-demo/DashboardSignals.vue'
import '@/components/agione-demo/demo-scoped.css'
import '@/components/agione-demo/english-typography.css'

const { t: translate, locale } = useI18n({ useScope: 'global' })
const userStore = useUserStore()
let dateStorage
try { dateStorage = window.sessionStorage } catch (_) {}
const controller = createAgioneController(agioneOpsApi, (next) => {
  state.value = next
}, { nativeOnly: true, localNative: true, dateStorage })
const state = ref(controller.snapshot())
const liveKeys = new Set([
  'cachedRange', 'originalAsOf', 'realSnapshotNotice', 'realSnapshotShort',
  'realSnapshotBadge', 'readOnlyRangeHelp', 'snapshotUnavailable',
  'snapshotUnavailableHelp', 'noConnections', 'noConnectionsHelp',
  'dataVersion', 'loading', 'snapshotWindow', 'refreshSnapshot',
  'readingSnapshot'
])
const t = (key, ...args) => {
  const name = key.replace('agione.', '')
  if (state.value.isLive && liveKeys.has(name))
    return translate(`agione.live.${name}`, ...args)
  if (
    (state.value.sourceKind === 'native' || !state.value.connectionId) &&
    liveKeys.has(name)
  ) return translate(`agione.nativeSnapshot.${name}`, ...args)
  if (state.value.isLive && ['errors.nativeNotConfigured',
    'errors.connectionNotConfigured'].includes(name))
    return translate(`agione.live.${name.split('.').at(-1)}`, ...args)
  if (['errors.nativeNotConfigured',
    'errors.connectionNotConfigured'].includes(name))
    return translate(
      `agione.nativeSnapshot.${name.split('.').at(-1)}`,
      ...args
    )
  return translate(key, ...args)
}

const workspace = createAgioneWorkspaceController(agioneOpsApi, (next) => {
  work.value = next
})
const work = ref(workspace.snapshot())
const workspaceTitle = computed(
  () =>
    ({
      focus: t('agione.demoDashboard'),
      aggregate: t('agione.demoAnalysis'),
      portrait: t('agione.demoPortrait')
    })[work.value.view]
)
const workspaceSubtitle = computed(
  () =>
    ({
      focus: t('agione.overviewSubtitle'),
      aggregate: t('agione.analysisSubtitle'),
      portrait: t('agione.portraitSubtitle')
    })[work.value.view]
)
function analyzeModel(id) {
  window.history.replaceState(
    null,
    '',
    `${window.location.pathname}${window.location.search}#aggregate`
  )
  return workspace.configure({
    view: 'aggregate',
    filters: { ...work.value.filters, modelIds: [id] }
  })
}
function workspaceNavKeys(event) {
  if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return
  event.preventDefault()
  const list = [...event.currentTarget.querySelectorAll('button')]
  const index = list.indexOf(document.activeElement)
  const target =
    event.key === 'Home'
      ? 0
      : event.key === 'End'
        ? list.length - 1
        : (index + (event.key === 'ArrowDown' ? 1 : -1) + list.length) %
          list.length
  list[target]?.focus()
  list[target]?.click()
}
function navigateWorkspace(view) {
  if (window.location.hash !== `#${view}`)
    window.history.replaceState(
      null,
      '',
      `${window.location.pathname}${window.location.search}#${view}`
    )
  return workspace.setView(view)
}
function openWorkspaceCustomer(id) {
  window.history.replaceState(
    null,
    '',
    `${window.location.pathname}${window.location.search}#portrait`
  )
  workspace.openCustomer(id)
}
function restoreWorkspace() {
  workspace.setView(viewFromHash(window.location.hash))
}
watch(
  () => [state.value.connectionId, state.value.dashboard,
    state.value.loading, state.value.listLoading, state.value.readOnly,
    state.value.error],
  ([id, frame, loading, listLoading, readOnly, error]) => {
    if (!id || !readOnly || id !== work.value.connectionId ||
        (!frame && (!loading || error))) workspace.attach(null, '')
    if (loading || listLoading) return
    if (readOnly && frame) {
      let selectedWindow = null
      if (state.value.sourceKind === 'native' && !state.value.isLive) {
        try { selectedWindow = syncWindow(state.value.startDate, state.value.endDate) }
        catch (_) { /* No selected range yet. */ }
      }
      workspace.attach(frame, id, selectedWindow)
    }
    else if (!frame) workspace.attach(null, '')
  },
  { flush: 'sync' }
)
const root = ref(null)
const diagnosis=ref('all')
const dark = ref(false)
const scopeDialog = ref(null)
const scopeDraft = ref({ customerIds: [], modelIds: [], statuses: [] })
function openScope() { workspace.options('customerTenantId'); workspace.options('modelId'); if(work.value.view==='portrait')workspace.queryDirectory();scopeDialog.value.open() }
function clearScope() {
  return workspace.setFilters([], {
    modelIds: [],
    statuses: [],
    failureTypes: []
  })
}
const savedFilters = ref([])
const selectedSavedFilter = ref('')
const saveFilterDialog = ref(null)
const saveFilterNameInput = ref(null)
const saveFilterName = ref('')
function currentFilterValue() {
  return {
    customerIds: [...work.value.customerIds],
    filters: { ...work.value.filters,
      modelIds: [...work.value.filters.modelIds],
      statuses: [...work.value.filters.statuses]
    }
  }
}
function saveCurrentFilter() {
  saveFilterName.value = ''
  claimOriginalDialog(saveFilterDialog.value)
  saveFilterDialog.value?.showModal()
  nextTick(() => saveFilterNameInput.value?.focus())
}
function closeSaveFilter() {
  saveFilterDialog.value?.close()
  releaseOriginalDialog(saveFilterDialog.value)
}
function confirmSaveFilter() {
  const name = saveFilterName.value.trim()
  if (!name) return
  const item = { name, ...currentFilterValue() }
  savedFilters.value = [
    ...savedFilters.value.filter((entry) => entry.name !== name),
    item
  ]
  selectedSavedFilter.value = name
  closeSaveFilter()
}
function applySavedFilter() {
  const item = savedFilters.value.find(
    (entry) => entry.name === selectedSavedFilter.value
  )
  if (item) workspace.setFilters(item.customerIds, item.filters)
}
function removeFilter(kind, value) {
  const customers = kind === 'customer'
    ? work.value.customerIds.filter((id) => id !== value)
    : [...work.value.customerIds]
  const filters = {
    ...work.value.filters,
    modelIds: kind === 'model'
      ? work.value.filters.modelIds.filter((id) => id !== value)
      : [...work.value.filters.modelIds],
    statuses: kind === 'status'
      ? work.value.filters.statuses.filter((status) => status !== value)
      : [...work.value.filters.statuses]
  }
  return workspace.setFilters(customers, filters)
}
const connectionControl = ref(null)
const connectionTrigger = ref(null)
const connectionMenu = ref(null)
const menuOpen = ref(false)
const menuPosition = ref({})
const dateDialog = ref(null)
const dateError = ref(false)
const pendingRange = ref(null)
const previousChecking = ref(false)
const previousAfterCurrent = ref(false)
async function retryPreviousComparison() {
  if (previousChecking.value || state.value.previousLoading) return
  previousChecking.value = true
  try {
    const result = await requestPreviousComparison(workspace, controller)
    if (result === 'current_required') {
      previousAfterCurrent.value = true
      await controller.sync()
      if (state.value.error) previousAfterCurrent.value = false
    }
  } finally {
    previousChecking.value = false
  }
}
watch(() => state.value.syncing, (syncing, before) => {
  if (before && !syncing && !state.value.previousLoading && !state.value.error && work.value.connectionId)
    void workspace.load()
})
watch(() => [state.value.syncing, state.value.loading], ([syncing, loading]) => {
  if (!previousAfterCurrent.value || syncing || loading) return
  previousAfterCurrent.value = false
  if (!state.value.error && !state.value.windowMissing)
    void retryPreviousComparison()
})
watch(() => state.value.previousLoading, (loading, before) => {
  if (before && !loading && !state.value.error && work.value.connectionId)
    void workspace.reload()
}, { flush: 'sync' })
watch(() => state.value.connectionId, () => { pendingRange.value = null })
watch(() => state.value.dashboard, () => {
  const selected = pendingRange.value
  const range = state.value.dashboard?.window
  if (selected && range && !state.value.dashboard?.coverage?.partial &&
      Date.parse(selected.start + 'T00:00:00+08:00') >= Date.parse(range.start) &&
      Date.parse(shiftDay(selected.end, 1) + 'T00:00:00+08:00') <= Date.parse(range.endExclusive))
    pendingRange.value = null
})
const narrow = ref(false)
const dateDraft = ref({
  start: state.value.startDate,
  end: state.value.endDate,
  month: state.value.endDate.slice(0, 7)
})
const latestDay = previousCompleteDay().endDate
const session = computed(() =>
  userStore.isAuthenticated ? `user:${userStore.userInfo?.id || 'pending'}` : ''
)
watch(
  session,
  (key) => {
    controller.reset(key)
    workspace.reset(key)
    workspace.setView(viewFromHash(window.location.hash))
    menuOpen.value = false
    if (dateDialog.value?.open) dateDialog.value.close()
    if (key) controller.load()
  },
  { immediate: true, flush: 'sync' }
)
const connection = computed(() =>
  state.value.connections.find((x) => x.id === state.value.connectionId)
)
const readOnly = computed(() => state.value.readOnly)
const isLive = computed(() => state.value.isLive)
const directoryCoverage = computed(
  () => work.value.coverage || state.value.dashboard?.coverage
)
const sourceTime = computed(() =>
  isLive.value ? state.value.dashboard?.provenance?.fetchedAt : readOnly.value
    ? state.value.dashboard?.provenance?.collectedAt ||
      state.value.dashboard?.publishedAt
    : state.value.dashboard?.publishedAt
)
const sourceBadge = computed(() =>
  isLive.value ? t('agione.live.realSnapshotBadge') : readOnly.value
    ? t('agione.realSnapshotBadge')
    : `${t('agione.localDemo')} · ${t('agione.synthetic')}`
)
const refreshDisabled = computed(
  () =>
    state.value.loading ||
    state.value.listLoading ||
    state.value.syncing ||
    !connection.value ||
    (!readOnly.value && !connection.value.verifiedAt)
)
const refreshLabel = computed(() =>
  isLive.value ? t(state.value.loading ? 'agione.live.refreshing' : 'agione.live.refresh') : readOnly.value
    ? t(
        state.value.syncing ? 'agione.syncing' : state.value.loading
          ? 'agione.readingSnapshot'
          : 'agione.refreshSnapshot'
      )
    : t(state.value.syncing ? 'agione.syncing' : 'agione.demoRefresh')
)
const previousLabel = computed(() =>
  t(
    readOnly.value
      ? 'agione.previousNotIntegrated'
      : 'agione.previousUnavailable'
  )
)
const previousHelp = computed(() =>
  t(readOnly.value ? 'agione.previousNotIntegratedHelp' : 'agione.previousHelp')
)
function refreshCurrent() {
  if (state.value.sourceKind === 'native' || isLive.value)
    return controller.sync()
  if (readOnly.value) return controller.refresh()
  return controller.sync()
}
const platforms = computed(() => [
  ...new Set(state.value.connections.map((x) => x.platform))
])
const ready = computed(
  () =>
    state.value.dashboard?.state === 'ready' && !!state.value.dashboard.summary
)
const displayFrame = computed(() =>
  readOnly.value && work.value.overview
    ? work.value.overview
    : state.value.dashboard
)
const displayStart = computed(() =>
  pendingRange.value?.start || (readOnly.value && work.value.window
    ? shanghaiDate(new Date(work.value.window.start))
    : state.value.startDate)
)
const displayEnd = computed(() =>
  pendingRange.value?.end || (readOnly.value && work.value.window
    ? shanghaiDate(new Date(Date.parse(work.value.window.endExclusive) - 1))
    : state.value.endDate)
)
const summary = computed(() => displayFrame.value?.summary || {})
const trend = computed(() =>
  (displayFrame.value?.trend || []).filter(
    (x) => typeof x.requests === 'number' && x.requests >= 0
  )
)
const plot = computed(() => trendPlot(trend.value, [], 'requests'))
const trendIndexes = computed(() => [
  ...new Set(
    Array.from({ length: Math.min(4, trend.value.length) }, (_, i) =>
      trend.value.length === 1
        ? 0
        : Math.round(
            (i * (trend.value.length - 1)) / Math.min(3, trend.value.length - 1)
          )
    )
  )
])
const models = computed(() =>
  [...(displayFrame.value?.modelDistribution || [])].sort(
    (a, b) => b.requests - a.requests
  )
)
const weekdays = computed(() =>
  locale.value.startsWith('zh')
    ? ['一', '二', '三', '四', '五', '六', '日']
    : ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
)
const calendarMonths = computed(() =>
  narrow.value
    ? [dateDraft.value.month]
    : [dateDraft.value.month, shiftMonth(dateDraft.value.month, 1)]
)
const isLastSeven = computed(
  () =>
    displayStart.value === shiftDay(latestDay, -6) &&
    displayEnd.value === latestDay
)
const snapshotDates = computed(() => {
  const window = readOnly.value
    ? work.value.window || state.value.dashboard?.window
    : state.value.dashboard?.window
  if (
    !window ||
    !Number.isFinite(Date.parse(window.start)) ||
    !Number.isFinite(Date.parse(window.endExclusive))
  )
    return null
  return {
    start: shanghaiDate(new Date(window.start)),
    end: shanghaiDate(new Date(Date.parse(window.endExclusive) - 1))
  }
})
const actualWindow = computed(() =>
  snapshotDates.value
    ? `${snapshotDates.value.start} — ${snapshotDates.value.end}`
    : '—'
)
const windowMismatch = computed(
  () =>
    snapshotDates.value &&
    (snapshotDates.value.start !== state.value.startDate ||
      snapshotDates.value.end !== state.value.endDate)
)
function accountLabel(kind) {
  return kind === 'operator' ? 'Operator' : 'Provider'
}
function selectConnection(id) {
  menuOpen.value = false
  controller.selectConnection(id)
}
async function toggleMenu(force = !menuOpen.value, focus = false) {
  menuOpen.value = force
  if (!force) return
  await nextTick()
  const bounds = connectionTrigger.value?.getBoundingClientRect()
  if (bounds)
    menuPosition.value = {
      left: `${Math.max(8, Math.min(bounds.left, window.innerWidth - 248))}px`,
      top: `${bounds.bottom + 9}px`
    }
  if (focus)
    (
      connectionMenu.value?.querySelector('[aria-checked="true"]') ||
      connectionMenu.value?.querySelector('button')
    )?.focus()
}
function menuKeys(event) {
  const list = [...(connectionMenu.value?.querySelectorAll('button') || [])]
  if (event.key === 'Escape') {
    event.preventDefault()
    menuOpen.value = false
    connectionTrigger.value?.focus()
  } else if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) {
    event.preventDefault()
    const at = list.indexOf(document.activeElement)
    list[
      event.key === 'Home'
        ? 0
        : event.key === 'End'
          ? list.length - 1
          : (at + (event.key === 'ArrowDown' ? 1 : -1) + list.length) %
            list.length
    ]?.focus()
  } else if (event.key === 'Tab') menuOpen.value = false
}
function outsideMenu(event) {
  if (!connectionControl.value?.contains(event.target)) menuOpen.value = false
}
function resize() {
  narrow.value = window.matchMedia('(max-width:560px)').matches
  menuOpen.value = false
}
function openDates() {
  dateDraft.value = {
    start: displayStart.value,
    end: displayEnd.value,
    month: shiftMonth(displayEnd.value.slice(0, 7), narrow.value ? 0 : -1)
  }
  dateError.value = false
  claimOriginalDialog(dateDialog.value)
  dateDialog.value?.showModal()
}
function closeDates() {
  dateDialog.value?.close()
  releaseOriginalDialog(dateDialog.value)
}
function pickDay(day) {
  dateDraft.value = {
    ...dateDraft.value,
    ...selectRange(dateDraft.value, day)
  }
}
function applyDates() {
  try {
    const queryWindow = syncWindow(dateDraft.value.start, dateDraft.value.end)
    if (state.value.sourceKind === 'native') {
      const cached = work.value.cachedWindow
      if (
        cached && !state.value.windowMissing &&
        Date.parse(queryWindow.start) >= Date.parse(cached.start) &&
        Date.parse(queryWindow.endExclusive) <= Date.parse(cached.endExclusive)
      ) {
        controller.setWindow(dateDraft.value.start, dateDraft.value.end)
        pendingRange.value = null
        workspace.setWindow(queryWindow)
      }
      else {
        pendingRange.value = { start: dateDraft.value.start, end: dateDraft.value.end }
        void controller.loadWindow(dateDraft.value.start, dateDraft.value.end)
      }
    } else if (isLive.value) {
      controller.setWindow(dateDraft.value.start, dateDraft.value.end)
      void controller.refresh()
    } else if (readOnly.value) workspace.setWindow(queryWindow)
    else controller.setWindow(dateDraft.value.start, dateDraft.value.end)
    closeDates()
  } catch (_) {
    dateError.value = true
  }
}
function recentSeven() {
  if (state.value.sourceKind === 'native') {
    const start = shiftDay(latestDay, -6)
    const cached = work.value.cachedWindow
    const window = syncWindow(start, latestDay)
    if (
      cached && !state.value.windowMissing && Date.parse(window.start) >= Date.parse(cached.start) &&
      Date.parse(window.endExclusive) <= Date.parse(cached.endExclusive)
    ) {
      controller.setWindow(start, latestDay)
      pendingRange.value = null
      return workspace.setWindow(window)
    }
    pendingRange.value = { start, end: latestDay }
    return controller.loadWindow(start, latestDay)
  }
  if (isLive.value) { controller.setWindow(shiftDay(latestDay, -6), latestDay); return controller.refresh() }
  if (readOnly.value) {
    const cached = work.value.cachedWindow
    if (cached) {
      const end = shanghaiDate(new Date(Date.parse(cached.endExclusive) - 1))
      const start = shiftDay(end, -6)
      return workspace.setWindow({
        ...cached,
        start:
          Date.parse(start + 'T00:00:00+08:00') < Date.parse(cached.start)
            ? cached.start
            : start + 'T00:00:00+08:00'
      })
    }
    return
  }
  controller.setWindow(shiftDay(latestDay, -6), latestDay)
}
function formatNumber(value) {
  return typeof value === 'number' && Number.isFinite(value)
    ? new Intl.NumberFormat(locale.value, { maximumFractionDigits: 2 }).format(
        value
      )
    : '—'
}
function formatPercent(value) {
  return typeof value === 'number' && Number.isFinite(value)
    ? `${formatNumber(value)}%`
    : '—'
}
function updatedTime(value) {
  const date = new Date(value)
  return value && Number.isFinite(date.getTime())
    ? new Intl.DateTimeFormat(locale.value.startsWith('zh') ? 'zh-CN' : 'en-GB', {
        timeZone: 'Asia/Shanghai',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        hourCycle: 'h23'
      }).format(date)
    : t('agione.notUpdated')
}
function formatTime(value) {
  return value && Number.isFinite(Date.parse(value))
    ? new Date(value).toLocaleString(locale.value.startsWith('zh') ? 'zh-CN' : 'en-GB', {
        timeZone: 'Asia/Shanghai'
      })
    : '—'
}
onMounted(() => {
  resize()
  restoreWorkspace()
  window.addEventListener('hashchange', restoreWorkspace)
  document.addEventListener('click', outsideMenu)
  window.addEventListener('resize', resize)
})
onBeforeUnmount(() => {
  releaseOriginalDialog(saveFilterDialog.value,{force:true})
  releaseOriginalDialog(dateDialog.value,{force:true})
  controller.dispose()
  workspace.dispose()
  window.removeEventListener('hashchange', restoreWorkspace)
  document.removeEventListener('click', outsideMenu)
  window.removeEventListener('resize', resize)
})
</script>

<style scoped>
/* Keep portal actions on the original business breadcrumb row. */
.agione-demo.integrated-controls .topbar {
  min-height: 55px;
  flex-wrap: nowrap;
  gap: 12px;
  padding-top: 7px;
  padding-bottom: 7px;
}

.agione-demo.integrated-controls .topbar .header-context {
  flex: 1 1 auto;
  min-width: 0;
  flex-wrap: nowrap;
}

.agione-demo.integrated-controls .topbar .crumb {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex-shrink: 1;
}

.agione-demo.integrated-controls .topbar .connection-control {
  flex-shrink: 0;
}

@media (max-width: 650px) {
  .agione-demo.integrated-controls .topbar {
    gap: 6px;
    padding-right: 10px;
    padding-left: 10px;
  }

  .agione-demo.integrated-controls .topbar .header-context {
    gap: 6px;
  }
}

.agione-demo {
  min-height: 100vh;
  box-sizing: border-box;
}
.agione-demo button:disabled {
  cursor: not-allowed;
}

.save-filter-dialog {
  width: min(420px, calc(100vw - 32px));
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 0;
  color: var(--ink);
  background: var(--surface);
  box-shadow: 0 18px 60px #15283f30;
}
.save-filter-dialog::backdrop { background: #15283f66; }
.save-filter-dialog form { padding: 22px 24px 20px; }
.save-filter-dialog .dialog-head { margin-bottom: 14px; }
.save-filter-dialog .dialog-head h2 { margin: 0; font-size: 18px; }
.save-filter-dialog .dialog-head button {
  border: 0;
  background: transparent;
  color: var(--muted);
  font-size: 20px;
  min-height: 30px;
  padding: 2px 8px;
}
.save-filter-help { margin: 0 0 16px; color: var(--muted); font-size: 13px; }
.save-filter-label { display: block; margin-bottom: 6px; font-size: 12px; color: var(--muted); }
.save-filter-dialog input {
  width: 100%;
  min-height: 40px;
  box-sizing: border-box;
  border: 1px solid var(--line);
  border-radius: 7px;
  padding: 8px 10px;
  color: var(--ink);
  background: var(--surface);
  font: inherit;
}
.save-filter-dialog input:focus { outline: 2px solid var(--blue); outline-offset: 2px; }
.save-filter-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 20px; }
.save-filter-actions button { min-height: 36px; padding: 7px 14px; }
@media (max-width: 560px) {
  .save-filter-dialog form { padding: 18px 16px 16px; }
}
</style>

<style>
html.agione-drawer-open { overflow: hidden; scrollbar-gutter: stable; }
</style>
