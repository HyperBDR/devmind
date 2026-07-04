import { computed } from 'vue'

export function useChannelModelRows({
  configuredRowsExpanded,
  drafts,
  props,
  search,
  shouldPersist,
  sortPriceItems
}) {
  const managedRows = computed(() => {
    if (!props.channel) return []
    return props.models
      .filter((model) => {
        const draft = drafts.value[model.id]
        return draft?.is_configured || shouldPersist(draft || {})
      })
      .map((model) => ({
        model,
        draft: drafts.value[model.id],
        priceItems: channelPriceItemsForModel(model, drafts.value[model.id])
      }))
  })

  const listedCount = computed(
    () => managedRows.value.filter((row) => row.draft.is_listed).length
  )

  const filteredRows = computed(() => {
    if (!props.channel) return []
    const keyword = search.value.trim().toLowerCase()
    return managedRows.value.filter((row) => {
      const currentModel = row.model
      const haystack = [
        currentModel.name,
        currentModel.code,
        currentModel.meta_model_name,
        currentModel.meta_model_code,
        currentModel.provider_name,
        currentModel.provider_code
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()
      if (keyword && !haystack.includes(keyword)) {
        return false
      }
      return true
    })
  })

  const displayedRows = computed(() => {
    if (configuredRowsExpanded.value) return filteredRows.value
    return filteredRows.value.slice(0, 20)
  })

  const hiddenConfiguredRowCount = computed(() =>
    Math.max(filteredRows.value.length - displayedRows.value.length, 0)
  )

  function channelPriceItemsForModel(model, draft) {
    if (!props.channel || !draft?.id) return []
    return sortPriceItems(
      props.channelPriceItems.filter(
        (item) =>
          String(item.channel) === String(props.channel.id) &&
          String(item.model) === String(model.id) &&
          item.is_current !== false
      )
    )
  }

  return {
    displayedRows,
    filteredRows,
    hiddenConfiguredRowCount,
    listedCount,
    managedRows
  }
}
