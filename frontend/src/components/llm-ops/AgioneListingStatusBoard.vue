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
      <div class="table-toolbar">
        <div>
          <h3 class="panel-title">模型挂售列表</h3>
          <p class="mt-1 text-xs text-slate-500">
            管理当前平台的上架、状态、批量下架与改价。
          </p>
        </div>
        <div class="flex flex-wrap items-center gap-3">
          <div class="flex items-center gap-2">
            <input
              v-model="searchQuery"
              type="text"
              class="h-9 w-[220px] rounded-md border border-slate-200 bg-white px-2.5 text-sm focus:border-agione-300 focus:outline-none focus:ring-2 focus:ring-agione-100"
              placeholder="搜索模型名称 / code"
            />
          </div>
          <span class="text-sm text-slate-500">
            {{ filteredListingRows.length }} /
            {{ rows.listingRows.value.length }}
          </span>
          <button
            type="button"
            class="add-listing-button"
            @click="openWorkspace(null, 'create')"
          >
            + 新建上架
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
              class="batch-action"
              :disabled="!selectedRows.length || savingListings"
              @click="handleBatchAction('price')"
            >
              批量改价
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
              <th class="table-head">挂售平台</th>
              <th class="table-head min-w-[200px]">模型信息 (ID / 元模型)</th>
              <th class="table-head">供货商 / 模型源</th>
              <th class="table-head min-w-[260px]">价格体系 (In / Out)</th>
              <th class="table-head">上架状态</th>
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
                  {{ row.lowest_option?.channel_name || '暂无供应' }}
                </p>
              </td>
              <td class="table-cell">
                <div class="flex flex-col gap-1 text-[12px] font-mono">
                  <div
                    class="flex justify-between rounded bg-emerald-50 px-2 py-1"
                  >
                    <span class="font-bold text-emerald-700">售价</span>
                    <span class="text-emerald-700">
                      In:
                      {{
                        rows.money(
                          row.active_listings?.[0]
                            ?.retail_input_price_per_million,
                          row.active_listings?.[0]?.currency
                        )
                      }}
                      · Out:
                      {{
                        rows.money(
                          row.active_listings?.[0]
                            ?.retail_output_price_per_million,
                          row.active_listings?.[0]?.currency
                        )
                      }}
                    </span>
                  </div>
                  <div class="flex justify-between px-2 text-slate-500">
                    <span>成本</span>
                    <span>
                      In:
                      {{
                        rows.money(
                          row.lowest_option?.input_price_per_million,
                          row.lowest_option?.currency
                        )
                      }}
                      · Out:
                      {{
                        rows.money(
                          row.lowest_option?.output_price_per_million,
                          row.lowest_option?.currency
                        )
                      }}
                    </span>
                  </div>
                </div>
              </td>
              <td class="table-cell">
                <span class="status-pill" :class="statusPillTone(row)">
                  {{ statusPillLabel(row) }}
                </span>
              </td>
              <td class="table-cell text-right">
                <div class="inline-flex gap-2">
                  <button
                    v-if="row.is_listed && !row.is_removed"
                    type="button"
                    class="row-link"
                    @click="openWorkspace(row.model.id, 'edit')"
                  >
                    编辑挂售
                  </button>
                  <button
                    v-else-if="!row.is_removed"
                    type="button"
                    class="row-link"
                    @click="openWorkspace(row.model.id, 'create')"
                  >
                    去挂售
                  </button>
                  <button
                    v-if="row.is_listed && !row.is_removed"
                    type="button"
                    class="row-link row-link-danger"
                    :disabled="savingListings"
                    @click="emitAction(row.model.id, 'offline')"
                  >
                    下架
                  </button>
                  <button
                    v-if="row.is_removed"
                    type="button"
                    class="row-link"
                    :disabled="savingListings"
                    @click="emitAction(row.model.id, 'restore')"
                  >
                    恢复
                  </button>
                  <button
                    v-else-if="!row.is_listed"
                    type="button"
                    class="row-link row-link-danger"
                    :disabled="savingListings || row.is_listed"
                    :title="row.is_listed ? '请先下架后再移除' : ''"
                    @click="emitAction(row.model.id, 'remove')"
                  >
                    移除
                  </button>
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

