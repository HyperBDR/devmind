<template>
  <section class="space-y-5">
    <div class="source-summary-strip">
      <div
        v-for="item in sourceMetrics"
        :key="item.label"
        class="source-summary-item"
      >
        <p class="text-xs font-medium text-slate-500">{{ item.label }}</p>
        <p class="font-mono text-lg font-semibold text-slate-900">
          {{ item.value }}
        </p>
        <p class="hidden min-w-0 truncate text-xs text-slate-400 md:block">
          {{ item.hint }}
        </p>
      </div>
    </div>

    <div class="panel overflow-hidden p-0">
      <div class="table-toolbar">
        <div>
          <h3 class="panel-title">模型价格源</h3>
          <p class="mt-1 text-xs text-slate-500">
            维护原厂、供货商、人工等价格源，供渠道采购价和平台上架价计算使用。
          </p>
        </div>
        <div class="flex flex-wrap justify-end gap-2">
          <button
            class="btn-secondary"
            type="button"
            @click="showManualImportModal = true"
          >
            Excel 批量导入
          </button>
          <button
            class="btn-primary"
            type="button"
            @click="showPriceSourceModal = true"
          >
            <span class="icon-mark" />
            新增价格源
          </button>
        </div>
      </div>
      <div class="overflow-x-auto">
        <table class="data-table source-table">
          <thead>
            <tr>
              <th class="table-head">价格源</th>
              <th class="table-head">关联对象</th>
              <th class="table-head">获取方式</th>
              <th class="table-head">状态</th>
              <th class="table-head">最近采集</th>
              <th class="table-head">价格地址</th>
              <th class="table-head text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="source in sourceRows" :key="source.id">
              <td class="table-cell">
                <div class="flex min-w-0 items-center gap-2">
                  <span :class="['source-badge', source.category_tone]">
                    {{ source.category_label }}
                  </span>
                  <p class="truncate font-medium text-slate-900">
                    {{ source.name }}
                  </p>
                </div>
                <p class="mt-1 truncate font-mono text-xs text-slate-400">
                  {{ source.slug }}
                </p>
              </td>
              <td class="table-cell">
                <p class="font-medium text-slate-900">
                  {{ source.relation_name }}
                </p>
                <p class="mt-1 text-xs text-slate-400">
                  {{ source.relation_hint }}
                </p>
              </td>
              <td class="table-cell">
                <p class="font-medium text-slate-900">
                  {{ source.source_type_label }}
                </p>
                <p class="mt-1 font-mono text-xs text-slate-400">
                  {{ source.currency || '-' }}
                </p>
              </td>
              <td class="table-cell">
                <span :class="['status-pill', source.status_tone]">
                  {{ source.status_label }}
                </span>
                <p class="mt-1 text-xs text-slate-400">
                  {{ source.status_hint }}
                </p>
              </td>
              <td class="table-cell">
                <p class="font-medium text-slate-900">
                  {{ source.latest_run_label }}
                </p>
                <p class="mt-1 text-xs text-slate-400">
                  {{ source.enabled_hint }}
                </p>
              </td>
              <td class="table-cell table-url-cell">
                <a
                  v-if="source.endpoint_url"
                  class="link-url"
                  :href="source.endpoint_url"
                  rel="noopener noreferrer"
                  target="_blank"
                  :title="source.endpoint_url"
                >
                  {{ source.endpoint_url }}
                </a>
                <span v-else class="text-slate-400">-</span>
              </td>
              <td class="table-cell text-right" @click.stop @keydown.stop>
                <div class="source-table-actions">
                  <button
                    class="link-btn"
                    type="button"
                    @click="selectedSource = source"
                  >
                    查看价格
                  </button>
                  <button
                    v-if="source.can_manual_entry"
                    class="link-btn"
                    type="button"
                    @click="priceEntrySource = source"
                  >
                    录入价格
                  </button>
                  <button
                    class="link-btn"
                    type="button"
                    @click="editingSource = source"
                  >
                    编辑
                  </button>
                  <button
                    type="button"
                    class="link-btn"
                    :disabled="updatingSourceId === source.id"
                    @click="toggleSource(source)"
                  >
                    {{ source.is_enabled ? '停用' : '启用' }}
                  </button>
                  <button
                    v-if="source.can_collect"
                    class="link-btn"
                    type="button"
                    :disabled="
                      !source.is_enabled ||
                      collectingSourceId === source.id
                    "
                    :title="source.collect_hint"
                    @click="collectSource(source)"
                  >
                    {{
                      collectingSourceId === source.id
                        ? '采集中'
                        : source.collect_action_label
                    }}
                  </button>
                  <button
                    class="link-btn text-rose-600 hover:text-rose-700"
                    type="button"
                    :disabled="deletingSourceId === source.id"
                    @click="deleteSource(source)"
                  >
                    {{ deletingSourceId === source.id ? '删除中' : '删除' }}
                  </button>
                </div>
              </td>
            </tr>
            <tr v-if="!sourceRows.length">
              <td class="table-cell text-slate-500" colspan="7">
                暂无模型价格源配置。
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="panel overflow-hidden p-0">
      <div class="table-toolbar">
        <div>
          <h3 class="panel-title">模型厂商</h3>
          <p class="mt-1 text-xs text-slate-500">
            维护模型所属厂商；价格口径由上方模型价格源和渠道配置承载。
          </p>
        </div>
      </div>
      <div class="overflow-x-auto">
        <table class="data-table">
          <thead>
            <tr>
              <th class="table-head">模型厂商</th>
              <th class="table-head">数量</th>
              <th class="table-head">默认价格地址</th>
              <th class="table-head">状态</th>
              <th class="table-head text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="provider in providerRows" :key="provider.id">
              <td class="table-cell">
                <p class="font-medium text-slate-900">{{ provider.name }}</p>
                <p class="mt-1 font-mono text-xs text-slate-400">
                  {{ provider.code }}
                </p>
              </td>
              <td class="table-cell">
                <p class="text-slate-900">
                  {{ provider.model_count || 0 }} 个模型
                </p>
                <p class="mt-1 text-xs text-slate-400">
                  {{ provider.source_count || 0 }} 个价格源
                </p>
              </td>
              <td class="table-cell table-url-cell">
                <a
                  v-if="provider.price_source_url"
                  class="link-url"
                  :href="provider.price_source_url"
                  rel="noopener noreferrer"
                  target="_blank"
                  :title="provider.price_source_url"
                >
                  {{ provider.price_source_url }}
                </a>
                <span v-else class="text-slate-400">-</span>
              </td>
              <td class="table-cell">
                <span :class="provider.is_active ? 'badge-ok' : 'badge-muted'">
                  {{ provider.is_active ? '启用' : '停用' }}
                </span>
              </td>
              <td class="table-cell text-right">
                <button
                  class="link-btn"
                  type="button"
                  @click="selectedProvider = provider"
                >
                  查看厂商定价
                </button>
                <button
                  class="link-btn ml-3"
                  type="button"
                  @click="openProviderModal(provider)"
                >
                  编辑
                </button>
              </td>
            </tr>
            <tr v-if="!providerRows.length">
              <td class="table-cell text-slate-500" colspan="5">
                暂无模型厂商。
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <ProviderModal
      :open="showProviderModal"
      :provider="editingProvider"
      @close="closeProviderModal"
      @saved="handleProviderSaved"
    />
    <ManualPriceImportModal
      :open="showManualImportModal"
      :providers="providers"
      @close="showManualImportModal = false"
      @imported="handleManualImported"
    />
    <PriceSourceModal
      :open="showPriceSourceModal || Boolean(editingSource)"
      :source="editingSource"
      @close="closePriceSourceModal"
      @saved="handleSourceSaved"
    />
    <ManualPriceEntryModal
      :open="Boolean(priceEntrySource)"
      :source="priceEntrySource"
      :providers="providers"
      :models="models"
      @close="priceEntrySource = null"
      @saved="handlePriceEntrySaved"
    />
    <ProviderPricingDrawer
      :provider="selectedProvider"
      :models="selectedProviderModels"
      :sources="selectedProviderSources"
      :price-items="selectedProviderPriceItems"
      :display-currency="displayCurrency"
      :exchange-rate="exchangeRate"
      @close="selectedProvider = null"
    />
    <SourcePriceDrawer
      :source="selectedSource"
      :models="models"
      :price-items="priceItems"
      :display-currency="displayCurrency"
      :exchange-rate="exchangeRate"
      :deleting="deletingSourceId === selectedSource?.id"
      @close="selectedSource = null"
      @delete="deleteSource"
      @refresh="emit('refresh')"
    />
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { llmOpsApi } from '@/api/llmOps'
import { useToast } from '@/composables/useToast'
import ManualPriceImportModal from '@/components/llm-ops/ManualPriceImportModal.vue'
import ManualPriceEntryModal from '@/components/llm-ops/ManualPriceEntryModal.vue'
import PriceSourceModal from '@/components/llm-ops/PriceSourceModal.vue'
import ProviderModal from '@/components/llm-ops/ProviderModal.vue'
import ProviderPricingDrawer from '@/components/llm-ops/ProviderPricingDrawer.vue'
import SourcePriceDrawer from '@/components/llm-ops/SourcePriceDrawer.vue'

