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
              @click="selectedProvider = provider"
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
      :meta-models="metaModels"
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
      :collecting-source-id="collectingSourceId"
      :deleting-source-id="deletingSourceId"
      @close="selectedProvider = null"
      @manual-entry-source="openManualEntryFromProvider"
      @edit-source="editSourceFromProvider"
      @toggle-source="toggleSource"
      @collect-source="collectSource"
      @delete-source="deleteSource"
    />
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { llmOpsApi } from '@/api/llmOps'
import { useToast } from '@/composables/useToast'
import ManualPriceImportModal from '@/components/llm-ops/ManualPriceImportModal.vue'
import ManualPriceEntryModal from '@/components/llm-ops/ManualPriceEntryModal.vue'
import PriceSourceModal from '@/components/llm-ops/PriceSourceModal.vue'
import ProviderPricingDrawer from '@/components/llm-ops/ProviderPricingDrawer.vue'
import OperationIconButton from '@/components/llm-ops/OperationIconButton.vue'
import {
  canApiSyncPriceSource as canApiSyncSource,
  canCollectPriceSource as canCollectSource,
  canManualEntryPriceSource as canManualEntrySource,
  isEntryPriceSource as isEntrySource,
  isModelsDevPriceSource as isModelsDevSource,
  normalizePriceSourceCategory as businessSourceCategory,
  priceSourceCategory,
  priceSourceCategoryRank as categoryRank,
  priceSourceCollectionMethod as sourceCollectionMethod
} from '@/utils/llmOpsPriceSources'

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

const sourceCategoryFilterOptions = computed(() => [
  {
    value: 'all',
    label: t('llmOps.providerManagement.filters.allTypes')
  },
  {
    value: 'official_provider',
    label: t('llmOps.providerManagement.category.officialProvider')
  },
  {
    value: 'supplier',
    label: t('llmOps.providerManagement.category.supplier')
  },
  {
    value: 'cloud_hosted',
    label: t('llmOps.providerManagement.category.cloudHosted')
  },
  {
    value: 'manual',
    label: t('llmOps.providerManagement.category.internal')
  },
  {
    value: 'unknown',
    label: t('llmOps.providerManagement.category.unknown')
  }
])

const sourceStatusFilterOptions = computed(() => [
  {
    value: 'all',
    label: t('llmOps.providerManagement.filters.allStatuses')
  },
  {
    value: 'active',
    label: t('llmOps.providerManagement.filters.activeOnly')
  },
  {
    value: 'inactive',
    label: t('llmOps.providerManagement.filters.inactiveOnly')
  }
])

// Source rows
const sourceRows = computed(() =>
  props.sources
    .map((source) => buildSourceRow(source))
    .sort((left, right) => {
      const leftRank = categoryRank(left.business_source_category)
      const rightRank = categoryRank(right.business_source_category)
      if (leftRank !== rightRank) return leftRank - rightRank
      return String(left.name).localeCompare(String(right.name))
    })
)

const entrySourceRows = computed(() => sourceRows.value.filter(isEntrySource))

const manualImportSourceRows = computed(() =>
  entrySourceRows.value.filter(canManualImportSource)
)

const sourceProviderRows = computed(() =>
  entrySourceRows.value.map((source) => buildSourceProviderRow(source))
)

// Metrics
const sourceMetrics = computed(() => {
  const coveredMetaModelIds = new Set()
  entrySourceRows.value.forEach((source) => {
    source.meta_model_ids.forEach((id) => coveredMetaModelIds.add(id))
  })

  const official = entrySourceRows.value.filter(
    (source) => source.business_source_category === 'official_provider'
  ).length
  const supplier = entrySourceRows.value.filter(
    (source) => source.business_source_category === 'supplier'
  ).length
  const cloudHosted = entrySourceRows.value.filter(
    (source) => source.business_source_category === 'cloud_hosted'
  ).length
  const internal = entrySourceRows.value.filter(
    (source) => source.business_source_category === 'manual'
  ).length

  return [
    {
      label: t('llmOps.providerManagement.metrics.sources.label'),
      value: entrySourceRows.value.length,
      hint: t('llmOps.providerManagement.metrics.sources.hint')
    },
    {
      label: t('llmOps.providerManagement.metrics.metaModels.label'),
      value: coveredMetaModelIds.size,
      hint: t('llmOps.providerManagement.metrics.metaModels.hint')
    },
    {
      label: t('llmOps.providerManagement.metrics.official.label'),
      value: official,
      hint: t('llmOps.providerManagement.metrics.official.hint')
    },
    {
      label: t('llmOps.providerManagement.metrics.supplierManual.label'),
      value: supplier + cloudHosted + internal,
      hint: t('llmOps.providerManagement.metrics.supplierManual.hint', {
        supplier,
        cloudHosted,
        internal
      })
    }
  ]
})

