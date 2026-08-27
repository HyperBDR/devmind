<template>
  <section class="space-y-4">
    <div class="overview-intro">
      <div>
        <p class="overview-kicker">{{ t('llmOps.overview.kicker') }}</p>
        <h2 class="overview-title">{{ t('llmOps.overview.title') }}</h2>
        <p class="overview-subtitle">{{ t('llmOps.overview.subtitle') }}</p>
      </div>
      <span class="overview-live-dot">{{ t('llmOps.overview.live') }}</span>
      <div class="overview-key-metrics">
        <button
          v-for="item in headlineKpiCards"
          :key="item.key"
          type="button"
          :class="['headline-metric', item.tone]"
          @click="handleKpiClick(item)"
        >
          <strong>{{ item.value }}</strong>
          <span>{{ item.label }}</span>
        </button>
      </div>
    </div>

    <div class="overview-insight-grid">
      <section class="insight-panel">
        <div class="insight-heading">
          <div>
            <p class="insight-eyebrow">{{ t('llmOps.overview.insights.healthEyebrow') }}</p>
            <h3>{{ t('llmOps.overview.insights.healthTitle') }}</h3>
          </div>
          <span class="insight-value">{{ healthScore }}%</span>
        </div>
        <div class="health-track"><span :style="{ width: `${healthScore}%` }" /></div>
        <div class="health-legend">
          <span><i class="legend-dot success" />{{ t('llmOps.overview.insights.covered') }} {{ coveredCount }}</span>
          <span><i class="legend-dot warn" />{{ t('llmOps.overview.insights.unlisted') }} {{ unlistedCount }}</span>
          <span><i class="legend-dot danger" />{{ t('llmOps.overview.insights.risk') }} {{ riskCount }}</span>
        </div>
      </section>

      <section class="insight-panel">
        <div class="insight-heading">
          <div>
            <p class="insight-eyebrow">{{ t('llmOps.overview.insights.channelEyebrow') }}</p>
            <h3>{{ t('llmOps.overview.insights.channelTitle') }}</h3>
          </div>
          <button class="insight-link" type="button" @click="emit('navigateToSection', 'channelMatrix')">
            {{ t('llmOps.overview.insights.viewDetails') }}
          </button>
        </div>
        <div v-if="channelBreakdown.length" class="channel-breakdown">
          <div v-for="item in channelBreakdown" :key="item.name" class="channel-row">
            <span>{{ item.name }}</span><strong>{{ item.count }}</strong>
            <span class="channel-bar"><i :style="{ width: `${item.percent}%` }" /></span>
          </div>
        </div>
        <p v-else class="insight-empty">{{ t('llmOps.overview.insights.noChannelData') }}</p>
      </section>
    </div>

    <div class="overview-density-grid">
      <section class="density-panel">
        <div class="density-heading">
          <div>
            <p class="insight-eyebrow">{{ t('llmOps.overview.insights.structureEyebrow') }}</p>
            <h3>{{ t('llmOps.overview.insights.structureTitle') }}</h3>
          </div>
        </div>
        <div class="structure-grid">
          <div v-for="item in structureStats" :key="item.label" class="structure-item">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
            <small>{{ item.hint }}</small>
          </div>
        </div>
      </section>

      <section class="density-panel">
        <div class="density-heading">
          <div>
            <p class="insight-eyebrow">{{ t('llmOps.overview.insights.riskEyebrow') }}</p>
            <h3>{{ t('llmOps.overview.insights.riskTitle') }}</h3>
          </div>
          <span class="risk-total">{{ riskCount }}</span>
        </div>
        <div class="risk-breakdown">
          <button v-for="item in riskBreakdown" :key="item.key" type="button" class="risk-row" @click="simulationStatusModel = item.filter">
            <span class="risk-mark" :class="item.tone" />
            <span>{{ item.label }}</span>
            <strong>{{ item.count }}</strong>
          </button>
        </div>
      </section>
    </div>

    <div class="panel overflow-hidden p-0">
      <div class="table-toolbar gap-3">
        <div>
          <h3 class="panel-title">
            {{ t('llmOps.overview.decisionTable.title') }}
          </h3>
          <p class="yield-tip">
            <strong>{{ t('llmOps.overview.yieldTip.label') }}</strong>
            {{ t('llmOps.overview.yieldTip.formula') }}
            <span>{{ t('llmOps.overview.yieldTip.requirement') }}</span>
          </p>
        </div>
        <div
          class="decision-filter-group"
          :aria-label="t('llmOps.overview.filters.label')"
          role="group"
        >
          <button
            v-for="option in simulationStatusOptions"
            :key="option.value"
            type="button"
            :aria-pressed="simulationStatus === option.value"
            :class="[
              'decision-filter-button',
              { 'is-active': simulationStatus === option.value }
            ]"
            @click="simulationStatusModel = option.value"
          >
            {{ option.label }}
          </button>
        </div>
      </div>

      <div class="overflow-x-auto">
        <table class="data-table decision-table">
          <thead>
            <tr>
              <th class="table-head">
                {{ t('llmOps.overview.columns.model') }}
              </th>
              <th class="table-head">
                {{ t('llmOps.overview.columns.procurement') }}
              </th>
              <th class="table-head">
                {{ t('llmOps.overview.columns.listing') }}
              </th>
              <th class="table-head">
                {{ t('llmOps.overview.columns.yield') }}
              </th>
              <th class="table-head min-w-72">
                {{ t('llmOps.overview.columns.recommendation') }}
              </th>
              <th class="table-head">
                {{ t('llmOps.overview.columns.lastUpdate') }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in monitorTableRows"
              :key="row.model_id"
              :aria-label="rowAriaLabel(row)"
              :class="[
                'decision-row transition',
                rowClass(row),
                isOperationalRow(row) ? 'cursor-pointer' : 'cursor-default'
              ]"
              @click="handleRowClick(row)"
            >
              <td class="table-cell min-w-52">
                <p class="font-medium text-slate-900">
                  {{ row.model_name }}
                </p>
                <p class="mt-1 text-xs text-slate-500">
                  {{ modelContext(row) }}
                </p>
              </td>
              <td class="table-cell min-w-52">
                <p class="font-medium text-slate-900">
                  {{ channelText(row.recommended_channel) }}
                </p>
                <p class="mt-1 text-xs text-slate-500">
                  {{ coverageLabel(row) }}
                </p>
                <PricePair :rows="procurementPriceRows(row)" />
              </td>
              <td class="table-cell min-w-48">
                <span
                  :class="
                    row.current_listing?.is_listed ? 'badge-ok' : 'badge-muted'
                  "
                >
                  {{ currentListingText(row) }}
                </span>
                <PricePair :rows="listingPriceRows(row)" />
              </td>
              <td class="table-cell min-w-36">
                <PricePair :rows="yieldRows(row)" />
              </td>
              <td class="table-cell min-w-72">
                <div class="decision-advice">
                  <div class="decision-advice-head">
                    <span :class="['status-pill', row.status_tone]">
                      {{ statusTitle(row) }}
                    </span>
                    <span class="decision-priority">
                      {{ decisionPriorityLabel(row) }}
                    </span>
                  </div>
                  <p class="decision-reason">{{ decisionReason(row) }}</p>
                  <p class="decision-impact">{{ decisionImpact(row) }}</p>
                </div>
                <button
                  type="button"
                  class="decision-action-button"
                  @click.stop="handleRowClick(row)"
                >
                  {{ actionLabel(row) }}
                </button>
              </td>
              <td class="table-cell min-w-36 text-xs text-slate-500">
                <span :title="absoluteTime(row.last_data_event_at)">
                  {{ relativeTime(row.last_data_event_at) }}
                </span>
                <button
                  v-if="isDataEvent(row.data_event_type)"
                  type="button"
                  :class="['event-link', eventTone(row.data_event_type)]"
                  @click.stop="handleDataEvent(row.data_event_type)"
                >
                  {{ eventLabel(row.data_event_type) }}
                </button>
              </td>
            </tr>
            <tr v-if="!monitorTableRows.length">
              <td class="table-cell text-slate-500" colspan="6">
                {{ emptyMessage }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, defineComponent, h } from 'vue'