const props = defineProps({
  providers: {
    type: Array,
    required: true
  },
  models: {
    type: Array,
    required: true
  },
  sources: {
    type: Array,
    required: true
  },
  collectionRuns: {
    type: Array,
    default: () => []
  },
  priceItems: {
    type: Array,
    default: () => []
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

const emit = defineEmits(['refresh'])
const { showSuccess, showError } = useToast()

const selectedProvider = ref(null)
const selectedSource = ref(null)
const editingSource = ref(null)
const priceEntrySource = ref(null)
const showPriceSourceModal = ref(false)
const showProviderModal = ref(false)
const showManualImportModal = ref(false)
const editingProvider = ref(null)
const collectingSourceId = ref(null)
const updatingSourceId = ref(null)
const deletingSourceId = ref(null)

const sourceMetrics = computed(() => {
  const official = props.sources.filter(
    (source) => source.source_category === 'official_provider'
  ).length
  const supplier = props.sources.filter(
    (source) => source.source_category === 'supplier'
  ).length
  const manual = props.sources.filter(
    (source) => source.source_category === 'manual'
  ).length
  const unknown = props.sources.filter(
    (source) => !knownCategories.has(source.source_category)
  ).length
  return [
    {
      label: '原厂来源',
      value: official,
      hint: '可用于对比或采购计算'
    },
    {
      label: '供货商来源',
      value: supplier,
      hint: '可用于渠道采购价计算'
    },
    {
      label: '人工维护',
      value: manual,
      hint: 'Excel 或临时维护的模型价格源'
    },
    {
      label: '待确认',
      value: unknown,
      hint: '需要确认用途或价格口径'
    }
  ]
})

const sourceRows = computed(() =>
  props.sources
    .map((source) => {
      const category = sourceCategory(source.source_category)
      const relation = sourceRelation(source)
      const latestRun = latestRunForSource(source.id)
      return {
        ...source,
        category_label: category.label,
        category_tone: category.tone,
        relation_name: relation.name,
        relation_hint: relation.hint,
        source_type_label: sourceTypeLabel(source),
        status_label: sourceStatus(source, latestRun).label,
        status_tone: sourceStatus(source, latestRun).tone,
        status_hint: sourceStatus(source, latestRun).hint,
        latest_run_label: latestRunLabel(source, latestRun),
        can_collect: canCollectSource(source),
        can_manual_entry: canManualEntrySource(source),
        collect_action_label: collectActionLabel(source),
        collect_hint: collectHint(source),
        enabled_hint: source.is_enabled
          ? '会参与采集和价格计算'
          : '停用后不可触发采集'
      }
    })
    .sort((left, right) => {
      const leftRank = categoryRank(left.source_category)
      const rightRank = categoryRank(right.source_category)
      if (leftRank !== rightRank) return leftRank - rightRank
      return String(left.name).localeCompare(String(right.name))
    })
)

const providerRows = computed(() =>
  props.providers.map((provider) => {
    const providerSources = props.sources.filter(
      (source) => String(source.provider) === String(provider.id)
    )
    const priceSource = preferredPriceSource(providerSources)
    return {
      ...provider,
      source_count: providerSources.length,
      primary_source_id: priceSource?.id || null,
      price_source_url: priceSource?.endpoint_url || provider.website || '',
      primary_source_url: priceSource?.endpoint_url || ''
    }
  })
)

const selectedProviderModels = computed(() => {
  if (!selectedProvider.value) return []
  return props.models.filter(
    (model) => String(model.provider) === String(selectedProvider.value.id)
  )
})

const selectedProviderSources = computed(() => {
  if (!selectedProvider.value) return []
  return props.sources.filter(
    (source) => String(source.provider) === String(selectedProvider.value.id)
  )
})

const selectedProviderPriceItems = computed(() => {
  if (!selectedProvider.value) return []
  return props.priceItems.filter(
    (item) => String(item.provider) === String(selectedProvider.value.id)
  )
})

function openProviderModal(provider) {
  if (!provider) return
  editingProvider.value = provider
  showProviderModal.value = true
}

function closeProviderModal() {
  showProviderModal.value = false
  editingProvider.value = null
}

function handleProviderSaved() {
  closeProviderModal()
  emit('refresh')
}

function handleManualImported() {
  showManualImportModal.value = false
  emit('refresh')
}

function closePriceSourceModal() {
  showPriceSourceModal.value = false
  editingSource.value = null
}

function handleSourceSaved() {
  closePriceSourceModal()
  emit('refresh')
}

function handlePriceEntrySaved() {
  priceEntrySource.value = null
  emit('refresh')
}

async function toggleSource(source) {
  updatingSourceId.value = source.id
  try {
    await llmOpsApi.updateCollectionSource(source.id, {
      is_enabled: !source.is_enabled
    })
    showSuccess(`${source.name} 已${source.is_enabled ? '停用' : '启用'}`)
    emit('refresh')
  } catch (error) {
    showError(errorMessage(error, '更新价格源状态失败'))
  } finally {
    updatingSourceId.value = null
  }
}

async function collectSource(source) {
  if (!source.can_collect || !source.is_enabled) return
  collectingSourceId.value = source.id
  try {
    const response = await llmOpsApi.collectCollectionSource(source.id)
    const stats = response?.data || {}
    showSuccess(
      `${source.name} 采集完成：` +
        `${stats.models || 0} 个模型，` +
        `${stats.changed || 0} 个变化`
    )
    emit('refresh')
  } catch (error) {
    showError(errorMessage(error, '价格采集失败'))
  } finally {
    collectingSourceId.value = null
  }
}

async function deleteSource(source) {
  if (!source?.id) return
  const confirmed = window.confirm(
    `确认删除模型价格源「${source.name}」吗？\n\n` +
      '删除后会移除该价格源及其采集记录，关联模型或渠道会失去这个价格来源。'
  )
  if (!confirmed) return

  deletingSourceId.value = source.id
  try {
    await llmOpsApi.deleteCollectionSource(source.id)
    if (selectedSource.value?.id === source.id) {
      selectedSource.value = null
    }
    showSuccess('模型价格源已删除')
    emit('refresh')
  } catch (error) {
    showError(errorMessage(error, '删除模型价格源失败'))
  } finally {
    deletingSourceId.value = null
  }
}

function preferredPriceSource(sources) {
  return (
    sources.find((source) => source.source_category === 'official_provider') ||
    sources.find((source) => source.updates_model_prices) ||
    sources.find((source) => source.endpoint_url) ||
    null
  )
}

const knownCategories = new Set([
  'official_provider',
  'supplier',
  'manual',
  'unknown'
])

function sourceCategory(category) {
  const labels = {
    official_provider: {
      label: '原厂',
      tone: 'official'
    },
    supplier: {
      label: '供货商',
      tone: 'supplier'
    },
    manual: {
      label: '人工',
      tone: 'manual'
    },
    unknown: {
      label: '其他',
      tone: 'unknown'
    }
  }
  return labels[category] || labels.unknown
}

function categoryRank(category) {
  const ranks = {
    official_provider: 1,
    supplier: 2,
    manual: 3,
    unknown: 4
  }
  return ranks[category] || 9
}

function sourceRelation(source) {
  if (source.provider_name) {
    return {
      name: source.provider_name,
      hint: '模型厂商'
    }
  }
  if (source.channel_name) {
    return {
      name: source.channel_name,
      hint: '转发渠道 / 供应商'
    }
  }
  return {
    name: '未绑定',
    hint: '需要确认归属或渠道'
  }
}

function sourceTypeLabel(source) {
  const type = source?.source_type || ''
  const category = source?.source_category || ''
  if (isModelsDevSource(source)) {
    return 'models.dev 聚合源'
  }
  if (category === 'official_provider') return '官方价格页'
  if (category === 'manual') return '手动维护'
  if (category === 'supplier') return '供应商手动维护'
  const labels = {
    agione: 'Agione',
    yunce: 'Yunce',
    custom: '自定义'
  }
  return labels[type] || type || '-'
}

function sourceStatus(source, latestRun) {
  if (!source.is_enabled) {
    return {
      label: '停用',
      tone: 'muted',
      hint: '不会参与采集'
    }
  }
  if (canManualEntrySource(source)) {
    return {
      label: '手动维护',
      tone: 'info',
      hint: '通过录入或 Excel 导入更新'
    }
  }
  if (!canCollectSource(source)) {
    return {
      label: '待适配',
      tone: 'warn',
      hint: collectHint(source)
    }
  }
  if (latestRun?.status === 'failed') {
    return {
      label: '采集失败',
      tone: 'danger',
      hint: '需要检查价格地址或采集器'
    }
  }
  if (['running', 'pending', 'processing'].includes(latestRun?.status)) {
    return {
      label: '采集中',
      tone: 'info',
      hint: '请稍后刷新'
    }
  }
  return {
    label: '启用',
    tone: 'ok',
    hint: '可参与采集和计算'
  }
}

function canCollectSource(source) {
  return Boolean(
    source.provider && source.source_category === 'official_provider'
  )
}

function canManualEntrySource(source) {
  return ['supplier', 'manual', 'unknown'].includes(source.source_category)
}

function collectActionLabel(source) {
  if (canCollectSource(source)) return '采集价格'
  return '暂不支持'
}

function collectHint(source) {
  if (canCollectSource(source)) {
    if (isModelsDevSource(source)) {
      return '从 models.dev 聚合 JSON 拉取并入库'
    }
    return '从配置的价格地址拉取并入库'
  }
  if (canManualEntrySource(source)) {
    return '请使用录入价格或 Excel 批量导入'
  }
  if (source.source_type === 'yunce') {
    return '需通过专用采集器执行'
  }
  return '等待适配采集器'
}

function isModelsDevSource(source) {
  return String(source?.endpoint_url || '')
    .toLowerCase()
    .includes('models.dev/api.json')
}

function errorMessage(error, fallback) {
  return (
    error?.response?.data?.detail ||
    error?.response?.data?.message ||
    error?.message ||
    fallback
  )
}

function latestRunForSource(sourceId) {
  const rows = props.collectionRuns
    .filter((run) => String(run.source) === String(sourceId))
    .sort(
      (left, right) =>
        new Date(
          right.finished_at || right.started_at || right.created_at || 0
        ).getTime() -
        new Date(
          left.finished_at || left.started_at || left.created_at || 0
        ).getTime()
    )
  return rows[0] || null
}

function latestRunLabel(source, run) {
  if (run?.finished_at || run?.started_at) {
    return formatDateTime(run.finished_at || run.started_at)
  }
  if (source.last_collected_at) {
    return formatDateTime(source.last_collected_at)
  }
  return '未采集'
}

function formatDateTime(value) {
  if (!value) return '-'
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  }).format(new Date(value))
}
</script>

<style scoped>
.panel {
  @apply rounded-lg border border-slate-200 bg-white p-4 shadow-sm;
}

.panel-title {
  @apply text-sm font-semibold text-slate-900;
}

.source-summary-strip {
  @apply grid gap-px overflow-hidden rounded-lg border border-slate-200 bg-slate-200 shadow-sm sm:grid-cols-2 lg:grid-cols-4;
}

.source-summary-item {
  @apply flex min-w-0 items-center gap-3 bg-white px-4 py-3;
}

.table-toolbar {
  @apply flex flex-col gap-3 border-b border-slate-200 bg-white px-4 py-3 sm:flex-row sm:items-center sm:justify-between;
}

.icon-mark {
  @apply inline-block h-3.5 w-3.5 shrink-0 rounded-sm bg-current;
}

.data-table {
  @apply min-w-full table-fixed divide-y divide-slate-200;
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
  @apply min-w-0 px-4 py-3 text-sm text-slate-600;
}

.table-url-cell {
  @apply max-w-none;
}

.source-table {
  @apply min-w-[68rem];
}

.source-table-actions {
  @apply flex min-w-0 flex-wrap items-center justify-end gap-x-3 gap-y-1;
}

.empty-row {
  @apply px-4 py-6 text-sm text-slate-500;
}

.btn-primary {
  @apply inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60;
}

.link-btn {
  @apply text-sm font-medium text-indigo-600 hover:text-indigo-700;
}

.link-btn:disabled {
  @apply cursor-not-allowed text-slate-400 hover:text-slate-400;
}

.link-url {
  @apply block truncate text-sm font-medium text-indigo-600 hover:text-indigo-700 hover:underline;
}

.badge-ok {
  @apply rounded-full border border-emerald-100 bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700;
}

.badge-muted {
  @apply rounded-full border border-slate-200 bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600;
}

.status-pill {
  @apply inline-flex rounded-full border px-2 py-1 text-xs font-medium;
}

.status-pill.ok {
  @apply border-emerald-100 bg-emerald-50 text-emerald-700;
}

.status-pill.info {
  @apply border-sky-100 bg-sky-50 text-sky-700;
}

.status-pill.warn {
  @apply border-amber-100 bg-amber-50 text-amber-700;
}

.status-pill.danger {
  @apply border-rose-100 bg-rose-50 text-rose-700;
}

.status-pill.muted {
  @apply border-slate-200 bg-slate-100 text-slate-600;
}

.source-badge {
  @apply rounded-full border px-2 py-1 text-xs font-medium;
}

.source-badge.official {
  @apply border-emerald-100 bg-emerald-50 text-emerald-700;
}

.source-badge.supplier {
  @apply border-indigo-100 bg-indigo-50 text-indigo-700;
}

.source-badge.manual {
  @apply border-amber-100 bg-amber-50 text-amber-700;
}

.source-badge.unknown {
  @apply border-slate-200 bg-slate-100 text-slate-600;
}
</style>
