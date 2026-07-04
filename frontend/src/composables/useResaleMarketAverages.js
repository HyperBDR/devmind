import { computed } from 'vue'

import { RESALE_PRICE_DIMENSION_SPECS } from '@/utils/resalePricing'

export function useResaleMarketAverages({
  addMarketSample,
  averageMarketSamples,
  channelPriceValue,
  form,
  modelById,
  priceSpecForItemDimension,
  props,
  selectedMetaModelProcurements
}) {
  const selectedMetaModelPriceItems = computed(() => {
    const metaModelId = form.value.modelId
    if (!metaModelId) return []
    return (props.priceItems || []).filter((item) => {
      if (item.source_is_enabled === false) return false
      if (String(item.meta_model || '') === String(metaModelId)) return true
      const model = modelById.value.get(String(item.model || ''))
      return String(model?.meta_model || '') === String(metaModelId)
    })
  })

  const marketAvg = computed(() => {
    const samples = {
      in: [],
      out: [],
      cacheIn: []
    }
    selectedMetaModelPriceItems.value.forEach((item) => {
      const spec = priceSpecForItemDimension(item.dimension)
      if (!spec || item.is_current === false) return
      addMarketSample(samples[spec.marketKey], item.unit_price, item.currency)
    })
    RESALE_PRICE_DIMENSION_SPECS.forEach((spec) => {
      if (samples[spec.marketKey].length) return
      selectedMetaModelProcurements.value.forEach((procurement) => {
        ;(procurement.options || []).forEach((option) => {
          const price = channelPriceValue(
            option,
            procurement.model_id,
            spec.itemDimension,
            option[spec.costField]
          )
          addMarketSample(
            samples[spec.marketKey],
            price.value,
            price.currency || option.currency
          )
        })
      })
    })
    return {
      in: averageMarketSamples(samples.in),
      out: averageMarketSamples(samples.out),
      cacheIn: averageMarketSamples(samples.cacheIn)
    }
  })

  return { marketAvg }
}
