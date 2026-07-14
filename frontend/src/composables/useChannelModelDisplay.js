export function normalizeSearch(value) {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '')
}

export function useChannelModelDisplay({
  hasKnownSourceCategory,
  metaModelByCode,
  metaModelById,
  modalityLabel,
  modelSourceCategory,
  sourceCategoryLabel,
  t
}) {
  const translate = typeof t === 'function' ? t : (key) => key

  function metaModelForSourceModel(model) {
    const metaId = String(model?.meta_model || '').trim()
    if (metaId && metaModelById.value.has(metaId)) {
      return metaModelById.value.get(metaId)
    }
    const metaCode = normalizeSearch(model?.meta_model_code || '')
    if (metaCode && metaModelByCode.value.has(metaCode)) {
      return metaModelByCode.value.get(metaCode)
    }
    return null
  }

  function metaModelIdentityKey(metaModel) {
    const id = String(metaModel?.id || '').trim()
    if (id) return id
    return normalizeSearch(metaModel?.code || metaModel?.name || '')
  }

  function metaModelVendorKey(group) {
    return normalizeSearch(group.ownerCode || group.ownerName || 'unknown')
  }

  function metaModelVendorName(group) {
    return (
      group.ownerName ||
      group.ownerCode ||
      translate('llmOps.channelModelDrawer.unassignedVendor')
    )
  }

  function stripModelNamespace(value) {
    const text = String(value || '').trim()
    if (!text.includes('/')) return text
    return text.split('/').pop() || text
  }

  function metaModelDisplayName(metaModel) {
    return (
      stripModelNamespace(metaModel?.name) ||
      stripModelNamespace(metaModel?.code) ||
      ''
    )
  }

  function modelMetaIdentityKey(model) {
    return normalizeSearch(
      model.meta_model || model.meta_model_code || model.code || model.name
    )
  }

  function modelDisplayName(model) {
    return (
      stripModelNamespace(model?.meta_model_name) ||
      stripModelNamespace(model?.name) ||
      stripModelNamespace(model?.code) ||
      ''
    )
  }

  function modelOptionSearchText(option) {
    return normalizeSearch(
      [
        option.name,
        option.code,
        option.modality,
        option.modalitySummary,
        option.models.map((model) => model.modality).join(' '),
        option.models.map((model) => model.provider_name).join(' '),
        option.models.map((model) => model.provider_code).join(' '),
        option.models.map((model) => model.source_name).join(' '),
        option.models.map((model) => modelSourceCategory(model)).join(' '),
        modalityLabel(option.modality)
      ]
        .filter(Boolean)
        .join(' ')
    )
  }

  function providerModelDescription(model) {
    return [
      hasKnownSourceCategory(modelSourceCategory(model))
        ? sourceCategoryLabel(modelSourceCategory(model))
        : null,
      model.currency || translate('llmOps.channelModelDrawer.defaultCurrency')
    ]
      .filter(Boolean)
      .join(' · ')
  }

  function modelOptionMeta(option) {
    const parts = []
    if (normalizeSearch(option.code) !== normalizeSearch(option.name)) {
      parts.push(option.code)
    }
    parts.push(
      translate('llmOps.channelModelDrawer.upstreamSourceCount', {
        count: option.providerCount
      })
    )
    return parts.filter(Boolean).join(' · ')
  }

  function channelModelSubtitle(row) {
    const model = row?.model || {}
    const name = String(modelDisplayName(model) || '').trim()
    const code = String(model.meta_model_code || model.code || '').trim()
    if (code && code !== name) return code
    return [
      model.source_name || model.provider_name,
      model.code && model.code !== code ? model.code : ''
    ]
      .filter(Boolean)
      .join(' · ')
  }

  function fuzzyScore(haystack, keyword) {
    if (!keyword) return 1
    if (haystack.includes(keyword)) {
      return 1000 - haystack.indexOf(keyword)
    }
    let haystackIndex = 0
    let score = 0
    for (const char of keyword) {
      const foundIndex = haystack.indexOf(char, haystackIndex)
      if (foundIndex === -1) return 0
      score += Math.max(1, 80 - (foundIndex - haystackIndex))
      haystackIndex = foundIndex + 1
    }
    return score
  }

  return {
    channelModelSubtitle,
    fuzzyScore,
    metaModelDisplayName,
    metaModelForSourceModel,
    metaModelIdentityKey,
    metaModelVendorKey,
    metaModelVendorName,
    modelDisplayName,
    modelMetaIdentityKey,
    modelOptionMeta,
    modelOptionSearchText,
    providerModelDescription
  }
}
