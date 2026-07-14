<template>
  <section class="space-y-6">
    <div class="kpi-decision-groups">
      <div
        v-for="group in groupedKpiCards"
        :key="group.key"
        class="kpi-decision-group"
      >
        <div class="kpi-decision-group-head">
          <span class="kpi-decision-group-mark" :class="group.markClass" />
          <span>{{ group.label }}</span>
        </div>
        <div
          class="grid gap-3"
          :class="group.items.length > 1 ? 'md:grid-cols-2' : 'md:grid-cols-1'"
        >
          <div v-for="item in group.items" :key="item.key" class="kpi-card">
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <p class="text-xs font-medium text-slate-500">
                  {{ item.label }}
                </p>
                <p class="kpi-value mt-2 text-2xl font-semibold">
                  {{ item.value }}
                </p>
              </div>
              <span :class="['kpi-tone', item.tone]">
                {{ item.badge }}
              </span>
            </div>
            <div class="mt-3 h-1.5 overflow-hidden rounded-full bg-slate-200">
              <div
                class="h-full rounded-full transition-all"
                :class="item.barClass"
                :style="{ width: `${item.progress}%` }"
              />
            </div>
            <p class="mt-2 text-xs text-slate-500">
              {{ item.hint }}
            </p>
          </div>
        </div>
      </div>
    </div>

    <div class="panel overflow-hidden p-0">
      <div class="table-toolbar">
        <div>
          <h3 class="panel-title">
            {{ t('llmOps.overview.decisionTable.title') }}
          </h3>
          <p class="mt-1 text-xs text-slate-500">
            {{ t('llmOps.overview.decisionTable.subtitle') }}
          </p>
        </div>
        <div class="flex flex-col gap-2 sm:flex-row">
          <CompactSelect
            v-model="simulationStatusModel"
            :options="simulationStatusOptions"
            class-name="w-40"
            size="sm"
          />
        </div>
      </div>
      <div class="overflow-x-auto">
        <table class="data-table decision-table">
          <thead>
            <tr>
              <th class="table-head w-10" />
              <th class="table-head">
                {{ t('llmOps.overview.columns.model') }}
              </th>
              <th class="table-head">
                {{ t('llmOps.overview.columns.provider') }}
              </th>
              <th class="table-head text-right">
                {{ t('llmOps.overview.columns.coverage') }}
              </th>
              <th class="table-head">
                {{ t('llmOps.overview.columns.recommended') }}
              </th>
              <th class="table-head">
                {{ t('llmOps.overview.columns.currentListing') }}
              </th>
              <th class="table-head text-right">
                {{ t('llmOps.overview.columns.purchasePrice') }}
              </th>
              <th class="table-head text-right">
                {{ t('llmOps.overview.columns.listingPrice') }}
              </th>
              <th class="table-head text-right">
                {{ t('llmOps.overview.columns.inputYield') }}
              </th>
              <th class="table-head text-right">
                {{ t('llmOps.overview.columns.outputYield') }}
              </th>
              <th class="table-head">
                {{ t('llmOps.overview.columns.action') }}
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
              :class="['decision-row', rowClass(row)]"
              class="cursor-pointer transition"
              role="button"
              tabindex="0"
              @click="handleRowClick(row)"
              @keydown.enter="handleRowClick(row)"
              @keydown.space.prevent="handleRowClick(row)"
            >
              <td class="table-cell">
                <span
                  :class="['status-icon', row.status_tone]"
                  :title="statusTitle(row)"
                >
                  {{ statusGlyph(row.decision_status) }}
                </span>
              </td>
              <td class="table-cell">
                <p class="font-medium text-slate-900">
                  {{ row.model_name }}
                </p>
                <p
                  v-if="monitorModelSubtitle(row)"
                  class="mt-1 font-mono text-xs text-slate-500"
                >
                  {{ monitorModelSubtitle(row) }}
                </p>
              </td>
              <td class="table-cell">{{ row.provider_name }}</td>
              <td class="table-cell text-right font-mono">
                {{ row.coverage_count }} / {{ operationalChannelCount }}
              </td>
              <td class="table-cell">
                <span v-if="row.recommended_channel?.channel_name">
                  {{ channelText(row.recommended_channel) }}
                </span>
                <span v-else class="text-slate-400">-</span>
              </td>
              <td class="table-cell">
                <span v-if="row.current_listing?.is_listed" class="badge-ok">
                  {{ currentListingText(row) }}
                </span>
                <span v-else class="badge-muted">
                  {{ t('llmOps.status.unlisted') }}
                </span>
              </td>
              <td class="table-cell text-right font-mono text-xs">
                <div v-if="procurementPriceRows(row).length" class="price-pair">
                  <span
                    v-for="price in procurementPriceRows(row)"
                    :key="price.label"
                    class="price-pair-row"
                  >
                    <span class="price-pair-label">{{ price.label }}</span>
                    <span>{{ price.value }}</span>
                  </span>
                </div>
                <span v-else class="text-slate-400">-</span>
              </td>
              <td class="table-cell text-right font-mono text-xs">
                <div v-if="listingPriceRows(row).length" class="price-pair">
                  <span
                    v-for="price in listingPriceRows(row)"
                    :key="price.label"
                    class="price-pair-row"
                  >
                    <span class="price-pair-label">{{ price.label }}</span>
                    <span>{{ price.value }}</span>
                  </span>
                </div>
                <span v-else class="text-slate-400">-</span>
              </td>
              <td class="table-cell text-right font-mono">
                {{ percent(row.input_yield) }}
              </td>
              <td class="table-cell text-right font-mono">
                {{ percent(row.output_yield) }}
              </td>
              <td class="table-cell">
                <div class="decision-action-cell">
                  <span :class="['status-pill', row.status_tone]">
                    {{ actionLabel(row) }}
                  </span>
                  <div class="decision-hover-panel" role="status">
                    <div class="decision-hover-title">
                      {{ statusTitle(row) }}
                    </div>
                    <div class="decision-hover-grid">
                      <span>{{ t('llmOps.overview.hover.action') }}</span>
                      <strong>{{ actionLabel(row) }}</strong>
                      <span>{{ t('llmOps.overview.hover.recommended') }}</span>
                      <strong>{{
                        channelText(row.recommended_channel)
                      }}</strong>
                      <span>{{ t('llmOps.overview.hover.current') }}</span>
                      <strong>{{ currentListingText(row) }}</strong>
                      <span>{{
                        t('llmOps.overview.hover.purchasePrice')
                      }}</span>
                      <strong>{{
                        priceSummary(procurementPriceRows(row))
                      }}</strong>
                      <span>{{ t('llmOps.overview.hover.listingPrice') }}</span>
                      <strong>{{ priceSummary(listingPriceRows(row)) }}</strong>
                      <span>{{ t('llmOps.overview.hover.yield') }}</span>
                      <strong>{{ yieldSummary(row) }}</strong>
                    </div>
                  </div>
                </div>
              </td>
              <td class="table-cell text-xs text-slate-500">
                <div class="flex flex-col gap-1">
                  <span :title="absoluteTime(row.last_data_event_at)">
                    {{ relativeTime(row.last_data_event_at) }}
                  </span>
                  <span
                    v-if="row.data_event_type"
                    :class="['event-pill', eventTone(row.data_event_type)]"
                  >
                    {{ eventLabel(row.data_event_type) }}
                  </span>
                </div>
              </td>
            </tr>
            <tr v-if="!monitorTableRows.length">
              <td class="table-cell text-slate-500" colspan="12">
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
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import CompactSelect from '@/components/llm-ops/CompactSelect.vue'

