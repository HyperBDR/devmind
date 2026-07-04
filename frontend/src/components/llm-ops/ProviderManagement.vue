<template>
  <section class="provider-management space-y-5">
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
          <h3 class="panel-title">
            {{ t('llmOps.providerManagement.title') }}
          </h3>
        </div>
        <div class="provider-toolbar-actions">
          <button
            class="btn-secondary btn-action-sync"
            type="button"
            :disabled="syncingAllSources || !hasSyncablePriceSources"
            @click="syncAllPriceSources"
          >
            <svg
              class="source-primary-icon"
              aria-hidden="true"
              :class="{ 'is-spinning': syncingAllSources }"
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
            {{
              syncingAllSources
                ? t('llmOps.providerManagement.actions.submitting')
                : t('llmOps.providerManagement.actions.syncAllPrices')
            }}
          </button>
          <button
            class="btn-primary source-primary-button btn-action-create"
            type="button"
            @click="showPriceSourceModal = true"
          >
            <svg
              class="source-primary-icon"
              aria-hidden="true"
              fill="none"
              stroke="currentColor"
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              viewBox="0 0 24 24"
            >
              <path d="M12 5v14" />
              <path d="M5 12h14" />
            </svg>
            {{ t('llmOps.providerManagement.actions.createSource') }}
          </button>
        </div>
      </div>

      <div class="table-toolbar border-t border-slate-100">
        <div class="grid w-full gap-3 md:grid-cols-[minmax(0,1fr)_10rem_10rem]">
          <input
            v-model="sourceSearch"
            class="field-input"
            :placeholder="
              t('llmOps.providerManagement.filters.searchPlaceholder')
            "
          />
          <select v-model="sourceCategoryFilter" class="field-input">
            <option
              v-for="option in sourceCategoryFilterOptions"
              :key="option.value"
              :value="option.value"
            >
              {{ option.label }}
            </option>
          </select>
          <select v-model="sourceStatusFilter" class="field-input">
            <option
              v-for="option in sourceStatusFilterOptions"
              :key="option.value"
              :value="option.value"
            >
              {{ option.label }}
            </option>
          </select>
        </div>
      </div>

      <div class="overflow-hidden">
        <table class="data-table provider-table">
          <colgroup>
            <col class="source-name-col" />
            <col class="source-type-col" />
            <col class="source-model-col" />
            <col class="source-status-col" />
            <col class="source-action-col" />
          </colgroup>
          <thead>
            <tr>
              <th class="table-head">
                {{ t('llmOps.providerManagement.table.source') }}
              </th>
              <th class="table-head">
                {{ t('llmOps.providerManagement.table.type') }}
              </th>
              <th class="table-head">
                {{ t('llmOps.providerManagement.table.metaModels') }}
              </th>
              <th class="table-head">
                {{ t('llmOps.providerManagement.table.status') }}
              </th>
              <th class="table-head">
                {{ t('llmOps.providerManagement.table.actions') }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="provider in filteredSourceProviderRows"
              :key="provider.id"
              class="cursor-pointer"
              @click="openSourceDetail(provider)"
            >
              <td class="table-cell">
                <p class="truncate font-medium text-slate-900">
                  {{ provider.name }}
                </p>
                <p class="mt-1 truncate font-mono text-xs text-slate-400">
                  {{ provider.code }}
                </p>
              </td>

              <td class="table-cell">
                <div class="flex justify-center">
                  <span :class="['source-badge', provider.sync_mode_tone]">
                    {{ provider.sync_mode_label }}
                  </span>
                </div>
              </td>

              <td class="table-cell">
                <p class="font-medium text-slate-900">
                  {{
                    t('llmOps.providerManagement.modelsCount', {
                      count: provider.covered_model_count
                    })
                  }}
                </p>
              </td>

              <td class="table-cell">
                <span :class="['status-pill', provider.status_tone]">
                  {{ provider.status_label }}
                </span>
              </td>

              <td class="table-cell">
                <div class="provider-actions">
                  <OperationIconButton
                    icon="edit"
                    label="编辑价格源"
                    :disabled="!provider.primary_source"
                    @click.stop="
                      editSourceFromProvider(provider.primary_source)
                    "
                  />
                  <OperationIconButton
                    v-if="provider.primary_source?.can_manual_entry"
                    icon="manual"
                    label="配置模型价格"
                    tone="primary"
                    @click.stop="
                      openManualEntryFromProvider(provider.primary_source)
                    "
                  />
                  <OperationIconButton
                    v-if="canManualImportSource(provider.primary_source)"
                    icon="import"
                    :label="t('llmOps.providerManagement.actions.bulkImport')"
                    tone="success"
                    @click.stop="
                      openManualImportFromProvider(provider.primary_source)
                    "
                  />
                  <OperationIconButton
                    v-if="provider.primary_source?.can_collect"
                    icon="collect"
                    :label="
                      provider.primary_source?.collect_action_label ||
                      '同步价格'
                    "
                    :disabled="
                      !provider.primary_source.is_enabled ||
                      String(collectingSourceId || '') ===
                        String(provider.primary_source.id)
                    "
                    @click.stop="collectSource(provider.primary_source)"
                  />
                  <OperationIconButton
                    v-if="canOfficialResetSource(provider.primary_source)"
                    icon="reset"
                    label="重置官方价格"
                    tone="danger"
                    @click.stop="
                      openOfficialResetModal(provider.primary_source)
                    "
                  />
                  <OperationIconButton
                    icon="delete"
                    label="删除价格源"
                    tone="danger"
                    :disabled="
                      !provider.primary_source ||
                      String(deletingSourceId || '') ===
                        String(provider.primary_source.id)
                    "
                    @click.stop="deleteSource(provider.primary_source)"
                  />
                </div>
              </td>
            </tr>
            <tr v-if="!filteredSourceProviderRows.length">
              <td class="table-cell text-slate-500" colspan="5">
                {{ t('llmOps.providerManagement.empty') }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <ManualPriceImportModal
      :open="showManualImportModal"
      :providers="providers"
      :sources="manualImportSourceRows"
      :initial-source-id="manualImportSourceId"
      @close="closeManualImportModal"
      @imported="handleManualImported"
    />
    <PriceSourceModal
      :open="showPriceSourceModal || Boolean(editingSource)"
      :source="editingSource"
      @close="closePriceSourceModal"
      @saved="handleSourceSaved"
    />
    <div
      v-if="showOfficialResetModal"
      class="fixed inset-0 z-[60] flex items-center justify-center bg-slate-950/30 px-4 py-6"
      @click.self="closeOfficialResetModal"
    >
      <section class="reset-modal">
        <div class="modal-header">
          <div>
            <p class="modal-eyebrow">Official Price Reset</p>
            <h3 class="modal-title">重置官方价格数据</h3>
            <p class="modal-desc">
              清理历史 seed / 同步写入的官方价格脏数据，并重新同步官方价格。
            </p>
          </div>
          <button
            type="button"
            class="btn-secondary btn-action-cancel"
            :disabled="officialResetBusy"
            @click="closeOfficialResetModal"
          >
            关闭
          </button>
        </div>

        <div class="reset-modal-body">
          <label class="field-group">
            <span class="field-label">清理范围</span>
            <select
              v-model="officialResetScope"
              class="field-input"
              :disabled="officialResetBusy || officialResetScopeLocked"
              @change="officialResetPreview = null"
            >
              <option value="all">全部官方来源</option>
              <option
                v-for="option in officialResetProviderOptions"
                :key="option.code"
                :value="option.code"
              >
                {{ option.label }}
              </option>
            </select>
          </label>

          <div v-if="officialResetPreview" class="reset-preview-grid">
            <div
              v-for="item in officialResetPreviewItems"
              :key="item.label"
              class="reset-preview-item"
            >
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
            </div>
          </div>
          <p v-else class="reset-empty">
            先预览清理范围，再执行重置。平台会保留手工价格、供货商价格和渠道配置。
          </p>

          <div
            v-if="officialResetLegacySources.length"
            class="reset-legacy-list"
          >
            <p>将删除的历史模型级来源</p>
            <div>
              <span v-for="slug in officialResetLegacySources" :key="slug">
                {{ slug }}
              </span>
            </div>
          </div>
        </div>

        <div class="modal-footer">
          <button
            type="button"
            class="btn-secondary"
            :disabled="officialResetBusy"
            @click="previewOfficialReset"
          >
            {{ officialResetPreviewing ? '预览中...' : '预览影响' }}
          </button>
          <button
            type="button"
            class="btn-danger"
            :disabled="!officialResetPreview || officialResetBusy"
            @click="executeOfficialReset"
          >
            {{ officialResetExecuting ? '重置中...' : '确认重置并同步' }}
          </button>
        </div>
      </section>
    </div>
    <ManualPriceEntryModal
      :open="Boolean(priceEntrySource)"
      :source="priceEntrySource"
      :providers="providers"
      :meta-models="priceEntryMetaModels"
      :models="priceEntryModels"
      @close="priceEntrySource = null"
      @saved="handlePriceEntrySaved"
    />
    <SourcePriceDrawer
      :source="selectedProvider?.primary_source || null"
      :models="[]"
      :price-items="selectedProviderPriceItems"
      :deleting="
        String(deletingSourceId || '') ===
        String(selectedProvider?.primary_source?.id || '')
      "
      :loading="selectedProviderLoading"
      :page="selectedProviderPage"
      :page-size="selectedProviderPageSize"
      :total-items="selectedProviderTotal"
      @close="selectedProvider = null"
      @delete="deleteSource"
      @page-change="loadSelectedProviderPriceItems"
    />
  </section>
</template>

<script setup>
import '@/components/llm-ops/providerManagement.css'

import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { llmOpsApi } from '@/api/llmOps'
import { useProviderSourceRows } from '@/composables/useProviderSourceRows'
import { useToast } from '@/composables/useToast'
import ManualPriceImportModal from '@/components/llm-ops/ManualPriceImportModal.vue'
import ManualPriceEntryModal from '@/components/llm-ops/ManualPriceEntryModal.vue'
import PriceSourceModal from '@/components/llm-ops/PriceSourceModal.vue'
import SourcePriceDrawer from '@/components/llm-ops/SourcePriceDrawer.vue'
import OperationIconButton from '@/components/llm-ops/OperationIconButton.vue'
import {
  errorMessage,
  fetchList,
  paginationPayload,
  paginationResults
} from '@/utils/llmOpsPagination'

const props = defineProps({
  providers: {
    type: Array,
    required: true
  },
  metaModels: {
    type: Array,
    default: () => []
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

const emit = defineEmits(['refresh', 'manual-price-saved'])
const { showSuccess, showError } = useToast()
const { t } = useI18n()

// Workspace state
const selectedProvider = ref(null)
const editingSource = ref(null)
const priceEntrySource = ref(null)
const manualImportSourceId = ref('')
const showPriceSourceModal = ref(false)
const showManualImportModal = ref(false)
const showOfficialResetModal = ref(false)
const officialResetScope = ref('all')
const officialResetScopeLocked = ref(false)
const officialResetPreview = ref(null)
const officialResetPreviewing = ref(false)
const officialResetExecuting = ref(false)
const collectingSourceId = ref(null)
const syncingAllSources = ref(false)
const deletingSourceId = ref(null)
const sourceSearch = ref('')
const sourceCategoryFilter = ref('all')
const sourceStatusFilter = ref('all')
const selectedProviderLoading = ref(false)
const selectedProviderPage = ref(1)
const selectedProviderPageSize = ref(50)
const selectedProviderTotal = ref(0)
const selectedProviderPriceItems = ref([])
const localPriceEntryMetaModels = ref([])
const localPriceEntryModels = ref([])

const priceEntryMetaModels = computed(() =>
  props.metaModels.length ? props.metaModels : localPriceEntryMetaModels.value
)

const priceEntryModels = computed(() =>
  props.models.length ? props.models : localPriceEntryModels.value
)

const {
  filteredSourceProviderRows,
  hasSyncablePriceSources,
  manualImportSourceRows,
  officialResetProviderOptions,
  sourceCategoryFilterOptions,
  sourceMetrics,
  sourceStatusFilterOptions,
  canManualImportSource,
  canOfficialResetSource
} = useProviderSourceRows({
  props,
  sourceSearch,
  sourceCategoryFilter,
  sourceStatusFilter,
  t
})

const officialResetBusy = computed(
  () => officialResetPreviewing.value || officialResetExecuting.value
)

const officialResetPreviewItems = computed(() => {
  const stats = officialResetPreview.value?.stats || {}
  return [
    { label: '匹配来源', value: stats.sources_matched || 0 },
    { label: '保留真实来源', value: stats.provider_sources_kept || 0 },
    { label: '删除历史来源', value: stats.legacy_sources_deleted || 0 },
    { label: '重置模型', value: stats.models_reset || 0 },
    { label: '删除价格项', value: stats.price_items_deleted || 0 },
    { label: '删除快照', value: stats.snapshots_deleted || 0 },
    { label: '删除历史', value: stats.history_deleted || 0 },
    { label: '删除运行记录', value: stats.runs_deleted || 0 }
  ]
})

const officialResetLegacySources = computed(
  () => officialResetPreview.value?.stats?.legacy_source_slugs || []
)

// Actions
function handleManualImported() {
  closeManualImportModal()
  emit('refresh')
}

function closeManualImportModal() {
  showManualImportModal.value = false
  manualImportSourceId.value = ''
}

function closePriceSourceModal() {
  showPriceSourceModal.value = false
  editingSource.value = null
}

function handleSourceSaved() {
  closePriceSourceModal()
  emit('refresh')
}

function handlePriceEntrySaved(payload) {
  priceEntrySource.value = null
  emit('manual-price-saved', payload)
}

async function openSourceDetail(provider) {
  selectedProvider.value = provider
  selectedProviderPage.value = 1
  selectedProviderPriceItems.value = []
  selectedProviderTotal.value = 0
  await loadSelectedProviderPriceItems(1)
}

async function loadSelectedProviderPriceItems(
  page = selectedProviderPage.value
) {
  const source = selectedProvider.value?.primary_source
  if (!source?.id) return
  selectedProviderLoading.value = true
  try {
    const response = await llmOpsApi.listModelPriceItems({
      source: source.id,
      is_current: 'true',
      page,
      page_size: selectedProviderPageSize.value
    })
    const payload = paginationPayload(response)
    selectedProviderPriceItems.value = paginationResults(payload)
    selectedProviderTotal.value = Number(
      payload?.count || selectedProviderPriceItems.value.length
    )
    selectedProviderPage.value = page
  } catch (error) {
    selectedProviderPriceItems.value = []
    selectedProviderTotal.value = 0
    showError(errorMessage(error, '加载价格源明细失败。'))
  } finally {
    selectedProviderLoading.value = false
  }
}

function openOfficialResetModal(source = null) {
  const canResetSource = canOfficialResetSource(source)
  officialResetScope.value = canResetSource ? source.provider_code : 'all'
  officialResetScopeLocked.value = canResetSource
  officialResetPreview.value = null
  selectedProvider.value = null
  showOfficialResetModal.value = true
}

function closeOfficialResetModal() {
  if (officialResetBusy.value) return
  showOfficialResetModal.value = false
  officialResetPreview.value = null
  officialResetScopeLocked.value = false
}

function officialResetPayload(extra = {}) {
  const payload =
    officialResetScope.value === 'all'
      ? { all: true }
      : { provider_codes: [officialResetScope.value] }
  return { ...payload, ...extra }
}

async function previewOfficialReset() {
  officialResetPreviewing.value = true
  try {
    const response = await llmOpsApi.previewOfficialPriceReset(
      officialResetPayload()
    )
    officialResetPreview.value = apiPayload(response)
  } catch (error) {
    showError(errorMessage(error, '预览官方价格重置范围失败。'))
  } finally {
    officialResetPreviewing.value = false
  }
}

async function executeOfficialReset() {
  if (!officialResetPreview.value) return
  const confirmed = window.confirm(
    '确认清理所选官方价格数据并重新同步？该操作会删除官方价格项、采集快照和历史模型级来源。'
  )
  if (!confirmed) return

  officialResetExecuting.value = true
  try {
    const response = await llmOpsApi.resetOfficialPrices(
      officialResetPayload({
        confirm: true,
        sync: true
      })
    )
    const payload = apiPayload(response)
    const stats = payload.stats || {}
    showSuccess(
      `官方价格已重置并同步：删除价格项 ${stats.price_items_deleted || 0}，重置模型 ${stats.models_reset || 0}`
    )
    showOfficialResetModal.value = false
    officialResetPreview.value = null
    officialResetScopeLocked.value = false
    emit('refresh')
  } catch (error) {
    showError(errorMessage(error, '重置官方价格失败。'))
  } finally {
    officialResetExecuting.value = false
  }
}

async function openManualEntryFromProvider(source) {
  selectedProvider.value = null
  await ensurePriceEntryCatalogLoaded()
  priceEntrySource.value = source
}

function openManualImportFromProvider(source) {
  if (!canManualImportSource(source)) return
  selectedProvider.value = null
  manualImportSourceId.value = source.id
  showManualImportModal.value = true
}

async function ensurePriceEntryCatalogLoaded() {
  const requests = []
  if (!priceEntryMetaModels.value.length) {
    requests.push(
      fetchList(llmOpsApi.listMetaModels).then((rows) => {
        localPriceEntryMetaModels.value = rows
      })
    )
  }
  if (!priceEntryModels.value.length) {
    requests.push(
      fetchList(llmOpsApi.listModels).then((rows) => {
        localPriceEntryModels.value = rows
      })
    )
  }
  if (!requests.length) return
  try {
    await Promise.all(requests)
  } catch (error) {
    showError(errorMessage(error, '加载手工录价模型目录失败。'))
  }
}

function editSourceFromProvider(source) {
  selectedProvider.value = null
  editingSource.value = source
}

async function collectSource(source) {
  if (!source?.id || !source.can_collect || !source.is_enabled) return
  if (String(collectingSourceId.value || '') === String(source.id)) return
  collectingSourceId.value = source.id
  try {
    const response = await llmOpsApi.collectCollectionSource(source.id)
    const payload = apiPayload(response)
    const taskId = payload.task_id
    showSuccess(
      t('llmOps.providerManagement.messages.syncSubmitted', {
        name: source.name,
        taskId: taskId
          ? t('llmOps.providerManagement.messages.taskId', { taskId })
          : ''
      })
    )
    emit('refresh')
  } catch (error) {
    showError(
      errorMessage(error, t('llmOps.providerManagement.errors.syncFailed'))
    )
  } finally {
    collectingSourceId.value = null
  }
}

async function syncAllPriceSources() {
  if (!hasSyncablePriceSources.value) return
  syncingAllSources.value = true
  try {
    const response = await llmOpsApi.syncAllCollectionSources()
    const payload = apiPayload(response)
    const taskId = payload.task_id
    showSuccess(
      t('llmOps.providerManagement.messages.syncAllSubmitted', {
        taskId: taskId
          ? t('llmOps.providerManagement.messages.taskId', { taskId })
          : ''
      })
    )
    emit('refresh')
  } catch (error) {
    showError(
      errorMessage(error, t('llmOps.providerManagement.errors.syncAllFailed'))
    )
  } finally {
    syncingAllSources.value = false
  }
}

async function deleteSource(source) {
  if (!source?.id) return
  const confirmed = window.confirm(
    t('llmOps.providerManagement.confirm.deleteSource', {
      name: source.name
    })
  )
  if (!confirmed) return

  deletingSourceId.value = source.id
  try {
    await llmOpsApi.deleteCollectionSource(source.id)
    showSuccess(t('llmOps.providerManagement.messages.deleted'))
    emit('refresh')
  } catch (error) {
    showError(
      errorMessage(error, t('llmOps.providerManagement.errors.deleteFailed'))
    )
  } finally {
    deletingSourceId.value = null
  }
}

function apiPayload(response) {
  return response?.data?.data || response?.data || {}
}
</script>
