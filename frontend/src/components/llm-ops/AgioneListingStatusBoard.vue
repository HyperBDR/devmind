<!--
  AgioneListingStatusBoard — overview of resale listings on the current
  platform. Re-styled to match the demo "model publishing" list view,
  but keeps the existing emit contract so the parent (LLMOps.vue) does
  not need to be rewritten. The board now exposes `open-workspace` for
  the immersive workspace drawer.
-->
<template>
  <section class="agione-listing-status-board space-y-4">
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
              :class="{ 'listing-row-focused': isFocusedRow(row) }"
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
import '@/components/llm-ops/agioneListingStatusBoard.css'

import { ref, toRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { llmOpsApi } from '@/api/llmOps'
import OperationIconButton from '@/components/llm-ops/OperationIconButton.vue'
import { useAgioneListingDisplay } from '@/composables/useAgioneListingDisplay'
import { useAgioneListingExport } from '@/composables/useAgioneListingExport'
import { useAgioneListingSelection } from '@/composables/useAgioneListingSelection'
import { useToast } from '@/composables/useToast'
import { useAgioneListingRows } from '@/composables/useAgioneListingRows'

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
  },
  focusModelId: {
    type: [String, Number],
    default: null
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

const savingListings = ref(false)

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

const {
  allVisibleSelected,
  canBatchOffline,
  currentPage,
  exportableRows,
  filteredListingRows,
  goToNextPage,
  goToPreviousPage,
  isHiddenRow,
  listingEmptyText,
  listingStatusFilter,
  pageSize,
  pageSizeOptions,
  paginatedListingRows,
  rowSelectionKey,
  selectableRows,
  selectedModelIds,
  selectedOfflineRows,
  selectedRows,
  setSelectedModelIds,
  searchQuery,
  isSelectable,
  toggleAllVisible,
  toggleRow,
  totalPages,
  visibleListingRows
} = useAgioneListingSelection({ rows })

const {
  batchConfirmAction,
  batchConfirmLabel,
  batchConfirmTone,
  listingKpis,
  listingStatusOptions,
  platformLabel,
  activeListingChannelLabel,
  batchActionClass,
  listingCurrency,
  listingPointText,
  listingPriceMetrics,
  listingUnifiedMarginRate,
  marginPillTitle,
  marginPillTone,
  rowActionIcon,
  rowStateActions,
  statusPillLabel,
  statusPillTone
} = useAgioneListingDisplay({
  isHiddenRow,
  props,
  selectedRows,
  t,
  visibleListingRows
})

watch(
  () => [props.focusModelId, visibleListingRows.value.length],
  () => {
    focusListingModel()
  },
  { immediate: true }
)

const { exportFormat, exportListings } = useAgioneListingExport({
  activeListingChannelLabel,
  exportableRows,
  listingCurrency,
  listingPointText,
  listingUnifiedMarginRate,
  platformLabel,
  rows,
  statusPillLabel
})

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

function focusListingModel() {
  const modelId = props.focusModelId
  if (!modelId) return
  const row = visibleListingRows.value.find(
    (item) => String(item.model?.id) === String(modelId)
  )
  const model =
    row?.model ||
    props.models.find((item) => String(item.id) === String(modelId))
  if (!model) return
  listingStatusFilter.value = 'all'
  searchQuery.value = rows.modelDisplayName(model) || model.code || ''
}

function isFocusedRow(row) {
  return (
    props.focusModelId && String(row.model?.id) === String(props.focusModelId)
  )
}

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