import { useI18n } from 'vue-i18n'

const PricePair = defineComponent({
  props: {
    rows: { type: Array, default: () => [] }
  },
  setup(props) {
    return () => {
      if (!props.rows.length) {
        return h('span', { class: 'text-slate-400' }, '-')
      }
      return h(
        'div',
        { class: 'price-pair mt-2 font-mono text-xs' },
        props.rows.map((row) =>
          h('span', { class: 'price-pair-row', key: row.label }, [
            h('span', { class: 'price-pair-label' }, row.label),
            h('span', row.value)
          ])
        )
      )
    }
  }
})

const props = defineProps({
  kpiCards: { type: Array, required: true },
  monitorModelSubtitle: { type: Function, required: true },
  monitorTableRows: { type: Array, required: true },
  simulationStatus: { type: String, required: true },
  simulationStatusOptions: { type: Array, required: true }
})

const emit = defineEmits([
  'navigateToSection',
  'update:simulationStatus'
])

const { t } = useI18n()

const headlineKpiKeys = new Set([
  'active_model_skus',
  'channel_coverage_rate',
  'listing_coverage_rate',
  'overall_yield',
  'risk_points'
])

const headlineKpiCards = computed(() =>
  props.kpiCards.filter((item) => headlineKpiKeys.has(item.key))
)

