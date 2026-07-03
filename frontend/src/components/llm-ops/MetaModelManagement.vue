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

    <div class="grid gap-4">
      <article class="panel min-w-0 overflow-hidden p-0">
        <div class="table-toolbar">
          <div class="toolbar-copy">
            <h3 class="panel-title">
              {{ t('llmOps.metaModelManagement.title') }}
            </h3>
            <p class="mt-1 text-xs text-slate-500">
              {{ t('llmOps.metaModelManagement.description') }}
            </p>
          </div>
          <div class="vendor-toolbar-summary">
            <button
              class="btn-secondary btn-action-sync"
              type="button"
              :aria-busy="syncingMetaModels"
              :disabled="syncingMetaModels"
              @click="syncMetaModels"
            >
              <svg
                aria-hidden="true"
                :class="[
                  'sync-action-icon',
                  { 'is-spinning': syncingMetaModels }
                ]"
                fill="none"
                stroke="currentColor"
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                viewBox="0 0 24 24"
              >
                <path d="M21 12a9 9 0 0 1-15.4 6.4L3 16" />
                <path d="M3 16v5h5" />
                <path d="M3 12a9 9 0 0 1 15.4-6.4L21 8" />
                <path d="M21 3v5h-5" />
              </svg>
              {{ syncActionLabel }}
            </button>
            <input
              v-model="vendorSearchKeyword"
              class="control-field vendor-search"
              name="meta-model-vendor-search"
              :placeholder="
                t('llmOps.metaModelManagement.filters.searchVendors')
              "
            />
            <span class="summary-pill">
              <span>{{ t('llmOps.metaModelManagement.summary.vendors') }}</span>
              <strong>{{ vendorRows.length }}</strong>
            </span>
          </div>
        </div>
        <div class="vendor-list">
          <div class="vendor-list-header">
            <span>{{ t('llmOps.metaModelManagement.table.vendor') }}</span>
            <span>{{ t('llmOps.metaModelManagement.table.metaModels') }}</span>
            <span>{{ t('llmOps.metaModelManagement.table.actions') }}</span>
          </div>
          <button
            v-for="row in filteredVendorRows"
            :key="row.id || row.code"
            class="vendor-row"
            type="button"
            :class="{ active: vendorRowActive(row) }"
            @click="openVendorModelsDrawer(row)"
          >
            <div class="vendor-name-cell">
              <ProviderIcon :provider="row.code || row.name" size="lg" />
              <div class="min-w-0">
                <p class="truncate text-sm font-semibold text-slate-900">
                  {{ row.name }}
                </p>
                <p class="mt-1 font-mono text-xs text-slate-400">
                  {{ row.code || '-' }}
                </p>
              </div>
            </div>
            <div class="metric-stack">
              <p class="metric-value">
                {{ row.meta_model_count }}
              </p>
            </div>
            <span class="link-btn text-center">
              {{ t('llmOps.metaModelManagement.actions.viewModels') }}
            </span>
          </button>
          <div v-if="!filteredVendorRows.length" class="empty-state">
            <h4 class="empty-title">
              {{ vendorEmptyTitle }}
            </h4>
            <p class="empty-copy">
              {{ vendorEmptyDescription }}
            </p>
            <button
              v-if="!vendorRows.length"
              class="btn-secondary btn-action-sync"
              type="button"
              :aria-busy="syncingMetaModels"
              :disabled="syncingMetaModels"
              @click="syncMetaModels"
            >
              <svg
                aria-hidden="true"
                :class="[
                  'sync-action-icon',
                  { 'is-spinning': syncingMetaModels }
                ]"
                fill="none"
                stroke="currentColor"
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                viewBox="0 0 24 24"
              >
                <path d="M21 12a9 9 0 0 1-15.4 6.4L3 16" />
                <path d="M3 16v5h5" />
                <path d="M3 12a9 9 0 0 1 15.4-6.4L21 8" />
                <path d="M21 3v5h-5" />
              </svg>
              {{ syncActionLabel }}
            </button>
          </div>
        </div>
      </article>
    </div>

    <div
      v-if="showVendorModelsDrawer"
      class="fixed inset-0 z-50 flex justify-end bg-slate-950/30"
      @click.self="closeVendorModelsDrawer"
    >
      <aside class="meta-drawer library-drawer">
        <div class="drawer-header">
          <div class="min-w-0 flex-1">
            <p class="drawer-eyebrow">
              {{ t('llmOps.metaModelManagement.drawer.eyebrow') }}
            </p>
            <div class="vendor-drawer-title-row">
              <ProviderIcon
                v-if="selectedVendorRow"
                :provider="selectedVendorRow.code || selectedVendorRow.name"
                size="lg"
              />
              <h3 class="drawer-title">
                {{
                  selectedVendorRow?.name ||
                  t('llmOps.metaModelManagement.drawer.fallbackTitle')
                }}
              </h3>
            </div>
            <p class="mt-1 font-mono text-xs text-slate-500">
              {{ selectedVendorRow?.code || '-' }}
            </p>
            <p class="drawer-desc">
              {{ t('llmOps.metaModelManagement.drawer.description') }}
            </p>
          </div>
          <div class="drawer-header-actions">
            <button
              class="btn-secondary btn-action-sync"
              type="button"
              :disabled="syncingMetaModels"
              @click="syncMetaModels"
            >
              {{ syncActionLabel }}
            </button>
            <button
              class="btn-secondary btn-action-cancel"
              type="button"
              @click="closeVendorModelsDrawer"
            >
              {{ t('llmOps.metaModelManagement.actions.close') }}
            </button>
          </div>
        </div>

        <div class="drawer-body">
          <div class="panel">
            <div class="drawer-filter-bar">
              <CompactSelect
                v-model="statusFilter"
                :options="statusOptions"
                class-name="control-select sm:w-36"
              />
              <CompactSelect
                v-model="modalityFilter"
                :options="modalityOptions"
                class-name="control-select sm:w-40"
              />
              <CompactSelect
                v-model="pageSize"
                :options="pageSizeOptions"
                class-name="control-select sm:w-32"
              />
              <input
                v-model="searchKeyword"
                class="control-field drawer-search"
                name="meta-model-search"
                :placeholder="
                  t('llmOps.metaModelManagement.filters.searchModels')
                "
              />
              <p class="drawer-result-note">
                {{
                  t('llmOps.metaModelManagement.summary.modelResult', {
                    total: vendorMetaRows.length,
                    active: selectedVendorActiveCount
                  })
                }}
              </p>
            </div>
          </div>

          <div class="panel min-w-0 overflow-hidden p-0">
            <div class="min-w-0 overflow-x-auto">
              <table class="data-table meta-model-table">
                <colgroup>
                  <col class="model-col" />
                  <col class="capability-col" />
                  <col class="context-col" />
                  <col class="release-col" />
                  <col class="status-col" />
                </colgroup>
                <thead>
                  <tr>
                    <th class="table-head">
                      {{ t('llmOps.metaModelManagement.table.metaModel') }}
                    </th>
                    <th class="table-head">
                      {{ t('llmOps.metaModelManagement.table.capability') }}
                    </th>
                    <th class="table-head">
                      {{ t('llmOps.metaModelManagement.table.context') }}
                    </th>
                    <th class="table-head">
                      {{ t('llmOps.metaModelManagement.table.releaseDate') }}
                    </th>
                    <th class="table-head">
                      {{ t('llmOps.metaModelManagement.table.status') }}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in paginatedVendorMetaRows" :key="item.id">
                    <td class="table-cell">
                      <div
                        class="meta-model-main"
                        :title="metaModelTitle(item)"
                      >
                        <p class="meta-model-name">
                          {{ compactMetaModelName(item) }}
                        </p>
                        <p
                          v-if="shouldShowMetaModelCode(item)"
                          class="meta-model-code"
                        >
                          {{ item.code }}
                        </p>
                      </div>
                    </td>
                    <td class="table-cell">
                      <div class="meta-model-capabilities">
                        <div class="capability-icon-list">
                          <span
                            v-for="capability in capabilityItems(item)"
                            :key="capability.key"
                            :class="['capability-icon-token', capability.tone]"
                            :aria-label="capability.label"
                            :title="capability.label"
                            role="img"
                          >
                            <svg
                              aria-hidden="true"
                              class="capability-icon"
                              fill="none"
                              stroke="currentColor"
                              stroke-linecap="round"
                              stroke-linejoin="round"
                              stroke-width="2"
                              viewBox="0 0 24 24"
                            >
                              <path
                                v-for="path in capability.paths"
                                :key="path"
                                :d="path"
                              />
                            </svg>
                            <span class="sr-only">{{ capability.label }}</span>
                          </span>
                        </div>
                      </div>
                    </td>
                    <td class="table-cell">
                      <div class="meta-model-context">
                        <p
                          class="font-mono text-xs font-semibold text-slate-800"
                        >
                          {{
                            t('llmOps.metaModelManagement.context.input', {
                              value: compactTokenLabel(item.context_window)
                            })
                          }}
                        </p>
                        <p class="mt-1 font-mono text-xs text-slate-400">
                          {{
                            t('llmOps.metaModelManagement.context.output', {
                              value: compactTokenLabel(item.max_output_tokens)
                            })
                          }}
                        </p>
                      </div>
                    </td>
                    <td class="table-cell">
                      <p
                        class="text-center font-mono text-xs font-semibold text-slate-700"
                      >
                        {{ releaseDateLabel(item.release_date) }}
                      </p>
                    </td>
                    <td class="table-cell">
                      <div class="meta-model-status">
                        <span :class="['status-pill', statusTone(item.status)]">
                          {{ statusLabel(item.status) }}
                        </span>
                      </div>
                    </td>
                  </tr>
                  <tr v-if="!vendorMetaRows.length">
                    <td class="table-cell text-slate-500" colspan="5">
                      {{ t('llmOps.metaModelManagement.empty.models') }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-if="vendorMetaRows.length" class="pagination-bar">
              <p class="text-xs text-slate-500">
                {{
                  t('llmOps.metaModelManagement.pagination.summary', {
                    total: vendorMetaRows.length,
                    current: safeCurrentPage,
                    pages: totalPages
                  })
                }}
              </p>
              <div class="flex items-center gap-2">
                <button
                  class="btn-secondary pagination-btn btn-action-neutral"
                  type="button"
                  :disabled="safeCurrentPage <= 1"
                  @click="goToPreviousPage"
                >
                  {{ t('llmOps.metaModelManagement.pagination.previous') }}
                </button>
                <button
                  class="btn-secondary pagination-btn btn-action-neutral"
                  type="button"
                  :disabled="safeCurrentPage >= totalPages"
                  @click="goToNextPage"
                >
                  {{ t('llmOps.metaModelManagement.pagination.next') }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </aside>
    </div>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { llmOpsApi } from '@/api/llmOps'
import { useToast } from '@/composables/useToast'
import CompactSelect from '@/components/llm-ops/CompactSelect.vue'
import ProviderIcon from '@/components/llm/ProviderIcon.vue'
import { resolveCanonicalMetaOwner } from '@/utils/llmOpsMeta'

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
const { t } = useI18n()

const searchKeyword = ref('')
const vendorSearchKeyword = ref('')
const statusFilter = ref('')
const modalityFilter = ref('')
const pageSize = ref(20)
const currentPage = ref(1)
const selectedVendorId = ref('')
const showVendorModelsDrawer = ref(false)
const syncingMetaModels = ref(false)

const statusOptions = computed(() => [
  {
    value: '',
    label: t('llmOps.metaModelManagement.filters.allStatuses')
  },
  { value: 'active', label: t('llmOps.metaModelManagement.status.active') },
  {
    value: 'deprecated',
    label: t('llmOps.metaModelManagement.status.deprecated')
  },
  { value: 'unknown', label: t('llmOps.metaModelManagement.status.unknown') }
])

const modalityOptions = computed(() => [
  {
    value: '',
    label: t('llmOps.metaModelManagement.filters.allModalities')
  },
  { value: 'text', label: t('llmOps.metaModelManagement.modality.text') },
  {
    value: 'multimodal',
    label: t('llmOps.metaModelManagement.modality.multimodal')
  },
  { value: 'audio', label: t('llmOps.metaModelManagement.modality.audio') },
  { value: 'video', label: t('llmOps.metaModelManagement.modality.video') }
])

const pageSizeOptions = computed(() => [
  {
    value: 10,
    label: t('llmOps.metaModelManagement.pagination.pageSize', { count: 10 })
  },
  {
    value: 20,
    label: t('llmOps.metaModelManagement.pagination.pageSize', { count: 20 })
  },
  {
    value: 50,
    label: t('llmOps.metaModelManagement.pagination.pageSize', { count: 50 })
  }
])

const rows = computed(() =>
  props.metaModels.map((item) => {
    const skuCount = props.models.filter(
      (model) => String(model.meta_model) === String(item.id)
    ).length
    const canonicalVendor = resolveCanonicalMetaOwner(item, props.providers)
    return {
      ...item,
      owner_key: item.owner_code || canonicalVendor.code,
      owner_code: item.owner_code || canonicalVendor.code,
      owner_name: item.owner_name || canonicalVendor.name,
      sku_count: skuCount
    }
  })
)

const vendorRows = computed(() => {
  const map = new Map()
  props.providers.forEach((provider) => {
    map.set(String(provider.code), {
      id: provider.code,
      name: provider.name,
      code: provider.code,
      meta_model_count: 0,
      sku_count: 0
    })
  })
  rows.value.forEach((item) => {
    if (!item.owner_key) {
      // The backend canonical resolver guarantees every meta
      // model has an owner. Rows without one are skipped so
      // the UI never shows an "unbound" owner bucket.
      return
    }
    const key = String(item.owner_key)
    if (!map.has(key)) {
      map.set(key, {
        id: key,
        name: item.owner_name || key,
        code: item.owner_code || key,
        meta_model_count: 0,
        sku_count: 0
      })
    }
    const row = map.get(key)
    row.meta_model_count += 1
    row.sku_count += item.sku_count
  })
  return Array.from(map.values())
    .filter((row) => row.meta_model_count > 0)
    .sort((left, right) => {
      if (right.meta_model_count !== left.meta_model_count) {
        return right.meta_model_count - left.meta_model_count
      }
      return String(left.name).localeCompare(String(right.name))
    })
})

const filteredVendorRows = computed(() => {
  const keyword = vendorSearchKeyword.value.trim().toLowerCase()
  if (!keyword) return vendorRows.value
  return vendorRows.value.filter((row) =>
    [row.name, row.code]
      .filter(Boolean)
      .join(' ')
      .toLowerCase()
      .includes(keyword)
  )
})

const selectedVendorRow = computed(() =>
  vendorRows.value.find(
    (item) => String(item.id) === String(selectedVendorId.value)
  )
)

const vendorMetaRows = computed(() => {
  const keyword = searchKeyword.value.trim().toLowerCase()
  return rows.value
    .filter((item) => {
      if (!selectedVendorId.value) {
        return false
      }
      if (String(item.owner_key || '') !== String(selectedVendorId.value)) {
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
      const leftTime = releaseDateTime(left.release_date)
      const rightTime = releaseDateTime(right.release_date)
      if (rightTime !== leftTime) {
        return rightTime - leftTime
      }
      return String(left.name).localeCompare(String(right.name))
    })
})

const totalPages = computed(() =>
  Math.max(1, Math.ceil(vendorMetaRows.value.length / Number(pageSize.value)))
)

const safeCurrentPage = computed(() =>
  Math.min(Math.max(Number(currentPage.value) || 1, 1), totalPages.value)
)

const paginatedVendorMetaRows = computed(() => {
  const size = Number(pageSize.value)
  const start = (safeCurrentPage.value - 1) * size
  return vendorMetaRows.value.slice(start, start + size)
})

// resolveCanonicalVendor / canonicalMetaOwnerCode moved to
// frontend/src/utils/llmOpsMeta.js for reuse across the
// immersive publishing workspace and the meta model library.

const metricCards = computed(() => {
  const active = props.metaModels.filter((item) => item.status === 'active')
  const deprecated = props.metaModels.filter(
    (item) => item.status === 'deprecated'
  )
  const boundVendorIds = new Set(
    props.metaModels
      .map((item) => item.owner_code)
      .filter((vendor) => vendor !== null && vendor !== undefined)
      .map(String)
  )
  return [
    {
      label: t('llmOps.metaModelManagement.metrics.metaModels.label'),
      value: props.metaModels.length,
      hint: t('llmOps.metaModelManagement.metrics.metaModels.hint')
    },
    {
      label: t('llmOps.metaModelManagement.metrics.boundVendors.label'),
      value: boundVendorIds.size,
      hint: t('llmOps.metaModelManagement.metrics.boundVendors.hint')
    },
    {
      label: t('llmOps.metaModelManagement.metrics.status.label'),
      value: `${active.length}/${deprecated.length}`,
      hint: t('llmOps.metaModelManagement.metrics.status.hint')
    }
  ]
})

const selectedVendorActiveCount = computed(
  () => vendorMetaRows.value.filter((item) => item.status === 'active').length
)

const syncActionLabel = computed(() =>
  syncingMetaModels.value
    ? t('llmOps.metaModelManagement.actions.syncing')
    : t('llmOps.metaModelManagement.actions.sync')
)

const vendorEmptyTitle = computed(() =>
  vendorRows.value.length
    ? t('llmOps.metaModelManagement.empty.filteredVendorsTitle')
    : t('llmOps.metaModelManagement.empty.vendorsTitle')
)

const vendorEmptyDescription = computed(() =>
  vendorRows.value.length
    ? t('llmOps.metaModelManagement.empty.filteredVendorsDescription')
    : t('llmOps.metaModelManagement.empty.vendorsDescription')
)

function openVendorModelsDrawer(row) {
  selectedVendorId.value = row?.id ? String(row.id) : ''
  currentPage.value = 1
  showVendorModelsDrawer.value = Boolean(selectedVendorId.value)
}

function closeVendorModelsDrawer() {
  showVendorModelsDrawer.value = false
}

function goToPreviousPage() {
  currentPage.value = Math.max(safeCurrentPage.value - 1, 1)
}

function goToNextPage() {
  currentPage.value = Math.min(safeCurrentPage.value + 1, totalPages.value)
}

watch(
  [searchKeyword, statusFilter, modalityFilter, selectedVendorId, pageSize],
  () => {
    currentPage.value = 1
  }
)

async function syncMetaModels() {
  syncingMetaModels.value = true
  try {
    const response = await llmOpsApi.syncMetaModels()
    const stats = response?.data || {}
    showSuccess(
      t('llmOps.metaModelManagement.messages.synced', {
        count: stats.models || 0
      })
    )
    emit('refresh')
  } catch (error) {
    showError(errorMessage(error, t('llmOps.metaModelManagement.errors.sync')))
  } finally {
    syncingMetaModels.value = false
  }
}

function searchableText(item) {
  return [
    item.name,
    item.code,
    item.family,
    item.owner_name,
    ...(Array.isArray(item.aliases) ? item.aliases : [])
  ]
    .join(' ')
    .toLowerCase()
}

function vendorRowActive(row) {
  return (
    String(selectedVendorId.value) === String(row.id) &&
    showVendorModelsDrawer.value
  )
}

function featureLabels(item) {
  const features = item.capabilities?.features || []
  return Array.isArray(features) ? features.slice(0, 3) : []
}

function capabilityItems(item) {
  const modality = String(item.modality || '').trim()
  const items = []
  if (modality) {
    items.push(
      capabilityDescriptor(modality, modalityLabel(modality), 'primary')
    )
  }
  featureLabels(item).forEach((feature) => {
    items.push(capabilityDescriptor(feature, featureLabel(feature), 'default'))
  })
  return items
}

function capabilityDescriptor(value, label, tone) {
  const key = String(value || '').trim()
  return {
    key,
    label,
    tone,
    paths: capabilityIconPaths(key)
  }
}

function capabilityIconPaths(value) {
  const normalized = String(value || '').toLowerCase()
  const iconMap = {
    attachment: [
      'M21.44 11.05 12 20.49a6 6 0 0 1-8.49-8.49l9.9-9.9a4 4 0 0 1 5.66 5.66l-9.9 9.9a2 2 0 1 1-2.83-2.83l8.49-8.49'
    ],
    audio: ['M4 10v4', 'M8 8v8', 'M12 5v14', 'M16 8v8', 'M20 10v4'],
    chat: ['M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4Z'],
    image_generation: ['M4 5h16v14H4Z', 'm4 15 4-4 4 4 3-3 5 5', 'M9 9h.01'],
    multimodal: ['M4 5h16v14H4Z', 'M8 9h.01', 'm4 15 4-4 4 4 2-2 4 4'],
    reasoning: [
      'M9 18h6',
      'M10 22h4',
      'M8 14a6 6 0 1 1 8 0c-.8.7-1.3 1.6-1.5 2.5h-5A5 5 0 0 0 8 14Z'
    ],
    structured_output: ['M8 8 4 12l4 4', 'm16 8 4 4-4 4', 'M14 4 10 20'],
    text: ['M4 6h16', 'M4 12h16', 'M4 18h10'],
    tool_calling: [
      'M14.7 6.3a4 4 0 0 0-5 5L4 17v3h3l5.7-5.7a4 4 0 0 0 5-5l-2.4 2.4-2-2Z'
    ],
    video: ['M4 6h11a3 3 0 0 1 3 3v6a3 3 0 0 1-3 3H4Z', 'm18 10 4-2v8l-4-2']
  }
  return iconMap[normalized] || ['M5 5h14v14H5Z']
}

function featureLabel(value) {
  const labels = {
    attachment: t('llmOps.metaModelManagement.features.attachment'),
    chat: t('llmOps.metaModelManagement.features.chat'),
    image_generation: t('llmOps.metaModelManagement.features.imageGeneration'),
    reasoning: t('llmOps.metaModelManagement.features.reasoning'),
    structured_output: t(
      'llmOps.metaModelManagement.features.structuredOutput'
    ),
    tool_calling: t('llmOps.metaModelManagement.features.toolCalling')
  }
  return labels[value] || value || '-'
}

function compactMetaModelName(item) {
  const name = String(item.name || '').trim()
  const code = String(item.code || '').trim()
  if (!name) return code || '-'
  if (!code) return name
  if (normalizeModelIdentity(name) === normalizeModelIdentity(code)) {
    return code
  }
  return name
}

function metaModelTitle(item) {
  return [item.name, item.code].filter(Boolean).join(' · ')
}

function shouldShowMetaModelCode(item) {
  const code = String(item.code || '').trim()
  return Boolean(code && compactMetaModelName(item) !== code)
}

function normalizeModelIdentity(value) {
  return String(value || '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '')
}

function numberLabel(value) {
  if (!value) return '-'
  return new Intl.NumberFormat('en-US').format(value)
}

function releaseDateLabel(value) {
  if (!value) return '-'
  return String(value).slice(0, 10)
}

function releaseDateTime(value) {
  if (!value) return 0
  const parsed = Date.parse(value)
  return Number.isNaN(parsed) ? 0 : parsed
}

function compactTokenLabel(value) {
  const numeric = Number(value || 0)
  if (!numeric) return '-'
  if (numeric >= 1000000) {
    return `${compactNumber(numeric / 1000000)}M`
  }
  if (numeric >= 1000) {
    return `${compactNumber(numeric / 1000)}K`
  }
  return numberLabel(numeric)
}

function compactNumber(value) {
  if (Number.isInteger(value)) return String(value)
  return value.toFixed(1).replace(/\\.0$/, '')
}

function modalityLabel(value) {
  const labels = {
    text: t('llmOps.metaModelManagement.modality.text'),
    multimodal: t('llmOps.metaModelManagement.modality.multimodal'),
    audio: t('llmOps.metaModelManagement.modality.audio'),
    video: t('llmOps.metaModelManagement.modality.video')
  }
  return labels[value] || value || '-'
}

function statusLabel(value) {
  const labels = {
    active: t('llmOps.metaModelManagement.status.active'),
    deprecated: t('llmOps.metaModelManagement.status.deprecated'),
    unknown: t('llmOps.metaModelManagement.status.unknown')
  }
  return (
    labels[value] || value || t('llmOps.metaModelManagement.status.unknown')
  )
}

function statusTone(value) {
  const tones = {
    active: 'ok',
    deprecated: 'warn',
    unknown: 'muted'
  }
  return tones[value] || 'muted'
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

.toolbar-copy {
  @apply min-w-0 flex-1;
}

.drawer-entry-grid {
  @apply grid gap-4 xl:grid-cols-2;
}

.drawer-entry-card {
  @apply rounded-2xl border border-slate-200 bg-white p-5 shadow-sm;
}

.source-summary-strip {
  @apply grid gap-px overflow-hidden rounded-lg border border-slate-200 bg-slate-200 shadow-sm sm:grid-cols-3;
}

.source-summary-item {
  @apply flex min-w-0 items-center gap-3 bg-white px-4 py-3;
}

.table-toolbar {
  @apply flex flex-col gap-3 border-b border-slate-200 bg-white px-4 py-3 sm:flex-row sm:items-center sm:justify-between;
}

.meta-library-toolbar {
  @apply flex flex-col gap-3 border-b border-slate-200 bg-white px-4 py-3 2xl:flex-row 2xl:items-start 2xl:justify-between;
}

.meta-toolbar-actions {
  @apply flex flex-wrap items-center gap-2 2xl:justify-end;
}

.meta-toolbar-search {
  @apply min-w-[14rem] sm:w-64 xl:w-56 2xl:w-64;
}

.meta-drawer {
  @apply h-full overflow-y-auto bg-white shadow-2xl;
}

.vendor-drawer {
  width: min(100%, 36rem);
}

.library-drawer {
  width: min(100%, 78rem);
}

.drawer-header {
  @apply sticky top-0 z-10 flex flex-col gap-4 border-b border-slate-200 bg-white px-5 py-4 xl:flex-row xl:items-start xl:justify-between;
}

.drawer-eyebrow {
  @apply text-xs font-semibold uppercase tracking-[0.18em] text-indigo-600;
}

.drawer-title {
  @apply mt-2 text-xl font-semibold text-slate-900;
}

.drawer-desc {
  @apply mt-1 text-sm leading-6 text-slate-500;
}

.drawer-header-actions {
  @apply flex flex-wrap items-center gap-2;
}

.drawer-body {
  @apply space-y-5 px-5 py-5;
}

.drawer-filter-bar {
  @apply flex flex-wrap items-center gap-2;
}

.drawer-search {
  @apply min-w-[16rem] sm:w-72;
}

.drawer-result-note {
  @apply ml-auto whitespace-nowrap text-xs font-medium text-slate-500;
}

.vendor-search {
  @apply min-w-[10rem] sm:w-44;
}

.vendor-toolbar-summary {
  @apply flex flex-wrap items-center gap-2 sm:justify-end;
}

.empty-state {
  @apply flex flex-col items-center gap-3 px-4 py-10 text-center;
}

.empty-title {
  @apply text-sm font-semibold text-slate-900;
}

.empty-copy {
  @apply max-w-xl text-sm leading-6 text-slate-500;
}

.sync-action-icon {
  @apply h-4 w-4;
}

.sync-action-icon.is-spinning {
  animation: meta-sync-spin 0.9s linear infinite;
}

@keyframes meta-sync-spin {
  from {
    transform: rotate(0deg);
  }

  to {
    transform: rotate(360deg);
  }
}

.summary-pill {
  @apply inline-flex h-9 items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 text-xs font-medium text-slate-500;
}

.summary-pill.wide {
  @apply max-w-full;
}

.summary-pill span {
  @apply whitespace-nowrap;
}

.summary-pill strong {
  @apply min-w-0 truncate font-mono text-xs font-semibold text-slate-800;
}

.data-table {
  @apply w-full min-w-[980px] table-fixed divide-y divide-slate-200;
}

.data-table tbody {
  @apply divide-y divide-slate-100 bg-white;
}

.data-table tr {
  @apply hover:bg-slate-50;
}

.table-head {
  @apply whitespace-nowrap bg-slate-50 px-4 py-3 text-center text-xs font-semibold uppercase tracking-wide text-slate-500;
}

.table-cell {
  @apply min-w-0 px-4 py-3 align-top text-sm text-slate-600;
}

.meta-model-table .table-cell {
  @apply text-center align-middle;
}

.meta-model-table .model-col {
  width: 26%;
}

.meta-model-table .capability-col {
  width: 32%;
}

.meta-model-table .context-col {
  width: 14%;
}

.meta-model-table .release-col {
  width: 14%;
}

.meta-model-table .status-col {
  width: 10%;
}

.control-field {
  @apply h-9 rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-700 outline-none transition placeholder:text-slate-400 focus:border-indigo-300 focus:ring-4 focus:ring-indigo-50;
}

.control-select :deep(.compact-select-trigger) {
  @apply h-9 rounded-lg border-slate-200 px-3 text-sm text-slate-700;
}

.btn-primary {
  @apply inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60;
}

.btn-secondary {
  @apply inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60;
}

.pagination-bar {
  @apply flex flex-col gap-3 border-t border-slate-200 bg-white px-4 py-3 sm:flex-row sm:items-center sm:justify-between;
}

.pagination-btn {
  @apply min-w-20 justify-center;
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

.vendor-list {
  @apply divide-y divide-slate-100;
}

.vendor-list-header {
  @apply grid grid-cols-[minmax(10rem,1fr)_7rem_6rem] items-center gap-3 bg-slate-50 px-4 py-2.5 text-center text-xs font-semibold uppercase tracking-wide text-slate-500;
}

.vendor-list-header span:first-child {
  @apply text-left;
}

.vendor-row {
  @apply grid w-full grid-cols-[minmax(10rem,1fr)_7rem_6rem] items-center gap-3 px-4 py-3 text-left transition hover:bg-slate-50;
}

.vendor-row.active {
  @apply bg-indigo-50;
}

.vendor-row-static {
  @apply cursor-default hover:bg-white;
}

.vendor-name-cell {
  @apply flex min-w-0 items-center gap-3;
}

.vendor-drawer-title-row {
  @apply flex min-w-0 items-center gap-2;
}

.metric-pair {
  @apply flex justify-end gap-4;
}

.metric-stack {
  @apply min-w-0 text-center;
}

.metric-value {
  @apply font-mono text-sm font-semibold tabular-nums text-slate-900;
}

.metric-label {
  @apply mt-1 text-[11px] font-medium uppercase text-slate-400;
}

.meta-model-main {
  @apply mx-auto grid max-w-[14rem] min-w-0 justify-items-center gap-1 text-center;
}

.meta-model-name {
  @apply max-w-full truncate text-sm font-semibold leading-5 text-slate-900;
}

.meta-model-code {
  @apply max-w-full truncate font-mono text-[11px] leading-4 text-slate-400;
}

.meta-model-capabilities {
  @apply mx-auto flex min-w-0 max-w-full justify-center overflow-hidden;
}

.capability-icon-list {
  @apply inline-flex max-w-full flex-nowrap items-center justify-center gap-1.5 overflow-hidden whitespace-nowrap;
}

.capability-icon-token {
  @apply inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-slate-200 bg-slate-50 text-slate-500;
}

.capability-icon-token.primary {
  @apply border-indigo-100 bg-indigo-50 text-indigo-600;
}

.capability-icon-token.default {
  @apply border-slate-200 bg-slate-50 text-slate-500;
}

.capability-icon {
  @apply h-4 w-4 shrink-0;
}

.meta-model-context {
  @apply mx-auto min-w-0 text-center;
}

.meta-model-count {
  @apply min-w-[8rem];
}

.meta-model-status {
  @apply mx-auto flex min-w-0 justify-center;
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