const props = defineProps({
  kpiCards: { type: Array, required: true },
  monitorModelSubtitle: { type: Function, required: true },
  monitorTableRows: { type: Array, required: true },
  operationalChannelCount: { type: Number, required: true },
  simulationStatus: { type: String, required: true },
  simulationStatusOptions: { type: Array, required: true }
})

const emit = defineEmits(['navigateToWorkspace', 'update:simulationStatus'])

const { t } = useI18n()

const simulationStatusModel = computed({
  get: () => props.simulationStatus,
  set: (value) => emit('update:simulationStatus', value)
})

const emptyMessage = computed(() => {
  if (props.simulationStatus === 'all') {
    return t('llmOps.overview.emptyDecisionRows')
  }
  if (props.simulationStatus === 'priority') {
    return t('llmOps.overview.emptyDecisionAllReady')
  }
  return t('llmOps.overview.emptyDecisionFiltered')
})

const KPI_GROUP_ORDER = ['supply', 'yield', 'data']
const KPI_GROUP_MARKS = {
  supply: 'mark-supply',
  yield: 'mark-yield',
  data: 'mark-data'
}

const groupedKpiCards = computed(() =>
  KPI_GROUP_ORDER.map((key) => ({
    key,
    label: kpiGroupLabel(key),
    markClass: KPI_GROUP_MARKS[key],
    items: props.kpiCards.filter((item) => item.group === key)
  })).filter((group) => group.items.length)
)

