<template>
  <section class="space-y-4">
    <div class="panel">
      <div
        class="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between"
      >
        <div>
          <h3 class="panel-title">
            {{ t('llmOps.channelPriceMatrixPanel.title') }}
          </h3>
          <p class="mt-1 text-xs text-slate-500">
            {{ t('llmOps.channelPriceMatrixPanel.subtitle') }}
          </p>
        </div>
        <div class="flex flex-col gap-3 lg:flex-row lg:items-end">
          <label class="matrix-filter">
            <span>{{
              t('llmOps.channelPriceMatrixPanel.filters.search')
            }}</span>
            <input
              v-model="keyword"
              class="llm-ops-input h-9 w-full sm:w-64"
              :placeholder="
                t('llmOps.channelPriceMatrixPanel.searchPlaceholder')
              "
              type="search"
            />
          </label>
          <label class="matrix-filter">
            <span>{{
              t('llmOps.channelPriceMatrixPanel.filters.coverage')
            }}</span>
            <CompactSelect
              v-model="statusFilter"
              :options="statusFilterOptions"
              class-name="w-full sm:w-40"
              size="sm"
            />
          </label>
          <div class="matrix-filter">
            <span>{{
              t('llmOps.channelPriceMatrixPanel.filters.dimension')
            }}</span>
            <div
              class="dimension-switch"
              role="group"
              :aria-label="
                t('llmOps.channelPriceMatrixPanel.filters.dimension')
              "
            >
              <button
                v-for="dimension in dimensions"
                :key="dimension.value"
                type="button"
                :aria-pressed="priceDimension === dimension.value"
                :class="{ 'is-active': priceDimension === dimension.value }"
                @click="priceDimension = dimension.value"
              >
                {{ dimension.label }}
              </button>
            </div>
          </div>
        </div>
      </div>
      <div class="matrix-context mt-4">
        <span>{{ t('llmOps.channelPriceMatrixPanel.context.platform') }}</span>
        <strong>{{ summary.agione?.platform_name || '-' }}</strong>
        <span aria-hidden="true">·</span>
        <span>{{
          t('llmOps.channelPriceMatrixPanel.context.normalized')
        }}</span>
        <span aria-hidden="true">·</span>
        <strong>{{ displayCurrency }} / 1M Tokens</strong>
      </div>
    </div>

    <div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <div v-for="item in metrics" :key="item.label" class="kpi-card">
        <p class="text-xs font-medium text-slate-500">{{ item.label }}</p>
        <p class="kpi-value mt-2 text-2xl font-semibold">{{ item.value }}</p>
        <p class="mt-2 text-xs text-slate-500">{{ item.hint }}</p>
      </div>
    </div>

    <div class="panel overflow-hidden p-0">
      <div class="table-toolbar gap-3">
        <div>
          <h3 class="panel-title">
            {{ t('llmOps.channelPriceMatrixPanel.tableTitle') }}
          </h3>
          <p class="mt-1 text-xs text-slate-500">
            {{ dimensionLabel }} · {{ displayCurrency }} / 1M Tokens
          </p>
        </div>
        <div class="matrix-legend">
          <span>
            <i class="is-best" />
            {{ t('llmOps.channelPriceMatrixPanel.tags.lowest') }}
          </span>
          <span>
            <i class="is-current" />
            {{ t('llmOps.channelPriceMatrixPanel.tags.current') }}
          </span>
          <span>
            <i class="is-stale" />
            {{ t('llmOps.channelPriceMatrixPanel.tags.stale') }}
          </span>
        </div>
      </div>

      <div v-if="filteredRows.length" class="overflow-x-auto">
        <table class="data-table matrix-table">
          <thead>
            <tr>
              <th class="table-head sticky-model">
                {{ t('llmOps.fields.model') }}
              </th>
              <th
                v-for="channel in visibleChannels"
                :key="channel.id"
                class="table-head min-w-48"
              >
                {{ channel.name }}
              </th>
              <th class="table-head sticky-action">
                {{ t('llmOps.channelPriceMatrixPanel.columns.decision') }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in filteredRows" :key="row.model_id">
              <td class="table-cell sticky-model">
                <button
                  type="button"
                  class="model-link"
                  @click="openModelDetail(row)"
                >
                  {{ row.model_name }}
                </button>
                <p class="mt-1 text-xs text-slate-500">
                  {{ row.provider_name }} · {{ row.model_code }}
                </p>
                <p class="mt-1 text-[11px] text-slate-400">
                  {{
                    t('llmOps.channelPriceMatrixPanel.coverageSummary', {
                      covered: row.coverage_count || 0,
                      total: visibleChannels.length
                    })
                  }}
                </p>
              </td>
              <td
                v-for="channel in visibleChannels"
                :key="`${row.model_id}-${channel.id}`"
                class="table-cell p-2"
              >
                <button
                  v-if="optionFor(row, channel)"
                  type="button"
                  :class="priceCellClasses(row, channel)"
                  :aria-label="priceCellLabel(row, channel)"
                  @click="openCompare(row, optionFor(row, channel))"
                >
                  <strong class="font-mono text-sm">
                    {{ optionMoney(optionFor(row, channel)) }}
                  </strong>
                  <span class="price-cell-meta">
                    {{ freshnessLabel(optionFor(row, channel)) }}
                  </span>
                  <span class="price-cell-tags">
                    <span v-if="isBest(row, channel)" class="is-best">
                      {{ t('llmOps.channelPriceMatrixPanel.tags.lowest') }}
                    </span>
                    <span v-if="isCurrent(row, channel)" class="is-current">
                      {{ t('llmOps.channelPriceMatrixPanel.tags.current') }}
                    </span>
                  </span>
                </button>
                <span v-else class="empty-price-cell">—</span>
              </td>
              <td class="table-cell sticky-action">
                <span :class="['status-pill', decisionTone(row)]">
                  {{ decisionLabel(row) }}
                </span>
                <button
                  type="button"
                  :class="[
                    'mt-2 block text-xs font-semibold',
                    effectiveAction(row) === 'keep'
                      ? 'text-slate-500'
                      : 'text-agione-600'
                  ]"
                  @click="runAction(row)"
                >
                  {{ actionLabel(effectiveAction(row)) }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-else class="matrix-empty" role="status">
        <h3>{{ t('llmOps.channelPriceMatrixPanel.emptyTitle') }}</h3>
        <p>{{ t('llmOps.channelPriceMatrixPanel.empty') }}</p>
        <button type="button" class="btn-primary mt-4" @click="resetFilters">
          {{ t('llmOps.channelPriceMatrixPanel.resetFilters') }}
        </button>
      </div>
    </div>

    <ChannelPriceCompareDrawer
      :open="compareOpen"
      :row="compareRow"
      :option="compareOption"
      :dimension="priceDimension"
      :action="compareRow ? effectiveAction(compareRow) : 'keep'"
      :action-text="compareRow ? actionLabel(effectiveAction(compareRow)) : ''"
      :channel-offerings="channelOfferings"
      @close="closeCompare"
      @view-detail="openModelDetail"
      @apply="runAction"
    />
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import {
  effectiveMatrixAction,
  hasStaleChannelPrice,
  optionFreshness
} from '@/utils/llmOpsChannelPriceMatrix'
import { asArray } from '@/utils/llmOpsPagination'

import ChannelPriceCompareDrawer from './ChannelPriceCompareDrawer.vue'
import CompactSelect from './CompactSelect.vue'

const props = defineProps({
  summary: { type: Object, default: () => ({}) },
  channels: { type: Array, default: () => [] },
  channelOfferings: { type: Array, default: () => [] }
})

const emit = defineEmits(['navigate-to-detail', 'navigate-to-section'])
const { t } = useI18n()
const keyword = ref('')
const statusFilter = ref('all')
const priceDimension = ref('input')
const compareOpen = ref(false)
const compareRow = ref(null)
const compareOption = ref(null)

const dimensions = computed(() => [
  { label: t('llmOps.price.input'), value: 'input' },
  { label: t('llmOps.price.output'), value: 'output' }
])
const dimensionLabel = computed(() =>
  priceDimension.value === 'output'
    ? t('llmOps.price.output')
    : t('llmOps.price.input')
)
const statusFilterOptions = computed(() => [
  { label: t('llmOps.channelPriceMatrixPanel.filters.all'), value: 'all' },
  {
    label: t('llmOps.channelPriceMatrixPanel.filters.missing'),
    value: 'missing'
  },
  {
    label: t('llmOps.channelPriceMatrixPanel.filters.single'),
    value: 'single'
  },
  {
    label: t('llmOps.channelPriceMatrixPanel.filters.ready'),
    value: 'ready'
  },
  {
    label: t('llmOps.channelPriceMatrixPanel.filters.stale'),
    value: 'stale'
  }
])

const rows = computed(() =>
  asArray(props.summary.agione?.diagnostics).filter(
    (row) =>
      row.operation_scope !== 'market_reference' ||
      Number(row.coverage_count || 0) > 0
  )
)
const visibleChannels = computed(() =>
  props.channels.filter((channel) => channel.is_active !== false)
)
const displayCurrency = computed(
  () => props.summary.currency?.display_currency || 'CNY'
)

const filteredRows = computed(() => {
  const query = keyword.value.trim().toLowerCase()
  return rows.value.filter((row) => {
    const matchesKeyword =
      !query ||
      [row.model_name, row.model_code, row.provider_name].some((value) =>
        String(value || '')
          .toLowerCase()
          .includes(query)
      )
    if (!matchesKeyword) return false
    if (statusFilter.value === 'missing') return !row.best_channel
    if (statusFilter.value === 'single') return row.coverage_count === 1
    if (statusFilter.value === 'ready') return row.coverage_count > 1
    if (statusFilter.value === 'stale') return hasStaleChannelPrice(row)
    return true
  })
})

const metrics = computed(() => {
  const total = rows.value.length
  const averageCoverage = total
    ? rows.value.reduce(
        (sum, row) => sum + Number(row.coverage_count || 0),
        0
      ) / total
    : 0
  const switchOpportunities = rows.value.filter(
    (row) => row.decision_status === 'not_lowest_channel'
  ).length
  const stalePrices = rows.value.reduce(
    (count, row) =>
      count +
      (row.options || []).filter(
        (option) => optionFreshness(option).state === 'stale'
      ).length,
    0
  )
  return [
    {
      label: t('llmOps.channelPriceMatrixPanel.metrics.total.label'),
      value: total,
      hint: t('llmOps.channelPriceMatrixPanel.metrics.total.hint')
    },
    {
      label: t('llmOps.channelPriceMatrixPanel.metrics.average.label'),
      value: averageCoverage.toFixed(1),
      hint: t('llmOps.channelPriceMatrixPanel.metrics.average.hint')
    },
    {
      label: t('llmOps.channelPriceMatrixPanel.metrics.opportunities.label'),
      value: switchOpportunities,
      hint: t('llmOps.channelPriceMatrixPanel.metrics.opportunities.hint')
    },
    {
      label: t('llmOps.channelPriceMatrixPanel.metrics.stale.label'),
      value: stalePrices,
      hint: t('llmOps.channelPriceMatrixPanel.metrics.stale.hint')
    }
  ]
})

function optionFor(row, channel) {
  return (row.options || []).find(
    (option) => String(option.channel_id) === String(channel.id)
  )
}

function isBest(row, channel) {
  return String(row.best_channel?.channel_id) === String(channel.id)
}

function isCurrent(row, channel) {
  return String(row.current_listing?.channel_id) === String(channel.id)
}

function optionMoney(option) {
  const field =
    priceDimension.value === 'output'
      ? 'output_price_per_million'
      : 'input_price_per_million'
  const value = option?.[field]
  if (value === null || value === undefined || value === '') return '-'
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return '-'
  return `${option.currency || displayCurrency.value} ${parsed.toFixed(4)}`
}

function freshnessLabel(option) {
  const result = optionFreshness(option)
  if (result.state === 'unknown') {
    return t('llmOps.channelPriceMatrixPanel.freshness.unknown')
  }
  const minutes = Math.floor(result.ageMs / (60 * 1000))
  if (minutes < 60) {
    return t('llmOps.channelPriceMatrixPanel.freshness.minutes', {
      count: Math.max(1, minutes)
    })
  }
  const hours = Math.floor(minutes / 60)
  if (hours < 24) {
    return t('llmOps.channelPriceMatrixPanel.freshness.hours', {
      count: hours
    })
  }
  return t('llmOps.channelPriceMatrixPanel.freshness.days', {
    count: Math.floor(hours / 24)
  })
}

function priceCellClasses(row, channel) {
  const option = optionFor(row, channel)
  return [
    'price-cell',
    {
      'is-best': isBest(row, channel),
      'is-current': isCurrent(row, channel),
      'is-stale': optionFreshness(option).state === 'stale'
    }
  ]
}

function priceCellLabel(row, channel) {
  return t('llmOps.channelPriceMatrixPanel.priceCellLabel', {
    channel: channel.name,
    dimension: dimensionLabel.value,
    model: row.model_name,
    price: optionMoney(optionFor(row, channel))
  })
}

function effectiveAction(row) {
  return effectiveMatrixAction(row)
}

const ACTION_LABELS = {
  refresh_prices: 'llmOps.channelPriceMatrixPanel.actions.refreshPrices',
  configure_channel: 'llmOps.decision.action.configureChannel',
  configure_exchange_rate: 'llmOps.decision.action.configureExchange',
  configure_platform_fee: 'llmOps.decision.action.configurePlatformFee',
  review_pricing_or_channel: 'llmOps.decision.action.reviewMargin',
  switch_lowest_channel: 'llmOps.decision.action.switchLowestChannel',
  publish_listing: 'llmOps.decision.action.publishToPlatform',
  add_channel_coverage: 'llmOps.decision.action.addChannelCoverage',
  view_market_price: 'llmOps.decision.action.viewMarketPrice',
  keep: 'llmOps.channelPriceMatrixPanel.actions.viewDetail'
}

function actionLabel(action) {
  return t(ACTION_LABELS[action] || ACTION_LABELS.keep)
}

function decisionLabel(row) {
  if (effectiveAction(row) === 'refresh_prices') {
    return t('llmOps.channelPriceMatrixPanel.status.stale')
  }
  return t(`llmOps.decision.status.${row.decision_status || 'ready'}`)
}

function decisionTone(row) {
  if (effectiveAction(row) === 'refresh_prices') return 'warn'
  if (['no_supply', 'low_yield'].includes(row.decision_status)) return 'danger'
  if (
    ['not_lowest_channel', 'unlisted', 'single_channel'].includes(
      row.decision_status
    )
  ) {
    return 'warn'
  }
  return row.decision_status === 'ready' ? 'success' : 'info'
}

function openCompare(row, option) {
  compareRow.value = row
  compareOption.value = option
  compareOpen.value = true
}

function closeCompare() {
  compareOpen.value = false
  compareRow.value = null
  compareOption.value = null
}

function openModelDetail(row) {
  closeCompare()
  emit('navigate-to-detail', row.model_id)
}

function runAction(row) {
  closeCompare()
  if (effectiveAction(row) === 'refresh_prices') {
    const staleOption = (row.options || []).find(
      (option) => optionFreshness(option).state === 'stale'
    )
    emit('navigate-to-section', {
      section: staleOption?.price_source_id ? 'providers' : 'collectionHealth',
      sourceId: staleOption?.price_source_id || null
    })
    return
  }
  emit('navigate-to-detail', row.model_id)
}

function resetFilters() {
  keyword.value = ''
  statusFilter.value = 'all'
}
</script>

<style scoped>
.matrix-filter {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
.matrix-filter > span,
.matrix-context,
.matrix-legend {
  color: var(--ui-text-muted);
  font-size: 0.72rem;
  font-weight: 600;
}
.dimension-switch {
  display: inline-flex;
  overflow: hidden;
  border: 1px solid var(--ui-border-default);
  border-radius: 0.5rem;
  background: var(--ui-bg-card);
}
.dimension-switch button {
  min-width: 4.5rem;
  min-height: 2.25rem;
  padding: 0.4rem 0.75rem;
  color: var(--ui-text-secondary);
  font-size: 0.75rem;
  font-weight: 600;
}
.dimension-switch button + button {
  border-left: 1px solid var(--ui-border-default);
}
.dimension-switch button.is-active {
  background: var(--ui-color-primary-subtle);
  color: var(--ui-color-primary);
}
.matrix-context,
.matrix-legend,
.matrix-legend span {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.45rem;
}
.matrix-context strong {
  color: var(--ui-text-primary);
}
.matrix-legend {
  gap: 0.9rem;
}
.matrix-legend i {
  width: 0.7rem;
  height: 0.7rem;
  border: 1px solid var(--ui-border-default);
  border-radius: 0.2rem;
  background: var(--ui-bg-muted);
}
.matrix-legend i.is-best {
  border-color: var(--ui-color-success);
  background: var(--ui-color-success-subtle);
}
.matrix-legend i.is-current {
  border-color: var(--ui-color-primary);
  background: var(--ui-color-primary-subtle);
}
.matrix-legend i.is-stale {
  border-color: var(--ui-color-warning);
  background: var(--ui-color-warning-subtle);
}
.matrix-table {
  min-width: 72rem;
}
.sticky-model {
  position: sticky;
  left: 0;
  z-index: 2;
  min-width: 14rem;
  background: var(--ui-bg-card) !important;
  text-align: left !important;
}
thead .sticky-model {
  z-index: 4;
  background: var(--ui-bg-subtle) !important;
}
.sticky-action {
  position: sticky;
  right: 0;
  z-index: 2;
  min-width: 10rem;
  background: var(--ui-bg-card) !important;
}
thead .sticky-action {
  z-index: 4;
  background: var(--ui-bg-subtle) !important;
}
.model-link {
  color: var(--ui-text-primary);
  font-weight: 650;
  text-align: left;
}
.model-link:hover,
.model-link:focus-visible {
  color: var(--ui-color-primary);
  text-decoration: underline;
  text-underline-offset: 0.2rem;
  outline: none;
}
.price-cell {
  display: flex;
  width: 100%;
  min-height: 5.4rem;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.35rem;
  border: 1px solid var(--ui-border-soft);
  border-radius: 0.6rem;
  background: var(--ui-bg-card);
  padding: 0.65rem;
  color: var(--ui-text-primary);
  text-align: left;
  transition:
    border-color 150ms ease,
    background 150ms ease;
}
.price-cell:hover,
.price-cell:focus-visible {
  border-color: var(--ui-color-primary);
  outline: none;
}
.price-cell.is-best {
  border-color: var(--ui-color-success);
  background: var(--ui-color-success-subtle);
}
.price-cell.is-current {
  box-shadow: inset 3px 0 0 var(--ui-color-primary);
}
.price-cell.is-stale {
  border-color: var(--ui-color-warning);
  background: var(--ui-color-warning-subtle);
}
.price-cell-meta {
  color: var(--ui-text-muted);
  font-size: 0.68rem;
}
.price-cell-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
}
.price-cell-tags span {
  border-radius: 999px;
  background: var(--ui-bg-muted);
  padding: 0.12rem 0.4rem;
  color: var(--ui-text-muted);
  font-size: 0.62rem;
  font-weight: 700;
}
.price-cell-tags span.is-best {
  color: var(--ui-color-success);
}
.price-cell-tags span.is-current {
  color: var(--ui-color-primary);
}
.empty-price-cell {
  display: flex;
  min-height: 5.4rem;
  align-items: center;
  justify-content: center;
  border: 1px dashed var(--ui-border-soft);
  border-radius: 0.6rem;
  color: var(--ui-text-muted);
}
.matrix-empty {
  padding: 3.5rem 1.5rem;
  text-align: center;
}
.matrix-empty h3 {
  color: var(--ui-text-primary);
  font-weight: 700;
}
.matrix-empty p {
  margin-top: 0.4rem;
  color: var(--ui-text-muted);
  font-size: 0.8rem;
}
@media (max-width: 640px) {
  .matrix-legend {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
