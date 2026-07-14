import { computed } from 'vue'

export function useChannelModelSelection({
  baseAvailableModels,
  fuzzyScore,
  metaModelDisplayName,
  metaModelForSourceModel,
  metaModelIdentityKey,
  metaModelVendorKey,
  metaModelVendorName,
  modalityLabel,
  modelOptionSearchText,
  modelSearch,
  modelSourceCategory,
  normalizeSearch,
  providerModelDescription,
  providerPriceSummary,
  purchaseSourceLabel,
  selectedModelKeys,
  selectedProviderByModelKey,
  selectedVendorKey,
  sourceCategoryBadge,
  t
}) {
  const translate = typeof t === 'function' ? t : (key) => key

  const candidateMetaModelGroups = computed(() => {
    const groups = new Map()
    baseAvailableModels.value.forEach((model) => {
      const metaModel = metaModelForSourceModel(model)
      if (!metaModel) return

      const key = metaModelIdentityKey(metaModel)
      const group = groups.get(key) || {
        key,
        metaModel,
        name: metaModelDisplayName(metaModel),
        code: metaModel.code || model.meta_model_code || '',
        ownerCode: metaModel.owner_code || model.meta_model_owner_code || '',
        ownerName: metaModel.owner_name || model.meta_model_owner_name || '',
        modality: metaModel.modality || model.modality,
        modalities: new Set(),
        models: []
      }
      group.models.push(model)
      const modality = metaModel.modality || model.modality
      if (modality) {
        group.modalities.add(modality)
      }
      group.providerCount = uniqueProviderModelsForGroup(group).length
      groups.set(key, group)
    })
    return Array.from(groups.values())
      .map((group) => ({
        ...group,
        modalitySummary: Array.from(group.modalities)
          .map((modality) => modalityLabel(modality))
          .join(' / ')
      }))
      .sort((left, right) => left.name.localeCompare(right.name))
  })

  const vendorOptions = computed(() => {
    const vendors = new Map()
    candidateMetaModelGroups.value.forEach((group) => {
      const key = metaModelVendorKey(group)
      const vendor = vendors.get(key) || {
        label: metaModelVendorName(group),
        value: key,
        count: 0
      }
      vendor.count += 1
      vendors.set(key, vendor)
    })
    return Array.from(vendors.values())
      .map((vendor) => ({
        label: vendor.label,
        value: vendor.value,
        description: translate('llmOps.channelModelDrawer.vendorAddableCount', {
          count: vendor.count
        })
      }))
      .sort((left, right) => left.label.localeCompare(right.label))
  })

  const availableModelGroups = computed(() => {
    return candidateMetaModelGroups.value.filter(
      (group) =>
        !selectedVendorKey.value ||
        metaModelVendorKey(group) === selectedVendorKey.value
    )
  })

  const availableModelCount = computed(() => availableModelGroups.value.length)

  const availableModelOptions = computed(() => {
    const keyword = normalizeSearch(modelSearch.value)
    const limit = keyword ? 80 : 24
    return availableModelGroups.value
      .map((option) => {
        const haystack = modelOptionSearchText(option)
        return {
          option,
          score: keyword ? fuzzyScore(haystack, keyword) : 1
        }
      })
      .filter((item) => item.score > 0)
      .sort((left, right) => right.score - left.score)
      .map((item) => item.option)
      .slice(0, limit)
  })

  const selectedModelOptions = computed(() =>
    availableModelGroups.value.filter((option) =>
      selectedModelKeys.value.has(option.key)
    )
  )

  const selectedModelCount = computed(() => selectedModelOptions.value.length)

  const selectedResolvedModels = computed(() =>
    selectedModelOptions.value.map((group) => {
      const selectedProviderId =
        selectedProviderByModelKey.value[group.key] || ''
      const model = group.models.find(
        (item) => String(item.id) === String(selectedProviderId)
      )
      return {
        group,
        model: model || null,
        options: providerOptionsForModelGroup(group)
      }
    })
  )

  const selectedResolvedCount = computed(
    () => selectedResolvedModels.value.filter((item) => item.model).length
  )

  const selectedCostModel = computed(() => {
    const selected = selectedResolvedModels.value.find((item) => item.model)
    return selected?.model || selectedModelOptions.value[0]?.models?.[0] || null
  })

  const canAddSelectedModels = computed(
    () =>
      selectedModelCount.value > 0 &&
      selectedResolvedCount.value === selectedModelCount.value
  )

  function providerOptionsForModelGroup(group) {
    if (!group) return []
    return uniqueProviderModelsForGroup(group)
      .slice()
      .sort((left, right) =>
        purchaseSourceLabel(left).localeCompare(purchaseSourceLabel(right))
      )
      .map((model) => ({
        label: purchaseSourceLabel(model),
        value: model.id,
        description: providerModelDescription(model),
        badge: sourceCategoryBadge(modelSourceCategory(model)),
        searchText: [
          model.provider_name,
          model.provider_code,
          model.source_name,
          modelSourceCategory(model),
          model.currency
        ].join(' ')
      }))
  }

  function uniqueProviderModelsForGroup(group) {
    if (!group?.models?.length) return []
    const modelsByUpstream = new Map()
    group.models.forEach((model) => {
      const key = providerOptionIdentityKey(model)
      const current = modelsByUpstream.get(key)
      if (
        !current ||
        providerOptionScore(model) > providerOptionScore(current)
      ) {
        modelsByUpstream.set(key, model)
      }
    })
    return Array.from(modelsByUpstream.values())
  }

  function providerOptionIdentityKey(model) {
    const sourceId = String(model?.source || '').trim()
    if (sourceId) return `source:${sourceId}`
    return `model:${model?.id || model?.code || model?.name || ''}`
  }

  function providerOptionScore(model) {
    return providerPriceSummary(model).length
  }

  function isModelSelected(key) {
    return selectedModelKeys.value.has(key)
  }

  function toggleModelSelection(modelOption) {
    const next = new Set(selectedModelKeys.value)
    if (next.has(modelOption.key)) {
      next.delete(modelOption.key)
      removeSelectedProvider(modelOption.key)
    } else {
      next.add(modelOption.key)
      ensureDefaultProvider(modelOption)
    }
    selectedModelKeys.value = next
  }

  function selectVisibleModels() {
    const next = new Set(selectedModelKeys.value)
    availableModelOptions.value.forEach((modelOption) => {
      next.add(modelOption.key)
      ensureDefaultProvider(modelOption)
    })
    selectedModelKeys.value = next
  }

  function clearSelectedModels() {
    selectedModelKeys.value = new Set()
    selectedProviderByModelKey.value = {}
  }

  function ensureDefaultProvider(group) {
    if (selectedProviderByModelKey.value[group.key]) return
    const options = uniqueProviderModelsForGroup(group)
    if (options.length !== 1) return
    selectBatchPriceSourceModel(group.key, options[0].id)
  }

  function removeSelectedProvider(key) {
    const next = { ...selectedProviderByModelKey.value }
    delete next[key]
    selectedProviderByModelKey.value = next
  }

  function selectBatchPriceSourceModel(key, value) {
    selectedProviderByModelKey.value = {
      ...selectedProviderByModelKey.value,
      [key]: value
    }
  }

  return {
    availableModelCount,
    availableModelGroups,
    availableModelOptions,
    canAddSelectedModels,
    candidateMetaModelGroups,
    clearSelectedModels,
    isModelSelected,
    providerOptionsForModelGroup,
    selectBatchPriceSourceModel,
    selectVisibleModels,
    selectedCostModel,
    selectedModelCount,
    selectedModelOptions,
    selectedResolvedCount,
    selectedResolvedModels,
    toggleModelSelection,
    uniqueProviderModelsForGroup,
    vendorOptions
  }
}