// Filters
const filteredSourceProviderRows = computed(() => {
  const keyword = sourceSearch.value.trim().toLowerCase()
  return sourceProviderRows.value.filter((provider) => {
    if (sourceStatusFilter.value === 'active' && !provider.filter_is_active) {
      return false
    }
    if (sourceStatusFilter.value === 'inactive' && provider.filter_is_active) {
      return false
    }
    if (
      sourceCategoryFilter.value !== 'all' &&
      !provider.category_keys.includes(sourceCategoryFilter.value)
    ) {
      return false
    }
    if (!keyword) return true
    return provider.search_text.includes(keyword)
  })
})

const hasSyncablePriceSources = computed(() =>
  sourceRows.value.some((source) => source.can_collect && source.is_enabled)
)

// Official reset state
const officialResetProviderOptions = computed(() =>
  sourceRows.value
    .filter(
      (source) =>
        source.source_category === 'official_provider' &&
        source.provider_code &&
        String(source.slug || '') === `${source.provider_code}-official`
    )
    .map((source) => ({
      code: source.provider_code,
      label: source.provider_name || source.name || source.provider_code
    }))
    .sort((left, right) => left.label.localeCompare(right.label))
)

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

// Drawer selection
const selectedProviderModels = computed(() => {
  if (!selectedProvider.value) return []
  return modelsForSourceIds(selectedProviderSourceIds.value)
})

const selectedProviderPriceItems = computed(() => {
  if (!selectedProvider.value) return []
  return priceItemsForSourceIds(selectedProviderSourceIds.value)
})

const selectedProviderSources = computed(() => {
  if (!selectedProvider.value) return []
  const sourceIds = selectedProviderSourceIds.value
  return sourceRows.value.filter((source) => sourceIds.has(String(source.id)))
})

const selectedProviderSourceIds = computed(
  () => new Set(selectedProvider.value?.source_ids || [])
)

function buildSourceProviderRow(source) {
  return {
    id: `source-${source.id}`,
    name: source.name,
    code: source.slug,
    category_keys: [source.business_source_category],
    covered_model_count: source.covered_model_count,
    meta_model_ids: source.meta_model_ids,
    price_item_count: source.price_item_count,
    primary_source: source,
    source_count: 1,
    source_ids: [String(source.id)],
    status_label: source.status_label,
    status_tone: source.status_tone,
    sync_mode_label: source.sync_mode_label,
    sync_mode_tone: source.sync_mode_tone,
    filter_is_active: source.is_enabled,
    search_text: source.search_text
  }
}

function modelsForSourceIds(sourceIds) {
  const pricedModelIds = new Set(
    priceItemsForSourceIds(sourceIds)
      .map((item) => String(item.model || ''))
      .filter(Boolean)
  )
  return props.models.filter(
    (model) =>
      sourceIds.has(String(model.source || '')) ||
      pricedModelIds.has(String(model.id))
  )
}

function priceItemsForSourceIds(sourceIds) {
  return props.priceItems.filter(
    (item) =>
      item.is_current !== false && sourceIds.has(String(item.source || ''))
  )
}

function buildSourceRow(source) {
  const relation = sourceRelation(source)
  const categoryKey = businessSourceCategory(source)
  const category = sourceCategory(categoryKey)
  const currentItems = currentPriceItemsForSource(source.id)
  const latestRun = latestRunForSource(source.id)
  const status = sourceStatus(source, latestRun)
  const syncMode = sourceSyncMode(source)
  const metaModelIds = metaModelIdsForSource(source, currentItems)

  return {
    ...source,
    business_source_category: categoryKey,
    category_label: category.label,
    category_tone: category.tone,
    relation_name: relation.name,
    relation_hint: relation.hint,
    config_summary: sourceConfigSummary(source, relation),
    status_label: status.label,
    status_tone: status.tone,
    status_hint: status.hint,
    sync_mode_label: syncMode.label,
    sync_mode_tone: syncMode.tone,
    meta_model_ids: metaModelIds,
    covered_model_count: metaModelIds.length,
    price_item_count: currentItems.length,
    dimension_count: dimensionCount(currentItems),
    can_collect: canCollectSource(source),
    can_manual_entry: canManualEntrySource(source),
    collect_action_label: collectActionLabel(source),
    collect_mode_label: collectModeLabel(source),
    search_text: buildSourceSearchText(source, relation, category, currentItems)
  }
}

