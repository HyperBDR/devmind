<!--
  AgioneListingStatusBoard — overview of resale listings on the current
  platform. Re-styled to match the demo "model publishing" list view,
  but keeps the existing emit contract so the parent (LLMOps.vue) does
  not need to be rewritten. The board now exposes `open-workspace` for
  the immersive workspace drawer.
-->
<template>
  <section class="space-y-4">
    <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
      <div
        v-for="item in listingKpis"
        :key="item.label"
        class="rounded-[12px] border border-slate-200 bg-white px-4 py-3 shadow-sm"
      >
        <p class="text-xs font-medium text-slate-500">
          {{ item.label }}
        </p>
        <p
          class="mt-2 flex items-baseline gap-2 font-mono text-2xl font-semibold text-slate-900"
        >
          {{ item.value }}
          <span
            v-if="item.delta"
            :class="item.deltaTone"
            class="text-xs font-medium"
          >
            {{ item.delta }}
          </span>
        </p>
        <p v-if="item.hint" class="mt-1 text-[11px] text-slate-400">
          {{ item.hint }}
        </p>
      </div>
    </div>

    <div class="panel overflow-hidden p-0">
      <div class="listing-board-toolbar">
        <div class="listing-board-heading">
          <h3 class="panel-title">
            {{ t('llmOps.listingBoard.title') }}
          </h3>
          <p class="listing-board-subtitle">
            {{ t('llmOps.listingBoard.subtitle') }}
          </p>
        </div>
        <div class="listing-board-controls">
          <input
            v-model="searchQuery"
            type="text"
            class="listing-search-input"
            :placeholder="t('llmOps.listingBoard.searchPlaceholder')"
          />
          <div class="status-filter-group">
            <button
              v-for="option in listingStatusOptions"
              :key="option.value"
              type="button"
              class="status-filter-chip"
              :class="
                listingStatusFilter === option.value
                  ? 'status-filter-chip-active'
                  : ''
              "
              @click="listingStatusFilter = option.value"
            >
              {{ option.label }}
            </button>
          </div>
          <label class="pagination-size-field">
            <span>{{ t('llmOps.listingBoard.pagination.pageSize') }}</span>
            <select v-model.number="pageSize" class="pagination-select">
              <option v-for="size in pageSizeOptions" :key="size" :value="size">
                {{ size }}
              </option>
            </select>
          </label>
          <span class="listing-count">
            {{ filteredListingRows.length }} /
            {{ visibleListingRows.length }}
          </span>
          <div class="export-control-group">
            <label class="sr-only" for="listing-export-format">
              {{ t('llmOps.listingBoard.export.formatLabel') }}
            </label>
            <select
              id="listing-export-format"
              v-model="exportFormat"
              class="export-format-select"
            >
              <option value="csv">
                {{ t('llmOps.listingBoard.export.csv') }}
              </option>
              <option value="excel">
                {{ t('llmOps.listingBoard.export.excel') }}
              </option>
            </select>
            <button
              type="button"
              class="export-listing-button"
              :disabled="!exportableRows.length"
              @click="exportListings"
            >
              {{ t('llmOps.listingBoard.export.action') }}
            </button>
          </div>
          <template v-if="selectedRows.length">
            <span class="listing-selected-count">
              {{
                t('llmOps.listingBoard.selectedCount', {
                  count: selectedRows.length
                })
              }}
            </span>
            <button
              type="button"
              class="batch-action"
              :class="batchActionClass(batchConfirmTone)"
              :disabled="!batchConfirmAction || savingListings"
              @click="handleBatchAction('confirm')"
            >
              {{ batchConfirmLabel }}
            </button>
            <button
              type="button"
              class="batch-action"
              :class="batchActionClass('danger')"
              :disabled="!canBatchOffline || savingListings"
              @click="handleBatchAction('offline')"
            >
              {{ t('llmOps.listingBoard.batch.offline') }}
            </button>
            <button
              type="button"
              class="batch-action"
              :class="batchActionClass('default')"
              :disabled="savingListings"
              @click="handleBatchAction('price')"
            >
              {{ t('llmOps.listingBoard.batch.price') }}
            </button>
          </template>
          <button
            type="button"
            class="add-listing-button btn-action-create"
            @click="openWorkspace(null, 'create')"
          >
            {{ t('llmOps.listingBoard.createListing') }}
          </button>
        </div>
      </div>

      <div class="overflow-x-auto">
        <table class="data-table listing-table">
          <colgroup>
            <col class="select-col" />
            <col class="platform-col" />
            <col class="model-col" />
            <col class="source-col" />
            <col class="cost-col" />
            <col class="retail-col" />
            <col class="point-col" />
            <col class="margin-col" />
            <col class="status-col" />
            <col class="action-col" />
          </colgroup>
          <thead>
            <tr>
              <th class="table-head w-10">
                <input
                  class="row-checkbox"
                  type="checkbox"
                  :checked="allVisibleSelected"
                  :disabled="!selectableRows.length"
                  @change="toggleAllVisible"
                />
              </th>
              <th class="table-head">
                {{ t('llmOps.listingBoard.table.platform') }}
              </th>
              <th class="table-head min-w-[200px]">
                {{ t('llmOps.listingBoard.table.model') }}
              </th>
              <th class="table-head">
                {{ t('llmOps.listingBoard.table.supplyChain') }}
              </th>
              <th class="table-head">
                {{ t('llmOps.listingBoard.table.cost') }}
              </th>
              <th class="table-head">
                {{ t('llmOps.listingBoard.table.retail') }}
              </th>
              <th class="table-head">
                {{ t('llmOps.listingBoard.table.points') }}
              </th>
              <th class="table-head">
                {{ t('llmOps.listingBoard.table.margin') }}
              </th>
              <th class="table-head">
                {{ t('llmOps.listingBoard.table.status') }}
              </th>
              <th class="table-head">
                {{ t('llmOps.listingBoard.table.actions') }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in paginatedListingRows"
              :key="row.status_listing?.id || 'model-' + row.model.id"
              class="cursor-default"
            >
              <td class="table-cell">
                <input
                  class="row-checkbox"
                  type="checkbox"
                  :checked="selectedModelIds.has(rowSelectionKey(row))"
                  :disabled="!isSelectable(row)"
                  @change="toggleRow(row)"
                />
              </td>
              <td class="table-cell">
                <p class="font-medium text-slate-900">
                  {{ platformLabel }}
                </p>
              </td>
              <td class="table-cell">
                <p class="font-medium text-slate-900">
                  {{ rows.modelDisplayName(row.model) }}
                </p>
                <p
                  v-if="rows.listingModelSubtitle(row)"
                  class="mt-1 font-mono text-[11px] text-slate-500"
                >
                  {{ rows.listingModelSubtitle(row) }}
                </p>
              </td>
              <td class="table-cell">
                <p class="font-medium text-slate-900">
                  {{ row.provider_name || '—' }}
                </p>
                <p class="mt-0.5 text-[11px] text-slate-500">
                  {{ activeListingChannelLabel(row) }}
                </p>
              </td>
              <td class="table-cell">
                <div class="metric-stack">
                  <div
                    v-for="metric in listingPriceMetrics(row)"
                    :key="`cost-${metric.key}`"
                    class="metric-line"
                  >
                    <span class="metric-label">{{ metric.label }}</span>
                    <strong class="metric-value">{{ metric.cost }}</strong>
                  </div>
                </div>
              </td>
              <td class="table-cell">
                <div class="metric-stack">
                  <div
                    v-for="metric in listingPriceMetrics(row)"
                    :key="`retail-${metric.key}`"
                    class="metric-line metric-line-value"
                  >
                    <strong class="metric-value text-emerald-600">
                      {{ metric.retail }}
                    </strong>
                  </div>
                </div>
              </td>
              <td class="table-cell">
                <div class="metric-stack">
                  <div
                    v-for="metric in listingPriceMetrics(row)"
                    :key="`point-${metric.key}`"
                    class="metric-line metric-line-value"
                  >
                    <strong class="metric-value text-agione-600">
                      {{ metric.points }}
                    </strong>
                  </div>
                </div>
              </td>
              <td class="table-cell">
                <span
                  v-if="listingUnifiedMarginRate(row) !== null"
                  class="margin-pill"
                  :class="marginPillTone(row)"
                  :title="marginPillTitle(row)"
                  :aria-label="marginPillTitle(row)"
                >
                  {{ Number(listingUnifiedMarginRate(row)).toFixed(1) }}%
                </span>
                <span v-else class="text-slate-400">—</span>
              </td>
              <td class="table-cell">
                <span class="status-pill" :class="statusPillTone(row)">
                  {{ statusPillLabel(row) }}
                </span>
              </td>
              <td class="table-cell action-cell">
                <div class="row-actions">
                  <OperationIconButton
                    v-for="action in rowStateActions(row)"
                    :key="action.kind"
                    :icon="rowActionIcon(action.kind)"
                    :label="action.label"
                    :tone="action.tone"
                    :disabled="savingListings"
                    @click="emitAction(row, action.kind)"
                  />
                </div>
              </td>
            </tr>
            <tr v-if="!paginatedListingRows.length">
              <td class="table-cell text-slate-500" colspan="10">
                {{ listingEmptyText }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="filteredListingRows.length" class="pagination-bar">
        <p class="pagination-summary">
          {{
            t('llmOps.listingBoard.pagination.summary', {
              current: currentPage,
              total: totalPages,
              count: filteredListingRows.length
            })
          }}
        </p>
        <div class="pagination-actions">
          <button
            type="button"
            class="pagination-button"
            :disabled="currentPage <= 1"
            @click="goToPreviousPage"
          >
            {{ t('llmOps.listingBoard.pagination.previous') }}
          </button>
          <button
            type="button"
            class="pagination-button"
            :disabled="currentPage >= totalPages"
            @click="goToNextPage"
          >
            {{ t('llmOps.listingBoard.pagination.next') }}
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, toRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { llmOpsApi } from '@/api/llmOps'
import OperationIconButton from '@/components/llm-ops/OperationIconButton.vue'
import { useToast } from '@/composables/useToast'
import { useAgioneListingRows } from '@/composables/useAgioneListingRows'
import {
  averageMarginRate,
  RESALE_PRICE_DIMENSION_SPECS
} from '@/utils/resalePricing'

const props = defineProps({
  agionePlatform: {
    type: Object,
    default: null
  },
  providers: {
    type: Array,
    required: true
  },
  models: {
    type: Array,
    required: true
  },
  priceItems: {
    type: Array,
    default: () => []
  },
  listings: {
    type: Array,
    required: true
  },
  summary: {
    type: Object,
    required: true
  },
  platformCount: {
    type: Number,
    default: 0
  },
  pointConversion: {
    type: Object,
    default: null
  },
  displayCurrency: {
    type: String,
    default: 'CNY'
  },
  exchangeRate: {
    type: Number,
    default: 7.15
  }
})

const emit = defineEmits([
  'refresh',
  'action',
  'open-workspace',
  'listings-updated'
])
const { t } = useI18n()
const { showSuccess, showError } = useToast()

const listingStatusFilter = ref('all')
const searchQuery = ref('')
const pageSize = ref(10)
const currentPage = ref(1)
const savingListings = ref(false)
const selectedModelIds = ref(new Set())
const exportFormat = ref('csv')
const pageSizeOptions = [10, 20, 50]

const listingStatusOptions = computed(() => [
  { label: t('llmOps.listingBoard.filters.actionable'), value: 'actionable' },
  { label: t('llmOps.listingBoard.filters.all'), value: 'all' },
  { label: t('llmOps.listingBoard.filters.listed'), value: 'listed' }
])

const unusedModelId = ref('')
const unusedChannelId = ref('')
const unusedProfitRate = ref('0')

const rows = useAgioneListingRows({
  agionePlatformRef: toRef(props, 'agionePlatform'),
  providersRef: toRef(props, 'providers'),
  modelsRef: toRef(props, 'models'),
  priceItemsRef: toRef(props, 'priceItems'),
  listingsRef: toRef(props, 'listings'),
  summaryRef: toRef(props, 'summary'),
  displayCurrencyRef: toRef(props, 'displayCurrency'),
  exchangeRateRef: toRef(props, 'exchangeRate'),
  selectedTrendModelIdRef: unusedModelId,
  selectedTrendChannelIdRef: unusedChannelId,
  trendProfitRateRef: unusedProfitRate,
  pointConversionRef: toRef(props, 'pointConversion')
})

const platformLabel = computed(
  () => props.agionePlatform?.name || t('llmOps.listingBoard.platformFallback')
)

const visibleListingRows = computed(() =>
  rows.listingRows.value.filter((row) => !isHiddenRow(row))
)

const filteredListingRows = computed(() => {
  const all = visibleListingRows.value
  const query = String(searchQuery.value || '')
    .trim()
    .toLowerCase()
  return all
    .filter((row) => {
      if (listingStatusFilter.value === 'actionable') {
        if (!isActionableRow(row)) return false
      } else if (listingStatusFilter.value === 'listed') {
        if (!row.is_listed) return false
      } else if (listingStatusFilter.value === 'all') {
        // visible rows only
      } else {
        return false
      }
      if (!query) return true
      const name = String(rows.modelDisplayName(row.model) || '').toLowerCase()
      const code = String(row.model?.code || '').toLowerCase()
      return name.includes(query) || code.includes(query)
    })
    .sort((left, right) => {
      if (listingStatusFilter.value !== 'all') return 0
      return String(left.model?.name || '').localeCompare(
        String(right.model?.name || '')
      )
    })
})

const totalPages = computed(() =>
  Math.max(1, Math.ceil(filteredListingRows.value.length / pageSize.value))
)

const paginatedListingRows = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredListingRows.value.slice(start, start + pageSize.value)
})

