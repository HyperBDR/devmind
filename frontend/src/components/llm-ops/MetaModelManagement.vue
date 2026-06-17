<template>
  <section class="space-y-5">
    <div class="source-summary-strip">
      <div
        v-for="item in metricCards"
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

    <div class="grid gap-4 xl:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
      <div class="panel overflow-hidden p-0">
        <div class="table-toolbar">
          <div>
            <h3 class="panel-title">元模型厂商</h3>
            <p class="mt-1 text-xs text-slate-500">
              按厂商查看元模型覆盖、模型 SKU 和价格项。
            </p>
          </div>
          <button
            class="btn-secondary"
            type="button"
            @click="vendorFilter = ''"
          >
            全部
          </button>
        </div>
        <div class="divide-y divide-slate-100">
          <button
            v-for="row in vendorRows"
            :key="row.id || 'unbound'"
            class="vendor-row"
            type="button"
            :class="{ active: vendorRowActive(row) }"
            @click="vendorFilter = row.id ? String(row.id) : 'unbound'"
          >
            <div class="min-w-0">
              <p class="truncate text-sm font-semibold text-slate-900">
                {{ row.name }}
              </p>
              <p class="mt-1 font-mono text-xs text-slate-400">
                {{ row.code || 'unbound' }}
              </p>
            </div>
            <div class="text-right">
              <p class="font-mono text-sm font-semibold text-slate-900">
                {{ row.meta_model_count }}
              </p>
              <p class="mt-1 text-xs text-slate-400">
                {{ row.sku_count }} SKU
              </p>
            </div>
          </button>
          <div
            v-if="!vendorRows.length"
            class="px-4 py-6 text-sm text-slate-500"
          >
            暂无元模型厂商。
          </div>
        </div>
      </div>

      <div class="panel overflow-hidden p-0">
        <div class="table-toolbar">
          <div>
            <h3 class="panel-title">元模型库</h3>
            <p class="mt-1 text-xs text-slate-500">
              管理厂商、模型家族、别名和采集后的归一化模型身份。
            </p>
          </div>
          <div class="flex flex-col gap-2 sm:flex-row sm:items-center">
            <select v-model="statusFilter" class="field-sm sm:w-32">
              <option value="">全部状态</option>
              <option value="active">Active</option>
              <option value="deprecated">Deprecated</option>
              <option value="unknown">Unknown</option>
            </select>
            <select v-model="modalityFilter" class="field-sm sm:w-36">
              <option value="">全部模态</option>
              <option value="text">Text</option>
              <option value="multimodal">Multimodal</option>
              <option value="audio">Audio</option>
              <option value="video">Video</option>
            </select>
            <input
              v-model="searchKeyword"
              class="field-sm sm:w-64"
              placeholder="搜索名称、Code、别名或家族"
            />
            <button
              class="btn-secondary"
              type="button"
              :disabled="syncingMetaModels"
              @click="syncMetaModels"
            >
              {{ syncingMetaModels ? '同步中' : '同步真实元模型' }}
            </button>
            <button class="btn-primary" type="button" @click="openModal()">
              <span class="icon-mark" />
              新增元模型
            </button>
          </div>
        </div>
        <div class="overflow-x-auto">
          <table class="data-table">
            <thead>
              <tr>
                <th class="table-head">元模型</th>
                <th class="table-head">厂商</th>
                <th class="table-head">能力</th>
                <th class="table-head text-right">模型 SKU</th>
                <th class="table-head">状态</th>
                <th class="table-head text-right">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in filteredRows" :key="item.id">
                <td class="table-cell">
                  <div class="min-w-56">
                    <p class="font-medium text-slate-900">
                      {{ item.name }}
                    </p>
                    <p class="mt-1 font-mono text-xs text-slate-400">
                      {{ item.code }}
                    </p>
                    <div class="mt-2 flex flex-wrap gap-1">
                      <span
                        v-for="alias in previewAliases(item)"
                        :key="alias"
                        class="alias-chip"
                      >
                        {{ alias }}
                      </span>
                    </div>
                  </div>
                </td>
                <td class="table-cell">
                  <p class="font-medium text-slate-800">
                    {{ item.effective_vendor_name || item.vendor_name || '未归类' }}
                  </p>
                  <p class="mt-1 text-xs text-slate-400">
                    {{ item.family || '未归类' }}
                    <span v-if="item.version"> · {{ item.version }}</span>
                  </p>
                </td>
                <td class="table-cell">
                  <div class="flex flex-wrap gap-1.5">
                    <span class="source-badge supplier">
                      {{ modalityLabel(item.modality) }}
                    </span>
                    <span
                      v-for="feature in featureLabels(item)"
                      :key="feature"
                      class="source-badge unknown"
                    >
                      {{ feature }}
                    </span>
                  </div>
                  <p class="mt-2 text-xs text-slate-400">
                    {{ tokenLabel(item) }}
                  </p>
                </td>
                <td class="table-cell text-right">
                  <p class="font-mono text-sm font-semibold text-slate-900">
                    {{ item.sku_count }}
                  </p>
                  <p class="mt-1 text-xs text-slate-400">
                    {{ item.provider_price_count || 0 }} price rows
                  </p>
                </td>
                <td class="table-cell">
                  <span :class="['status-pill', statusTone(item.status)]">
                    {{ statusLabel(item.status) }}
                  </span>
                  <p class="mt-2 text-xs text-slate-400">
                    {{ lifecycleLabel(item) }}
                  </p>
                </td>
                <td class="table-cell text-right">
                  <button
                    class="link-btn"
                    type="button"
                    @click="openModal(item)"
                  >
                    编辑
                  </button>
                  <button
                    class="danger-link-btn ml-3"
                    type="button"
                    :disabled="deletingId === item.id || item.sku_count > 0"
                    @click="deleteMetaModel(item)"
                  >
                    {{
                      item.sku_count > 0
                        ? '已关联'
                        : deletingId === item.id
                          ? '删除中'
                          : '删除'
                    }}
                  </button>
                </td>
              </tr>
              <tr v-if="!filteredRows.length">
                <td class="table-cell text-slate-500" colspan="6">
                  暂无符合条件的元模型。
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <MetaModelModal
      :open="showModal"
      :meta-model="editingMetaModel"
      :providers="providers"
      @close="closeModal"
      @saved="handleSaved"
    />
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { llmOpsApi } from '@/api/llmOps'
import { useToast } from '@/composables/useToast'
import MetaModelModal from '@/components/llm-ops/MetaModelModal.vue'
import { resolveCanonicalMetaVendor } from '@/utils/llmOpsMeta'

