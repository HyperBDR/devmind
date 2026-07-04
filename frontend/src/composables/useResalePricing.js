import {
  averageMarginRate,
  isMarginAutoApprovable,
  referenceRetailPrice,
  RESALE_PRICE_DIMENSION_SPECS
} from '@/utils/resalePricing'

export function useResalePricing({
  currencyLabel,
  currencySymbol,
  getMarketAvg,
  globalPricing,
  platformCurrencyLabel,
  props,
  selectedPlatformAutoApproveLimit,
  selectedPlatformFeeRate,
  selectedPlatformLabel,
  selectedPlatformServiceFeeRate,
  t,
  workflowAutoApproveEnabled
}) {
  const priceMetricConfigs = Object.fromEntries(
    RESALE_PRICE_DIMENSION_SPECS.map((item) => [
      item.key,
      {
        label: item.label,
        shortLabel: item.shortLabel,
        priceField: item.workspacePriceField,
        priceTextField: item.workspacePriceTextField,
        costRawField: item.workspaceCostField,
        costTextField: item.workspaceCostTextField,
        marketKey: item.marketKey,
        itemDimension: item.itemDimension
      }
    ])
  )

  function convertCurrencyAmount(amount, sourceCurrency, targetCurrency) {
    if (amount === null || amount === undefined || amount === '') return null
    const source = String(sourceCurrency || '').toUpperCase()
    const target = String(targetCurrency || '').toUpperCase()
    const num = Number(amount)
    if (!Number.isFinite(num) || !source || !target) return null
    if (source === target) return num
    const rate = Number(globalPricing.value.exchangeRate || 0)
    if (!Number.isFinite(rate) || rate <= 0) return null
    if (source === 'USD' && target === 'CNY') return num * rate
    if (source === 'CNY' && target === 'USD') return num / rate
    return null
  }

  function convertToDisplay(amount, currency) {
    return convertCurrencyAmount(amount, currency || 'USD', currencyLabel.value)
  }

  function normalizeDiscountRatio(value) {
    const ratio = Number(value)
    if (!Number.isFinite(ratio) || ratio <= 0) return 1
    return ratio
  }

  function basePriceFromRatio(price, ratio) {
    const priceValue = Number(price)
    const ratioValue = normalizeDiscountRatio(ratio)
    if (!Number.isFinite(priceValue)) return null
    return priceValue / ratioValue
  }

  function marginFromListingPrices(row, priceIn, priceOut, priceCacheIn) {
    const margin = averageMarginRate(
      [
        { price: priceIn, cost: row.costInRaw },
        { price: priceOut, cost: row.costOutRaw },
        { price: priceCacheIn, cost: row.costCacheInRaw }
      ].filter(Boolean)
    )
    return normalizeMargin(margin ?? 20)
  }

  function marginFromRowPrices(row, patch = {}) {
    return marginFromListingPrices(
      row,
      patch.priceInRaw ?? row.priceInRaw,
      patch.priceOutRaw ?? row.priceOutRaw,
      patch.priceCacheInRaw ?? row.priceCacheInRaw
    )
  }

  function normalizeMargin(value) {
    const margin = Number(value)
    if (!Number.isFinite(margin)) return 0
    return Number(margin.toFixed(1))
  }

  function referenceMarginFloor() {
    const feeRate = Number(selectedPlatformFeeRate.value)
    const serviceFeeRate = Number(selectedPlatformServiceFeeRate.value)
    const fee = Number.isFinite(feeRate) && feeRate > 0 ? feeRate : 0
    const service =
      Number.isFinite(serviceFeeRate) && serviceFeeRate > 0 ? serviceFeeRate : 0
    return normalizeMargin((fee + service) * 100)
  }

  function clampMarginToReference(value) {
    return Math.max(normalizeMargin(value), referenceMarginFloor())
  }

  function priceFromMargin(cost, margin) {
    const costValue = Number(cost) || 0
    const marginValue = Number(margin) || 0
    return formatEditablePrice(costValue * (1 + marginValue / 100))
  }

  function pricePatchForMargin(row, margin, options = {}) {
    const shouldClamp = options.clampToReference !== false
    const nextMargin = shouldClamp
      ? clampMarginToReference(margin)
      : normalizeMargin(margin)
    const patch = {
      margin: nextMargin,
      priceInRaw: priceFromMargin(row.costInRaw, nextMargin),
      priceOutRaw: priceFromMargin(row.costOutRaw, nextMargin)
    }
    patch.priceCacheInRaw = priceFromMargin(row.costCacheInRaw, nextMargin)
    return patch
  }

  function formatCredit(price) {
    const amount = Number(price)
    const rate = Number(globalPricing.value.creditRatio) || 0
    if (!Number.isFinite(amount) || rate <= 0) return '0'
    const converted = convertCurrencyAmount(
      amount,
      currencyLabel.value,
      props.pointConversion?.currency || platformCurrencyLabel.value
    )
    if (converted === null) return '-'
    return formatRoundedPoints(converted * rate)
  }

  function formatRoundedPoints(value) {
    const points = Number(value)
    if (!Number.isFinite(points)) return '0'
    const mode = props.pointConversion?.rounding_mode || 'half_up'
    if (mode === 'up') return String(Math.ceil(points))
    if (mode === 'down') return String(Math.floor(points))
    return String(Math.round(points))
  }

  function formatReadonlyNumber(value, digits) {
    const num = Number(value)
    if (!Number.isFinite(num)) return '-'
    return num.toFixed(digits).replace(/\.?0+$/, '')
  }

  function formatMoneyAmount(value) {
    const num = Number(value)
    if (!Number.isFinite(num)) return '-'
    return `${currencySymbol.value}${num.toFixed(4)}`
  }

  function formatEditablePrice(value) {
    const amount = Number(value)
    if (!Number.isFinite(amount)) return 0
    return Number(amount.toFixed(2))
  }

  function editablePriceInputText(value) {
    if (value === null || value === undefined) return ''
    if (typeof value === 'string') return value
    const amount = Number(value)
    if (!Number.isFinite(amount)) return ''
    return amount.toFixed(2)
  }

  function formatMinimumPrice(value) {
    const amount = Number(value)
    if (!Number.isFinite(amount)) return 0
    return Number((Math.ceil(amount * 100) / 100).toFixed(2))
  }

  function formatDiscount(value) {
    const ratio = normalizeDiscountRatio(value)
    return `${(ratio * 100).toFixed(1).replace(/\.0$/, '')}%`
  }

  function formatPercent(value) {
    const num = Number(value)
    if (!Number.isFinite(num)) return '-'
    return `${num.toFixed(1).replace(/\.0$/, '')}%`
  }

  function formatRatioPercent(value) {
    const num = Number(value)
    if (!Number.isFinite(num)) return '-'
    return `${(num * 100).toFixed(2).replace(/\.?0+$/, '')}%`
  }

  function referencePriceForCost(cost) {
    return referenceRetailPrice(cost, {
      feeRate: selectedPlatformFeeRate.value,
      serviceFeeRate: selectedPlatformServiceFeeRate.value
    })
  }

  function referencePriceText(value) {
    const amount = Number(value)
    if (!Number.isFinite(amount)) return '-'
    return amount.toFixed(2)
  }

  function referencePriceTitle(dimension) {
    return t('llmOps.publishingWorkspace.pricing.referenceTitle', {
      serviceFee: formatRatioPercent(selectedPlatformServiceFeeRate.value),
      commission: formatRatioPercent(selectedPlatformFeeRate.value),
      reference:
        currencySymbol.value + referencePriceText(dimension.referencePriceRaw)
    })
  }

  function isBelowReferencePrice(price, referencePrice) {
    if (price === null || price === undefined || price === '') return false
    const priceValue = Number(price)
    const referenceValue = Number(referencePrice)
    if (!Number.isFinite(priceValue) || !Number.isFinite(referenceValue)) {
      return false
    }
    return priceValue + 0.000001 < referenceValue
  }

  function rowHasBelowReferencePrice(row) {
    return priceDimensions(row).some((dimension) =>
      isBelowReferencePrice(dimension.priceRaw, dimension.referencePriceRaw)
    )
  }

  function autoApproveStatus(margin) {
    if (!workflowAutoApproveEnabled.value) {
      return {
        ok: true,
        label: '免审路径已关闭'
      }
    }
    if (selectedPlatformAutoApproveLimit.value === null) {
      return {
        ok: true,
        label: t('llmOps.publishingWorkspace.margin.noAutoApprove')
      }
    }
    const isAllowed = isMarginAutoApprovable(
      margin,
      selectedPlatformAutoApproveLimit.value
    )
    if (isAllowed === null) {
      return {
        ok: true,
        label: t('llmOps.publishingWorkspace.margin.autoApproveInactive')
      }
    }
    if (isAllowed) {
      return {
        ok: true,
        label: t('llmOps.publishingWorkspace.margin.withinAutoApprove', {
          value: formatPercent(selectedPlatformAutoApproveLimit.value)
        })
      }
    }
    return {
      ok: false,
      label: t('llmOps.publishingWorkspace.margin.aboveAutoApprove', {
        value: formatPercent(selectedPlatformAutoApproveLimit.value)
      })
    }
  }

  function costFormulaParts(row, key) {
    if (key === 'cache') {
      return {
        baseCost: row.baseCostCacheInRaw,
        discount: row.discountCacheIn,
        cost: row.costCacheInRaw
      }
    }
    const isInput = key === 'input'
    return {
      baseCost: isInput ? row.baseCostInRaw : row.baseCostOutRaw,
      discount: isInput ? row.discountIn : row.discountOut,
      cost: isInput ? row.costInRaw : row.costOutRaw
    }
  }

  function costFormulaText(row, key) {
    const parts = costFormulaParts(row, key)
    return `${formatMoneyAmount(parts.baseCost)} × ${formatDiscount(
      parts.discount
    )} = ${formatMoneyAmount(parts.cost)}`
  }

  function costFormulaTitle(row, key) {
    return t('llmOps.publishingWorkspace.pricing.costFormulaTitle', {
      formula: costFormulaText(row, key)
    })
  }

  function marketAverageText(avg) {
    const value = Number(avg)
    if (!Number.isFinite(value) || value <= 0) return '-'
    return `${currencySymbol.value}${value.toFixed(2)}`
  }

  function priceDiffText(price, avg) {
    const p = Number(price)
    const a = Number(avg)
    if (!Number.isFinite(p) || !Number.isFinite(a) || a <= 0) {
      return t('llmOps.publishingWorkspace.pricing.noBenchmark')
    }
    const diff = p - a
    const pct = Math.abs((diff / a) * 100).toFixed(1)
    if (diff < -0.00001) {
      return t('llmOps.publishingWorkspace.pricing.lowerThanAverage', {
        pct
      })
    }
    if (diff > 0.00001) {
      return t('llmOps.publishingWorkspace.pricing.higherThanAverage', {
        pct
      })
    }
    return t('llmOps.publishingWorkspace.pricing.sameAsAverage')
  }

  function priceDiffAmountText(price, avg) {
    const p = Number(price)
    const a = Number(avg)
    if (!Number.isFinite(p) || !Number.isFinite(a) || a <= 0) return ''
    const diff = p - a
    const prefix = diff > 0 ? '+' : diff < 0 ? '-' : ''
    return `${prefix}${currencySymbol.value}${Math.abs(diff).toFixed(2)}`
  }

  function priceDiffClass(price, avg) {
    const p = Number(price)
    const a = Number(avg)
    if (!Number.isFinite(p) || !Number.isFinite(a) || a === 0) {
      return 'text-slate-400'
    }
    if (p < a) return 'text-emerald-600'
    if (p > a) return 'text-amber-600'
    return 'text-slate-500'
  }

  function priceSpecForItemDimension(dimension) {
    return RESALE_PRICE_DIMENSION_SPECS.find(
      (spec) => spec.itemDimension === dimension
    )
  }

  function addMarketSample(samples, value, currency) {
    const converted = convertToDisplay(value, currency)
    if (converted === null || converted <= 0) return
    samples.push(converted)
  }

  function averageMarketSamples(samples) {
    if (!samples.length) return 0
    const sum = samples.reduce((total, value) => total + value, 0)
    return Number((sum / samples.length).toFixed(4))
  }

  function priceDimensions(row) {
    const marketAvg = getMarketAvg()
    return ['input', 'output', 'cache'].map((key) => {
      const config = priceMetricConfigs[key]
      const referencePrice = formatMinimumPrice(
        referencePriceForCost(row[config.costRawField])
      )
      return {
        key,
        label: config.label,
        shortLabel: config.shortLabel,
        priceRaw: row[config.priceField],
        priceText: row[config.priceTextField],
        costRaw: row[config.costRawField],
        costText: row[config.costTextField],
        marketAverage: marketAvg[config.marketKey] || 0,
        referencePriceRaw: referencePrice,
        referencePriceText: referencePriceText(referencePrice)
      }
    })
  }

  function marketMarginRefsFor(row) {
    const margins = priceDimensions(row)
      .map((dimension) => {
        const marketPrice = Number(dimension.marketAverage)
        const cost = Number(dimension.costRaw)
        if (
          !Number.isFinite(marketPrice) ||
          !Number.isFinite(cost) ||
          marketPrice <= 0 ||
          cost <= 0
        ) {
          return null
        }
        return ((marketPrice - cost) / cost) * 100
      })
      .filter((value) => value !== null)
    if (!margins.length) return []
    const average =
      margins.reduce((total, value) => total + value, 0) / margins.length
    return [
      {
        source: t('llmOps.publishingWorkspace.pricing.marketAverage'),
        price: Number(average.toFixed(2))
      }
    ]
  }

  function marginAxisRangeFor(row) {
    const current = Number(row.margin)
    const floor = referenceMarginFloor()
    const approveLimit = Number(selectedPlatformAutoApproveLimit.value)
    const limit =
      Number.isFinite(approveLimit) && approveLimit > floor
        ? approveLimit
        : Math.max(floor + 20, Number.isFinite(current) ? current : floor)
    return {
      min: floor,
      max: limit
    }
  }

  function marginPolicyTooltip(type) {
    const isMin = type === 'min'
    const floor = referenceMarginFloor()
    const approveLimit = Number(selectedPlatformAutoApproveLimit.value)
    return {
      title: isMin
        ? t('llmOps.publishingWorkspace.margin.minTitle')
        : t('llmOps.publishingWorkspace.margin.autoApproveTitle'),
      source: isMin
        ? t('llmOps.publishingWorkspace.margin.minSource')
        : t('llmOps.publishingWorkspace.margin.autoApproveSource'),
      rows: isMin
        ? [
            {
              label: t('llmOps.publishingWorkspace.margin.platformFloor'),
              value: formatPercent(floor),
              source: t('llmOps.publishingWorkspace.margin.feeBreakdown', {
                serviceFee: formatRatioPercent(
                  selectedPlatformServiceFeeRate.value
                ),
                commission: formatRatioPercent(selectedPlatformFeeRate.value)
              })
            }
          ]
        : [
            {
              label: t('llmOps.publishingWorkspace.margin.autoApproveLimit'),
              value: Number.isFinite(approveLimit)
                ? formatPercent(approveLimit)
                : t('llmOps.publishingWorkspace.fallback.notConfigured'),
              source: selectedPlatformLabel.value
            }
          ]
    }
  }

  return {
    addMarketSample,
    autoApproveStatus,
    averageMarketSamples,
    basePriceFromRatio,
    convertCurrencyAmount,
    convertToDisplay,
    costFormulaText,
    costFormulaTitle,
    editablePriceInputText,
    formatCredit,
    formatEditablePrice,
    formatPercent,
    formatReadonlyNumber,
    isBelowReferencePrice,
    marginAxisRangeFor,
    marginFromListingPrices,
    marginFromRowPrices,
    marginPolicyTooltip,
    marketAverageText,
    marketMarginRefsFor,
    normalizeDiscountRatio,
    normalizeMargin,
    priceDiffAmountText,
    priceDiffClass,
    priceDiffText,
    priceDimensions,
    priceFromMargin,
    pricePatchForMargin,
    priceSpecForItemDimension,
    referencePriceTitle,
    rowHasBelowReferencePrice
  }
}