const selectableRows = computed(() =>
  paginatedListingRows.value.filter((row) => isSelectable(row))
)

const selectedRows = computed(() =>
  filteredListingRows.value.filter((row) =>
    selectedModelIds.value.has(rowSelectionKey(row))
  )
)

const exportableRows = computed(() =>
  filteredListingRows.value.filter(
    (row) => row.status_listing && !isHiddenRow(row)
  )
)

const selectedOfflineRows = computed(() =>
  selectedRows.value.filter(
    (row) => row.workflow_status === 'online' && !isHiddenRow(row)
  )
)

const canBatchOffline = computed(
  () =>
    selectedRows.value.length > 0 &&
    selectedRows.value.every(
      (row) => row.workflow_status === 'online' && !isHiddenRow(row)
    )
)

const batchConfirmAction = computed(() => {
  if (!selectedRows.value.length) return ''
  const actions = new Set(
    selectedRows.value
      .filter((row) => !isHiddenRow(row))
      .map((row) => batchConfirmActionForStatus(row.workflow_status))
      .filter(Boolean)
  )
  return actions.size === 1 ? Array.from(actions)[0] : ''
})

const batchConfirmLabel = computed(() => {
  return (
    {
      submit: t('llmOps.listingBoard.batch.confirmSubmit'),
      confirm_publish: t('llmOps.listingBoard.batch.confirmPublish'),
      confirm_update: t('llmOps.listingBoard.batch.confirmUpdate'),
      confirm_offline: t('llmOps.listingBoard.batch.confirmOffline')
    }[batchConfirmAction.value] || t('llmOps.listingBoard.batch.confirm')
  )
})

const batchConfirmTone = computed(() => actionTone(batchConfirmAction.value))

function batchConfirmActionForStatus(status) {
  return (
    {
      draft: 'submit',
      update_draft: 'submit',
      pending_publish: 'confirm_publish',
      pending_update: 'confirm_update',
      pending_offline: 'confirm_offline'
    }[status] || ''
  )
}

function actionTone(kind) {
  return (
    {
      submit: 'primary',
      confirm_publish: 'success',
      confirm_update: 'success',
      confirm_offline: 'danger',
      request_offline: 'warn',
      direct_offline: 'danger',
      mark_offline_exception: 'danger',
      delete: 'danger',
      republish: 'primary',
      start_edit: 'default',
      edit: 'default',
      withdraw: 'default',
      abandon_update: 'warn',
      reject_offline: 'default'
    }[kind] || 'default'
  )
}

