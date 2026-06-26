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
          <h3 class="panel-title">模型挂售列表</h3>
          <p class="listing-board-subtitle">仅展示当前平台流程内模型。</p>
        </div>
        <div class="listing-board-controls">
          <input
            v-model="searchQuery"
            type="text"
            class="listing-search-input"
            placeholder="搜索模型 / code"
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
            <span>每页</span>
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
          <template v-if="selectedRows.length">
            <span class="listing-selected-count">
              已选 {{ selectedRows.length }}
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
              批量下架
            </button>
            <button
              type="button"
              class="batch-action"
              :class="batchActionClass('default')"
              :disabled="savingListings"
              @click="handleBatchAction('price')"
            >
              批量改价
            </button>
          </template>
          <button
            type="button"
            class="add-listing-button btn-action-create"
            @click="openWorkspace(null, 'create')"
          >
            新建上架
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
              <th class="table-head">挂售平台</th>
              <th class="table-head min-w-[200px]">模型</th>
              <th class="table-head">供货链路</th>
              <th class="table-head">成本</th>
              <th class="table-head">售价</th>
              <th class="table-head">积分</th>
              <th class="table-head">利润率</th>
              <th class="table-head">状态</th>
              <th class="table-head">操作</th>
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
                  <button
                    v-for="action in rowStateActions(row)"
                    :key="action.kind"
                    type="button"
                    :class="[
                      'row-action-button',
                      rowActionMenuItemClass(action.tone)
                    ]"
                    :disabled="savingListings"
                    @click="emitAction(row, action.kind)"
                  >
                    {{ rowActionVisibleLabel(action) }}
                  </button>
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
          第 {{ currentPage }} / {{ totalPages }} 页 · 共
          {{ filteredListingRows.length }} 条
        </p>
        <div class="pagination-actions">
          <button
            type="button"
            class="pagination-button"
            :disabled="currentPage <= 1"
            @click="goToPreviousPage"
          >
            上一页
          </button>
          <button
            type="button"
            class="pagination-button"
            :disabled="currentPage >= totalPages"
            @click="goToNextPage"
          >
            下一页
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, toRef, watch } from 'vue'
import { llmOpsApi } from '@/api/llmOps'
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
const { showSuccess, showError } = useToast()

const listingStatusFilter = ref('all')
const searchQuery = ref('')
const pageSize = ref(10)
const currentPage = ref(1)
const savingListings = ref(false)
const selectedModelIds = ref(new Set())
const pageSizeOptions = [10, 20, 50]

const listingStatusOptions = [
  { label: '待处理', value: 'actionable' },
  { label: '全部', value: 'all' },
  { label: '已上架', value: 'listed' },
  { label: '未上架', value: 'unlisted' }
]

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

const platformLabel = computed(() => props.agionePlatform?.name || '挂售平台')

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
      } else if (listingStatusFilter.value === 'unlisted') {
        if (row.is_listed) return false
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
      submit: '批量确认提交',
      confirm_publish: '批量确认上架',
      confirm_update: '批量确认更新',
      confirm_offline: '批量确认下架'
    }[batchConfirmAction.value] || '批量确认'
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

function rowActionVisibleLabel(action) {
  return (
    {
      abandon_update: '放弃',
      confirm_offline: '确认下架',
      confirm_publish: '确认上架',
      confirm_update: '确认更新',
      delete: '删除',
      direct_offline: '直接下架',
      edit: '编辑',
      mark_offline_exception: '标记异常',
      reject_offline: '驳回',
      republish: '重新发布',
      request_offline: '申请下架',
      start_edit: '编辑',
      submit: '提交',
      withdraw: '撤回'
    }[action.kind] || action.label
  )
}

