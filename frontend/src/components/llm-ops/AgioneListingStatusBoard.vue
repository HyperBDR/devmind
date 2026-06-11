<template>
  <section class="space-y-5">
    <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
      <div
        v-for="item in listingKpis"
        :key="item.label"
        class="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3"
      >
        <p class="text-xs font-medium text-slate-500">
          {{ item.label }}
        </p>
        <p class="mt-2 text-2xl font-semibold text-slate-900">
          {{ item.value }}
        </p>
      </div>
    </div>

    <div class="panel overflow-hidden p-0">
      <div class="table-toolbar">
        <div class="flex flex-col gap-1">
          <h3 class="panel-title">模型挂售状态</h3>
          <p class="text-xs text-slate-500">
            管理当前平台的上架、下架、移除和恢复。
          </p>
        </div>
        <div class="flex flex-wrap items-center gap-3">
          <span class="text-sm text-slate-500">
            {{ filteredListingRows.length }} / {{ rows.listingRows.value.length }}
          </span>
          <button
            type="button"
            class="add-listing-button"
            @click="emitAction(null, 'create')"
          >
            添加上架模型
          </button>
        </div>
      </div>

      <div class="border-b border-slate-100 bg-white px-4 py-3">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div class="flex flex-wrap gap-2">
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
          <div class="flex flex-wrap items-center gap-2">
            <span class="text-xs text-slate-500">
              已选 {{ selectedRows.length }}
            </span>
            <button
              type="button"
              class="batch-action"
              :disabled="!selectedOfflineRows.length || savingListings"
              @click="handleBatchAction('offline')"
            >
              批量下架
            </button>
            <button
              type="button"
              class="batch-action batch-action-danger"
              :disabled="!selectedRemoveRows.length || savingListings"
              @click="handleBatchAction('remove')"
            >
              批量移除
            </button>
          </div>
        </div>
      </div>

      <div class="overflow-x-auto">
        <table class="data-table">
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
              <th class="table-head">模型</th>
              <th class="table-head">状态</th>
              <th class="table-head">当前渠道</th>
              <th class="table-head">挂售价</th>
              <th class="table-head">价差</th>
              <th class="table-head text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in filteredListingRows"
              :key="row.model.id"
              class="cursor-default"
            >
              <td class="table-cell">
                <input
                  class="row-checkbox"
                  type="checkbox"
                  :checked="selectedModelIds.has(String(row.model.id))"
                  :disabled="!isSelectable(row)"
                  @change="toggleRow(row)"
                />
              </td>
              <td class="table-cell">
                <p class="font-medium text-slate-900">
                  {{ rows.modelDisplayName(row.model) }}
                </p>
                <p class="mt-1 font-mono text-xs text-slate-500">
                  {{ rows.listingModelSubtitle(row) }}
                </p>
              </td>
              <td class="table-cell">
                <span
                  class="status-pill"
                  :class="statusPillTone(row)"
                >
                  {{ statusPillLabel(row) }}
                </span>
              </td>
              <td class="table-cell text-slate-600">
                {{ rows.activeListingChannels(row) }}
              </td>
              <td class="table-cell">
                <span class="block text-slate-700">
                  {{ rows.activeListingPriceSummary(row) }}
                </span>
                <span
                  v-if="rows.activeListingPointSummary(row)"
                  class="mt-1 block text-xs text-slate-400"
                >
                  {{ rows.activeListingPointSummary(row) }}
                </span>
              </td>
              <td class="table-cell">
                <span v-if="row.is_removed" class="text-slate-400">-</span>
                <span v-else-if="!row.is_listed" class="text-slate-500">
                  {{ row.lowest_option ? '可上架' : '缺渠道' }}
                </span>
                <span v-else-if="row.has_lowest_listing" class="text-emerald-600">
                  当前最低价
                </span>
                <span v-else-if="row.price_gap !== null" class="text-amber-600">
                  比最低高 {{ rows.money(row.price_gap, row.lowest_option?.currency) }}
                </span>
                <span v-else class="text-slate-400">-</span>
              </td>
              <td class="table-cell text-right">
                <div class="relative inline-block" @click.stop>
                  <button
                    type="button"
                    class="row-action-trigger"
                    :class="{ 'row-action-trigger-open': openMenuId === String(row.model.id) }"
                    @click="toggleMenu(row.model.id)"
                  >
                    <span class="sr-only">操作</span>
                    <svg viewBox="0 0 20 20" fill="currentColor" class="h-4 w-4">
                      <path d="M10 6.5a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3zm0 5a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3zm0 5a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3z" />
                    </svg>
                  </button>
                  <div
                    v-if="openMenuId === String(row.model.id)"
                    class="row-action-menu"
                    role="menu"
                  >
                    <button
                      type="button"
                      class="row-action-item"
                      @click="emitAction(row.model.id, 'view')"
                    >
                      查看详情
                    </button>
                    <button
                      v-if="!row.lowest_option && !row.is_listed"
                      type="button"
                      class="row-action-item"
                      @click="emitAction(row.model.id, 'configure-channel')"
                    >
                      配置渠道
                    </button>
                    <button
                      v-else
                      type="button"
                      class="row-action-item"
                      @click="emitAction(row.model.id, 'edit')"
                    >
                      编辑挂售
                    </button>
                    <button
                      v-if="row.is_listed"
                      type="button"
                      class="row-action-item"
                      :disabled="savingListings"
                      @click="emitAction(row.model.id, 'offline')"
                    >
                      下架
                    </button>
                    <div class="row-action-divider" />
                    <button
                      v-if="row.is_removed"
                      type="button"
                      class="row-action-item"
                      :disabled="savingListings"
                      @click="emitAction(row.model.id, 'restore')"
                    >
                      恢复挂售
                    </button>
                    <button
                      v-else
                      type="button"
                      class="row-action-item row-action-item-danger"
                      :disabled="savingListings || row.is_listed"
                      :title="row.is_listed ? '请先下架后再移除' : ''"
                      @click="emitAction(row.model.id, 'remove')"
                    >
                      移除挂售
                    </button>
                  </div>
                </div>
              </td>
            </tr>
            <tr v-if="!filteredListingRows.length">
              <td class="table-cell text-slate-500" colspan="7">
                {{ listingEmptyText }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, toRef, watch } from 'vue'