function rowActionIcon(kind) {
  return (
    {
      abandon_update: 'remove',
      confirm_offline: 'powerOff',
      confirm_publish: 'approve',
      confirm_update: 'approve',
      create: 'add',
      delete: 'delete',
      direct_offline: 'powerOff',
      edit: 'edit',
      mark_offline_exception: 'reject',
      reject_offline: 'reject',
      republish: 'submit',
      request_offline: 'offlineRequest',
      start_edit: 'edit',
      submit: 'submit',
      withdraw: 'withdraw'
    }[kind] || 'edit'
  )
}

function batchActionClass(tone) {
  return `batch-action-${tone || 'default'}`
}

const allVisibleSelected = computed(
  () =>
    selectableRows.value.length > 0 &&
    selectableRows.value.every((row) =>
      selectedModelIds.value.has(rowSelectionKey(row))
    )
)

const listingKpis = computed(() => {
  const visibleRows = visibleListingRows.value
  const listedRows = visibleRows.filter((row) => row.is_listed)
  const rowMargins = listedRows
    .map((row) => listingUnifiedMarginRate(row))
    .filter((value) => value !== null)
  const avgMargin = rowMargins.length
    ? Number(
        (
          rowMargins.reduce((sum, value) => sum + value, 0) / rowMargins.length
        ).toFixed(1)
      )
    : null
  return [
    {
      label: t('llmOps.listingBoard.kpis.availableModels.label'),
      value: visibleRows.length,
      hint: t('llmOps.listingBoard.kpis.availableModels.hint', {
        count: unlistedCount(visibleRows, listedRows)
      }),
      delta: t('llmOps.listingBoard.kpis.availableModels.delta'),
      deltaTone: 'text-slate-400'
    },
    {
      label: t('llmOps.listingBoard.kpis.platforms.label'),
      value: props.platformCount,
      hint: t('llmOps.listingBoard.kpis.platforms.hint'),
      delta: t('llmOps.listingBoard.kpis.platforms.delta'),
      deltaTone: 'text-slate-400'
    },
    {
      label: t('llmOps.listingBoard.kpis.listed.label'),
      value: listedRows.length,
      hint: t('llmOps.listingBoard.kpis.listed.hint'),
      delta:
        listedRows.length > 0
          ? t('llmOps.listingBoard.kpis.listed.activeDelta')
          : t('llmOps.listingBoard.kpis.listed.pendingDelta'),
      deltaTone: listedRows.length > 0 ? 'text-emerald-600' : 'text-amber-600'
    },
    {
      label: t('llmOps.listingBoard.kpis.unlisted.label'),
      value: visibleRows.length - listedRows.length,
      hint: t('llmOps.listingBoard.kpis.unlisted.hint'),
      delta: t('llmOps.listingBoard.kpis.unlisted.delta'),
      deltaTone: 'text-amber-600'
    },
    {
      label: t('llmOps.listingBoard.kpis.averageMargin.label'),
      value: avgMargin !== null ? `${avgMargin}%` : '—',
      hint: t('llmOps.listingBoard.kpis.averageMargin.hint'),
      delta: t('llmOps.listingBoard.kpis.averageMargin.delta'),
      deltaTone: 'text-slate-400'
    }
  ]
})

function unlistedCount(visibleRows, listedRows) {
  return visibleRows.length - listedRows.length
}

const listingEmptyText = computed(() => {
  if (listingStatusFilter.value === 'actionable')
    return t('llmOps.listingBoard.empty.actionable')
  if (listingStatusFilter.value === 'listed')
    return t('llmOps.listingBoard.empty.listed')
  return t('llmOps.listingBoard.empty.default')
})

function isHiddenRow(row) {
  return (
    row.is_removed ||
    row.workflow_status === 'deleted' ||
    row.publish_status === 'deleted'
  )
}

function isActionableRow(row) {
  if (isHiddenRow(row)) return false
  if (
    [
      'draft',
      'pending_publish',
      'update_draft',
      'pending_update',
      'pending_offline',
      'offline_exception',
      'offline'
    ].includes(row.workflow_status)
  ) {
    return true
  }
  return false
}

function activeListingChannelLabel(row) {
  const activeListings = row.active_listings || []
  if (activeListings.length > 1) {
    return t('llmOps.listingBoard.supply.activeLinks', {
      count: activeListings.length
    })
  }
  return row.lowest_option?.channel_name || t('llmOps.listingBoard.supply.none')
}

function listingPriceMetrics(row) {
  return RESALE_PRICE_DIMENSION_SPECS.filter((spec) => {
    if (spec.key !== 'cache') return true
    return (
      row.status_listing?.[spec.retailField] ||
      row.lowest_option?.[spec.costField]
    )
  }).map((spec) => ({
    key: spec.key,
    label: spec.label,
    retail: listingAmountText(
      listingDisplayAmount(
        row.status_listing?.[spec.retailField],
        row.status_listing?.currency
      )
    ),
    points: listingPointText(
      row.status_listing?.[spec.retailField],
      row.status_listing?.currency
    ),
    cost: listingAmountText(row.lowest_option?.[spec.costField])
  }))
}

function listingAmountText(value) {
  if (value === null || value === undefined || value === '') return '-'
  const amount = Number(value)
  if (!Number.isFinite(amount)) return '-'
  return amount.toFixed(4)
}

function listingPointText(value, currency) {
  const amount = Number(value)
  const rate = Number(props.pointConversion?.points_per_currency_unit || 0)
  if (!Number.isFinite(amount) || !Number.isFinite(rate) || rate <= 0) {
    return '-'
  }
  const converted = convertPointCurrencyAmount(
    amount,
    currency,
    props.pointConversion?.currency
  )
  if (converted === null) return '-'
  return String(Math.round(converted * rate))
}

function listingDisplayAmount(value, currency) {
  return convertPointCurrencyAmount(
    value,
    currency,
    props.displayCurrency || 'CNY'
  )
}

function listingCurrency(row) {
  return row.status_listing?.currency || props.displayCurrency || 'CNY'
}

function metricCostValue(row, spec) {
  return formatExportAmount(row.lowest_option?.[spec.costField])
}

function metricRetailValue(row, spec) {
  return formatExportAmount(row.status_listing?.[spec.retailField])
}

function metricPointValue(row, spec) {
  const points = listingPointText(
    row.status_listing?.[spec.retailField],
    row.status_listing?.currency
  )
  return points === '-' ? '' : points
}

function formatExportAmount(value) {
  if (value === null || value === undefined || value === '') return ''
  const amount = Number(value)
  if (!Number.isFinite(amount)) return ''
  return amount.toFixed(6)
}

function formatExportPercent(value) {
  if (value === null || value === undefined || value === '') return ''
  const amount = Number(value)
  if (!Number.isFinite(amount)) return ''
  return `${amount.toFixed(2)}%`
}

function exportColumnLabel(key) {
  return t(`llmOps.listingBoard.export.columns.${key}`)
}

function exportMetricColumnLabel(spec, key) {
  return t('llmOps.listingBoard.export.metricColumn', {
    metric: spec.label,
    field: exportColumnLabel(key)
  })
}

function listingExportColumns() {
  const baseColumns = [
    { key: 'platform', label: exportColumnLabel('platform') },
    { key: 'model', label: exportColumnLabel('model') },
    { key: 'modelCode', label: exportColumnLabel('modelCode') },
    { key: 'metaModel', label: exportColumnLabel('metaModel') },
    { key: 'provider', label: exportColumnLabel('provider') },
    { key: 'channel', label: exportColumnLabel('channel') },
    { key: 'status', label: exportColumnLabel('status') },
    { key: 'currency', label: exportColumnLabel('currency') }
  ]
  const metricColumns = RESALE_PRICE_DIMENSION_SPECS.flatMap((spec) => [
    {
      key: `${spec.key}_cost`,
      label: exportMetricColumnLabel(spec, 'cost')
    },
    {
      key: `${spec.key}_retail`,
      label: exportMetricColumnLabel(spec, 'retail')
    },
    {
      key: `${spec.key}_points`,
      label: exportMetricColumnLabel(spec, 'points')
    }
  ])
  return [
    ...baseColumns,
    ...metricColumns,
    { key: 'margin', label: exportColumnLabel('margin') },
    { key: 'updatedAt', label: exportColumnLabel('updatedAt') }
  ]
}