function handleRowClick(row) {
  emit('navigateToWorkspace', {
    autoListing: Boolean(
      row.current_listing?.is_listed && row.current_listing.channel_id === null
    ),
    modelId: row.model_id
  })
}

function percent(value) {
  if (value === null || value === undefined || value === '') return '-'
  const num = Number(value) * 100
  return `${num.toFixed(1)}%`
}

const STATUS_GLYPHS = {
  no_supply: '!',
  currency_unresolved: '?',
  platform_fee_unresolved: '⚙',
  low_yield: '¥',
  not_lowest_channel: '↧',
  unlisted: '+',
  single_channel: '◐',
  ready: '✓'
}

function statusGlyph(status) {
  return STATUS_GLYPHS[status] || '·'
}

function statusTitle(row) {
  const key = `llmOps.decision.status.${row.decision_status || 'ready'}`
  return t(key)
}

function rowAriaLabel(row) {
  return `${row.model_name || ''} ${statusTitle(row)} ${actionLabel(row)}`.trim()
}

function rowClass(row) {
  const statusClass = `decision-row-${row.decision_status || 'ready'}`
  return row.is_data_anomaly
    ? `${statusClass} decision-row-data_anomaly`
    : statusClass
}

function channelText(channel) {
  if (!channel) return '-'
  if (channel.channel_type === 'auto_best' || channel.channel_id === null) {
    return t('llmOps.channel.autoBest')
  }
  return channel.channel_name || '-'
}

function currentListingText(row) {
  if (!row.current_listing?.is_listed) return t('llmOps.status.unlisted')
  const listing = row.current_listing
  if (listing.channel_type === 'auto_best' || listing.channel_id === null) {
    return t('llmOps.channel.autoBest')
  }
  return listing.channel_name || t('llmOps.status.listed')
}

function procurementPriceRows(row) {
  const channel = row.recommended_channel
  if (!channel) return []
  return [
    priceRow(
      t('llmOps.price.input'),
      channel.input_price_per_million,
      channel.currency
    ),
    priceRow(
      t('llmOps.price.output'),
      channel.output_price_per_million,
      channel.currency
    )
  ]
}