const props = defineProps({
  metaModels: {
    type: Array,
    required: true
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
  }
})

const emit = defineEmits(['refresh'])
const { showSuccess, showError } = useToast()

const searchKeyword = ref('')
const vendorFilter = ref('')
const statusFilter = ref('')
const modalityFilter = ref('')
const showModal = ref(false)
const editingMetaModel = ref(null)
const deletingId = ref(null)
const syncingMetaModels = ref(false)

const rows = computed(() =>
  props.metaModels.map((item) => {
    const skuCount = props.models.filter(
      (model) => String(model.meta_model) === String(item.id)
    ).length
    const canonicalVendor = resolveCanonicalMetaVendor(item, props.providers)
    return {
      ...item,
      effective_vendor:
        item.effective_vendor || canonicalVendor.id,
      effective_vendor_code:
        item.effective_vendor_code || canonicalVendor.code,
      effective_vendor_name:
        item.effective_vendor_name || canonicalVendor.name,
      sku_count: skuCount
    }
  })
)

const vendorRows = computed(() => {
  const map = new Map()
  props.providers.forEach((provider) => {
    map.set(String(provider.id), {
      id: provider.id,
      name: provider.name,
      code: provider.code,
      meta_model_count: 0,
      sku_count: 0
    })
  })
  rows.value.forEach((item) => {
    if (!item.effective_vendor) {
      // The backend canonical resolver guarantees every meta
      // model has a vendor. Rows without one are skipped so
      // the UI never shows an "unbound" vendor bucket.
      return
    }
    const key = String(item.effective_vendor)
    if (!map.has(key)) {
      return
    }
    const row = map.get(key)
    row.meta_model_count += 1
    row.sku_count += item.sku_count
  })
  return Array.from(map.values())
    .filter((row) => row.meta_model_count || row.id)
    .sort((left, right) => {
      if (right.meta_model_count !== left.meta_model_count) {
        return right.meta_model_count - left.meta_model_count
      }
      return String(left.name).localeCompare(String(right.name))
    })
})