function listingExportRecord(row) {
  const listing = row.status_listing || {}
  const record = {
    platform: platformLabel.value,
    model: rows.modelDisplayName(row.model),
    modelCode: row.model?.code || listing.model_code || '',
    metaModel: listing.meta_model_name || row.model?.meta_model_name || '',
    provider: row.provider_name || row.procurement?.provider_name || '',
    channel: listing.channel_name || activeListingChannelLabel(row),
    status: statusPillLabel(row),
    currency: listingCurrency(row),
    margin: formatExportPercent(listingUnifiedMarginRate(row)),
    updatedAt: listing.updated_at || listing.created_at || ''
  }
  RESALE_PRICE_DIMENSION_SPECS.forEach((spec) => {
    record[`${spec.key}_cost`] = metricCostValue(row, spec)
    record[`${spec.key}_retail`] = metricRetailValue(row, spec)
    record[`${spec.key}_points`] = metricPointValue(row, spec)
  })
  return record
}

function exportListings() {
  const columns = listingExportColumns()
  const records = exportableRows.value.map(listingExportRecord)
  if (!records.length) return
  if (exportFormat.value === 'excel') {
    downloadExcelExport(columns, records)
    return
  }
  downloadCsvExport(columns, records)
}

function downloadCsvExport(columns, records) {
  const lines = [
    columns.map((column) => csvCell(column.label)).join(','),
    ...records.map((record) =>
      columns.map((column) => csvCell(record[column.key])).join(',')
    )
  ]
  downloadExportFile(
    ['\uFEFF', lines.join('\n')],
    exportFileName('csv'),
    'text/csv;charset=utf-8;'
  )
}

function downloadExcelExport(columns, records) {
  const thead = columns
    .map((column) => `<th>${htmlCell(column.label)}</th>`)
    .join('')
  const tbody = records
    .map((record) => {
      const cells = columns
        .map(
          (column) =>
            `<td style="mso-number-format:'\\@';">` +
            `${htmlCell(record[column.key])}</td>`
        )
        .join('')
      return `<tr>${cells}</tr>`
    })
    .join('')
  const html = [
    '<html><head><meta charset="UTF-8"></head><body>',
    '<table border="1">',
    `<thead><tr>${thead}</tr></thead>`,
    `<tbody>${tbody}</tbody>`,
    '</table></body></html>'
  ].join('')
  downloadExportFile(
    ['\uFEFF', html],
    exportFileName('xls'),
    'application/vnd.ms-excel;charset=utf-8;'
  )
}

function exportFileName(extension) {
  const date = new Date().toISOString().slice(0, 10)
  return `agione-listings-${date}.${extension}`
}