function rowActionMenuItemClass(tone) {
  return `row-action-menu-item-${tone || 'default'}`
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
      label: '可挂售模型',
      value: visibleRows.length,
      hint: `${unlistedCount(visibleRows, listedRows)} 个未上架`,
      delta: '本周期',
      deltaTone: 'text-slate-400'
    },
    {
      label: '挂售平台',
      value: props.platformCount,
      hint: '可见挂售平台汇总',
      delta: '稳定',
      deltaTone: 'text-slate-400'
    },
    {
      label: '已上架',
      value: listedRows.length,
      hint: '外部平台当前在线',
      delta: listedRows.length > 0 ? '+ 上架中' : '待上架',
      deltaTone: listedRows.length > 0 ? 'text-emerald-600' : 'text-amber-600'
    },
    {
      label: '未上架',
      value: visibleRows.length - listedRows.length,
      hint: '可在工作台一键处理',
      delta: '需处理',
      deltaTone: 'text-amber-600'
    },
    {
      label: '整体平均利润率',
      value: avgMargin !== null ? `${avgMargin}%` : '—',
      hint: '按 Input / Output / Cached 统一估算',
      delta: '参考',
      deltaTone: 'text-slate-400'
    }
  ]
})

function unlistedCount(visibleRows, listedRows) {
  return visibleRows.length - listedRows.length
}

const listingEmptyText = computed(() => {
  if (listingStatusFilter.value === 'actionable')
    return '暂无需要处理的挂售模型。'
  if (listingStatusFilter.value === 'listed') return '当前没有已上架的模型。'
  if (listingStatusFilter.value === 'unlisted') return '当前没有可上架的模型。'
  return '没有符合筛选条件的模型。'
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
    return `${activeListings.length} 条上架链路`
  }
  return row.lowest_option?.channel_name || '暂无供应'
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
    retail: listingAmountText(row.status_listing?.[spec.retailField]),
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
      price: row.status_listing?.[spec.retailField],
      cost: row.lowest_option?.[spec.costField]
    }))
  )
}

function statusPillLabel(row) {
  const labels = {
    draft: '草稿',
    pending_publish: '待发布',
    online: '已上架',
    update_draft: '更新草稿',
    pending_update: '待更新',
    pending_offline: '待下架',
    offline_exception: '下架异常',
    offline: '已下架',
    deleted: '已失效'
  }
  return labels[row.workflow_status] || '未上架'
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
      { label: '继续编辑', kind: 'edit', tone: 'default' },
      { label: '确认提交', kind: 'submit', tone: 'primary' },
      { label: '删除数据', kind: 'delete', tone: 'danger' }
    ],
    pending_publish: [
      { label: '撤回申请', kind: 'withdraw', tone: 'default' },
      { label: '确认上架', kind: 'confirm_publish', tone: 'success' }
    ],
    online: [
      { label: '发起编辑', kind: 'start_edit', tone: 'default' },
      { label: '发起下架', kind: 'request_offline', tone: 'warn' },
      { label: '直接下架', kind: 'direct_offline', tone: 'danger' }
    ],
    update_draft: [
      { label: '继续编辑', kind: 'edit', tone: 'default' },
      { label: '确认提交', kind: 'submit', tone: 'primary' },
      { label: '放弃修改', kind: 'abandon_update', tone: 'warn' }
    ],
    pending_update: [
      { label: '撤回修改', kind: 'withdraw', tone: 'default' },
      { label: '确认更新', kind: 'confirm_update', tone: 'success' }
    ],
    pending_offline: [
      { label: '撤回下架', kind: 'withdraw', tone: 'default' },
      { label: '确认下架', kind: 'confirm_offline', tone: 'danger' },
      { label: '驳回下架', kind: 'reject_offline', tone: 'default' },
      { label: '标记异常', kind: 'mark_offline_exception', tone: 'danger' }
    ],
    offline_exception: [
      { label: '确认下架', kind: 'confirm_offline', tone: 'danger' }
    ],
    offline: [
      { label: '重新发布', kind: 'republish', tone: 'primary' },
      { label: '删除数据', kind: 'delete', tone: 'danger' }
    ],
    deleted: []
  }
  return (
    actions[status] || [{ label: '去挂售', kind: 'create', tone: 'primary' }]
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
      ? `确认批量发起下架 ${modelIds.length} 个模型？`
      : kind === 'confirm'
        ? `${batchConfirmLabel.value} ${modelIds.length} 个模型？`
        : `确认对 ${modelIds.length} 个模型进入批量改价工作台？`
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
      showSuccess('已批量发起下架')
    } else if (kind === 'confirm') {
      const response = await llmOpsApi.bulkTransitionResaleListings(
        actionPayloadForRows(targetRows, batchConfirmAction.value)
      )
      emitUpdatedListings(response)
      showSuccess(batchConfirmLabel.value.replace('批量', '已批量'))
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
  if (kind === 'direct_offline') return '直接下架失败'
  if (isWorkflowTransition(kind)) return '状态流转失败'
  return '操作失败'
}

