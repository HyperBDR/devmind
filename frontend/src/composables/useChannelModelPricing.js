export function useChannelModelPricing({
  customPriceFields,
  normalizeSearch,
  props
}) {
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
    if (Number(value) === 0) return '缺价格'
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
    if (!previewItems.length) return '成本待生成'
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
        label: '延迟',
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
      return '不适用'
    }
    return '缺价格'
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
      return '不适用'
    }
    return '缺价格'
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
      return '不适用'
    }
    return fixedNumber(0, digits)
  }

  function isNotApplicablePrice(item, model) {
    const code = String(model?.code || '').toLowerCase()
    const label = String(item?.label || '')
    if (code.includes('embedding') && label.includes('出')) {
      return true
    }
    if (
      Number(model?.image_output_price_per_image || 0) > 0 &&
      (label.includes('文本入') || label.includes('文本出'))
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
    const normalized = String(label || '').replace('预估', '')
    const labels = {
      文入: 'Input',
      文出: 'Output',
      缓存: 'Cache',
      音入: 'Audio In',
      音出: 'Audio Out',
      视入: 'Video In',
      视出: 'Video Out',
      图入: 'Image In',
      图出: 'Image Out',
      文本入: 'Input',
      文本出: 'Output',
      图片出: 'Image Out',
      音频入: 'Audio In',
      音频出: 'Audio Out',
      视频入: 'Video In',
      视频出: 'Video Out'
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
    if (model.source_name || model.source_endpoint_url) return '源未入库'
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
        label: `${field.shortLabel}预估`,
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
          label: `${item.label}预估`,
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
    if (!model) return '未绑定上游'
    return model.source_name || model.provider_name || '未绑定上游'
  }

  function purchaseSourceLabel(model) {
    if (!model) return '未选择渠道上游'
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
      official_provider: '原厂',
      supplier: '供货商',
      manual: '人工',
      unknown: '未标记类型'
    }
    return labels[category] || '未标记类型'
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
      return (
        '已按全局显示货币换算展示；缺少同维度上游基准价时，' +
        '暂无法判断高低。'
      )
    }
    const delta = item.delta_amount || 0
    const percent = item.delta_percent || 0
    return `较上游价格 ${item.currency} ${Number(delta).toFixed(4)} / ${Number(percent).toFixed(2)}%`
  }

  function modalityLabel(modality) {
    const labels = {
      text: '文本',
      audio: '音频',
      video: '视频',
      multimodal: '多模态'
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