function downloadExportFile(parts, filename, type) {
  const blob = new Blob(parts, { type })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

function csvCell(value) {
  const text = spreadsheetSafeText(value)
  return `"${text.replace(/"/g, '""')}"`
}

function htmlCell(value) {
  const text = spreadsheetSafeText(value)
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function spreadsheetSafeText(value) {
  const text = value === null || value === undefined ? '' : String(value)
  return /^[=+\-@\t\r]/.test(text) ? `'${text}` : text
}

function convertPointCurrencyAmount(value, sourceCurrency, targetCurrency) {
  const amount = Number(value)
  if (!Number.isFinite(amount)) return null
  const source = String(
    sourceCurrency || props.displayCurrency || 'CNY'
  ).toUpperCase()
  const target = String(targetCurrency || source).toUpperCase()
  if (source === target) return amount
  const rate = Number(props.exchangeRate || 7.15)
  if (!Number.isFinite(rate) || rate <= 0) return null
  if (source === 'USD' && target === 'CNY') return amount * rate
  if (source === 'CNY' && target === 'USD') return amount / rate
  return null
}

function listingUnifiedMarginRate(row) {
  return averageMarginRate(
    RESALE_PRICE_DIMENSION_SPECS.filter((spec) => {
      if (spec.key !== 'cache') return true
      return (
        row.status_listing?.[spec.retailField] ||
        row.lowest_option?.[spec.costField]
      )
    }).map((spec) => ({
      price: listingDisplayAmount(
        row.status_listing?.[spec.retailField],
        row.status_listing?.currency
      ),
      cost: row.lowest_option?.[spec.costField]
    }))
  )
}

function normalizeMargin(value) {
  const margin = Number(value)
  if (!Number.isFinite(margin)) return null
  return Number(margin.toFixed(1))
}

function platformMarginFloor() {
  const feeRate = Number(props.agionePlatform?.fee_rate)
  const serviceFeeRate = Number(props.agionePlatform?.service_fee_rate)
  const fee = Number.isFinite(feeRate) && feeRate > 0 ? feeRate : 0
  const service =
    Number.isFinite(serviceFeeRate) && serviceFeeRate > 0 ? serviceFeeRate : 0
  return normalizeMargin((fee + service) * 100) ?? 0
}

function platformMarginLimit() {
  const limit = Number(props.agionePlatform?.auto_approve_max_margin_rate)
  return Number.isFinite(limit) ? limit : null
}

function marginToneKey(row) {
  const margin = listingUnifiedMarginRate(row)
  if (margin === null) return 'muted'
  const floor = platformMarginFloor()
  if (margin < floor) return 'low'
  const limit = platformMarginLimit()
  if (limit !== null && margin > limit) return 'high'
  return 'ok'
}

function marginPillTone(row) {
  return `margin-pill-${marginToneKey(row)}`
}

function marginPillTitle(row) {
  const margin = listingUnifiedMarginRate(row)
  const tone = marginToneKey(row)
  return t(`llmOps.listingBoard.marginTone.${tone}`, {
    value: formatMarginText(margin),
    floor: formatMarginText(platformMarginFloor()),
    limit: formatMarginText(platformMarginLimit())
  })
}

function formatMarginText(value) {
  const margin = Number(value)
  if (!Number.isFinite(margin)) return '-'
  return `${margin.toFixed(1).replace(/\.0$/, '')}%`
}

function statusPillLabel(row) {
  const labels = {
    draft: t('llmOps.listingBoard.workflowStatus.draft'),
    pending_publish: t('llmOps.listingBoard.workflowStatus.pendingPublish'),
    online: t('llmOps.listingBoard.workflowStatus.online'),
    update_draft: t('llmOps.listingBoard.workflowStatus.updateDraft'),
    pending_update: t('llmOps.listingBoard.workflowStatus.pendingUpdate'),
    pending_offline: t('llmOps.listingBoard.workflowStatus.pendingOffline'),
    offline_exception: t('llmOps.listingBoard.workflowStatus.offlineException'),
    offline: t('llmOps.listingBoard.workflowStatus.offline'),
    deleted: t('llmOps.listingBoard.workflowStatus.deleted')
  }
  return (
    labels[row.workflow_status] || t('llmOps.listingBoard.filters.unlisted')
  )
}

function statusPillTone(row) {
  if (isHiddenRow(row)) return 'tone-muted'
  if (row.workflow_status === 'online') {
    return 'tone-success'
  }
  if (
    ['pending_publish', 'pending_update', 'pending_offline'].includes(
      row.workflow_status
    )
  )
    return 'tone-warn'
  if (row.workflow_status === 'offline_exception') return 'tone-danger'
  if (['offline', 'deleted'].includes(row.workflow_status)) return 'tone-muted'
  return 'tone-warn'
}

function rowStateActions(row) {
  const status = row.workflow_status || 'draft'
  const actions = {
    draft: [
      {
        label: t('llmOps.listingBoard.rowActions.continueEdit'),
        kind: 'edit',
        tone: 'default'
      },
      {
        label: t('llmOps.listingBoard.rowActions.confirmSubmit'),
        kind: 'submit',
        tone: 'primary'
      },
      {
        label: t('llmOps.listingBoard.rowActions.deleteData'),
        kind: 'delete',
        tone: 'danger'
      }
    ],
    pending_publish: [
      {
        label: t('llmOps.listingBoard.rowActions.withdrawRequest'),
        kind: 'withdraw',
        tone: 'default'
      },
      {
        label: t('llmOps.listingBoard.rowActions.confirmPublish'),
        kind: 'confirm_publish',
        tone: 'success'
      }
    ],
    online: [
      {
        label: t('llmOps.listingBoard.rowActions.startEdit'),
        kind: 'start_edit',
        tone: 'default'
      },
      {
        label: t('llmOps.listingBoard.rowActions.requestOffline'),
        kind: 'request_offline',
        tone: 'warn'
      },
      {
        label: t('llmOps.listingBoard.rowActions.directOffline'),
        kind: 'direct_offline',
        tone: 'danger'
      }
    ],
    update_draft: [
      {
        label: t('llmOps.listingBoard.rowActions.continueEdit'),
        kind: 'edit',
        tone: 'default'
      },
      {
        label: t('llmOps.listingBoard.rowActions.confirmSubmit'),
        kind: 'submit',
        tone: 'primary'
      },
      {
        label: t('llmOps.listingBoard.rowActions.abandonChange'),
        kind: 'abandon_update',
        tone: 'warn'
      }
    ],
    pending_update: [
      {
        label: t('llmOps.listingBoard.rowActions.withdrawChange'),
        kind: 'withdraw',
        tone: 'default'
      },
      {
        label: t('llmOps.listingBoard.rowActions.confirmUpdate'),
        kind: 'confirm_update',
        tone: 'success'
      }
    ],
    pending_offline: [
      {
        label: t('llmOps.listingBoard.rowActions.withdrawOffline'),
        kind: 'withdraw',
        tone: 'default'
      },
      {
        label: t('llmOps.listingBoard.rowActions.confirmOffline'),
        kind: 'confirm_offline',
        tone: 'danger'
      },
      {
        label: t('llmOps.listingBoard.rowActions.rejectOffline'),
        kind: 'reject_offline',
        tone: 'default'
      },
      {
        label: t('llmOps.listingBoard.rowActions.markOfflineException'),
        kind: 'mark_offline_exception',
        tone: 'danger'
      }
    ],
    offline_exception: [
      {
        label: t('llmOps.listingBoard.rowActions.confirmOffline'),
        kind: 'confirm_offline',
        tone: 'danger'
      }
    ],
    offline: [
      {
        label: t('llmOps.listingBoard.rowActions.republish'),
        kind: 'republish',
        tone: 'primary'
      },
      {
        label: t('llmOps.listingBoard.rowActions.deleteData'),
        kind: 'delete',
        tone: 'danger'
      }
    ],
    deleted: []
  }
  return (
    actions[status] || [
      {
        label: t('llmOps.listingBoard.rowActions.goListing'),
        kind: 'create',
        tone: 'primary'
      }
    ]
  )
}

function isSelectable(row) {
  return !isHiddenRow(row)
}

function rowSelectionKey(row) {
  return String(row.status_listing?.id || `model-${row.model.id}`)
}

function setSelectedModelIds(ids) {
  selectedModelIds.value = new Set(ids.map((id) => String(id)))
}

function toggleRow(row) {
  const next = new Set(selectedModelIds.value)
  const id = rowSelectionKey(row)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  selectedModelIds.value = next
}

function toggleAllVisible(event) {
  const next = new Set(selectedModelIds.value)
  if (event.target.checked) {
    selectableRows.value.forEach((row) => next.add(rowSelectionKey(row)))
  } else {
    selectableRows.value.forEach((row) => next.delete(rowSelectionKey(row)))
  }
  selectedModelIds.value = next
}

function goToPreviousPage() {
  currentPage.value = Math.max(1, currentPage.value - 1)
}

function goToNextPage() {
  currentPage.value = Math.min(totalPages.value, currentPage.value + 1)
}

function emitAction(row, kind) {
  const modelId = row.model.id
  const listingId = row.status_listing?.id || null
  if (kind === 'start_edit') {
    emit('action', { modelId, listingId, kind: 'edit' })
    return
  }
  if (kind === 'direct_offline' || isWorkflowTransition(kind)) {
    handleDirectAction(row, kind)
    return
  }
  emit('action', { modelId, listingId, kind })
}

function isWorkflowTransition(kind) {
  return [
    'submit',
    'withdraw',
    'confirm_publish',
    'abandon_update',
    'confirm_update',
    'request_offline',
    'confirm_offline',
    'reject_offline',
    'mark_offline_exception',
    'republish',
    'delete'
  ].includes(kind)
}

function openWorkspace(modelId, kind) {
  emit('open-workspace', { modelId, kind })
}

watch(listingStatusFilter, () => {
  currentPage.value = 1
  selectedModelIds.value = new Set()
})

watch(searchQuery, () => {
  currentPage.value = 1
  selectedModelIds.value = new Set()
})

watch(pageSize, () => {
  currentPage.value = 1
  selectedModelIds.value = new Set()
})

watch(totalPages, (value) => {
  if (currentPage.value > value) {
    currentPage.value = value
  }
})

watch(
  () => rows.listingRows.value.map((row) => rowSelectionKey(row)).join(','),
  () => {
    const validIds = new Set(
      rows.listingRows.value.map((row) => rowSelectionKey(row))
    )
    setSelectedModelIds(
      Array.from(selectedModelIds.value).filter((id) => validIds.has(id))
    )
  }
)

onMounted(() => {
  // Intentionally empty: previous menu code was removed in favour of
  // inline action buttons that match the demo list layout.
})

onUnmounted(() => {
  // intentionally empty
})

function actionPayloadForRows(targetRows, action = null) {
  const modelIds = targetRows.map((row) => row.model.id)
  const listingIds = targetRows
    .map((row) => row.status_listing?.id)
    .filter(Boolean)
  const payload = {
    platform: props.agionePlatform.id,
    models: modelIds
  }
  if (listingIds.length === targetRows.length) {
    payload.listings = listingIds
  }
  if (action) payload.action = action
  return payload
}

async function handleDirectAction(row, kind) {
  if (!props.agionePlatform) return
  savingListings.value = true
  try {
    if (kind === 'direct_offline') {
      if (!confirm(workflowConfirmText(kind))) return
      const response = await llmOpsApi.bulkOfflineResaleListings(
        actionPayloadForRows([row])
      )
      emitUpdatedListings(response)
      showSuccess(workflowSuccessText(kind))
    } else if (isWorkflowTransition(kind)) {
      if (['request_offline', 'confirm_offline', 'delete'].includes(kind)) {
        if (!confirm(workflowConfirmText(kind))) return
      }
      const response = await llmOpsApi.bulkTransitionResaleListings(
        actionPayloadForRows([row], kind)
      )
      emitUpdatedListings(response)
      showSuccess(workflowSuccessText(kind))
    }
    emit('refresh')
  } catch (error) {
    const message =
      error?.response?.data?.detail ||
      error?.response?.data?.message ||
      error?.message ||
      ''
    showError(message || actionErrorLabel(kind))
  } finally {
    savingListings.value = false
  }
}

async function handleBatchAction(kind) {
  if (!props.agionePlatform || savingListings.value) return
  let targetRows = []
  if (kind === 'offline') targetRows = selectedOfflineRows.value
  else if (kind === 'price') targetRows = selectedRows.value
  else if (kind === 'confirm' && batchConfirmAction.value) {
    targetRows = selectedRows.value
  }
  if (!targetRows.length) return
  const modelIds = targetRows.map((row) => row.model.id)
  const selectedKeys = targetRows.map((row) => rowSelectionKey(row))
  const confirmMessage =
    kind === 'offline'
      ? t('llmOps.listingBoard.confirm.batchOffline', {
          count: modelIds.length
        })
      : kind === 'confirm'
        ? t('llmOps.listingBoard.confirm.batchConfirm', {
            action: batchConfirmLabel.value,
            count: modelIds.length
          })
        : t('llmOps.listingBoard.confirm.batchPrice', {
            count: modelIds.length
          })
  if (!confirm(confirmMessage)) return
  if (kind === 'price') {
    emit('open-workspace', { modelId: null, kind: 'batch-price', modelIds })
    return
  }
  savingListings.value = true
  try {
    if (kind === 'offline') {
      const response = await llmOpsApi.bulkTransitionResaleListings(
        actionPayloadForRows(targetRows, 'request_offline')
      )
      emitUpdatedListings(response)
      showSuccess(t('llmOps.listingBoard.messages.batchOfflineRequested'))
    } else if (kind === 'confirm') {
      const response = await llmOpsApi.bulkTransitionResaleListings(
        actionPayloadForRows(targetRows, batchConfirmAction.value)
      )
      emitUpdatedListings(response)
      showSuccess(
        t('llmOps.listingBoard.messages.batchConfirmed', {
          action: batchConfirmLabel.value
        })
      )
    }
    setSelectedModelIds(
      Array.from(selectedModelIds.value).filter(
        (id) => !selectedKeys.includes(id)
      )
    )
    emit('refresh')
  } catch (error) {
    const message =
      error?.response?.data?.detail ||
      error?.response?.data?.message ||
      error?.message ||
      ''
    showError(message || actionErrorLabel(kind))
  } finally {
    savingListings.value = false
  }
}

function emitUpdatedListings(response) {
  const data = response?.data?.data || response?.data || []
  emit('listings-updated', Array.isArray(data.results) ? data.results : data)
}

function actionErrorLabel(kind) {
  if (kind === 'direct_offline')
    return t('llmOps.listingBoard.errors.directOfflineFailed')
  if (isWorkflowTransition(kind))
    return t('llmOps.listingBoard.errors.transitionFailed')
  return t('llmOps.listingBoard.errors.operationFailed')
}

function workflowConfirmText(kind) {
  const messages = {
    request_offline: t('llmOps.listingBoard.confirm.requestOffline'),
    confirm_offline: t('llmOps.listingBoard.confirm.confirmOffline'),
    direct_offline: t('llmOps.listingBoard.confirm.directOffline'),
    delete: t('llmOps.listingBoard.confirm.delete')
  }
  return messages[kind] || t('llmOps.listingBoard.confirm.default')
}

function workflowSuccessText(kind) {
  const messages = {
    submit: t('llmOps.listingBoard.messages.submitted'),
    withdraw: t('llmOps.listingBoard.messages.withdrawn'),
    confirm_publish: t('llmOps.listingBoard.messages.publishConfirmed'),
    start_edit: t('llmOps.listingBoard.messages.updateDraftStarted'),
    abandon_update: t('llmOps.listingBoard.messages.updateAbandoned'),
    confirm_update: t('llmOps.listingBoard.messages.updateConfirmed'),
    request_offline: t('llmOps.listingBoard.messages.offlineRequested'),
    confirm_offline: t('llmOps.listingBoard.messages.offlineConfirmed'),
    direct_offline: t('llmOps.listingBoard.messages.directOfflineDone'),
    reject_offline: t('llmOps.listingBoard.messages.offlineRejected'),
    mark_offline_exception: t(
      'llmOps.listingBoard.messages.offlineExceptionMarked'
    ),
    republish: t('llmOps.listingBoard.messages.republishSubmitted'),
    delete: t('llmOps.listingBoard.messages.deleted')
  }
  return messages[kind] || t('llmOps.listingBoard.messages.statusUpdated')
}
</script>

<style scoped>
/* === Base utility classes (hardcoded, Tailwind fallback) === */
.bg-white {
  background-color: #ffffff;
}
.bg-slate-50 {
  background-color: #f8fafc;
}
.bg-slate-100 {
  background-color: #f1f5f9;
}
.bg-slate-200 {
  background-color: #e2e8f0;
}
.bg-slate-950 {
  background-color: #020617;
}
.bg-transparent {
  background-color: transparent;
}
.bg-emerald-50 {
  background-color: #ecfdf5;
}
.bg-emerald-500 {
  background-color: #10b981;
}
.bg-amber-50 {
  background-color: #fffbeb;
}
.bg-amber-500 {
  background-color: #f59e0b;
}
.bg-rose-50 {
  background-color: #fff1f2;
}
.bg-rose-500 {
  background-color: #f43f5e;
}
.bg-violet-500 {
  background-color: #8b5cf6;
}
.bg-sky-500 {
  background-color: #0ea5e9;
}
.bg-indigo-50 {
  background-color: #eef2ff;
}
.bg-indigo-100 {
  background-color: #e0e7ff;
}
.bg-agione-50 {
  background-color: #ece9f9;
}
.bg-agione-100 {
  background-color: #d8d2f0;
}
.bg-agione-200 {
  background-color: #b3a8e2;
}
.bg-agione-300 {
  background-color: #8b7dd1;
}
.bg-agione-400 {
  background-color: #7a6ac4;
}
.bg-agione-500 {
  background-color: #6a5ac7;
}
.bg-agione-600 {
  background-color: #5f4ecf;
}
.bg-agione-700 {
  background-color: #4a3eb0;
}
.bg-agione-800 {
  background-color: #3d3399;
}
.bg-agione-900 {
  background-color: #312870;
}
.text-white {
  color: #ffffff;
}
.text-slate-500 {
  color: #64748b;
}
.text-slate-600 {
  color: #475569;
}
.text-slate-700 {
  color: #334155;
}
.text-slate-900 {
  color: #0f172a;
}
.text-emerald-600 {
  color: #059669;
}
.text-emerald-700 {
  color: #047857;
}
.text-amber-600 {
  color: #d97706;
}
.text-amber-700 {
  color: #b45309;
}
.text-rose-500 {
  color: #f43f5e;
}
.text-rose-600 {
  color: #e11d48;
}
.text-rose-700 {
  color: #be123c;
}
.text-agione-50 {
  color: #ece9f9;
}
.text-agione-100 {
  color: #d8d2f0;
}
.text-agione-300 {
  color: #8b7dd1;
}
.text-agione-500 {
  color: #6a5ac7;
}
.text-agione-600 {
  color: #5f4ecf;
}
.text-agione-700 {
  color: #4a3eb0;
}
.text-agione-800 {
  color: #3d3399;
}
.border-slate-200 {
  border-color: #e2e8f0;
}
.border-slate-300 {
  border-color: #cbd5e1;
}
.border-emerald-100 {
  border-color: #d1fae5;
}
.border-emerald-200 {
  border-color: #a7f3d0;
}
.border-amber-100 {
  border-color: #fef3c7;
}
.border-amber-200 {
  border-color: #fde68a;
}
.border-rose-100 {
  border-color: #ffe4e6;
}
.border-rose-200 {
  border-color: #fecdd3;
}
.border-agione-100 {
  border-color: #d8d2f0;
}
.border-agione-200 {
  border-color: #b3a8e2;
}
.border-agione-300 {
  border-color: #8b7dd1;
}
.border-agione-400 {
  border-color: #7a6ac4;
}
.border-agione-500 {
  border-color: #6a5ac7;
}
.focus\:border-agione-300:focus {
  border-color: #8b7dd1;
}
.focus\:border-agione-400:focus {
  border-color: #7a6ac4;
}
.focus\:ring-2:focus {
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.3);
}
.focus\:ring-4:focus {
  box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.3);
}
.focus\:ring-agione-100:focus {
  box-shadow: 0 0 0 2px #d8d2f0;
}
.focus\:ring-agione-200:focus {
  box-shadow: 0 0 0 2px #b3a8e2;
}
.hover\:bg-slate-50:hover {
  background-color: #f8fafc;
}
.hover\:bg-agione-600:hover {
  background-color: #5f4ecf;
}
.hover\:bg-agione-700:hover {
  background-color: #4a3eb0;
}
.hover\:border-slate-300:hover {
  border-color: #cbd5e1;
}
.hover\:text-agione-700:hover {
  color: #4a3eb0;
}
.hover\:text-slate-500:hover {
  color: #64748b;
}
.disabled\:cursor-not-allowed:disabled {
  cursor: not-allowed;
}
.disabled\:opacity-50:disabled {
  opacity: 0.5;
}
.disabled\:opacity-60:disabled {
  opacity: 0.6;
}
.text-xs {
  font-size: 0.75rem;
  line-height: 1rem;
}
.text-sm {
  font-size: 0.875rem;
  line-height: 1.25rem;
}
.text-base {
  font-size: 1rem;
  line-height: 1.5rem;
}
.text-lg {
  font-size: 1.125rem;
  line-height: 1.75rem;
}
.text-xl {
  font-size: 1.25rem;
  line-height: 1.75rem;
}
.text-2xl {
  font-size: 1.5rem;
  line-height: 2rem;
}
.text-3xl {
  font-size: 1.875rem;
  line-height: 2.25rem;
}
.text-4xl {
  font-size: 2.25rem;
  line-height: 2.5rem;
}
.text-\[10px\] {
  font-size: 10px;
}
.text-\[11px\] {
  font-size: 11px;
}
.text-\[12px\] {
  font-size: 12px;
}
.text-\[13px\] {
  font-size: 13px;
}
.text-\[14px\] {
  font-size: 14px;
}
.text-\[15px\] {
  font-size: 15px;
}
.text-\[18px\] {
  font-size: 18px;
}
.text-\[24px\] {
  font-size: 24px;
}
.top-0 {
  top: 0;
}
.z-10 {
  z-index: 10;
}
.z-20 {
  z-index: 20;
}
.z-50 {
  z-index: 50;
}
.max-w-\[20rem\] {
  max-width: 20rem;
}
.w-60 {
  width: 15rem;
}
.w-72 {
  width: 18rem;
}
.w-80 {
  width: 20rem;
}
.w-36 {
  width: 9rem;
}
.w-32 {
  width: 8rem;
}
.h-9 {
  height: 2.25rem;
}
.h-7 {
  height: 1.75rem;
}
.h-8 {
  height: 2rem;
}
.text-left {
  text-align: left;
}
.text-right {
  text-align: right;
}
.text-center {
  text-align: center;
}
.border {
  border-width: 1px;
}
.bg-indigo-50 {
  background-color: #eef2ff;
}
.bg-indigo-100 {
  background-color: #e0e7ff;
}
.bg-indigo-500 {
  background-color: #6366f1;
}
.bg-indigo-600 {
  background-color: #4f46e5;
}
.bg-indigo-700 {
  background-color: #4338ca;
}
.text-indigo-300 {
  color: #a5b4fc;
}
.text-indigo-500 {
  color: #6366f1;
}
.text-indigo-600 {
  color: #4f46e5;
}
.text-indigo-700 {
  color: #4338ca;
}
.border-indigo-200 {
  border-color: #c7d2fe;
}
.border-indigo-300 {
  border-color: #a5b4fc;
}
.border-indigo-400 {
  border-color: #818cf8;
}
.focus\:border-indigo-300:focus {
  border-color: #a5b4fc;
}
.focus\:ring-indigo-100:focus {
  box-shadow: 0 0 0 2px #e0e7ff;
}