const coveredCount = computed(() => props.monitorTableRows.filter((row) => Number(row.coverage_count || 0) > 0).length)
const unlistedCount = computed(() => props.monitorTableRows.filter((row) => !row.current_listing?.is_listed).length)
const riskCount = computed(() => props.monitorTableRows.filter((row) => Number(row.decision_priority ?? 8) < 8).length)
const healthScore = computed(() => {
  const total = props.monitorTableRows.length
  if (!total) return 0
  return Math.round((coveredCount.value / total) * 100)
})
const channelBreakdown = computed(() => {
  const counts = new Map()
  props.monitorTableRows.forEach((row) => {
    const name = row.recommended_channel?.channel_name || t('llmOps.overview.insights.unassigned')
    counts.set(name, (counts.get(name) || 0) + 1)
  })
  const max = Math.max(...counts.values(), 1)
  return [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 4).map(([name, count]) => ({ name, count, percent: Math.round((count / max) * 100) }))
})

const structureStats = computed(() => [
  { label: t('llmOps.overview.insights.models'), value: props.monitorTableRows.length, hint: t('llmOps.overview.insights.modelsHint') },
  { label: t('llmOps.overview.insights.providers'), value: new Set(props.monitorTableRows.map((row) => row.provider_name).filter(Boolean)).size, hint: t('llmOps.overview.insights.providersHint') },
  { label: t('llmOps.overview.insights.channels'), value: new Set(props.monitorTableRows.map((row) => row.recommended_channel?.channel_name).filter(Boolean)).size, hint: t('llmOps.overview.insights.channelsHint') },
  { label: t('llmOps.overview.insights.listed'), value: props.monitorTableRows.filter((row) => row.current_listing?.is_listed).length, hint: t('llmOps.overview.insights.listedHint') }
])

