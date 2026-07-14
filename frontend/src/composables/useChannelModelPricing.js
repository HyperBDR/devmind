export function useChannelModelPricing({
  customPriceFields,
  normalizeSearch,
  props,
  t
}) {
  const translate = typeof t === 'function' ? t : (key) => key

  function convertCurrencyAmount(value, sourceCurrency = 'USD') {
    if (value === null || value === undefined || value === '') return null
    const source = String(sourceCurrency || '').toUpperCase()
    const target = String(props.displayCurrency || 'CNY').toUpperCase()
    const amount = Number(value)
    if (!Number.isFinite(amount)) return null
    if (source === target) return amount
    if (source === 'USD' && target === 'CNY') {
      return amount * Number(props.exchangeRate || 7.15)
    }
    if (source === 'CNY' && target === 'USD') {
      return amount / Number(props.exchangeRate || 7.15)
    }
    return null
  }

  function convertAmountBetween(value, sourceCurrency, targetCurrency) {
    if (value === null || value === undefined || value === '') return null
    const source = String(sourceCurrency || '').toUpperCase()
    const target = String(targetCurrency || '').toUpperCase()
    const amount = Number(value)
    if (!Number.isFinite(amount) || !source || !target) return null
    if (source === target) return amount
    if (source === 'USD' && target === 'CNY') {
      return amount * Number(props.exchangeRate || 7.15)
    }
    if (source === 'CNY' && target === 'USD') {
      return amount / Number(props.exchangeRate || 7.15)
    }
    return null
  }

  function money(value, currency = 'USD') {
    if (value === null || value === undefined || value === '') return '-'
    const displayValue = convertCurrencyAmount(value, currency)
    if (displayValue === null) {
      return `${currency || 'USD'} ${Number(value).toFixed(4)}`
    }
    return `${props.displayCurrency || 'CNY'} ${displayValue.toFixed(4)}`
  }

  function moneyOrStatus(value, currency = 'USD') {
    if (value === null || value === undefined || value === '') return '-'
    if (Number(value) === 0) {
      return translate('llmOps.channelModelDrawer.missingPrice')
    }
    return money(value, currency)
  }

  function compactCostSummary(row) {
    if (row?.priceItems?.length) {
      return priceSummaryText(
        sortPriceItems(row.priceItems).map((item) => ({
          label: priceItemDisplayLabel(item.dimension),
          value: item.unit_price,
          currency: item.currency
        }))
      )
    }
    const previewItems = draftPricePreview(row?.draft, row?.model)
    if (!previewItems.length) {
      return translate('llmOps.channelModelDrawer.pendingCostGeneration')
    }
    return priceSummaryText(
      previewItems.map((item) => ({
        label: previewPriceLabel(item.label),
        value: item.value,
        currency: item.currency,
        missingReason: item.missingReason || ''
      })),
      row?.model
    )
  }

  function upstreamPriceSummary(model) {
    const rows = providerPriceSummary(model)
    if (!rows.length) return '-'
    return priceSummaryText(rows, model)
  }

  function priceSummaryText(rows, model = null, limit = 3) {
    const items = dedupePriceSummaryRows(rows).slice(0, limit)
    if (!items.length) return '-'
    return items
      .map((item) => `${item.label} ${summaryPriceText(item, model)}`)
      .join(' · ')
  }

  function dedupePriceSummaryRows(rows) {
    const seen = new Set()
    return (rows || []).filter((item) => {
      const key = String(item?.label || '')
        .trim()
        .toLowerCase()
      if (!key || seen.has(key)) return false
      seen.add(key)
      return true
    })
  }

  function batchUpstreamPriceSummary(model) {
    const rows = providerPriceSummary(model)
    if (!rows.length) return '-'
    return batchPriceSummaryText(rows, model)
  }

  function batchPendingDraftPriceSummary(draft, model) {
    const rows = draftPricePreview(draft, model)
    if (!rows.length) return '-'
    return batchPriceSummaryText(
      rows.map((item) => ({
        ...item,
        label: previewPriceLabel(item.label)
      })),
      model
    )
  }

  function batchPriceSummaryText(rows, model) {
    const items = dedupePriceSummaryRows(rows).slice(0, 3)
    if (!items.length) return '-'
    return items
      .map((item) => `${item.label} ${priceNumberText(item, model)}`)
      .join(' · ')
  }

  function performanceSummaryItems(row) {
    const draft = row?.draft || {}
    return [
      {
        label: 'TPM',
        value: draft.tpm_limit || '-'
      },
      {
        label: 'RPM',
        value: draft.rpm_limit || '-'
      },
      {
        label: translate('llmOps.channelModelDrawer.performance.latencyShort'),
        value: draft.latency_ms ? `${draft.latency_ms}ms` : '-'
      }
    ]
  }

  function priceText(item, model) {
    if (!item) return '-'
    if (item.missingReason) return item.missingReason
    if (item.value === null || item.value === undefined || item.value === '') {
      return '-'
    }
    if (Number(item.value) !== 0) {
      return money(item.value, item.currency)
    }
    if (isNotApplicablePrice(item, model)) {
      return translate('llmOps.channelModelDrawer.notApplicable')
    }
    return translate('llmOps.channelModelDrawer.missingPrice')
  }

  function summaryPriceText(item, model) {
    if (!item) return '-'
    if (item.missingReason) return item.missingReason
    if (item.value === null || item.value === undefined || item.value === '') {
      return '-'
    }
    if (Number(item.value) !== 0) {
      return priceNumberText(item, model, 2)
    }
    if (isNotApplicablePrice(item, model)) {
      return translate('llmOps.channelModelDrawer.notApplicable')
    }
    return translate('llmOps.channelModelDrawer.missingPrice')
  }

  function fixedNumber(value, digits = 4) {
    const number = Number(value)
    if (!Number.isFinite(number)) return '-'
    return number.toFixed(digits)
  }

  function priceNumberText(item, model, digits = 4) {
    if (!item) return '-'
    if (item.missingReason) return item.missingReason
    if (item.value === null || item.value === undefined || item.value === '') {
      return '-'
    }
    if (Number(item.value) !== 0) {
      const displayValue = convertCurrencyAmount(item.value, item.currency)
      if (displayValue === null) {
        return fixedNumber(item.value, digits)
      }
      return fixedNumber(displayValue, digits)
    }
    if (isNotApplicablePrice(item, model)) {
      return translate('llmOps.channelModelDrawer.notApplicable')
    }
    return fixedNumber(0, digits)
  }

  function isNotApplicablePrice(item, model) {
    const code = String(model?.code || '').toLowerCase()
    const label = String(item?.label || '').toLowerCase()
    if (
      code.includes('embedding') &&
      (label.includes('out') || label.includes('output'))
    ) {
      return true
    }
    if (
      Number(model?.image_output_price_per_image || 0) > 0 &&
      (label.includes('input') || label.includes('output'))
    ) {
      return true
    }
    return false
  }

  function providerPriceSummary(model) {
    const itemRows = providerPriceItemsForModel(model)
    if (itemRows.length) {
      return compactPriceRows(
        itemRows.map((item) => [
          providerPriceItemLabel(item.dimension),
          item.unit_price,
          item.currency
        ])
      )
    }

    if (model.modality === 'video') {
      return compactPriceRowsWithMissingReason(model, [
        ['Video In', model.video_input_price_per_second, model.currency],
        ['Video Out', model.video_output_price_per_second, model.currency]
      ])
    }
    if (model.modality === 'audio') {
      return compactPriceRowsWithMissingReason(model, [
        ['Audio In', model.audio_input_price_per_second, model.currency],
        ['Audio Out', model.audio_output_price_per_second, model.currency]
      ])
    }
    if (model.image_output_price_per_image) {
      return compactPriceRowsWithMissingReason(model, [
        ['Input', model.input_price_per_million, model.currency],
        ['Output', model.output_price_per_million, model.currency],
        ['Image Out', model.image_output_price_per_image, model.currency]
      ])
    }
    return compactPriceRowsWithMissingReason(model, [
      ['Input', model.input_price_per_million, model.currency],
      ['Output', model.output_price_per_million, model.currency]
    ])
  }

  function providerPriceItemsForModel(model) {
    if (!model) return []
    const exactRows = sortPriceItems(
      props.priceItems.filter(
        (item) =>
          String(item.model) === String(model.id) && item.is_current !== false
      )
    )
    if (exactRows.length) return exactRows
    return fallbackPriceItemsForMetaModel(model)
  }

  function fallbackPriceItemsForMetaModel(model) {
    const metaModelId = String(model?.meta_model || '')
    const metaModelCode = normalizeSearch(model?.meta_model_code || '')
    if (!metaModelId && !metaModelCode) return []

    const rows = props.priceItems.filter((item) => {
      if (item.is_current === false || !hasPositiveUnitPrice(item)) {
        return false
      }
      const itemMetaId = String(item.meta_model || '')
      const itemMetaCode = normalizeSearch(item.meta_model_code || '')
      return (
        (metaModelId && itemMetaId === metaModelId) ||
        (metaModelCode && itemMetaCode === metaModelCode)
      )
    })
    if (!rows.length) return []

    const groups = new Map()
    rows.forEach((item) => {
      const key = String(item.source || item.model || '')
      const group = groups.get(key) || []
      group.push(item)
      groups.set(key, group)
    })

    const bestGroup = Array.from(groups.values()).sort(
      (left, right) => priceItemGroupScore(right) - priceItemGroupScore(left)
    )[0]
    return sortPriceItems(bestGroup || [])
  }

  function hasPositiveUnitPrice(item) {
    const value = Number(item?.unit_price)
    return Number.isFinite(value) && value > 0
  }

  function priceItemGroupScore(rows) {
    if (!rows?.length) return 0
    const first = rows[0] || {}
    const category = String(
      first.business_source_category || first.source_category || ''
    )
    const categoryScore =
      category === 'official_provider' ? 300 : category === 'supplier' ? 200 : 0
    const latestTime = Math.max(
      ...rows
        .map((item) => new Date(item.effective_from || item.updated_at || 0))
        .map((date) => date.getTime())
        .filter(Number.isFinite),
      0
    )
    return categoryScore + rows.length * 10 + latestTime / 100000000000
  }

  function sortPriceItems(items) {
    return items.slice().sort((left, right) => {
      const leftKey = priceDimensionSortKey(left)
      const rightKey = priceDimensionSortKey(right)
      return leftKey.localeCompare(rightKey)
    })
  }

  function priceDimensionSortKey(item) {
    const order = {
      text_input: 10,
      text_output: 20,
      cache_input: 30,
      image_input: 40,
      image_output: 50,
      audio_input: 60,
      audio_output: 70,
      video_input: 80,
      video_output: 90
    }
    const dimension = String(item?.dimension || '')
    const score = order[dimension] ?? 999
    return `${String(score).padStart(3, '0')}-${item?.tier_start || ''}-${dimension}`
  }

  function providerPriceItemLabel(dimension) {
    const labels = {
      text_input: 'Input',
      text_output: 'Output',
      cache_input: 'Cache',
      image_input: 'Image In',
      image_output: 'Image Out',
      audio_input: 'Audio In',
      audio_output: 'Audio Out',
      video_input: 'Video In',
      video_output: 'Video Out'
    }
    return labels[dimension] || dimensionLabel(dimension)
  }

  function priceItemDisplayLabel(dimension) {
    return providerPriceItemLabel(dimension)
  }

  function previewPriceLabel(label) {
    const normalized = String(label || '').trim()
    const labels = {
      [translate('llmOps.channelModelDrawer.priceField.textInputShort')]:
        'Input',
      [translate('llmOps.channelModelDrawer.priceField.textOutputShort')]:
        'Output',
      [translate('llmOps.channelModelDrawer.priceField.audioInputShort')]:
        'Audio In',
      [translate('llmOps.channelModelDrawer.priceField.audioOutputShort')]:
        'Audio Out',
      [translate('llmOps.channelModelDrawer.priceField.videoInputShort')]:
        'Video In',
      [translate('llmOps.channelModelDrawer.priceField.videoOutputShort')]:
        'Video Out'
    }
    return labels[normalized] || normalized || '-'
  }

  function compactPriceRowsWithMissingReason(model, rows) {
    const missingReason = missingPriceReason(model)
    return rows
      .filter(
        ([, value]) => value !== null && value !== undefined && value !== ''
      )
      .map(([label, value, currency]) => ({
        label,
        value,
        currency,
        missingReason: Number(value) === 0 && missingReason ? missingReason : ''
      }))
  }

  function missingPriceReason(model) {
    if (!model) return ''
    if (providerPriceItemsForModel(model).length) return ''
    if (model.last_price_updated_at) return ''
    if (model.source_name || model.source_endpoint_url) {
      return translate('llmOps.channelModelDrawer.sourceNotIngested')
    }
    return ''
  }

  function draftPricePreview(draft, model) {
    if (!model) return []
    const targetCurrency =
      draft.currency || props.channel?.currency || model.currency
    if (draft.price_mode === 'fixed') {
      return fixedPricePreview(draft, model, targetCurrency)
    }
    if (draft.price_mode === 'discount') {
      return discountPricePreview(
        model,
        targetCurrency,
        Number(draft.settlement_ratio || 0)
      )
    }
    return discountPricePreview(
      model,
      targetCurrency,
      Number(props.channel?.settlement_ratio || 1)
    )
  }

  function fixedPricePreview(draft, model, currency) {
    return customPriceFields(model)
      .map((field) => ({
        label: field.shortLabel,
        value: draft[field.key],
        currency
      }))
      .filter((item) => item.value !== '')
  }

  function discountPricePreview(model, currency, ratio) {
    if (!Number.isFinite(ratio) || ratio <= 0) return []
    return providerPriceSummary(model)
      .map((item) => {
        const sourceCurrency = item.currency || model.currency || currency
        const baseAmount = convertAmountBetween(
          item.value,
          sourceCurrency,
          currency
        )
        return {
          label: item.label,
          value: baseAmount === null ? null : baseAmount * ratio,
          currency,
          missingReason: item.missingReason || ''
        }
      })
      .filter((item) => item.value !== null)
  }

  function compactPriceRows(rows) {
    return rows
      .filter(
        ([, value]) => value !== null && value !== undefined && value !== ''
      )
      .map(([label, value, currency]) => ({ label, value, currency }))
  }

  function dimensionLabel(dimension) {
    const labels = {
      text_input: 'Input',
      text_output: 'Output',
      cache_input: 'Cache',
      image_input: 'Image In',
      image_output: 'Image Out',
      audio_input: 'Audio In',
      audio_output: 'Audio Out',
      video_input: 'Video In',
      video_output: 'Video Out'
    }
    return labels[dimension] || dimension || '-'
  }

  function upstreamSourceLabel(model) {
    if (!model) return translate('llmOps.channelModelDrawer.unboundUpstream')
    return (
      model.source_name ||
      model.provider_name ||
      translate('llmOps.channelModelDrawer.unboundUpstream')
    )
  }

  function purchaseSourceLabel(model) {
    if (!model) {
      return translate('llmOps.channelModelDrawer.noUpstreamSelected')
    }
    return upstreamSourceLabel(model)
  }

  function channelRowSourceLabel(row) {
    return (
      row.draft.price_source_name ||
      row.model.price_source_name ||
      purchaseSourceLabel(row.model)
    )
  }

  function modelSourceCategory(model) {
    return (
      model?.business_source_category || model?.source_category || 'unknown'
    )
  }

  function sourceCategoryLabel(category) {
    const labels = {
      official_provider: translate(
        'llmOps.channelModelDrawer.sourceCategory.officialProvider'
      ),
      supplier: translate('llmOps.channelModelDrawer.sourceCategory.supplier'),
      manual: translate('llmOps.channelModelDrawer.sourceCategory.manual'),
      unknown: translate('llmOps.channelModelDrawer.sourceCategory.unknown')
    }
    return (
      labels[category] ||
      translate('llmOps.channelModelDrawer.sourceCategory.unknown')
    )
  }

  function sourceCategoryBadge(category) {
    if (!hasKnownSourceCategory(category)) return ''
    return sourceCategoryLabel(category)
  }

  function hasKnownSourceCategory(category) {
    return ['official_provider', 'supplier', 'manual'].includes(category)
  }

  function sourceTone(category) {
    const tones = {
      official_provider: 'official',
      supplier: 'supplier',
      manual: 'manual',
      unknown: 'unknown'
    }
    return tones[category] || 'unknown'
  }

  function comparisonTone(status) {
    return {
      below_official: 'price-chip-good',
      same_as_official: 'price-chip-neutral',
      above_official: 'price-chip-warn',
      unknown: 'price-chip-muted'
    }[status || 'unknown']
  }

  function comparisonTitle(item) {
    if (item.comparison_status === 'unknown') {
      return translate('llmOps.channelModelDrawer.comparisonUnknown')
    }
    const delta = item.delta_amount || 0
    const percent = item.delta_percent || 0
    return translate('llmOps.channelModelDrawer.comparisonDelta', {
      currency: item.currency,
      delta: Number(delta).toFixed(4),
      percent: Number(percent).toFixed(2)
    })
  }

  function modalityLabel(modality) {
    const labels = {
      text: translate('llmOps.channelModelDrawer.modality.text'),
      audio: translate('llmOps.channelModelDrawer.modality.audio'),
      video: translate('llmOps.channelModelDrawer.modality.video'),
      multimodal: translate('llmOps.channelModelDrawer.modality.multimodal')
    }
    return labels[modality] || modality || '-'
  }

  return {
    batchPendingDraftPriceSummary,
    batchUpstreamPriceSummary,
    channelRowSourceLabel,
    compactCostSummary,
    comparisonTitle,
    comparisonTone,
    convertAmountBetween,
    convertCurrencyAmount,
    dimensionLabel,
    draftPricePreview,
    hasKnownSourceCategory,
    modalityLabel,
    money,
    moneyOrStatus,
    modelSourceCategory,
    performanceSummaryItems,
    priceText,
    providerPriceItemsForModel,
    providerPriceSummary,
    purchaseSourceLabel,
    sortPriceItems,
    sourceCategoryBadge,
    sourceCategoryLabel,
    sourceTone,
    upstreamPriceSummary
  }
}