.panel {
  border-radius: 12px;
  border-width: 1px;
  border-color: #e2e8f0;
  padding: 1rem;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
}

.panel.p-0 {
  padding: 0;
}

.panel-title {
  font-weight: 600;
  color: #0f172a;
}

.table-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  border-bottom-width: 1px;
  border-color: #e2e8f0;
  padding-left: 1rem;
  padding-right: 1rem;
  padding-top: 0.75rem;
  padding-bottom: 0.75rem;
  align-items: center;
  justify-content: space-between;
}

.listing-board-toolbar {
  --listing-control-height: 2.5rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  border-bottom: 1px solid #e2e8f0;
  padding: 0.75rem 1rem;
}

.listing-board-heading {
  min-width: 12rem;
}

.listing-board-subtitle {
  margin-top: 0.25rem;
  color: #64748b;
  font-size: 12px;
  line-height: 1.35;
  white-space: nowrap;
}

.listing-board-controls {
  display: flex;
  flex: 1 1 auto;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 0.5rem;
  min-width: 0;
}

.listing-search-input {
  height: var(--listing-control-height, 2.5rem);
  width: 12rem;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #ffffff;
  color: #334155;
  font-size: 13px;
  line-height: 1;
  outline: none;
  padding: 0 0.625rem;
}