const filteredRows = computed(() => {
  const keyword = searchKeyword.value.trim().toLowerCase()
  return rows.value
    .filter((item) => {
      if (
        vendorFilter.value &&
        vendorFilter.value !== 'unbound' &&
        String(item.effective_vendor || '') !== String(vendorFilter.value)
      ) {
        return false
      }
      if (statusFilter.value && item.status !== statusFilter.value) {
        return false
      }
      if (modalityFilter.value && item.modality !== modalityFilter.value) {
        return false
      }
      if (!keyword) return true
      return searchableText(item).includes(keyword)
    })
    .sort((left, right) => {
      const leftVendor = left.effective_vendor_name || ''
      const rightVendor = right.effective_vendor_name || ''
      if (leftVendor !== rightVendor) {
        return leftVendor.localeCompare(rightVendor)
      }
      return String(left.name).localeCompare(String(right.name))
    })
})

// resolveCanonicalVendor / canonicalMetaVendorCode moved to
// frontend/src/utils/llmOpsMeta.js for reuse across the
// immersive publishing workspace and the meta model library.

const metricCards = computed(() => {
  const active = props.metaModels.filter((item) => item.status === 'active')
  const deprecated = props.metaModels.filter(
    (item) => item.status === 'deprecated'
  )
  const boundVendorIds = new Set(
    props.metaModels
      .map((item) => item.vendor)
      .filter((vendor) => vendor !== null && vendor !== undefined)
      .map(String)
  )
  const linkedSkus = rows.value.reduce((total, item) => {
    return total + item.sku_count
  }, 0)
  return [
    {
      label: '元模型',
      value: props.metaModels.length,
      hint: '归一化后的模型身份'
    },
    {
      label: '已绑定厂商',
      value: boundVendorIds.size,
      hint: '存在元模型的厂商数'
    },
    {
      label: '可用 / 弃用',
      value: `${active.length}/${deprecated.length}`,
      hint: 'Active / Deprecated'
    },
    {
      label: '关联 SKU',
      value: linkedSkus,
      hint: '具体价格模型行'
    }
  ]
})

function openModal(item = null) {
  editingMetaModel.value = item
  showModal.value = true
}

function closeModal() {
  showModal.value = false
  editingMetaModel.value = null
}

function handleSaved() {
  closeModal()
  showSuccess('元模型已保存')
  emit('refresh')
}

async function deleteMetaModel(item) {
  if (!item?.id) return
  if (item.sku_count > 0) {
    showError('存在关联模型 SKU，不能直接删除元模型')
    return
  }
  const confirmed = window.confirm(
    `确认删除元模型「${item.name}」吗？\n\n` +
      `当前关联 ${item.sku_count || 0} 个模型 SKU。删除会影响这些模型的展示身份。`
  )
  if (!confirmed) return

  deletingId.value = item.id
  try {
    await llmOpsApi.deleteMetaModel(item.id)
    showSuccess('元模型已删除')
    emit('refresh')
  } catch (error) {
    showError(errorMessage(error, '删除元模型失败'))
  } finally {
    deletingId.value = null
  }
}