const riskBreakdown = computed(() => {
  const rows = props.monitorTableRows
  const count = (predicate) => rows.filter(predicate).length
  return [
    { key: 'unlisted', label: t('llmOps.overview.kpi.unlistedModels.label'), count: count((row) => !row.current_listing?.is_listed), filter: 'unlisted', tone: 'warn' },
    { key: 'yield', label: t('llmOps.overview.kpi.unresolvedYieldModels.label'), count: count((row) => row.input_yield == null && row.output_yield == null), filter: 'priority', tone: 'info' },
    { key: 'channel', label: t('llmOps.overview.kpi.missingChannel.label'), count: count((row) => Number(row.coverage_count || 0) === 0), filter: 'no_supply', tone: 'danger' },
    { key: 'decision', label: t('llmOps.overview.kpi.needsAction.label'), count: count((row) => Number(row.decision_priority ?? 8) < 8), filter: 'priority', tone: 'danger' }
  ]
})

const simulationStatusModel = computed({
  get: () => props.simulationStatus,
  set: (value) => emit('update:simulationStatus', value)
})

const emptyMessage = computed(() => {
  if (props.simulationStatus === 'priority') {
    return t('llmOps.overview.emptyDecisionAllReady')
  }
  return t('llmOps.overview.emptyDecisionFiltered')
})

function handleRowClick(row) {
  if (row.decision_action === 'refresh_prices') {
    emit('navigateToSection', {
      section: row.action_price_source_id
        ? 'providers'
        : 'collectionHealth',
      sourceId: row.action_price_source_id || null
    })
    return
  }
  emit('navigateToSection', {
    modelId: row.model_id,
    section: 'modelWorkbench'
  })
}

function handleKpiClick(item) {
  if (item.section) {
    emit('navigateToSection', item.section)
    return
  }
  if (item.filter) simulationStatusModel.value = item.filter
}

function handleDataEvent(type) {
  emit(
    'navigateToSection',
    type === 'reconciliation_anomaly' ? 'reconciler' : 'collectionHealth'
  )
}

function isOperationalRow(row) {
  return row.operation_scope === 'operational'
}

function isDataEvent(type) {
  return Boolean(type && type !== 'updated')
}

function modelContext(row) {
  const subtitle = props.monitorModelSubtitle(row)
  return [row.provider_name, subtitle].filter(Boolean).join(' / ') || '-'
}

function coverageLabel(row) {
  return t('llmOps.overview.coverageCount', {
    count: Number(row.coverage_count || 0)
  })
}

function percent(value) {
  if (value === null || value === undefined || value === '') return '-'
  return `${(Number(value) * 100).toFixed(1)}%`
}

function statusTitle(row) {
  const key = `llmOps.decision.status.${row.decision_status || 'ready'}`
  return t(key)
}

function decisionPriorityLabel(row) {
  const priority = Number(row.decision_priority ?? 8)
  if (priority <= 2) return t('llmOps.overview.priority.urgent')
  if (priority <= 5) return t('llmOps.overview.priority.attention')
  return t('llmOps.overview.priority.normal')
}

function decisionReason(row) {
  return t(`llmOps.overview.advice.${row.decision_status || 'ready'}.reason`, {
    channels: Number(row.coverage_count || 0)
  })
}

function decisionImpact(row) {
  return t(`llmOps.overview.advice.${row.decision_status || 'ready'}.impact`)
}

function rowAriaLabel(row) {
  return `${row.model_name || ''} ${statusTitle(row)} ${actionLabel(row)}`.trim()
}

function rowClass(row) {
  return `decision-row-${row.decision_status || 'ready'}`
}

function channelText(channel) {
  if (props.simulationStatus === 'market_reference') {
    return t('llmOps.decision.status.market_reference')
  }
  if (!channel) return t('llmOps.status.noSupply')
  if (channel.channel_type === 'auto_best' || channel.channel_id === null) {
    return t('llmOps.channel.autoBest')
  }
  return channel.channel_name || '-'
}

function currentListingText(row) {
  if (!isOperationalRow(row)) {
    return t('llmOps.decision.status.market_reference')
  }
  if (!row.current_listing?.is_listed) return t('llmOps.status.unlisted')
  const listing = row.current_listing
  if (listing.channel_type === 'auto_best' || listing.channel_id === null) {
    return t('llmOps.channel.autoBest')
  }
  return listing.channel_name || t('llmOps.status.listed')
}

