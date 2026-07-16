<template>
  <section class="space-y-4">
    <div
      class="queue-summary-grid"
      :aria-label="t('llmOps.overview.queueSummaryLabel')"
    >
      <button
        v-for="item in kpiCards"
        :key="item.key"
        type="button"
        :aria-pressed="simulationStatus === item.filter"
        :class="[
          'queue-summary-card',
          item.tone,
          { 'is-active': simulationStatus === item.filter }
        ]"
        @click="simulationStatusModel = item.filter"
      >
        <span class="queue-summary-label">{{ item.label }}</span>
        <strong class="queue-summary-value">{{ item.value }}</strong>
      </button>
    </div>

    <div class="panel overflow-hidden p-0">
      <div class="table-toolbar gap-3">
        <h3 class="panel-title">
          {{ t('llmOps.overview.decisionTable.title') }}
        </h3>
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
              <th class="table-head">
                {{ t('llmOps.overview.columns.decision') }}
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
              <td class="table-cell min-w-52">
                <span :class="['status-pill', row.status_tone]">
                  {{ statusTitle(row) }}
                </span>
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
  'navigateToWorkspace',
  'update:simulationStatus'
])

const { t } = useI18n()

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
  if (!isOperationalRow(row)) {
    emit('navigateToSection', {
      modelId: row.model_id,
      section: 'modelWorkbench'
    })
    return
  }
  emit('navigateToWorkspace', {
    autoListing: Boolean(
      row.current_listing?.is_listed && row.current_listing.channel_id === null
    ),
    modelId: row.model_id
  })
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
.queue-summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
}
.queue-summary-card {
  display: flex;
  min-height: 4.5rem;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  border: 1px solid var(--ui-border-soft);
  border-left: 0.2rem solid var(--ui-color-primary);
  border-radius: 0.5rem;
  background: var(--ui-bg-card);
  padding: 0.875rem 1rem;
  color: var(--ui-text-primary);
  text-align: left;
  transition:
    border-color 0.16s ease,
    background 0.16s ease;
}
.queue-summary-card:hover,
.queue-summary-card:focus-visible,
.queue-summary-card.is-active {
  border-color: var(--ui-color-primary);
  background: var(--ui-color-primary-subtle);
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
  .queue-summary-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}
</style>