const emit = defineEmits(['refresh', 'action', 'open-workspace'])
const { showSuccess, showError } = useToast()

const listingStatusFilter = ref('actionable')
const searchQuery = ref('')
const savingListings = ref(false)
const selectedModelIds = ref(new Set())

const listingStatusOptions = [
  { label: '待处理', value: 'actionable' },
  { label: '全部', value: 'all' },
  { label: '已上架', value: 'listed' },
  { label: '未上架', value: 'unlisted' },
  { label: '可优化', value: 'not_lowest' },
  { label: '已移除', value: 'removed' }
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
  listingExclusionsRef: toRef(props, 'listingExclusions'),
  summaryRef: toRef(props, 'summary'),
  displayCurrencyRef: toRef(props, 'displayCurrency'),
  exchangeRateRef: toRef(props, 'exchangeRate'),
  selectedTrendModelIdRef: unusedModelId,
  selectedTrendChannelIdRef: unusedChannelId,
  trendProfitRateRef: unusedProfitRate,
  pointConversionRef: toRef(props, 'pointConversion')
})

const platformLabel = computed(() => props.agionePlatform?.name || '挂售平台')

const filteredListingRows = computed(() => {
  const all = rows.listingRows.value
  const query = String(searchQuery.value || '')
    .trim()
    .toLowerCase()
  return all.filter((row) => {
    if (listingStatusFilter.value === 'actionable') {
      if (
        row.is_removed ||
        (row.is_listed &&
          (row.lowest_option || row.is_listed) &&
          row.has_lowest_listing)
      )
        return false
    } else if (listingStatusFilter.value === 'listed') {
      if (!row.is_listed || row.is_removed) return false
    } else if (listingStatusFilter.value === 'unlisted') {
      if (row.is_listed || row.is_removed) return false
    } else if (listingStatusFilter.value === 'not_lowest') {
      if (!row.is_listed || row.has_lowest_listing || row.is_removed)
        return false
    } else if (listingStatusFilter.value === 'removed') {
      if (!row.is_removed) return false
    } else if (listingStatusFilter.value === 'all') {
      // pass through
    } else {
      return false
    }
    if (!query) return true
    const name = String(rows.modelDisplayName(row.model) || '').toLowerCase()
    const code = String(row.model?.code || '').toLowerCase()
    return name.includes(query) || code.includes(query)
  })
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
  const totalMargin = listedRows.reduce((sum, row) => {
    const listing = row.active_listings?.[0]
    if (!listing) return sum
    const inP = Number(listing.retail_input_price_per_million) || 0
    const inC = Number(row.lowest_option?.input_price_per_million) || 0
    if (inC > 0) {
      sum += (inP - inC) / inC
    }
    return sum
  }, 0)
  const avgMargin = listedRows.length
    ? Number(((totalMargin / listedRows.length) * 100).toFixed(1))
    : 0
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
      hint: `${optimizedRows.length} 个处于最低价`,
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
      value: listedRows.length ? `${avgMargin}%` : '—',
      hint: `${listedRows.length - optimizedRows.length} 个非最低价`,
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
  if (listingStatusFilter.value === 'not_lowest')
    return '暂无需要优化的上架模型。'
  if (listingStatusFilter.value === 'removed') return '暂无已移除模型。'
  return '没有符合筛选条件的模型。'
})

function statusPillLabel(row) {
  if (row.is_removed) return '已移除'
  if (!row.is_listed) return '未上架'
  if (row.has_lowest_listing) return '在售 · 最低'
  return '可优化'
}

