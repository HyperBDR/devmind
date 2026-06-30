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
            class="btn-secondary btn-action-import"
            type="button"
            @click="showManualImportModal = true"
          >
            {{ t('llmOps.providerManagement.actions.bulkImport') }}
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
              v-for="provider in filteredProviderRows"
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
                <div class="flex flex-wrap justify-center gap-1.5">
                  <span
                    v-for="category in provider.category_badges"
                    :key="category.key"
                    :class="['source-badge', category.tone]"
                  >
                    {{ category.label }}
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
                    icon="view"
                    :label="t('llmOps.providerManagement.actions.viewModels')"
                    @click.stop="selectedProvider = provider"
                  />
                </div>
              </td>
            </tr>
            <tr v-if="!filteredProviderRows.length">
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
      :sources="entrySourceRows"
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
    <ProviderPricingDrawer
      :provider="selectedProvider"
      :models="selectedProviderModels"
      :sources="selectedProviderSources"
      :price-items="selectedProviderPriceItems"
      :display-currency="displayCurrency"
      :exchange-rate="exchangeRate"
      :collecting-source-id="collectingSourceId"
      @close="selectedProvider = null"
      @view-source="openSourceFromProvider"
      @manual-entry-source="priceEntrySource = $event"
      @edit-source="editingSource = $event"
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
import SourcePriceDrawer from '@/components/llm-ops/SourcePriceDrawer.vue'
import OperationIconButton from '@/components/llm-ops/OperationIconButton.vue'

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
const { t } = useI18n()

const selectedSource = ref(null)
const selectedProvider = ref(null)
const editingSource = ref(null)
const priceEntrySource = ref(null)
const showPriceSourceModal = ref(false)
const showManualImportModal = ref(false)
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
    value: 'manual',
    label: t('llmOps.providerManagement.category.manual')
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

const providerRows = computed(() =>
  props.providers
    .map((provider) => buildProviderRow(provider))
    .filter(
      (provider) =>
        provider.covered_model_count > 0 ||
        provider.source_count > 0 ||
        provider.price_item_count > 0
    )
    .sort((left, right) => String(left.name).localeCompare(String(right.name)))
)

const unboundSourceRows = computed(() => {
  const assignedSourceIds = new Set(
    providerRows.value.flatMap((provider) => provider.source_ids)
  )
  return sourceRows.value.filter(
    (source) => !assignedSourceIds.has(String(source.id))
  )
})

const unboundProviderRow = computed(() => {
  const sources = unboundSourceRows.value.filter(isEntrySource)
  if (!sources.length) return null

  const provider = {
    id: '__unbound_price_sources__',
    code: 'unbound-price-sources',
    name: t('llmOps.providerManagement.unboundSources.name'),
    is_active: sources.some((source) => source.is_enabled),
    is_unbound_sources: true
  }
  const categoryKeys = sourceCategoryKeysForProvider(provider, sources, [])
  const status = providerStatus(provider, sources)

  return {
    ...provider,
    category_badges: categoryKeys.map((key) => ({
      key,
      ...sourceCategory(key)
    })),
    category_keys: categoryKeys,
    covered_model_count: 0,
    meta_model_ids: [],
    price_item_count: 0,
    source_count: sources.length,
    source_ids: sources.map((source) => String(source.id)),
    status_label: status.label,
    status_tone: status.tone,
    filter_is_active: status.filterActive,
    search_text: [
      provider.name,
      provider.code,
      t('llmOps.providerManagement.unboundSources.hint'),
      ...sources.map((source) => source.search_text)
    ]
      .filter(Boolean)
      .join(' ')
      .toLowerCase()
  }
})

const tableProviderRows = computed(() => [
  ...providerRows.value,
  ...(unboundProviderRow.value ? [unboundProviderRow.value] : [])
])

const sourceMetrics = computed(() => {
  const coveredMetaModelIds = new Set()
  providerRows.value.forEach((provider) => {
    provider.meta_model_ids.forEach((id) => coveredMetaModelIds.add(id))
  })

  const official = entrySourceRows.value.filter(
    (source) => source.business_source_category === 'official_provider'
  ).length
  const supplier = entrySourceRows.value.filter(
    (source) => source.business_source_category === 'supplier'
  ).length
  const manual = entrySourceRows.value.filter(
    (source) => source.business_source_category === 'manual'
  ).length

  return [
    {
      label: t('llmOps.providerManagement.metrics.sources.label'),
      value: providerRows.value.length,
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
      value: supplier + manual,
      hint: t('llmOps.providerManagement.metrics.supplierManual.hint', {
        supplier,
        manual
      })
    }
  ]
})