async function syncMetaModels() {
  syncingMetaModels.value = true
  try {
    const response = await llmOpsApi.syncMetaModels()
    const stats = response?.data || {}
    showSuccess(`已同步 ${stats.models || 0} 个真实元模型`)
    emit('refresh')
  } catch (error) {
    showError(errorMessage(error, '同步元模型失败'))
  } finally {
    syncingMetaModels.value = false
  }
}

function searchableText(item) {
  return [
    item.name,
    item.code,
    item.family,
    item.version,
    item.vendor_name,
    ...(Array.isArray(item.aliases) ? item.aliases : [])
  ]
    .join(' ')
    .toLowerCase()
}

function vendorRowActive(row) {
  return String(vendorFilter.value) === String(row.id)
}

function previewAliases(item) {
  return Array.isArray(item.aliases) ? item.aliases.slice(0, 3) : []
}

function featureLabels(item) {
  const features = item.capabilities?.features || []
  return Array.isArray(features) ? features.slice(0, 3) : []
}

function tokenLabel(item) {
  const context = Number(item.context_window || 0)
  const output = Number(item.max_output_tokens || 0)
  if (!context && !output) return '未配置上下文'
  return `${numberLabel(context)} ctx / ${numberLabel(output)} out`
}

function numberLabel(value) {
  if (!value) return '-'
  return new Intl.NumberFormat('en-US').format(value)
}

function modalityLabel(value) {
  const labels = {
    text: 'Text',
    multimodal: 'Multimodal',
    audio: 'Audio',
    video: 'Video'
  }
  return labels[value] || value || '-'
}

function statusLabel(value) {
  const labels = {
    active: 'Active',
    deprecated: 'Deprecated',
    unknown: 'Unknown'
  }
  return labels[value] || value || 'Unknown'
}

function statusTone(value) {
  const tones = {
    active: 'ok',
    deprecated: 'warn',
    unknown: 'muted'
  }
  return tones[value] || 'muted'
}

function lifecycleLabel(item) {
  if (item.deprecated_at) return `弃用 ${item.deprecated_at}`
  if (item.released_at) return `发布 ${item.released_at}`
  return '未配置日期'
}

function errorMessage(error, fallback) {
  return (
    error?.response?.data?.detail ||
    error?.response?.data?.message ||
    error?.message ||
    fallback
  )
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

.field-sm {
  @apply rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none transition focus:border-indigo-300 focus:ring-4 focus:ring-indigo-50;
}

.btn-primary {
  @apply inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60;
}

.btn-secondary {
  @apply inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60;
}

.link-btn {
  @apply text-sm font-medium text-indigo-600 hover:text-indigo-700;
}

.danger-link-btn {
  @apply text-sm font-medium text-rose-600 hover:text-rose-700 disabled:cursor-not-allowed disabled:text-slate-400;
}

.icon-mark {
  @apply inline-block h-3.5 w-3.5 shrink-0 rounded-sm bg-current;
}

.vendor-row {
  @apply flex w-full items-center justify-between gap-3 px-4 py-3 text-left transition hover:bg-slate-50;
}

.vendor-row.active {
  @apply bg-indigo-50;
}

.alias-chip {
  @apply max-w-[10rem] truncate rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] font-medium text-slate-600;
}

.status-pill {
  @apply inline-flex rounded-full border px-2 py-1 text-xs font-medium;
}

.status-pill.ok {
  @apply border-emerald-100 bg-emerald-50 text-emerald-700;
}

.status-pill.warn {
  @apply border-amber-100 bg-amber-50 text-amber-700;
}

.status-pill.muted {
  @apply border-slate-200 bg-slate-100 text-slate-600;
}

.source-badge {
  @apply rounded-full border px-2 py-1 text-xs font-medium;
}

.source-badge.supplier {
  @apply border-indigo-100 bg-indigo-50 text-indigo-700;
}

.source-badge.unknown {
  @apply border-slate-200 bg-slate-100 text-slate-600;
}
</style>