.listing-search-input:focus {
  border-color: #8b7dd1;
  box-shadow: 0 0 0 2px #ece9f9;
}

.status-filter-group {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 0.375rem;
}

.listing-count,
.listing-selected-count {
  color: #64748b;
  font-size: 12px;
  line-height: 1;
  white-space: nowrap;
}

.pagination-size-field {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  color: #64748b;
  font-size: 12px;
  white-space: nowrap;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.export-control-group {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
}

.export-format-select {
  height: var(--listing-control-height, 2.5rem);
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #ffffff;
  color: #334155;
  font-size: 12px;
  outline: none;
  padding: 0 1.5rem 0 0.5rem;
}

.export-format-select:focus {
  border-color: #8b7dd1;
  box-shadow: 0 0 0 2px #ece9f9;
}

.export-listing-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: var(--listing-control-height, 2.5rem);
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: #ffffff;
  color: #334155;
  font-size: 12px;
  font-weight: 600;
  line-height: 1;
  padding: 0 0.75rem;
  white-space: nowrap;
}

.export-listing-button:hover:not(:disabled) {
  border-color: #8b7dd1;
  color: #4a3eb0;
}

.export-listing-button:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.pagination-select {
  height: var(--listing-control-height, 2.5rem);
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #ffffff;
  color: #334155;
  font-size: 12px;
  outline: none;
  padding: 0 1.5rem 0 0.5rem;
}

.data-table {
  width: 100%;
  table-layout: fixed;
  --tw-divide-y-reverse: 0;
  border-top-width: calc(1px * calc(1 - var(--tw-divide-y-reverse)));
  border-bottom-width: calc(1px * var(--tw-divide-y-reverse));
  --tw-divide-opacity: 1;
  border-color: rgb(226 232 240 / var(--tw-divide-opacity));
}

.data-table tbody {
  --tw-divide-y-reverse: 0;
  border-top-width: calc(1px * calc(1 - var(--tw-divide-y-reverse)));
  border-bottom-width: calc(1px * var(--tw-divide-y-reverse));
  --tw-divide-opacity: 1;
  border-color: rgb(241 245 249 / var(--tw-divide-opacity));
}

.data-table tr {
  background-color: #f8fafc;
}

.table-head {
  white-space: nowrap;
  background-color: #f8fafc;
  padding-left: 1rem;
  padding-right: 1rem;
  padding-top: 0.75rem;
  padding-bottom: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.025em;
  color: #64748b;
  text-align: center;
}

.table-cell {
  white-space: normal;
  padding-left: 1rem;
  padding-right: 1rem;
  padding-top: 0.75rem;
  padding-bottom: 0.75rem;
  color: #475569;
}

.listing-table {
  table-layout: fixed;
}

.listing-table .table-head,
.listing-table .table-cell {
  text-align: center;
  vertical-align: middle;
}

.listing-table .table-cell > p {
  margin-left: auto;
  margin-right: auto;
}

.listing-table .row-checkbox {
  margin-left: auto;
  margin-right: auto;
}

.listing-table th:first-child,
.listing-table td:first-child,
.listing-table th:last-child {
  padding-left: 0.5rem;
  padding-right: 0.5rem;
}

.listing-table .action-cell {
  padding-left: 0.375rem;
  padding-right: 0.375rem;
}

.listing-table th:nth-child(5),
.listing-table td:nth-child(5),
.listing-table th:nth-child(6),
.listing-table td:nth-child(6),
.listing-table th:nth-child(7),
.listing-table td:nth-child(7) {
  padding-left: 0.5rem;
  padding-right: 0.5rem;
}