function procurementPriceRows(row) {
  const channel = row.recommended_channel || row.reference_price
  if (!channel) return []
  return priceRows(
    channel.input_price_per_million,
    channel.output_price_per_million,
    channel.currency
  )
}

function listingPriceRows(row) {
  const listing = row.current_listing
  if (!listing?.is_listed) return []
  return priceRows(
    listing.retail_input_price_per_million,
    listing.retail_output_price_per_million,
    listing.currency
  )
}

function priceRows(input, output, currency) {
  return [
    priceRow(t('llmOps.price.input'), input, currency),
    priceRow(t('llmOps.price.output'), output, currency)
  ]
}

function yieldRows(row) {
  return [
    { label: t('llmOps.price.input'), value: percent(row.input_yield) },
    { label: t('llmOps.price.output'), value: percent(row.output_yield) }
  ]
}

function priceRow(label, value, currency) {
  return {
    label,
    value: formatPrice(value, currency)
  }
}

function formatPrice(value, currency) {
  if (value === null || value === undefined || value === '') return '-'
  const numberValue = Number(value)
  if (!Number.isFinite(numberValue)) return '-'
  return `${currency || ''} ${numberValue.toFixed(4)}`.trim()
}

const DECISION_ACTION_LABELS = {
  refresh_prices: 'llmOps.channelPriceMatrixPanel.actions.refreshPrices',
  configure_channel: 'llmOps.decision.action.configureChannel',
  configure_exchange_rate: 'llmOps.decision.action.configureExchange',
  configure_platform_fee: 'llmOps.decision.action.configurePlatformFee',
  review_pricing_or_channel: 'llmOps.decision.action.reviewMargin',
  switch_lowest_channel: 'llmOps.decision.action.switchLowestChannel',
  publish_listing: 'llmOps.decision.action.publishToPlatform',
  add_channel_coverage: 'llmOps.decision.action.addChannelCoverage',
  keep: 'llmOps.decision.action.keep',
  view_market_price: 'llmOps.decision.action.viewMarketPrice',
  no_supply: 'llmOps.decision.action.configureChannel',
  currency_unresolved: 'llmOps.decision.action.configureExchange',
  platform_fee_unresolved: 'llmOps.decision.action.configurePlatformFee',
  low_yield: 'llmOps.decision.action.reviewMargin',
  not_lowest_channel: 'llmOps.decision.action.switchLowestChannel',
  unlisted: 'llmOps.decision.action.publishToPlatform',
  single_channel: 'llmOps.decision.action.addChannelCoverage',
  market_reference: 'llmOps.decision.action.viewMarketPrice',
  ready: 'llmOps.decision.action.keep'
}

function actionLabel(row) {
  const action = row.decision_action
  const status = row.decision_status || 'ready'
  return t(
    DECISION_ACTION_LABELS[action] ||
      DECISION_ACTION_LABELS[status] ||
      DECISION_ACTION_LABELS.ready
  )
}

const EVENT_LABELS = {
  collection_failed: 'llmOps.overview.event.collectionFailed',
  source_disabled: 'llmOps.overview.event.sourceDisabled',
  reconciliation_anomaly: 'llmOps.overview.event.reconciliationAnomaly',
  stale: 'llmOps.overview.event.stale'
}

const EVENT_TONES = {
  collection_failed: 'event-link-danger',
  source_disabled: 'event-link-warn',
  reconciliation_anomaly: 'event-link-warn',
  stale: 'event-link-info'
}

function eventLabel(type) {
  return t(EVENT_LABELS[type] || EVENT_LABELS.collection_failed)
}

function eventTone(type) {
  return EVENT_TONES[type] || 'event-link-info'
}

function absoluteTime(value) {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}