function statusPillTone(row) {
  if (row.is_removed) return 'tone-muted'
  if (!row.is_listed) return 'tone-neutral'
  if (row.has_lowest_listing) return 'tone-success'
  return 'tone-warn'
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
  if (next.has(id)) next.delete(id)
  else next.add(id)
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

function emitAction(modelId, kind) {
  if (kind === 'remove' || kind === 'restore' || kind === 'offline') {
    handleDirectAction(modelId, kind)
    return
  }
  emit('action', { modelId, kind })
}

function openWorkspace(modelId, kind) {
  emit('open-workspace', { modelId, kind })
}

watch(listingStatusFilter, () => {
  selectedModelIds.value = new Set()
})

watch(searchQuery, () => {
  selectedModelIds.value = new Set()
})

watch(
  () => rows.listingRows.value.map((row) => row.model.id).join(','),
  () => {
    const validIds = new Set(
      rows.listingRows.value.map((row) => String(row.model.id))
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

async function handleDirectAction(modelId, kind) {
  if (!props.agionePlatform) return
  savingListings.value = true
  try {
    if (kind === 'remove') {
      if (
        !confirm(
          '确认从当前挂售平台列表移除该模型？\n\n不会删除模型、渠道价格或历史记录，仅在该挂售平台上不展示。'
        )
      )
        return
      await llmOpsApi.bulkRemoveResaleListingModels({
        platform: props.agionePlatform.id,
        models: [modelId],
        reason: 'Removed from listing workbench'
      })
      showSuccess('已移除')
    } else if (kind === 'offline') {
      if (!confirm('确认下架该模型在当前平台的所有活跃挂售渠道？')) return
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
  let targetRows = []
  if (kind === 'offline') targetRows = selectedOfflineRows.value
  else if (kind === 'remove') targetRows = selectedRemoveRows.value
  else if (kind === 'price') targetRows = selectedRows.value
  if (!targetRows.length) return
  const modelIds = targetRows.map((row) => row.model.id)
  const confirmMessage =
    kind === 'offline'
      ? `确认批量下架 ${modelIds.length} 个模型？`
      : kind === 'remove'
        ? `确认批量移除 ${modelIds.length} 个未上架模型？`
        : `确认对 ${modelIds.length} 个模型进入批量改价工作台？`
  if (!confirm(confirmMessage)) return
  if (kind === 'price') {
    emit('open-workspace', { modelId: null, kind: 'batch-price', modelIds })
    return
  }
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

.panel-title {
  font-weight: 600;
  color: #0f172a;
}

.table-toolbar {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  border-bottom-width: 1px;
  border-color: #e2e8f0;
  padding-left: 1rem;
  padding-right: 1rem;
  padding-top: 0.75rem;
  padding-bottom: 0.75rem;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
}

.data-table {
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
}

.table-cell {
  white-space: nowrap;
  padding-left: 1rem;
  padding-right: 1rem;
  padding-top: 0.75rem;
  padding-bottom: 0.75rem;
  color: #475569;
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

.status-filter-chip {
  border-radius: 9999px;
  border-width: 1px;
  border-color: #e2e8f0;
  padding-left: 0.75rem;
  padding-right: 0.75rem;
  padding-top: 0.25rem;
  padding-bottom: 0.25rem;
  font-weight: 500;
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
  height: 2.25rem;
  align-items: center;
  border-radius: 8px;
  background-color: #5f4ecf;
  padding-left: 0.75rem;
  padding-right: 0.75rem;
  font-weight: 500;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
  transition-property: color, background-color, border-color, box-shadow;
  transition-duration: 150ms;
  background-color: #4a3eb0;
}

.batch-action {
  display: inline-flex;
  height: 2rem;
  align-items: center;
  border-radius: 6px;
  border-width: 1px;
  border-color: #e2e8f0;
  padding-left: 0.75rem;
  padding-right: 0.75rem;
  font-weight: 500;
  color: #475569;
  transition-property: color, background-color, border-color, box-shadow;
  transition-duration: 150ms;
  border-color: #cbd5e1;
  background-color: #f8fafc;
}

.batch-action-danger {
  border-color: #ffe4e6;
  color: #e11d48;
  border-color: #fecdd3;
  background-color: #fff1f2;
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
  border-radius: 6px;
  border-width: 1px;
  border-color: #e2e8f0;
  padding-left: 0.625rem;
  padding-right: 0.625rem;
  font-weight: 500;
  color: #475569;
  transition-property: color, background-color, border-color, box-shadow;
  transition-duration: 150ms;
  border-color: #cbd5e1;
  background-color: #f8fafc;
}

.row-link-danger {
  border-color: #ffe4e6;
  color: #e11d48;
  border-color: #fecdd3;
  background-color: #fff1f2;
}
</style>