import { llmOpsApi } from '@/api/llmOps'
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
  listingExclusions: {
    type: Array,
    default: () => []
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

const emit = defineEmits(['refresh', 'action'])
const { showSuccess, showError } = useToast()

const listingStatusFilter = ref('actionable')
const openMenuId = ref(null)
const savingListings = ref(false)
const selectedModelIds = ref(new Set())

const listingStatusOptions = [
  { label: '待处理', value: 'actionable' },
  { label: '全部状态', value: 'all' },
  { label: '已上架', value: 'listed' },
  { label: '未上架', value: 'unlisted' },
  { label: '可优化', value: 'not_lowest' },
  { label: '已移除', value: 'removed' }
]

// Form-state stubs — the composable only reads them, StatusBoard never
// writes. They exist so the shared derivations in useAgioneListingRows
// have a valid input to track.
const unusedModelId = ref('')
const unusedChannelId = ref('')
const unusedProfitRate = ref('0')

const rows = useAgioneListingRows({
  agionePlatformRef: toRef(props, 'agionePlatform'),
  providersRef: toRef(props, 'providers'),
  modelsRef: toRef(props, 'models'),
  priceItemsRef: toRef(props, 'priceItems'),
  listingsRef: toRef(props, 'listings'),
  listingExclusionsRef: toRef(props, 'listingExclusions'),
  summaryRef: toRef(props, 'summary'),
  displayCurrencyRef: toRef(props, 'displayCurrency'),
  exchangeRateRef: toRef(props, 'exchangeRate'),
  selectedTrendModelIdRef: unusedModelId,
  selectedTrendChannelIdRef: unusedChannelId,
  trendProfitRateRef: unusedProfitRate,
  pointConversionRef: toRef(props, 'pointConversion')
})

const filteredListingRows = computed(() => {
  const all = rows.listingRows.value
  switch (listingStatusFilter.value) {
    case 'actionable':
      return all.filter(
        (row) =>
          !row.is_removed &&
          (
            !row.is_listed ||
            ((row.lowest_option || row.is_listed) && !row.has_lowest_listing)
          )
      )
    case 'listed':
      return all.filter((row) => row.is_listed && !row.is_removed)
    case 'unlisted':
      return all.filter((row) => !row.is_listed && !row.is_removed)
    case 'not_lowest':
      return all.filter(
        (row) => row.is_listed && !row.has_lowest_listing && !row.is_removed
      )
    case 'removed':
      return all.filter((row) => row.is_removed)
    case 'all':
    default:
      return all
  }
})

const selectableRows = computed(() =>
  filteredListingRows.value.filter((row) => isSelectable(row))
)

const selectedRows = computed(() =>
  filteredListingRows.value.filter((row) =>
    selectedModelIds.value.has(String(row.model.id))
  )
)

const selectedOfflineRows = computed(() =>
  selectedRows.value.filter((row) => row.is_listed && !row.is_removed)
)

const selectedRemoveRows = computed(() =>
  selectedRows.value.filter((row) => !row.is_listed && !row.is_removed)
)

const allVisibleSelected = computed(
  () =>
    selectableRows.value.length > 0 &&
    selectableRows.value.every((row) =>
      selectedModelIds.value.has(String(row.model.id))
    )
)

const listingKpis = computed(() => {
  const visibleRows = rows.listingRows.value.filter((row) => !row.is_removed)
  const listedRows = visibleRows.filter((row) => row.is_listed)
  const optimizedRows = listedRows.filter((row) => row.has_lowest_listing)
  return [
    { label: '可挂售模型', value: visibleRows.length },
    { label: '挂售平台', value: props.platformCount },
    { label: '已上架', value: listedRows.length },
    { label: '未上架', value: visibleRows.length - listedRows.length },
    {
      label: '非最低价',
      value: listedRows.length - optimizedRows.length
    }
  ]
})

const listingEmptyText = computed(() => {
  if (listingStatusFilter.value === 'actionable') {
    return '暂无需要处理的挂售模型。'
  }
  if (listingStatusFilter.value === 'listed') {
    return '当前没有已上架的模型。'
  }
  if (listingStatusFilter.value === 'unlisted') {
    return '当前没有可上架的模型。'
  }
  if (listingStatusFilter.value === 'not_lowest') {
    return '暂无需要优化的上架模型。'
  }
  if (listingStatusFilter.value === 'removed') {
    return '暂无已移除模型。'
  }
  return '没有符合筛选条件的模型。'
})

function statusPillLabel(row) {
  if (row.is_removed) return '已移除'
  if (!row.is_listed) return '未上架'
  if (row.has_lowest_listing) return '当前最低价'
  return '可优化'
}

function statusPillTone(row) {
  if (row.is_removed) return 'tone-muted'
  if (!row.is_listed) return 'tone-neutral'
  if (row.has_lowest_listing) return 'tone-success'
  return 'tone-warn'
}

function toggleMenu(modelId) {
  openMenuId.value =
    openMenuId.value === String(modelId) ? null : String(modelId)
}

function closeMenu() {
  openMenuId.value = null
}

function emitAction(modelId, kind) {
  closeMenu()
  if (kind === 'remove' || kind === 'restore' || kind === 'offline') {
    handleDirectAction(modelId, kind)
    return
  }
  emit('action', { modelId, kind })
}

function isSelectable(row) {
  return !row.is_removed
}

function setSelectedModelIds(ids) {
  selectedModelIds.value = new Set(ids.map((id) => String(id)))
}

function toggleRow(row) {
  const next = new Set(selectedModelIds.value)
  const id = String(row.model.id)
  if (next.has(id)) {
    next.delete(id)
  } else {
    next.add(id)
  }
  selectedModelIds.value = next
}

function toggleAllVisible(event) {
  const next = new Set(selectedModelIds.value)
  if (event.target.checked) {
    selectableRows.value.forEach((row) => next.add(String(row.model.id)))
  } else {
    selectableRows.value.forEach((row) => next.delete(String(row.model.id)))
  }
  selectedModelIds.value = next
}

watch(
  listingStatusFilter,
  () => {
    selectedModelIds.value = new Set()
  }
)

watch(
  () => rows.listingRows.value.map((row) => row.model.id).join(','),
  () => {
    const validIds = new Set(rows.listingRows.value.map((row) => String(row.model.id)))
    setSelectedModelIds(
      Array.from(selectedModelIds.value).filter((id) => validIds.has(id))
    )
  }
)

function handleCloseMenuOutside(event) {
  if (!openMenuId.value) return
  const target = event.target
  if (target && target.closest && target.closest('.relative')) return
  closeMenu()
}

onMounted(() => {
  document.addEventListener('click', handleCloseMenuOutside)
})
onUnmounted(() => {
  document.removeEventListener('click', handleCloseMenuOutside)
})

async function handleDirectAction(modelId, kind) {
  if (!props.agionePlatform) return
  savingListings.value = true
  try {
    if (kind === 'remove') {
      if (
        !confirm('确认从当前挂售平台列表移除该模型？\n\n不会删除模型、渠道价格或历史记录，仅在该挂售平台上不展示。')
      ) {
        return
      }
      await llmOpsApi.bulkRemoveResaleListingModels({
        platform: props.agionePlatform.id,
        models: [modelId],
        reason: 'Removed from listing workbench'
      })
      showSuccess('已移除')
    } else if (kind === 'offline') {
      if (!confirm('确认下架该模型在当前平台的所有活跃挂售渠道？')) {
        return
      }
      await llmOpsApi.bulkOfflineResaleListings({
        platform: props.agionePlatform.id,
        models: [modelId]
      })
      showSuccess('已下架')
    } else if (kind === 'restore') {
      await llmOpsApi.bulkRestoreResaleListingModels({
        platform: props.agionePlatform.id,
        models: [modelId]
      })
      showSuccess('已恢复')
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
  const targetRows =
    kind === 'offline' ? selectedOfflineRows.value : selectedRemoveRows.value
  if (!targetRows.length) return
  const modelIds = targetRows.map((row) => row.model.id)
  const confirmMessage =
    kind === 'offline'
      ? `确认批量下架 ${modelIds.length} 个模型？`
      : `确认批量移除 ${modelIds.length} 个未上架模型？`
  if (!confirm(confirmMessage)) return

  savingListings.value = true
  try {
    if (kind === 'offline') {
      await llmOpsApi.bulkOfflineResaleListings({
        platform: props.agionePlatform.id,
        models: modelIds
      })
      showSuccess('已批量下架')
    } else {
      await llmOpsApi.bulkRemoveResaleListingModels({
        platform: props.agionePlatform.id,
        models: modelIds,
        reason: 'Batch removed from listing workbench'
      })
      showSuccess('已批量移除')
    }
    setSelectedModelIds(
      Array.from(selectedModelIds.value).filter(
        (id) => !modelIds.map(String).includes(id)
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

function actionErrorLabel(kind) {
  if (kind === 'remove') return '移除失败'
  if (kind === 'offline') return '下架失败'
  return '恢复失败'
}
</script>

<style scoped>
.panel {
  @apply rounded-lg border border-slate-200 bg-white p-4 shadow-sm;
}

.panel-title {
  @apply text-sm font-semibold text-slate-900;
}

.table-toolbar {
  @apply flex flex-col gap-3 border-b border-slate-200 bg-white px-4 py-3 sm:flex-row sm:items-center sm:justify-between;
}

.data-table {
  @apply min-w-full divide-y divide-slate-200;
}

.data-table tbody {
  @apply divide-y divide-slate-100 bg-white;
}

.data-table tr {
  @apply hover:bg-slate-50;
}

.table-head {
  @apply whitespace-nowrap bg-slate-50 px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500;
}

.table-cell {
  @apply whitespace-nowrap px-4 py-3 text-sm text-slate-600;
}

.status-pill {
  @apply inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium;
}

.status-pill.tone-success {
  @apply bg-emerald-50 text-emerald-700;
}

.status-pill.tone-warn {
  @apply bg-amber-50 text-amber-700;
}

.status-pill.tone-neutral {
  @apply bg-slate-100 text-slate-500;
}

.status-pill.tone-muted {
  @apply bg-slate-200 text-slate-600;
}

.status-filter-chip {
  @apply rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-600 transition hover:border-slate-300 hover:bg-slate-50;
}

.status-filter-chip-active {
  @apply border-indigo-200 bg-indigo-50 text-indigo-700;
}

.add-listing-button {
  @apply inline-flex h-9 items-center rounded-lg bg-indigo-600 px-3 text-sm font-medium text-white shadow-sm transition hover:bg-indigo-700;
}

.batch-action {
  @apply inline-flex h-8 items-center rounded-md border border-slate-200 bg-white px-3 text-xs font-medium text-slate-600 transition hover:border-slate-300 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50;
}

.batch-action-danger {
  @apply border-rose-100 text-rose-600 hover:border-rose-200 hover:bg-rose-50;
}

.row-checkbox {
  @apply h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 disabled:cursor-not-allowed disabled:opacity-40;
}

.row-action-trigger {
  @apply inline-flex h-8 w-8 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-500 transition hover:border-slate-300 hover:bg-slate-50;
}

.row-action-trigger-open {
  @apply border-slate-300 bg-slate-50 text-slate-700;
}

.row-action-menu {
  @apply absolute right-0 z-20 mt-1 w-40 overflow-hidden rounded-lg border border-slate-200 bg-white py-1 shadow-lg;
}

.row-action-item {
  @apply block w-full px-3 py-2 text-left text-sm text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50;
}

.row-action-item-danger {
  @apply text-rose-600 hover:bg-rose-50;
}

.row-action-divider {
  @apply my-1 h-px bg-slate-100;
}
</style>