function listingPriceRows(row) {
  const listing = row.current_listing
  if (!listing?.is_listed) return []
  return [
    priceRow(
      t('llmOps.price.input'),
      listing.retail_input_price_per_million,
      listing.currency
    ),
    priceRow(
      t('llmOps.price.output'),
      listing.retail_output_price_per_million,
      listing.currency
    )
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

function priceSummary(rows) {
  if (!rows.length) return '-'
  return rows.map((row) => `${row.label}: ${row.value}`).join(' / ')
}

function yieldSummary(row) {
  return `${percent(row.input_yield)} / ${percent(row.output_yield)}`
}

const GROUP_LABELS = {
  supply: 'llmOps.overview.kpiGroup.supply',
  yield: 'llmOps.overview.kpiGroup.yield',
  data: 'llmOps.overview.kpiGroup.data'
}

function kpiGroupLabel(group) {
  return t(GROUP_LABELS[group] || GROUP_LABELS.supply)
}

const DECISION_ACTION_LABELS = {
  no_supply: 'llmOps.decision.action.configureChannel',
  currency_unresolved: 'llmOps.decision.action.configureExchange',
  platform_fee_unresolved: 'llmOps.decision.action.configurePlatformFee',
  low_yield: 'llmOps.decision.action.reviewMargin',
  not_lowest_channel: 'llmOps.decision.action.switchLowestChannel',
  unlisted: 'llmOps.decision.action.publishToPlatform',
  single_channel: 'llmOps.decision.action.addChannelCoverage',
  ready: 'llmOps.decision.action.keep'
}

function actionLabel(row) {
  const status = row.decision_status || 'ready'
  return t(DECISION_ACTION_LABELS[status] || DECISION_ACTION_LABELS.ready)
}

const EVENT_LABELS = {
  updated: 'llmOps.overview.event.updated',
  collection_failed: 'llmOps.overview.event.collectionFailed',
  source_disabled: 'llmOps.overview.event.sourceDisabled',
  reconciliation_anomaly: 'llmOps.overview.event.reconciliationAnomaly',
  stale: 'llmOps.overview.event.stale'
}

const EVENT_TONES = {
  updated: 'event-pill-muted',
  collection_failed: 'event-pill-danger',
  source_disabled: 'event-pill-warn',
  reconciliation_anomaly: 'event-pill-warn',
  stale: 'event-pill-info'
}

function eventLabel(type) {
  return t(EVENT_LABELS[type] || EVENT_LABELS.updated)
}

function eventTone(type) {
  return EVENT_TONES[type] || 'event-pill-muted'
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
.kpi-decision-groups {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(0, 1fr) minmax(0, 1fr);
  gap: 1rem;
}
.kpi-decision-group {
  min-width: 0;
}
.kpi-decision-group-head {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
  color: var(--ui-text-muted);
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}
.kpi-decision-group-mark {
  width: 0.45rem;
  height: 0.45rem;
  border-radius: 9999px;
  background: var(--ui-color-primary);
}
.kpi-decision-group-mark.mark-supply {
  background: var(--ui-color-primary);
}
.kpi-decision-group-mark.mark-yield {
  background: var(--ui-color-warning);
}
.kpi-decision-group-mark.mark-data {
  background: var(--ui-color-info);
}
.status-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.5rem;
  height: 1.5rem;
  border-radius: 9999px;
  font-weight: 700;
  font-size: 0.7rem;
  background: var(--ui-color-primary-subtle);
  color: var(--ui-color-primary);
  border: 1px solid var(--ui-border-soft);
}
.status-icon.danger {
  background: var(--ui-color-destructive-subtle);
  color: var(--ui-color-destructive);
}
.status-icon.warn {
  background: var(--ui-color-warning-subtle);
  color: var(--ui-color-warning);
}
.status-icon.success {
  background: var(--ui-color-success-subtle);
  color: var(--ui-color-success);
}
.status-icon.info {
  background: var(--ui-color-info-subtle);
  color: var(--ui-color-info);
}
.event-pill {
  display: inline-flex;
  align-items: center;
  border-radius: 9999px;
  padding: 0 0.5rem;
  height: 1.25rem;
  font-size: 0.7rem;
  font-weight: 500;
  letter-spacing: 0.02em;
  white-space: nowrap;
  border: 1px solid var(--ui-border-soft);
  background: var(--ui-bg-muted);
  color: var(--ui-text-secondary);
}
.event-pill-muted {
  background: var(--ui-bg-muted);
  color: var(--ui-text-muted);
}
.event-pill-danger {
  background: var(--ui-color-destructive-subtle);
  color: var(--ui-color-destructive);
  border-color: rgba(225, 29, 72, 0.2);
}
.event-pill-warn {
  background: var(--ui-color-warning-subtle);
  color: var(--ui-color-warning);
  border-color: rgba(217, 119, 6, 0.2);
}
.event-pill-info {
  background: var(--ui-color-info-subtle);
  color: var(--ui-color-info);
  border-color: rgba(37, 99, 235, 0.2);
}
.decision-table tbody tr {
  border-bottom: 1px solid var(--ui-border-soft);
}
.decision-row {
  position: relative;
  outline: none;
}
.decision-row::before {
  content: '';
  position: absolute;
  inset: 0 auto 0 0;
  width: 0.2rem;
  background: transparent;
}
.decision-row:hover,
.decision-row:focus-visible {
  background: var(--ui-bg-subtle);
}
.decision-row:focus-visible {
  box-shadow: inset 0 0 0 2px rgba(95, 78, 207, 0.28);
}
.decision-row-no_supply,
.decision-row-low_yield {
  background: rgba(255, 241, 242, 0.42);
}
.decision-row-no_supply::before,
.decision-row-low_yield::before {
  background: var(--ui-color-destructive);
}
.decision-row-no_supply > td:first-child,
.decision-row-low_yield > td:first-child {
  box-shadow: inset 0.2rem 0 0 var(--ui-color-destructive);
}
.decision-row-platform_fee_unresolved,
.decision-row-currency_unresolved,
.decision-row-single_channel {
  background: rgba(239, 246, 255, 0.42);
}
.decision-row-platform_fee_unresolved::before,
.decision-row-currency_unresolved::before,
.decision-row-single_channel::before {
  background: var(--ui-color-info);
}
.decision-row-platform_fee_unresolved > td:first-child,
.decision-row-currency_unresolved > td:first-child,
.decision-row-single_channel > td:first-child {
  box-shadow: inset 0.2rem 0 0 var(--ui-color-info);
}
.decision-row-not_lowest_channel,
.decision-row-unlisted {
  background: rgba(255, 251, 235, 0.5);
}
.decision-row-not_lowest_channel::before,
.decision-row-unlisted::before {
  background: var(--ui-color-warning);
}
.decision-row-not_lowest_channel > td:first-child,
.decision-row-unlisted > td:first-child {
  box-shadow: inset 0.2rem 0 0 var(--ui-color-warning);
}
.decision-row-data_anomaly > td:first-child {
  box-shadow: inset 0.2rem 0 0 var(--ui-color-destructive);
}
.price-pair {
  display: inline-flex;
  min-width: 7.5rem;
  flex-direction: column;
  gap: 0.15rem;
}
.price-pair-row {
  display: flex;
  justify-content: flex-end;
  gap: 0.45rem;
  white-space: nowrap;
}
.price-pair-label {
  color: var(--ui-text-muted);
  font-family: inherit;
}
.decision-action-cell {
  position: relative;
  display: inline-flex;
}
.decision-hover-panel {
  position: absolute;
  z-index: 20;
  top: calc(100% + 0.5rem);
  right: 0;
  width: min(22rem, calc(100vw - 2rem));
  padding: 0.75rem;
  border: 1px solid var(--ui-border-default);
  border-radius: 0.5rem;
  background: var(--ui-bg-card);
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.16);
  opacity: 0;
  transform: translateY(-0.25rem);
  pointer-events: none;
  transition:
    opacity 0.16s ease,
    transform 0.16s ease;
}
.decision-row:hover .decision-hover-panel,
.decision-row:focus-within .decision-hover-panel {
  opacity: 1;
  transform: translateY(0);
}
.decision-hover-title {
  margin-bottom: 0.5rem;
  color: var(--ui-text-primary);
  font-size: 0.78rem;
  font-weight: 700;
}
.decision-hover-grid {
  display: grid;
  grid-template-columns: max-content minmax(0, 1fr);
  gap: 0.35rem 0.75rem;
  color: var(--ui-text-muted);
  font-size: 0.75rem;
}
.decision-hover-grid strong {
  min-width: 0;
  color: var(--ui-text-primary);
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.badge-ok {
  display: inline-flex;
  align-items: center;
  border-radius: 0.5rem;
  background: var(--ui-color-success-subtle);
  color: var(--ui-color-success);
  padding: 0.125rem 0.5rem;
  font-size: 0.75rem;
  font-weight: 500;
}
.badge-muted {
  display: inline-flex;
  align-items: center;
  border-radius: 0.5rem;
  background: var(--ui-bg-muted);
  color: var(--ui-text-muted);
  padding: 0.125rem 0.5rem;
  font-size: 0.75rem;
  font-weight: 500;
}
@media (max-width: 1024px) {
  .kpi-decision-groups {
    grid-template-columns: 1fr;
  }
}
</style>