.select-col {
  width: 3%;
}

.platform-col {
  width: 7%;
}

.model-col {
  width: 16%;
}

.source-col {
  width: 12%;
}

.cost-col,
.retail-col {
  width: 12%;
}

.point-col {
  width: 8%;
}

.margin-col {
  width: 8%;
}

.status-col {
  width: 8%;
}

.action-col {
  width: 12%;
  min-width: 9.25rem;
}

.metric-stack {
  display: grid;
  gap: 0.25rem;
  margin-left: auto;
  margin-right: auto;
  max-width: 9.25rem;
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono',
    'Courier New', monospace;
  font-size: 12px;
}

.metric-line {
  display: grid;
  grid-template-columns: 3rem minmax(0, 1fr);
  align-items: baseline;
  column-gap: 0.25rem;
  min-height: 1.375rem;
  color: #475569;
}

.metric-line-value {
  grid-template-columns: minmax(0, 1fr);
}

.metric-label {
  color: #94a3b8;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0;
  text-align: right;
  text-transform: uppercase;
}

.metric-value {
  min-width: 0;
  overflow: hidden;
  text-align: center;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #0f172a;
  font-weight: 700;
}

.metric-label + .metric-value {
  text-align: right;
}

.margin-pill {
  display: inline-flex;
  min-width: 4.5rem;
  align-items: center;
  justify-content: center;
  border-radius: 9999px;
  border: 1px solid transparent;
  background-color: #f8fafc;
  padding: 0.25rem 0.625rem;
  color: #475569;
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono',
    'Courier New', monospace;
  font-size: 12px;
  font-weight: 700;
}

.margin-pill-low {
  border-color: #fde68a;
  background-color: #fffbeb;
  color: #b45309;
}

.margin-pill-ok {
  border-color: #a7f3d0;
  background-color: #ecfdf5;
  color: #047857;
}

.margin-pill-high {
  border-color: #fecdd3;
  background-color: #fff1f2;
  color: #be123c;
}

.margin-pill-muted {
  border-color: #e2e8f0;
  background-color: #f8fafc;
  color: #64748b;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  border-radius: 9999px;
  padding-left: 0.625rem;
  padding-right: 0.625rem;
  padding-top: 0.25rem;
  padding-bottom: 0.25rem;
  font-weight: 500;
}

.status-pill.tone-success {
  background-color: #ecfdf5;
  color: #047857;
}

.status-pill.tone-warn {
  background-color: #fffbeb;
  color: #b45309;
}

.status-pill.tone-neutral {
  background-color: #f1f5f9;
  color: #64748b;
}

.status-pill.tone-muted {
  background-color: #e2e8f0;
  color: #475569;
}

.status-pill.tone-danger {
  background-color: #fff1f2;
  color: #be123c;
}

.status-filter-chip {
  display: inline-flex;
  min-height: var(--listing-control-height, 2.5rem);
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  border-width: 1px;
  border-color: #e2e8f0;
  padding: 0 0.625rem;
  font-size: 12px;
  font-weight: 600;
  line-height: 1;
  text-align: center;
  white-space: nowrap;
  color: #475569;
  transition-property: color, background-color, border-color, box-shadow;
  transition-duration: 150ms;
  border-color: #cbd5e1;
  background-color: #f8fafc;
}

.status-filter-chip-active {
  border-color: #b3a8e2;
  background-color: #ece9f9;
  color: #4a3eb0;
}

.add-listing-button {
  display: inline-flex;
  height: var(--listing-control-height, 2.5rem);
  min-height: var(--listing-control-height, 2.5rem) !important;
  align-items: center;
  justify-content: center;
  min-width: 5.5rem;
  border-radius: 8px;
  background-color: #5f4ecf;
  padding: 0 0.75rem;
  font-size: 12px;
  font-weight: 700;
  line-height: 1;
  text-align: center;
  white-space: nowrap;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
  transition-property: color, background-color, border-color, box-shadow;
  transition-duration: 150ms;
  background-color: #4a3eb0;
}

.batch-action {
  display: inline-flex;
  height: var(--listing-control-height, 2.5rem);
  min-height: var(--listing-control-height, 2.5rem) !important;
  align-items: center;
  justify-content: center;
  min-width: 4.5rem;
  border-radius: 6px;
  border-width: 1px;
  border-color: #e2e8f0;
  padding: 0 0.625rem;
  font-size: 12px;
  font-weight: 600;
  line-height: 1;
  text-align: center;
  white-space: nowrap;
  color: #475569;
  transition-property: color, background-color, border-color, box-shadow;
  transition-duration: 150ms;
  border-color: #cbd5e1;
  background-color: #f8fafc;
}

.batch-action:disabled,
.row-link:disabled {
  cursor: not-allowed;
  border-color: #e2e8f0;
  background-color: #f8fafc;
  color: #94a3b8;
  box-shadow: none;
}

.batch-action-primary {
  border-color: #8b7dd1;
  background-color: #5f4ecf;
  color: #ffffff;
}

.batch-action-success {
  border-color: #86efac;
  background-color: #ecfdf5;
  color: #047857;
}

.batch-action-warn {
  border-color: #fed7aa;
  background-color: #fff7ed;
  color: #c2410c;
}

.batch-action-danger {
  border-color: #fecdd3;
  background-color: #fff1f2;
  color: #e11d48;
}

.pagination-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  border-top: 1px solid #e2e8f0;
  background-color: #fff;
  padding: 0.875rem 1rem;
}

.pagination-summary {
  color: #64748b;
  font-size: 0.875rem;
}

.pagination-actions {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}

.pagination-select,
.pagination-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: var(--listing-control-height, 2.5rem);
  border-radius: 8px;
  border: 1px solid #cbd5e1;
  background-color: #fff;
  color: #334155;
  font-size: 0.875rem;
  font-weight: 500;
  transition:
    color 150ms,
    background-color 150ms,
    border-color 150ms,
    box-shadow 150ms;
}

.pagination-select {
  min-width: 4.5rem;
  padding: 0 0.75rem;
}

.pagination-button {
  min-width: 4.75rem;
  padding: 0 0.875rem;
}

.pagination-select:focus,
.pagination-button:focus {
  outline: none;
  border-color: #b3a8e2;
  box-shadow: 0 0 0 3px rgba(179, 168, 226, 0.24);
}

.pagination-button:hover:not(:disabled) {
  border-color: #b3a8e2;
  color: #4a3eb0;
}

.pagination-button:disabled {
  cursor: not-allowed;
  border-color: #e2e8f0;
  background-color: #f8fafc;
  color: #94a3b8;
}

.row-checkbox {
  height: 1rem;
  width: 1rem;
  border-radius: 4px;
  border-color: #cbd5e1;
  color: #5f4ecf;
  box-shadow: 0 0 0 2px #6a5ac755;
}

.row-link {
  display: inline-flex;
  height: 1.75rem;
  align-items: center;
  justify-content: center;
  min-width: 3.75rem;
  border-radius: 6px;
  border-width: 1px;
  border-color: #e2e8f0;
  padding-left: 0.625rem;
  padding-right: 0.625rem;
  font-weight: 500;
  line-height: 1;
  text-align: center;
  white-space: nowrap;
  color: #475569;
  transition-property: color, background-color, border-color, box-shadow;
  transition-duration: 150ms;
  border-color: #cbd5e1;
  background-color: #f8fafc;
}

.row-link-primary {
  border-color: #8b7dd1;
  background-color: #5f4ecf;
  color: #ffffff;
}

.row-link-success {
  border-color: #86efac;
  background-color: #ecfdf5;
  color: #047857;
}

.row-link-warn {
  border-color: #fed7aa;
  background-color: #fff7ed;
  color: #c2410c;
}

.row-link-danger {
  border-color: #fecdd3;
  background-color: #fff1f2;
  color: #e11d48;
}

.action-cell {
  overflow: visible;
  vertical-align: middle;
}

.row-actions {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  justify-content: center;
  margin-left: auto;
  margin-right: auto;
  max-width: 9rem;
  min-width: 0;
  white-space: nowrap;
}
</style>