function relativeTime(value) {
  if (!value) return '-'
  const target = new Date(value).getTime()
  if (!Number.isFinite(target)) return '-'
  const diffMs = Date.now() - target
  if (diffMs < 0) return t('llmOps.overview.time.justNow')
  const sec = Math.floor(diffMs / 1000)
  if (sec < 60) return t('llmOps.overview.time.secondsAgo', { count: sec })
  const min = Math.floor(sec / 60)
  if (min < 60) return t('llmOps.overview.time.minutesAgo', { count: min })
  const hr = Math.floor(min / 60)
  if (hr < 24) return t('llmOps.overview.time.hoursAgo', { count: hr })
  const day = Math.floor(hr / 24)
  if (day < 30) return t('llmOps.overview.time.daysAgo', { count: day })
  return absoluteTime(value)
}
</script>

<style scoped>
.overview-intro {
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  border: 1px solid #dbeafe;
  border-radius: 1.5rem;
  background: radial-gradient(circle at 0% 0%, rgba(16,185,129,.15), transparent 38%), radial-gradient(circle at 100% 100%, rgba(14,165,233,.13), transparent 42%), linear-gradient(135deg, rgba(255,255,255,.98), rgba(248,250,252,.98));
  box-shadow: 0 24px 60px -42px rgba(15,23,42,.45);
  padding: 1.5rem 1.75rem;
}
.overview-key-metrics {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  width: min(100%, 48rem);
  margin-left: auto;
  border-left: 1px solid #dbeafe;
}
.headline-metric {
  min-width: 0;
  padding: .2rem .85rem;
  border-right: 1px solid #dbeafe;
  color: var(--ui-text-secondary);
  text-align: left;
}
.headline-metric strong { display: block; color: var(--ui-text-primary); font-size: 1.45rem; letter-spacing: -.04em; }
.headline-metric span { display: block; margin-top: .2rem; font-size: .68rem; line-height: 1.25; }
.headline-metric.warn strong { color: #b45309; }
.headline-metric.danger strong { color: #dc2626; }
.overview-kicker {
  color: #059669;
  font-size: 0.68rem;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}
.overview-title {
  margin-top: 0.2rem;
  color: var(--ui-text-primary);
  font-size: 1.8rem;
  font-weight: 700;
  letter-spacing: -0.03em;
}
.overview-subtitle {
  margin-top: 0.25rem;
  color: var(--ui-text-secondary);
  font-size: 0.82rem;
}
.overview-live-dot {
  border: 1px solid #a7f3d0;
  border-radius: 999px;
  background: #ecfdf5;
  color: #047857;
  font-size: 0.68rem;
  font-weight: 700;
  padding: 0.35rem 0.65rem;
  text-transform: uppercase;
}
.overview-insight-grid {
  display: grid;
  gap: 0.75rem;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
.insight-panel {
  border: 1px solid var(--ui-border-default);
  border-radius: var(--ui-radius-card);
  background: var(--ui-bg-card);
  padding: 1rem 1.1rem;
}
.insight-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; }
.insight-eyebrow { color: var(--ui-text-muted); font-size: 0.67rem; font-weight: 800; letter-spacing: 0.1em; text-transform: uppercase; }
.insight-heading h3 { margin-top: 0.2rem; color: var(--ui-text-primary); font-size: 0.95rem; font-weight: 700; }
.insight-value { color: var(--ui-color-primary); font-size: 1.45rem; font-weight: 750; }
.health-track { height: 0.45rem; margin-top: 1rem; overflow: hidden; border-radius: 999px; background: var(--ui-bg-muted); }
.health-track span { display: block; height: 100%; border-radius: inherit; background: var(--ui-color-success); }
.health-legend { display: flex; flex-wrap: wrap; gap: 0.8rem; margin-top: 0.8rem; color: var(--ui-text-secondary); font-size: 0.72rem; }
.legend-dot { display: inline-block; width: 0.45rem; height: 0.45rem; margin-right: 0.3rem; border-radius: 50%; }
.legend-dot.success { background: var(--ui-color-success); }
.legend-dot.warn { background: var(--ui-color-warning); }
.legend-dot.danger { background: var(--ui-color-destructive); }
.insight-link { color: var(--ui-color-primary); font-size: 0.72rem; font-weight: 700; }
.insight-link:hover { text-decoration: underline; }
.channel-breakdown { display: grid; gap: 0.65rem; margin-top: 1rem; }
.channel-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 0.5rem; color: var(--ui-text-secondary); font-size: 0.75rem; }
.channel-row strong { color: var(--ui-text-primary); }
.channel-bar { grid-column: 1 / -1; height: 0.28rem; overflow: hidden; border-radius: 999px; background: var(--ui-bg-muted); }
.channel-bar i { display: block; height: 100%; border-radius: inherit; background: var(--ui-color-primary); }
.insight-empty { margin-top: 1rem; color: var(--ui-text-muted); font-size: 0.78rem; }
.overview-density-grid { display: grid; grid-template-columns: 1.2fr .8fr; gap: .75rem; }
.density-panel { border: 1px solid #e5e7eb; border-radius: 1.15rem; background: #fff; padding: 1.1rem 1.2rem; box-shadow: 0 12px 28px -24px rgba(15,23,42,.45); }
.density-heading { display: flex; align-items: flex-start; justify-content: space-between; }
.density-heading h3 { margin-top: .2rem; color: var(--ui-text-primary); font-size: .95rem; font-weight: 700; }
.structure-grid { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: .6rem; margin-top: 1rem; }
.structure-item { border-left: 2px solid #d1fae5; padding-left: .7rem; }
.structure-item span, .structure-item small { display: block; color: var(--ui-text-muted); font-size: .7rem; }
.structure-item strong { display: block; margin: .25rem 0; color: var(--ui-text-primary); font-size: 1.45rem; }
.risk-total { color: #dc2626; font-size: 1.45rem; font-weight: 750; }
.risk-breakdown { display: grid; gap: .25rem; margin-top: .75rem; }
.risk-row { display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: .6rem; border-radius: .55rem; padding: .5rem .35rem; color: var(--ui-text-secondary); font-size: .78rem; text-align: left; }
.risk-row:hover { background: #f8fafc; }
.risk-row strong { color: var(--ui-text-primary); }
.risk-mark { width: .5rem; height: .5rem; border-radius: 50%; background: #94a3b8; }
.risk-mark.warn { background: #f59e0b; }
.risk-mark.danger { background: #ef4444; }
.risk-mark.info { background: #38bdf8; }
.queue-summary-card:hover,
.queue-summary-card:focus-visible,
.queue-summary-card.is-active {
  border-color: #bae6fd;
  background: #f8fafc;
  box-shadow: 0 18px 34px -24px rgba(15,23,42,.5);
  transform: translateY(-2px);
  outline: none;
}
.queue-summary-card.danger {
  border-left-color: var(--ui-color-destructive);
}
.queue-summary-card.warn {
  border-left-color: var(--ui-color-warning);
}
.queue-summary-card.success {
  border-left-color: var(--ui-color-success);
}
.queue-summary-label {
  color: var(--ui-text-secondary);
  font-size: 0.8rem;
  font-weight: 600;
}
.queue-summary-value {
  color: var(--ui-text-primary);
  font-size: 1.5rem;
  line-height: 1;
}
.decision-filter-group {
  display: inline-flex;
  overflow: hidden;
  border: 1px solid var(--ui-border-default);
  border-radius: 0.5rem;
  background: var(--ui-bg-card);
}
.yield-tip {
  max-width: 48rem;
  margin-top: .35rem;
  color: var(--ui-text-secondary);
  font-size: .72rem;
  line-height: 1.5;
}
.yield-tip strong { color: var(--ui-text-primary); }
.yield-tip span { color: var(--ui-text-muted); }
.decision-filter-button {
  min-height: 2rem;
  padding: 0.35rem 0.75rem;
  color: var(--ui-text-secondary);
  font-size: 0.75rem;
  font-weight: 600;
}
.decision-filter-button + .decision-filter-button {
  border-left: 1px solid var(--ui-border-default);
}
.decision-filter-button:hover,
.decision-filter-button:focus-visible,
.decision-filter-button.is-active {
  background: var(--ui-color-primary-subtle);
  color: var(--ui-color-primary);
  outline: none;
}
.decision-table tbody tr {
  border-bottom: 1px solid var(--ui-border-soft);
}
.decision-row {
  transition: background 0.16s ease;
}
.decision-row:hover {
  background: var(--ui-bg-subtle);
}
.decision-row-no_supply > td:first-child,
.decision-row-low_yield > td:first-child {
  box-shadow: inset 0.2rem 0 0 var(--ui-color-destructive);
}
.decision-row-platform_fee_unresolved > td:first-child,
.decision-row-currency_unresolved > td:first-child,
.decision-row-single_channel > td:first-child {
  box-shadow: inset 0.2rem 0 0 var(--ui-color-info);
}
.decision-row-not_lowest_channel > td:first-child,
.decision-row-unlisted > td:first-child {
  box-shadow: inset 0.2rem 0 0 var(--ui-color-warning);
}
.price-pair {
  display: inline-flex;
  min-width: 7.5rem;
  flex-direction: column;
  gap: 0.15rem;
}
.price-pair-row {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  white-space: nowrap;
}
.price-pair-label {
  color: var(--ui-text-muted);
  font-family: inherit;
}
.event-link {
  display: block;
  margin-top: 0.35rem;
  border-radius: 0.25rem;
  font-size: 0.7rem;
  font-weight: 600;
  text-decoration: underline;
  text-underline-offset: 0.15rem;
}
.decision-action-button {
  display: block;
  margin-top: 0.5rem;
  color: var(--ui-color-primary);
  font-size: 0.75rem;
  font-weight: 600;
  text-align: left;
}
.decision-advice { display: grid; gap: .35rem; }
.decision-advice-head { display: flex; align-items: center; gap: .5rem; }
.decision-priority { color: var(--ui-text-muted); font-size: .68rem; font-weight: 650; }
.decision-reason { color: var(--ui-text-primary); font-size: .78rem; font-weight: 600; line-height: 1.4; }
.decision-impact { color: var(--ui-text-secondary); font-size: .72rem; line-height: 1.4; }
.decision-action-button:hover,
.decision-action-button:focus-visible {
  text-decoration: underline;
  text-underline-offset: 0.15rem;
  outline: none;
}
.event-link-danger {
  color: var(--ui-color-destructive);
}
.event-link-warn {
  color: var(--ui-color-warning);
}
.event-link-info {
  color: var(--ui-color-info);
}
.badge-ok,
.badge-muted {
  display: inline-flex;
  align-items: center;
  border-radius: 0.5rem;
  padding: 0.125rem 0.5rem;
  font-size: 0.75rem;
  font-weight: 500;
}
.badge-ok {
  background: var(--ui-color-success-subtle);
  color: var(--ui-color-success);
}
.badge-muted {
  background: var(--ui-bg-muted);
  color: var(--ui-text-muted);
}
@media (min-width: 768px) {
}
@media (max-width: 767px) {
  .overview-insight-grid, .overview-density-grid { grid-template-columns: 1fr; }
  .structure-grid { grid-template-columns: repeat(2, minmax(0,1fr)); }
  .overview-intro { flex-direction: column; }
  .overview-key-metrics { width: 100%; margin: .5rem 0 0; border-top: 1px solid #dbeafe; border-left: 0; }
  .headline-metric { padding: .7rem .45rem 0; }
}
</style>