function workflowConfirmText(kind) {
  const messages = {
    request_offline: '确认发起下架申请？外部平台仍保持已上架，等待确认下架。',
    confirm_offline: '确认外部平台已完成下架？该模型将进入已下架状态。',
    direct_offline: '确认直接下架？该操作表示外部平台已同步下线。',
    delete: '确认删除该挂售数据？删除后将从常规业务列表隐藏。'
  }
  return messages[kind] || '确认执行该状态操作？'
}

function workflowSuccessText(kind) {
  const messages = {
    submit: '已提交',
    withdraw: '已撤回',
    confirm_publish: '已确认上架',
    start_edit: '已进入更新草稿',
    abandon_update: '已放弃修改',
    confirm_update: '已确认更新',
    request_offline: '已发起下架',
    confirm_offline: '已确认下架',
    direct_offline: '已直接下架',
    reject_offline: '已驳回下架',
    mark_offline_exception: '已标记异常',
    republish: '已重新提交发布',
    delete: '已删除'
  }
  return messages[kind] || '状态已更新'
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
  height: 2rem;
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

.pagination-select {
  height: 2rem;
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
.listing-table th:last-child,
.listing-table .action-cell {
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
  width: 14%;
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
  width: 10%;
}

.metric-stack {
  display: grid;
  gap: 0.375rem;
  margin-left: auto;
  margin-right: auto;
  max-width: 12rem;
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono',
    'Courier New', monospace;
  font-size: 12px;
}

.metric-line {
  display: grid;
  grid-template-columns: 4rem minmax(0, 1fr);
  align-items: baseline;
  column-gap: 0.5rem;
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
  text-align: left;
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
  background-color: #ece9f9;
  padding: 0.25rem 0.625rem;
  color: #4a3eb0;
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono',
    'Courier New', monospace;
  font-size: 12px;
  font-weight: 700;
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
  min-height: 2rem;
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
  height: 2rem;
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
  height: 2rem;
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
  min-height: 2rem;
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
}

.row-actions {
  display: grid;
  grid-template-columns: minmax(5.75rem, 6.5rem);
  gap: 0.3rem;
  margin-left: auto;
  margin-right: auto;
  max-width: 6.5rem;
  min-width: 0;
}

.row-action-button {
  display: inline-flex;
  min-height: 2rem;
  min-width: 0;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background-color: #fff;
  padding: 0 0.5rem;
  font-size: 12px;
  font-weight: 700;
  line-height: 1;
  white-space: nowrap;
  transition:
    background-color 150ms ease,
    border-color 150ms ease,
    color 150ms ease;
}

.row-action-menu-item-default {
  border-color: #cbd5e1;
  background-color: #fff;
  color: #475569;
}

.row-action-menu-item-primary {
  border-color: #c7d2fe;
  background-color: #eef2ff;
  color: #3730a3;
}

.row-action-menu-item-success {
  border-color: #a7f3d0;
  background-color: #ecfdf5;
  color: #047857;
}

.row-action-menu-item-warn {
  border-color: #fed7aa;
  background-color: #fff7ed;
  color: #b45309;
}

.row-action-menu-item-danger {
  border-color: #fecdd3;
  background-color: #fff1f2;
  color: #be123c;
}

.row-action-button:hover:not(:disabled) {
  border-color: #94a3b8;
  background-color: #f8fafc;
  color: #334155;
}

.row-action-menu-item-primary:hover:not(:disabled) {
  border-color: #818cf8;
  background-color: #e0e7ff;
  color: #312e81;
}

.row-action-menu-item-warn:hover:not(:disabled) {
  border-color: #fdba74;
  background-color: #ffedd5;
  color: #9a3412;
}

.row-action-menu-item-danger:hover:not(:disabled) {
  border-color: #fda4af;
  background-color: #ffe4e6;
  color: #9f1239;
}

.row-action-menu-item-success:hover:not(:disabled) {
  border-color: #6ee7b7;
  background-color: #d1fae5;
  color: #065f46;
}

.row-action-button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}
</style>
