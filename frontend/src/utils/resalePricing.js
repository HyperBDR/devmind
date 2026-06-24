export const RESALE_PRICE_DIMENSION_SPECS = [
  {
    key: 'input',
    label: 'Input',
    shortLabel: 'In',
    retailField: 'retail_input_price_per_million',
    costField: 'input_price_per_million',
    workspacePriceField: 'priceInRaw',
    workspacePriceTextField: 'priceIn',
    workspaceCostField: 'costInRaw',
    workspaceCostTextField: 'costIn',
    marketKey: 'in',
    itemDimension: 'text_input'
  },
  {
    key: 'output',
    label: 'Output',
    shortLabel: 'Out',
    retailField: 'retail_output_price_per_million',
    costField: 'output_price_per_million',
    workspacePriceField: 'priceOutRaw',
    workspacePriceTextField: 'priceOut',
    workspaceCostField: 'costOutRaw',
    workspaceCostTextField: 'costOut',
    marketKey: 'out',
    itemDimension: 'text_output'
  },
  {
    key: 'cache',
    label: 'Cached',
    shortLabel: 'Cached',
    retailField: 'retail_cache_input_price_per_million',
    costField: 'cache_input_price_per_million',
    workspacePriceField: 'priceCacheInRaw',
    workspacePriceTextField: 'priceCacheIn',
    workspaceCostField: 'costCacheInRaw',
    workspaceCostTextField: 'costCacheIn',
    marketKey: 'cacheIn',
    itemDimension: 'cache_input'
  }
]

export function marginRateFromPrice(price, cost) {
  const priceValue = Number(price)
  const costValue = Number(cost)
  if (
    !Number.isFinite(priceValue) ||
    !Number.isFinite(costValue) ||
    costValue <= 0
  ) {
    return null
  }
  return Number((((priceValue - costValue) / costValue) * 100).toFixed(2))
}

export function averageMarginRate(pairs = []) {
  const rates = pairs
    .map(({ price, cost }) => marginRateFromPrice(price, cost))
    .filter((value) => value !== null)
  if (!rates.length) return null
  return Number(
    (rates.reduce((sum, value) => sum + value, 0) / rates.length).toFixed(2)
  )
}

export function referenceRetailPrice(
  cost,
  {
    feeRate = 0,
    serviceFeeRate = 0
  } = {}
) {
  const costValue = Number(cost)
  const feeRateValue = Number(feeRate)
  const serviceFeeRateValue = Number(serviceFeeRate)
  if (
    !Number.isFinite(costValue) ||
    !Number.isFinite(feeRateValue) ||
    !Number.isFinite(serviceFeeRateValue) ||
    costValue < 0 ||
    feeRateValue < 0 ||
    serviceFeeRateValue < 0
  ) {
    return null
  }
  return Number(
    (costValue * (1 + serviceFeeRateValue + feeRateValue)).toFixed(4)
  )
}

export function isMarginAutoApprovable(margin, maxMarginRate) {
  const marginValue = Number(margin)
  const limitValue = Number(maxMarginRate)
  if (!Number.isFinite(marginValue) || !Number.isFinite(limitValue)) {
    return null
  }
  return marginValue <= limitValue
}
