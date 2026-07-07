import { computed } from 'vue'

export function channelPriceItemKey(channelId, modelId, dimension) {
  return [channelId, modelId, dimension].map(String).join(':')
}

export function useResaleChainRows({
  basePriceFromRatio,
  channelPriceItemsByKey,
  convertToDisplay,
  editablePriceInputText,
  form,
  getChainState,
  modelById,
  normalizeDiscountRatio,
  normalizeMargin,
  priceFromMargin,
  selectedMetaModel,
  selectedMetaModelProcurements,
  supportedSupplierIds,
  t
}) {
  function channelPriceValue(option, modelId, dimension, fallbackValue) {
    const hasSummaryValue =
      fallbackValue !== null &&
      fallbackValue !== undefined &&
      fallbackValue !== ''
    if (hasSummaryValue) {
      return {
        value: fallbackValue,
        currency: option.currency,
        ratio: option.settlement_ratio
      }
    }

    const item = channelPriceItemsByKey.value.get(
      channelPriceItemKey(option.channel_id, modelId, dimension)
    )
    if (item && item.unit_price !== null && item.unit_price !== undefined) {
      return {
        value: item.unit_price,
        currency: item.currency || option.currency,
        ratio: item.settlement_ratio ?? option.settlement_ratio
      }
    }
    return {
      value: fallbackValue,
      currency: option.currency,
      ratio: option.settlement_ratio
    }
  }

  const chainRows = computed(() => {
    if (!form.value.modelId) return []
    const metaModel = selectedMetaModel.value
    if (!metaModel) return []
    const supplierFilter = form.value.supplierId
    const metaVendor = {
      id: metaModel.owner_key,
      code: metaModel.owner_code,
      name: metaModel.owner_name
    }
    return selectedMetaModelProcurements.value
      .flatMap((procurement) => {
        const skuModel = modelById.value.get(String(procurement.model_id))
        return (procurement.options || [])
          .filter((option) => {
            if (!supportedSupplierIds.value.has(String(option.channel_id))) {
              return false
            }
            if (!supplierFilter) return true
            return String(option.channel_id) === String(supplierFilter)
          })
          .map((option) => ({ procurement, skuModel, option }))
      })
      .map(({ procurement, skuModel, option }) => {
        const inputCost = channelPriceValue(
          option,
          procurement.model_id,
          'text_input',
          option.input_price_per_million
        )
        const outputCost = channelPriceValue(
          option,
          procurement.model_id,
          'text_output',
          option.output_price_per_million
        )
        const cacheInputCost = channelPriceValue(
          option,
          procurement.model_id,
          'cache_input',
          option.cache_input_price_per_million
        )
        const inDisplay = convertToDisplay(inputCost.value, inputCost.currency)
        const outDisplay = convertToDisplay(
          outputCost.value,
          outputCost.currency
        )
        const cacheInDisplay = convertToDisplay(
          cacheInputCost.value,
          cacheInputCost.currency
        )
        const baseInDisplay = convertToDisplay(
          option.base_input_price_per_million ??
            basePriceFromRatio(
              inputCost.value,
              option.input_price_per_million_settlement_ratio ?? inputCost.ratio
            ),
          inputCost.currency
        )
        const baseOutDisplay = convertToDisplay(
          option.base_output_price_per_million ??
            basePriceFromRatio(
              outputCost.value,
              option.output_price_per_million_settlement_ratio ??
                outputCost.ratio
            ),
          outputCost.currency
        )
        const baseCacheInDisplay = convertToDisplay(
          option.base_cache_input_price_per_million ??
            basePriceFromRatio(
              cacheInputCost.value,
              option.cache_input_price_per_million_settlement_ratio ??
                cacheInputCost.ratio
            ),
          cacheInputCost.currency
        )
        const discountIn = normalizeDiscountRatio(
          option.input_price_per_million_settlement_ratio ?? inputCost.ratio
        )
        const discountOut = normalizeDiscountRatio(
          option.output_price_per_million_settlement_ratio ?? outputCost.ratio
        )
        const discountCacheIn = normalizeDiscountRatio(
          option.cache_input_price_per_million_settlement_ratio ??
            cacheInputCost.ratio
        )
        const uniqueId = `${option.channel_id}-${procurement.model_id}`
        const state = getChainState(uniqueId)
        const margin = normalizeMargin(
          state.margin ??
            state.marginIn ??
            state.marginOut ??
            state.marginCacheIn ??
            20
        )
        const previewPriceInRaw = priceFromMargin(inDisplay ?? 0, margin)
        const previewPriceOutRaw = priceFromMargin(outDisplay ?? 0, margin)
        const previewPriceCacheInRaw = priceFromMargin(
          cacheInDisplay ?? 0,
          margin
        )
        const priceInRaw = state.priceInRaw ?? previewPriceInRaw
        const priceOutRaw = state.priceOutRaw ?? previewPriceOutRaw
        const priceCacheInRaw = state.priceCacheInRaw ?? previewPriceCacheInRaw
        return {
          uniqueId,
          channelId: option.channel_id,
          channelName: option.channel_name,
          supplierName: option.channel_name,
          source: option.channel_name,
          metaVendorId: metaVendor.id,
          metaVendorName: metaVendor.name || metaVendor.code,
          metaVendorCode: metaVendor.code,
          provider:
            metaVendor.name ||
            t('llmOps.publishingWorkspace.fallback.uncategorized'),
          modelId: procurement.model_id,
          skuModelName:
            skuModel?.name || procurement.model_name || procurement.model_code,
          modelName: metaModel.name || metaModel.code,
          metaModelId: metaModel.id,
          metaModelCode: metaModel.code,
          metaModelFamily: metaModel.family,
          costInRaw: inDisplay ?? 0,
          costOutRaw: outDisplay ?? 0,
          costCacheInRaw: cacheInDisplay ?? 0,
          baseCostInRaw: baseInDisplay ?? inDisplay ?? 0,
          baseCostOutRaw: baseOutDisplay ?? outDisplay ?? 0,
          baseCostCacheInRaw: baseCacheInDisplay ?? cacheInDisplay ?? 0,
          discountIn,
          discountOut,
          discountCacheIn,
          costIn: inDisplay !== null ? inDisplay.toFixed(4) : '-',
          costOut: outDisplay !== null ? outDisplay.toFixed(4) : '-',
          costCacheIn:
            cacheInDisplay !== null ? cacheInDisplay.toFixed(4) : '0.0000',
          hasCacheInput: cacheInDisplay !== null && cacheInDisplay > 0,
          tpmLimit: numberOrNull(option.tpm_limit),
          rpmLimit: numberOrNull(option.rpm_limit),
          latencyMs: numberOrNull(option.latency_ms),
          selected: Boolean(state.selected),
          margin,
          priceInRaw,
          priceOutRaw,
          priceCacheInRaw,
          priceIn: editablePriceInputText(priceInRaw),
          priceOut: editablePriceInputText(priceOutRaw),
          priceCacheIn: editablePriceInputText(priceCacheInRaw),
          isLowest: false
        }
      })
      .filter((row) => Number(row.costInRaw) > 0 && Number(row.costOutRaw) > 0)
      .sort((a, b) => Number(a.costInRaw) - Number(b.costInRaw))
      .map((row, idx) => ({ ...row, isLowest: idx === 0 }))
  })

  const selectedChainRows = computed(() =>
    chainRows.value.filter((row) => row.selected)
  )

  const groupedChainRows = computed(() => {
    const map = new Map()
    chainRows.value.forEach((row) => {
      const supplierKey = row.supplierName || row.source
      if (!map.has(supplierKey)) {
        map.set(supplierKey, {
          supplierName: supplierKey,
          metaVendorName: row.metaVendorName,
          sources: new Map()
        })
      }
      const entry = map.get(supplierKey)
      if (!entry.sources.has(row.source)) {
        entry.sources.set(row.source, { source: row.source, models: [] })
      }
      entry.sources.get(row.source).models.push(row)
    })
    return Array.from(map.values()).map((group) => ({
      supplierName: group.supplierName,
      metaVendorName: group.metaVendorName,
      sources: Array.from(group.sources.values())
    }))
  })

  function numberOrNull(value) {
    if (value === null || value === undefined || value === '') return null
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : null
  }

  return {
    chainRows,
    channelPriceValue,
    groupedChainRows,
    selectedChainRows
  }
}
