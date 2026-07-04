import { computed, nextTick, ref } from 'vue'

export function useChannelModelNewDraft({
  applyPriceMode,
  canAddSelectedModels,
  channelCurrency,
  clearSelectedModels,
  draftDefaults,
  drafts,
  emptyNewDraft,
  modelDropdownOpen,
  modelSearch,
  modelSourceCategory,
  percentInputToRatio,
  performanceFields,
  props,
  ratioPercent,
  ratioToPercentInput,
  recentlyAddedModelId,
  selectedResolvedModels
}) {
  const newDraft = ref(emptyNewDraft())

  const currencyOptions = computed(() => [
    {
      label: '使用渠道默认币种',
      value: '',
      description: `保存为 ${channelCurrency.value}`
    },
    { label: 'CNY', value: 'CNY', description: '固定保存为人民币' },
    { label: 'USD', value: 'USD', description: '固定保存为美元' }
  ])

  const newDraftRuleSummary = computed(() => {
    if (newDraft.value.price_mode === 'discount') {
      return `折扣 ${ratioPercent(newDraft.value.settlement_ratio)}`
    }
    if (newDraft.value.price_mode === 'fixed') return '固定成本价'
    return `默认折扣 ${ratioPercent(props.channel?.settlement_ratio, 1)}`
  })

  const newDraftPerformanceSummary = computed(() => {
    const parts = performanceFields.map((field) => {
      const value = newDraft.value[field.key] || '-'
      return `${field.shortLabel} ${value}`
    })
    return parts.join(' · ')
  })

  const newDraftSettlementPercent = computed({
    get() {
      return ratioToPercentInput(newDraft.value.settlement_ratio)
    },
    set(value) {
      newDraft.value.settlement_ratio = percentInputToRatio(value)
    }
  })

  function resetNewDraft() {
    newDraft.value = emptyNewDraft()
  }

  function addSelectedModels() {
    if (!canAddSelectedModels.value) return
    const modelsToAdd = selectedResolvedModels.value
      .map((item) => item.model)
      .filter(Boolean)
    modelsToAdd.forEach((model) => {
      drafts.value[model.id] = buildDraftForModel(model)
      applyPriceMode(drafts.value[model.id])
    })
    recentlyAddedModelId.value = modelsToAdd.at(-1)?.id || null
    resetNewDraft()
    modelSearch.value = ''
    clearSelectedModels()
    modelDropdownOpen.value = false
    nextTick(() => {
      const row = document.querySelector(
        '.recently-added-row, .recently-added-card'
      )
      row?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
    })
  }

  function buildDraftForModel(model) {
    return {
      ...draftDefaults(model, null),
      is_configured: true,
      is_listed: true,
      price_mode: newDraft.value.price_mode,
      price_source: model.source || '',
      price_source_name: model.source_name || '',
      price_source_category: modelSourceCategory(model) || '',
      price_source_endpoint_url: model.source_endpoint_url || '',
      currency: newDraft.value.currency,
      settlement_ratio:
        newDraft.value.price_mode === 'discount'
          ? newDraft.value.settlement_ratio
          : '',
      custom_input_price_per_million:
        newDraft.value.price_mode === 'fixed'
          ? newDraft.value.custom_input_price_per_million
          : '',
      custom_output_price_per_million:
        newDraft.value.price_mode === 'fixed'
          ? newDraft.value.custom_output_price_per_million
          : '',
      custom_audio_input_price_per_second:
        newDraft.value.price_mode === 'fixed'
          ? newDraft.value.custom_audio_input_price_per_second
          : '',
      custom_audio_output_price_per_second:
        newDraft.value.price_mode === 'fixed'
          ? newDraft.value.custom_audio_output_price_per_second
          : '',
      custom_video_input_price_per_second:
        newDraft.value.price_mode === 'fixed'
          ? newDraft.value.custom_video_input_price_per_second
          : '',
      custom_video_output_price_per_second:
        newDraft.value.price_mode === 'fixed'
          ? newDraft.value.custom_video_output_price_per_second
          : '',
      tpm_limit: newDraft.value.tpm_limit,
      rpm_limit: newDraft.value.rpm_limit,
      latency_ms: newDraft.value.latency_ms
    }
  }

  return {
    currencyOptions,
    newDraft,
    newDraftPerformanceSummary,
    newDraftRuleSummary,
    newDraftSettlementPercent,
    addSelectedModels,
    resetNewDraft
  }
}
