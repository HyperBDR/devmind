<template>
  <section class="meta-model-management space-y-5">
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
                    total: drawerTotal,
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
                  <tr v-if="drawerLoading">
                    <td class="table-cell text-slate-500" colspan="5">
                      {{ t('common.loading') }}
                    </td>
                  </tr>
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
                  <tr v-if="!drawerLoading && !vendorMetaRows.length">
                    <td class="table-cell text-slate-500" colspan="5">
                      {{ t('llmOps.metaModelManagement.empty.models') }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-if="drawerTotal" class="pagination-bar">
              <p class="text-xs text-slate-500">
                {{
                  t('llmOps.metaModelManagement.pagination.summary', {
                    total: drawerTotal,
                    current: safeCurrentPage,
                    pages: totalPages
                  })
                }}
              </p>
              <div class="pagination-actions">
                <label class="page-size-control">
                  <span>
                    {{
                      t('llmOps.metaModelManagement.pagination.pageSizeLabel')
                    }}
                  </span>
                  <CompactSelect
                    v-model="pageSize"
                    :options="pageSizeOptions"
                    class-name="control-select page-size-select"
                  />
                </label>
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
import '@/components/llm-ops/metaModelManagement.css'

import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { llmOpsApi } from '@/api/llmOps'
import { useToast } from '@/composables/useToast'
import CompactSelect from '@/components/llm-ops/CompactSelect.vue'
import ProviderIcon from '@/components/llm/ProviderIcon.vue'
import { resolveCanonicalMetaOwner } from '@/utils/llmOpsMeta'
import {
  errorMessage,
  paginationPayload,
  paginationResults
} from '@/utils/llmOpsPagination'

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
const pageSize = ref(10)
const currentPage = ref(1)
const selectedVendorId = ref('')
const showVendorModelsDrawer = ref(false)
const syncingMetaModels = ref(false)
const ownerRows = ref([])
const drawerRows = ref([])
const drawerTotal = ref(0)
const drawerLoading = ref(false)
const ownerSummaryLoading = ref(false)

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

const vendorRows = computed(() => ownerRows.value)

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

const vendorMetaRows = computed(() => drawerRows.value)

const totalPages = computed(() =>
  Math.max(1, Math.ceil(drawerTotal.value / Number(pageSize.value)))
)

const safeCurrentPage = computed(() =>
  Math.min(Math.max(Number(currentPage.value) || 1, 1), totalPages.value)
)

const paginatedVendorMetaRows = computed(() => vendorMetaRows.value)

// resolveCanonicalVendor / canonicalMetaOwnerCode moved to
// frontend/src/utils/llmOpsMeta.js for reuse across the
// immersive publishing workspace and the meta model library.

const metricCards = computed(() => {
  const totalModels = ownerRows.value.reduce(
    (total, row) => total + Number(row.meta_model_count || 0),
    0
  )
  const activeModels = ownerRows.value.reduce(
    (total, row) => total + Number(row.active_model_count || 0),
    0
  )
  return [
    {
      label: t('llmOps.metaModelManagement.metrics.metaModels.label'),
      value: ownerSummaryLoading.value ? '-' : totalModels,
      hint: t('llmOps.metaModelManagement.metrics.metaModels.hint')
    },
    {
      label: t('llmOps.metaModelManagement.metrics.boundVendors.label'),
      value: ownerSummaryLoading.value ? '-' : ownerRows.value.length,
      hint: t('llmOps.metaModelManagement.metrics.boundVendors.hint')
    },
    {
      label: t('llmOps.metaModelManagement.metrics.status.label'),
      value: ownerSummaryLoading.value
        ? '-'
        : `${activeModels}/${Math.max(totalModels - activeModels, 0)}`,
      hint: t('llmOps.metaModelManagement.metrics.status.hint')
    }
  ]
})

const selectedVendorActiveCount = computed(() => {
  if (statusFilter.value === 'active') return drawerTotal.value
  if (statusFilter.value) return 0
  return Number(selectedVendorRow.value?.active_model_count || 0)
})

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
  fetchVendorMetaModels()
}

function closeVendorModelsDrawer() {
  showVendorModelsDrawer.value = false
}

function goToPreviousPage() {
  currentPage.value = Math.max(safeCurrentPage.value - 1, 1)
  fetchVendorMetaModels()
}

function goToNextPage() {
  currentPage.value = Math.min(safeCurrentPage.value + 1, totalPages.value)
  fetchVendorMetaModels()
}

watch([searchKeyword, statusFilter, modalityFilter, pageSize], () => {
  currentPage.value = 1
  if (showVendorModelsDrawer.value) fetchVendorMetaModels()
})

onMounted(() => {
  fetchOwnerSummary()
})

async function fetchOwnerSummary() {
  ownerSummaryLoading.value = true
  try {
    const response = await llmOpsApi.listMetaModelOwnerSummary()
    ownerRows.value = paginationResults(paginationPayload(response))
  } catch (error) {
    showError(
      errorMessage(
        error,
        t('llmOps.metaModelManagement.errors.loadOwnerSummary')
      )
    )
  } finally {
    ownerSummaryLoading.value = false
  }
}

async function fetchVendorMetaModels() {
  if (!selectedVendorId.value) return
  drawerLoading.value = true
  try {
    const response = await llmOpsApi.listMetaModels({
      owner: selectedVendorId.value,
      status: statusFilter.value || undefined,
      modality: modalityFilter.value || undefined,
      search: searchKeyword.value.trim() || undefined,
      ordering: '-release_date',
      page: safeCurrentPage.value,
      page_size: Number(pageSize.value) || 10
    })
    const payload = paginationPayload(response)
    drawerRows.value = paginationResults(payload).map((item) => {
      const canonicalVendor = resolveCanonicalMetaOwner(item, props.providers)
      return {
        ...item,
        owner_key: item.owner_code || canonicalVendor.code,
        owner_code: item.owner_code || canonicalVendor.code,
        owner_name: item.owner_name || canonicalVendor.name
      }
    })
    drawerTotal.value = Number(payload?.count || drawerRows.value.length)
  } catch (error) {
    drawerRows.value = []
    drawerTotal.value = 0
    showError(
      errorMessage(error, t('llmOps.metaModelManagement.errors.loadDetails'))
    )
  } finally {
    drawerLoading.value = false
  }
}

async function syncMetaModels() {
  syncingMetaModels.value = true
  try {
    const response = await llmOpsApi.syncMetaModels()
    const stats = paginationPayload(response)
    showSuccess(
      t('llmOps.metaModelManagement.messages.synced', {
        count: stats.models || 0
      })
    )
    await fetchOwnerSummary()
    if (showVendorModelsDrawer.value) await fetchVendorMetaModels()
    emit('refresh')
  } catch (error) {
    showError(errorMessage(error, t('llmOps.metaModelManagement.errors.sync')))
  } finally {
    syncingMetaModels.value = false
  }
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
</script>