function buildSourceSearchText(source, relation, category, currentItems) {
  return [
    source.name,
    source.slug,
    relation.name,
    relation.hint,
    category.label,
    source.provider_name,
    source.channel_name,
    source.endpoint_url,
    ...currentItems.map((item) =>
      [
        item.meta_model_name,
        item.meta_model_code,
        item.meta_model_owner_name,
        item.meta_model_owner_code,
        item.provider_name,
        item.dimension
      ]
        .filter(Boolean)
        .join(' ')
    )
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase()
}

function currentPriceItemsForSource(sourceId) {
  return props.priceItems.filter(
    (item) =>
      String(item.source) === String(sourceId) && item.is_current !== false
  )
}

function metaModelIdsForSource(source, items) {
  const ids = items
    .map((item) =>
      String(item.meta_model || item.meta_model_code || item.model || '')
    )
    .filter(Boolean)
  if (ids.length) return Array.from(new Set(ids))

  return props.models
    .filter((model) => String(model.source) === String(source.id))
    .map((model) => String(model.meta_model || model.id))
}

function dimensionCount(items) {
  const dimensions = items
    .map((item) => `${item.dimension}:${item.billing_unit || ''}`)
    .filter(Boolean)
  return new Set(dimensions).size
}

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

function openManualEntryFromProvider(source) {
  selectedProvider.value = null
  priceEntrySource.value = source
}

function openManualImportFromProvider(source) {
  if (!canManualImportSource(source)) return
  selectedProvider.value = null
  manualImportSourceId.value = source.id
  showManualImportModal.value = true
}

function editSourceFromProvider(source) {
  selectedProvider.value = null
  editingSource.value = source
}

async function toggleSource(source) {
  if (!source?.id) return
  try {
    await llmOpsApi.updateCollectionSource(source.id, {
      is_enabled: !source.is_enabled
    })
    emit('refresh')
  } catch (error) {
    showError(
      errorMessage(error, t('llmOps.providerManagement.errors.saveFailed'))
    )
  }
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

function sourceCategory(category) {
  return priceSourceCategory(category, {
    official_provider: t('llmOps.providerManagement.category.officialProvider'),
    supplier: t('llmOps.providerManagement.category.supplier'),
    manual: t('llmOps.providerManagement.category.internal'),
    cloud_hosted: t('llmOps.providerManagement.category.cloudHosted'),
    unknown: t('llmOps.providerManagement.category.unknown')
  })
}

function sourceRelation(source) {
  if (source.channel_name) {
    return {
      name: source.channel_name,
      hint: t('llmOps.providerManagement.relation.forwardingChannel')
    }
  }
  if (source.provider_name) {
    return {
      name: source.provider_name,
      hint: t('llmOps.providerManagement.relation.metaProvider')
    }
  }
  return {
    name: t('llmOps.providerManagement.relation.unbound'),
    hint: t('llmOps.providerManagement.relation.needsOwner')
  }
}

function sourceModeLabel(source) {
  const type = source?.source_type || ''
  const method = sourceCollectionMethod(source)

  if (isModelsDevSource(source)) {
    return t('llmOps.providerManagement.sourceMode.aggregateSync')
  }
  if (method === 'auto_collect') {
    return t('llmOps.providerManagement.sourceMode.autoCollect')
  }
  if (method === 'manual_entry') {
    return t('llmOps.providerManagement.sourceMode.manualMaintenance')
  }
  if (method === 'manual_import') {
    return t('llmOps.providerManagement.sourceMode.manualImport')
  }
  if (method === 'api_sync') {
    return t('llmOps.providerManagement.sourceMode.apiSync')
  }

  const labels = {
    agione: 'Agione',
    yunce: t('llmOps.providerManagement.sourceMode.dedicatedCollect'),
    custom: t('llmOps.providerManagement.sourceMode.custom')
  }
  return (
    labels[type] || type || t('llmOps.providerManagement.sourceMode.pending')
  )
}

function sourceConfigSummary(source, relation = sourceRelation(source)) {
  return [relation.hint, sourceModeLabel(source), source.currency]
    .filter(Boolean)
    .join(' · ')
}

function sourceStatus(source, latestRun) {
  if (!source.is_enabled) {
    return {
      label: t('llmOps.providerManagement.sourceStatus.inactive.label'),
      tone: 'muted',
      hint: t('llmOps.providerManagement.sourceStatus.inactive.hint')
    }
  }
  if (isOfficialCollectionPendingSource(source)) {
    return {
      label: t('llmOps.providerManagement.sourceStatus.notAdapted.label'),
      tone: 'warn',
      hint: t('llmOps.providerManagement.sourceStatus.notAdapted.hint')
    }
  }
  if (!canCollectSource(source)) {
    return {
      label: t('llmOps.providerManagement.sourceStatus.pending.label'),
      tone: 'warn',
      hint: collectModeLabel(source)
    }
  }
  if (latestRun?.status === 'failed') {
    return {
      label: t('llmOps.providerManagement.sourceStatus.failed.label'),
      tone: 'danger',
      hint: t('llmOps.providerManagement.sourceStatus.failed.hint')
    }
  }
  if (['running', 'pending', 'processing'].includes(latestRun?.status)) {
    return {
      label: t('llmOps.providerManagement.sourceStatus.syncing.label'),
      tone: 'info',
      hint: t('llmOps.providerManagement.sourceStatus.syncing.hint')
    }
  }
  return {
    label: t('llmOps.providerManagement.sourceStatus.active.label'),
    tone: 'ok',
    hint: t('llmOps.providerManagement.sourceStatus.active.hint')
  }
}

function sourceSyncMode(source) {
  if (canCollectSource(source) || canApiSyncSource(source)) {
    return {
      label: t('llmOps.providerManagement.sourceSyncMode.auto'),
      tone: 'auto'
    }
  }
  if (
    canManualEntrySource(source) ||
    canManualImportSource(source) ||
    ['manual_entry', 'manual_import'].includes(sourceCollectionMethod(source))
  ) {
    return {
      label: t('llmOps.providerManagement.sourceSyncMode.manual'),
      tone: 'manual'
    }
  }
  return {
    label: t('llmOps.providerManagement.sourceSyncMode.pending'),
    tone: 'unknown'
  }
}

function collectActionLabel(source) {
  if (canCollectSource(source)) {
    return t('llmOps.providerManagement.actions.syncPrice')
  }
  return t('llmOps.providerManagement.actions.notSupported')
}

function collectModeLabel(source) {
  if (canCollectSource(source)) {
    if (isModelsDevSource(source)) {
      return 'models.dev'
    }
    return t('llmOps.providerManagement.collectMode.autoCollect')
  }
  if (canManualEntrySource(source)) {
    return t('llmOps.providerManagement.collectMode.manualMaintenance')
  }
  if (canApiSyncSource(source) || source.source_type === 'yunce') {
    return t('llmOps.providerManagement.collectMode.dedicatedCollector')
  }
  return t('llmOps.providerManagement.collectMode.pending')
}

function canManualImportSource(source) {
  return source?.business_source_category === 'manual'
}

function isOfficialCollectionPendingSource(source) {
  return Boolean(
    source?.business_source_category === 'official_provider' &&
      source?.updates_model_prices &&
      !canCollectSource(source)
  )
}

function canOfficialResetSource(source) {
  const providerCode = String(source?.provider_code || '').trim()
  return Boolean(
    providerCode &&
      source?.business_source_category === 'official_provider' &&
      String(source?.slug || '') === `${providerCode}-official` &&
      canCollectSource(source)
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

function errorMessage(error, fallback) {
  return (
    error?.response?.data?.detail ||
    error?.response?.data?.message ||
    error?.message ||
    fallback
  )
}

function apiPayload(response) {
  return response?.data?.data || response?.data || {}
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

.provider-toolbar-actions {
  @apply flex flex-wrap justify-end gap-2;
}

.data-table {
  @apply w-full min-w-full table-fixed divide-y divide-slate-200;
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
  @apply min-w-0 px-4 py-3 text-center text-sm text-slate-600;
}

.table-url-cell {
  @apply max-w-none;
}

.provider-table {
  @apply w-full min-w-0;
}

.provider-actions {
  @apply flex min-w-0 flex-nowrap items-center justify-center gap-1;
}

.source-name-col {
  width: 32%;
}

.source-type-col {
  width: 14%;
}

.source-model-col {
  width: 20%;
}

.source-status-col {
  width: 14%;
}

.source-action-col {
  width: 20%;
}

.field-input {
  @apply w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none transition placeholder:text-slate-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100;
}

.field-group {
  @apply flex min-w-0 flex-col gap-1.5;
}

.field-label {
  @apply text-xs font-medium text-slate-500;
}

.official-source-detail {
  @apply grid gap-3 rounded-lg border border-slate-200 bg-slate-50 p-4 md:grid-cols-2;
}

.official-source-detail div {
  @apply min-w-0;
}

.official-source-detail span {
  @apply block text-xs font-medium text-slate-500;
}

.official-source-detail strong {
  @apply mt-1 block truncate text-sm font-semibold text-slate-900;
}

.official-source-detail strong.break-all {
  @apply whitespace-normal;
}

.official-source-state {
  @apply rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-500;
}

.btn-primary {
  @apply inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60;
}

.source-primary-button {
  @apply h-9 rounded-md border border-indigo-500 bg-indigo-600 px-3.5 text-sm font-semibold shadow-sm shadow-indigo-100 hover:-translate-y-px hover:border-indigo-600 hover:bg-indigo-700 hover:shadow-md hover:shadow-indigo-100;
}

.source-primary-icon {
  @apply h-4 w-4 shrink-0;
}

.source-primary-icon.is-spinning {
  animation: source-sync-spin 0.9s linear infinite;
}

@keyframes source-sync-spin {
  from {
    transform: rotate(0deg);
  }

  to {
    transform: rotate(360deg);
  }
}

.btn-secondary {
  @apply inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60;
}

.btn-danger {
  @apply inline-flex items-center gap-2 rounded-lg border border-rose-100 bg-rose-50 px-3 py-2 text-sm font-medium text-rose-700 transition hover:border-rose-200 hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-60;
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

.source-badge.auto {
  @apply border-emerald-100 bg-emerald-50 text-emerald-700;
}

.source-badge.supplier {
  @apply border-indigo-100 bg-indigo-50 text-indigo-700;
}

.source-badge.cloud {
  @apply border-sky-100 bg-sky-50 text-sky-700;
}

.source-badge.manual {
  @apply border-amber-100 bg-amber-50 text-amber-700;
}

.source-badge.unknown {
  @apply border-slate-200 bg-slate-100 text-slate-600;
}

.reset-modal {
  @apply flex max-h-[calc(100vh-3rem)] w-full max-w-3xl flex-col overflow-hidden rounded-xl bg-white shadow-xl;
}

.modal-header {
  @apply flex items-start justify-between gap-4 border-b border-slate-200 px-5 py-4;
}

.modal-eyebrow {
  @apply text-xs font-semibold uppercase tracking-[0.18em] text-rose-600;
}

.modal-title {
  @apply mt-1 text-lg font-semibold text-slate-900;
}

.modal-desc {
  @apply mt-1 text-sm leading-6 text-slate-500;
}

.reset-modal-body {
  @apply space-y-4 overflow-y-auto px-5 py-4;
}

.reset-preview-grid {
  @apply grid gap-2 sm:grid-cols-2 lg:grid-cols-4;
}

.reset-preview-item {
  @apply rounded-lg border border-slate-200 bg-slate-50 px-3 py-2;
}

.reset-preview-item span {
  @apply block text-xs text-slate-500;
}

.reset-preview-item strong {
  @apply mt-1 block font-mono text-sm text-slate-900;
}

.reset-empty {
  @apply rounded-lg border border-dashed border-slate-200 bg-slate-50 px-3 py-3 text-sm leading-6 text-slate-500;
}

.reset-legacy-list {
  @apply rounded-lg border border-amber-100 bg-amber-50 px-3 py-3;
}

.reset-legacy-list p {
  @apply text-xs font-semibold text-amber-800;
}

.reset-legacy-list div {
  @apply mt-2 flex max-h-32 flex-wrap gap-1.5 overflow-y-auto;
}

.reset-legacy-list span {
  @apply rounded border border-amber-200 bg-white px-1.5 py-1 font-mono text-[11px] text-amber-800;
}

.modal-footer {
  @apply flex flex-wrap justify-end gap-2 border-t border-slate-200 px-5 py-4;
}
</style>