const filteredProviderRows = computed(() => {
  const keyword = sourceSearch.value.trim().toLowerCase()
  return tableProviderRows.value.filter((provider) => {
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

const selectedProviderModels = computed(() => {
  if (!selectedProvider.value) return []
  if (selectedProvider.value.is_unbound_sources) return []
  return modelsForProvider(selectedProvider.value)
})

const selectedProviderPriceItems = computed(() => {
  if (!selectedProvider.value) return []
  if (selectedProvider.value.is_unbound_sources) return []
  return priceItemsForProvider(selectedProvider.value)
})

const selectedProviderSources = computed(() => {
  if (!selectedProvider.value) return []
  if (selectedProvider.value.is_unbound_sources) {
    return unboundSourceRows.value
  }
  const sourceIds = new Set(
    selectedProviderPriceItems.value
      .map((item) => String(item.source || ''))
      .filter(Boolean)
  )
  return sourceRows.value.filter(
    (source) =>
      sourceMatchesProvider(source, selectedProvider.value) ||
      sourceIds.has(String(source.id))
  )
})

function buildProviderRow(provider) {
  const models = modelsForProvider(provider)
  const priceItems = priceItemsForProvider(provider)
  const sources = sourcesForProvider(provider, priceItems)
  const entrySources = sources.filter(isEntrySource)
  const metaModelIds = metaModelIdsForProvider(models, priceItems)
  const categoryKeys = sourceCategoryKeysForProvider(
    provider,
    entrySources,
    priceItems
  )
  const status = providerStatus(provider, entrySources)

  return {
    ...provider,
    category_badges: categoryKeys.map((key) => ({
      key,
      ...sourceCategory(key)
    })),
    category_keys: categoryKeys,
    covered_model_count: metaModelIds.length,
    meta_model_ids: metaModelIds,
    price_item_count: priceItems.length,
    output_source_count: Math.max(sources.length - entrySources.length, 0),
    source_count: entrySources.length,
    source_ids: sources.map((source) => String(source.id)),
    status_label: status.label,
    status_tone: status.tone,
    filter_is_active: status.filterActive,
    search_text: buildProviderSearchText(provider, models, sources, priceItems)
  }
}

function modelsForProvider(provider) {
  const providerSourceIds = sourceIdsForProvider(provider)
  const pricedModelIds = new Set(
    props.priceItems
      .filter(
        (item) =>
          item.is_current !== false &&
          providerSourceIds.has(String(item.source || ''))
      )
      .map((item) => String(item.model || ''))
      .filter(Boolean)
  )
  return props.models.filter(
    (model) =>
      sourceMatchesProvider(sourceForRecord(model), provider) ||
      pricedModelIds.has(String(model.id))
  )
}

function priceItemsForProvider(provider) {
  const providerSourceIds = sourceIdsForProvider(provider)
  return props.priceItems.filter(
    (item) =>
      item.is_current !== false &&
      providerSourceIds.has(String(item.source || ''))
  )
}

function sourceIdsForProvider(provider) {
  return new Set(
    sourceRows.value
      .filter((source) => sourceMatchesProvider(source, provider))
      .map((source) => String(source.id))
  )
}

function sourceForRecord(record) {
  if (!record?.source) return null
  return sourceRows.value.find(
    (source) => String(source.id) === String(record.source || '')
  )
}

function sourcesForProvider(provider, priceItems) {
  const sourceIds = new Set(
    priceItems.map((item) => String(item.source || '')).filter(Boolean)
  )
  return sourceRows.value.filter(
    (source) =>
      sourceMatchesProvider(source, provider) ||
      sourceIds.has(String(source.id))
  )
}

function sourceMatchesProvider(source, provider) {
  if (!source || !provider) return false
  return (
    String(source.provider || '') === String(provider.id) ||
    String(source.provider_code || '') === String(provider.code)
  )
}

function metaModelIdsForProvider(models, priceItems) {
  const ids = [
    ...models.map((model) => model.meta_model || model.meta_model_code),
    ...priceItems.map((item) => item.meta_model || item.meta_model_code)
  ]
    .map((id) => String(id || ''))
    .filter(Boolean)
  return Array.from(new Set(ids))
}

function sourceCategoryKeysForProvider(provider, sources, priceItems) {
  const sourceKeys = sources
    .filter(
      (source) =>
        provider?.is_unbound_sources || sourceMatchesProvider(source, provider)
    )
    .map((source) => source.business_source_category)
  const keys = [
    ...sourceKeys,
    ...priceItems.map((item) => businessSourceCategory(item))
  ].filter(Boolean)
  const uniqueKeys = Array.from(new Set(keys))
  return uniqueKeys.length
    ? uniqueKeys.sort((left, right) => categoryRank(left) - categoryRank(right))
    : ['unknown']
}

function providerStatus(provider, sources) {
  const hasEnabledSource = sources.some((source) => source.is_enabled)
  if (!provider.is_active || (sources.length > 0 && !hasEnabledSource)) {
    return {
      label: t('llmOps.providerManagement.sourceStatus.inactive.label'),
      tone: 'muted',
      filterActive: false
    }
  }
  if (!sources.length) {
    return {
      label: t('llmOps.providerManagement.sourceStatus.pending.label'),
      tone: 'warn',
      filterActive: true
    }
  }
  return {
    label: t('llmOps.providerManagement.sourceStatus.active.label'),
    tone: 'ok',
    filterActive: true
  }
}

function buildProviderSearchText(provider, models, sources, priceItems) {
  return [
    provider.name,
    provider.code,
    provider.website,
    ...sources.map((source) => source.search_text),
    ...models.map((model) =>
      [
        model.name,
        model.code,
        model.meta_model_name,
        model.meta_model_code,
        model.provider_name,
        model.meta_model_vendor_name
      ]
        .filter(Boolean)
        .join(' ')
    ),
    ...priceItems.map((item) =>
      [
        item.meta_model_name,
        item.meta_model_code,
        item.source_name,
        item.source_channel_name,
        item.source_provider_name
      ]
        .filter(Boolean)
        .join(' ')
    )
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase()
}

function buildSourceRow(source) {
  const relation = sourceRelation(source)
  const categoryKey = businessSourceCategory(source)
  const category = sourceCategory(categoryKey)
  const currentItems = currentPriceItemsForSource(source.id)
  const latestRun = latestRunForSource(source.id)
  const status = sourceStatus(source, latestRun)
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
        item.meta_model_vendor_name,
        item.meta_model_vendor_code,
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

function openSourceFromProvider(source) {
  selectedProvider.value = null
  selectedSource.value = source
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
    if (selectedSource.value?.id === source.id) {
      selectedSource.value = null
    }
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

function businessSourceCategory(source) {
  return (
    source?.business_source_category || source?.source_category || 'unknown'
  )
}

function sourceCategory(category) {
  const labels = {
    official_provider: {
      label: t('llmOps.providerManagement.category.officialProvider'),
      tone: 'official'
    },
    supplier: {
      label: t('llmOps.providerManagement.category.supplier'),
      tone: 'supplier'
    },
    manual: {
      label: t('llmOps.providerManagement.category.manual'),
      tone: 'manual'
    },
    unknown: {
      label: t('llmOps.providerManagement.category.unknown'),
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
      hint: t('llmOps.providerManagement.relation.metaProvider')
    }
  }
  if (source.channel_name) {
    return {
      name: source.channel_name,
      hint: t('llmOps.providerManagement.relation.forwardingChannel')
    }
  }
  return {
    name: t('llmOps.providerManagement.relation.unbound'),
    hint: t('llmOps.providerManagement.relation.needsOwner')
  }
}

function sourceModeLabel(source) {
  const type = source?.source_type || ''
  const category = source?.source_category || ''

  if (isModelsDevSource(source)) {
    return t('llmOps.providerManagement.sourceMode.aggregateSync')
  }
  if (category === 'official_provider') {
    return t('llmOps.providerManagement.sourceMode.autoCollect')
  }
  if (category === 'manual') {
    return t('llmOps.providerManagement.sourceMode.manualMaintenance')
  }
  if (category === 'supplier') {
    return t('llmOps.providerManagement.sourceMode.supplierMaintenance')
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
  if (canManualEntrySource(source)) {
    return {
      label: t('llmOps.providerManagement.sourceStatus.manual.label'),
      tone: 'info',
      hint: t('llmOps.providerManagement.sourceStatus.manual.hint')
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

function canCollectSource(source) {
  return Boolean(
    source.can_collect_prices &&
      source.source_category === 'official_provider' &&
      source.updates_model_prices
  )
}

function isEntrySource(source) {
  if (source?.source_category === 'official_provider') {
    return canCollectSource(source)
  }
  return canManualEntrySource(source)
}

function canManualEntrySource(source) {
  return ['supplier', 'manual', 'unknown'].includes(source.source_category)
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
  if (source.source_type === 'yunce') {
    return t('llmOps.providerManagement.collectMode.dedicatedCollector')
  }
  return t('llmOps.providerManagement.collectMode.pending')
}

function isModelsDevSource(source) {
  return String(source?.endpoint_url || '')
    .toLowerCase()
    .includes('models.dev/api.json')
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
  width: 34%;
}

.source-type-col {
  width: 10%;
}

.source-model-col {
  width: 22%;
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
