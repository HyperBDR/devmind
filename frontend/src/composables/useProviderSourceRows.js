import { computed } from 'vue'
import {
  canApiSyncPriceSource as canApiSyncSource,
  canCollectPriceSource as canCollectSource,
  canManualEntryPriceSource as canManualEntrySource,
  isEntryPriceSource as isEntrySource,
  isModelsDevPriceSource as isModelsDevSource,
  normalizePriceSourceCategory as businessSourceCategory,
  priceSourceCategory,
  priceSourceCategoryRank as categoryRank,
  priceSourceCollectionGroup,
  priceSourceCollectionGroupRank,
  priceSourceCollectionMethod as sourceCollectionMethod,
  priceSourceOwnerType,
  priceSourceOwnerTypeLabel
} from '@/utils/llmOpsPriceSources'

export function useProviderSourceRows({
  props,
  sourceSearch,
  sourceCategoryFilter,
  sourceStatusFilter,
  t
}) {
  const sourceCategoryFilterOptions = computed(() => [
    {
      value: 'all',
      label: t('llmOps.providerManagement.filters.allTypes')
    },
    {
      value: 'auto',
      label: t('llmOps.providerManagement.sourceSyncMode.auto')
    },
    {
      value: 'manual',
      label: t('llmOps.providerManagement.sourceSyncMode.manual')
    },
    {
      value: 'unknown',
      label: t('llmOps.providerManagement.sourceSyncMode.pending')
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
        const leftGroupRank = priceSourceCollectionGroupRank(
          left.collection_group
        )
        const rightGroupRank = priceSourceCollectionGroupRank(
          right.collection_group
        )
        if (leftGroupRank !== rightGroupRank) {
          return leftGroupRank - rightGroupRank
        }
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

  const sourceMetrics = computed(() => {
    const auto = entrySourceRows.value.filter(
      (source) => source.collection_group === 'auto'
    ).length
    const manual = entrySourceRows.value.filter(
      (source) => source.collection_group === 'manual'
    ).length

    return [
      {
        label: t('llmOps.providerManagement.metrics.sources.label'),
        value: entrySourceRows.value.length,
        hint: t('llmOps.providerManagement.metrics.sources.hint')
      },
      {
        label: t('llmOps.providerManagement.metrics.metaModels.label'),
        value: entrySourceRows.value.reduce(
          (total, source) => total + Number(source.covered_model_count || 0),
          0
        ),
        hint: t('llmOps.providerManagement.metrics.metaModels.hint')
      },
      {
        label: t('llmOps.providerManagement.metrics.autoSources.label'),
        value: auto,
        hint: t('llmOps.providerManagement.metrics.autoSources.hint')
      },
      {
        label: t('llmOps.providerManagement.metrics.manualSources.label'),
        value: manual,
        hint: t('llmOps.providerManagement.metrics.manualSources.hint')
      }
    ]
  })

  const filteredSourceProviderRows = computed(() => {
    const keyword = sourceSearch.value.trim().toLowerCase()
    return sourceProviderRows.value.filter((provider) => {
      if (sourceStatusFilter.value === 'active' && !provider.filter_is_active) {
        return false
      }
      if (
        sourceStatusFilter.value === 'inactive' &&
        provider.filter_is_active
      ) {
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

  const officialResetProviderOptions = computed(() =>
    sourceRows.value
      .filter((source) => canOfficialResetSource(source))
      .map((source) => ({
        code: source.provider_code,
        label: source.provider_name || source.name || source.provider_code
      }))
      .sort((left, right) => left.label.localeCompare(right.label))
  )

  function buildSourceProviderRow(source) {
    return {
      id: `source-${source.id}`,
      name: source.name,
      code: source.slug,
      category_keys: [source.collection_group],
      covered_model_count: source.covered_model_count,
      collect_mode_label: source.collect_mode_label,
      collect_mode_tone: source.collect_mode_tone,
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

  function buildSourceRow(source) {
    const relation = sourceRelation(source)
    const categoryKey = businessSourceCategory(source)
    const category = sourceCategory(categoryKey)
    const collectionGroup = priceSourceCollectionGroup(source)
    const ownerType = priceSourceOwnerType(source)
    const ownerLabel = sourceOwnerTypeLabel(ownerType)
    const latestRun = latestRunForSource(source.id)
    const status = sourceStatus(source, latestRun)
    const syncMode = sourceSyncMode(source)
    const modelCount = Number(
      source.current_meta_model_count || source.model_count || 0
    )
    const priceItemCount = Number(
      source.current_price_item_count || source.price_item_count || 0
    )

    return {
      ...source,
      business_source_category: categoryKey,
      category_label: category.label,
      category_tone: category.tone,
      collection_group: collectionGroup,
      source_owner_type: ownerType,
      source_owner_type_label: ownerLabel,
      relation_name: relation.name,
      relation_hint: relation.hint,
      config_summary: sourceConfigSummary(source, relation),
      status_label: status.label,
      status_tone: status.tone,
      status_hint: status.hint,
      sync_mode_label: syncMode.label,
      sync_mode_tone: syncMode.tone,
      meta_model_ids: [],
      covered_model_count: modelCount,
      price_item_count: priceItemCount,
      dimension_count: 0,
      can_collect: canCollectSource(source),
      can_manual_entry: canManualEntrySource(source),
      collect_action_label: collectActionLabel(source),
      collect_mode_label: collectModeLabel(source),
      collect_mode_tone: collectModeTone(source),
      search_text: buildSourceSearchText(source, relation, category, ownerLabel)
    }
  }

  function buildSourceSearchText(source, relation, category, ownerLabel) {
    return [
      source.name,
      source.slug,
      relation.name,
      relation.hint,
      category.label,
      ownerLabel,
      sourceCollectionMethod(source),
      source.provider_name,
      source.channel_name,
      source.endpoint_url
    ]
      .filter(Boolean)
      .join(' ')
      .toLowerCase()
  }

  function sourceCategory(category) {
    return priceSourceCategory(category, {
      official_provider: t(
        'llmOps.providerManagement.category.officialProvider'
      ),
      supplier: t('llmOps.providerManagement.category.supplier'),
      manual: t('llmOps.providerManagement.category.internal'),
      cloud_hosted: t('llmOps.providerManagement.category.cloudHosted'),
      unknown: t('llmOps.providerManagement.category.unknown')
    })
  }

  function sourceOwnerTypeLabel(ownerType) {
    return priceSourceOwnerTypeLabel(ownerType, {
      model_provider_official: t(
        'llmOps.providerManagement.category.officialProvider'
      ),
      cloud_provider_official: t(
        'llmOps.providerManagement.category.cloudHosted'
      ),
      supplier: t('llmOps.providerManagement.category.supplier'),
      internal: t('llmOps.providerManagement.category.internal'),
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
    return [
      relation.hint,
      sourceModeLabel(source),
      sourceOwnerTypeLabel(priceSourceOwnerType(source)),
      source.currency
    ]
      .filter(Boolean)
      .join(' · ')
  }

  function sourceStatus(source, latestRun = null) {
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
      hint: collectModeLabel(source)
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
    return priceSourceCollectionGroup(source) === 'manual'
  }

  function isOfficialCollectionPendingSource(source) {
    const ownerType = priceSourceOwnerType(source)
    return Boolean(
      ['model_provider_official', 'cloud_provider_official'].includes(
        ownerType
      ) &&
        sourceCollectionMethod(source) === 'auto_collect' &&
        source?.updates_model_prices &&
        !canCollectSource(source)
    )
  }

  function canOfficialResetSource(source) {
    const providerCode = String(source?.provider_code || '').trim()
    const ownerType = priceSourceOwnerType(source)
    return Boolean(
      providerCode &&
        ['model_provider_official', 'cloud_provider_official'].includes(
          ownerType
        ) &&
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

  function collectModeTone(source) {
    if (canCollectSource(source)) return 'auto'
    if (canApiSyncSource(source) || source.source_type === 'yunce') {
      return 'api'
    }
    if (canManualEntrySource(source)) return 'manual'
    return 'unknown'
  }

  return {
    filteredSourceProviderRows,
    hasSyncablePriceSources,
    manualImportSourceRows,
    officialResetProviderOptions,
    sourceCategoryFilterOptions,
    sourceMetrics,
    sourceRows,
    sourceStatusFilterOptions,
    canManualImportSource,
    canOfficialResetSource
  }
}
