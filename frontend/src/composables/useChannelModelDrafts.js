const customPriceKeys = [
  'custom_input_price_per_million',
  'custom_output_price_per_million',
  'custom_audio_input_price_per_second',
  'custom_audio_output_price_per_second',
  'custom_video_input_price_per_second',
  'custom_video_output_price_per_second'
]

const performanceFields = [
  {
    key: 'tpm_limit',
    label: 'TPM',
    shortLabel: 'TPM',
    placeholder: '每分钟 Token',
    shortPlaceholder: 'Token/min',
    title: '每分钟 Token 上限'
  },
  {
    key: 'rpm_limit',
    label: 'RPM',
    shortLabel: 'RPM',
    placeholder: '每分钟请求',
    shortPlaceholder: 'Req/min',
    title: '每分钟请求上限'
  },
  {
    key: 'latency_ms',
    label: '延迟(ms)',
    shortLabel: '延迟',
    placeholder: '毫秒',
    shortPlaceholder: 'ms',
    title: '渠道平均延迟，单位毫秒'
  }
]

const performanceFieldKeys = performanceFields.map((field) => field.key)

export function useChannelModelDrafts({
  baselineDrafts,
  channelCurrency,
  drafts,
  getChannel,
  getModelSourceCategory
}) {
  function emptyNewDraft() {
    return {
      model: '',
      price_source: '',
      price_source_name: '',
      price_source_category: '',
      price_source_endpoint_url: '',
      is_listed: false,
      price_mode: 'channel_default',
      currency: '',
      settlement_ratio: '',
      custom_input_price_per_million: '',
      custom_output_price_per_million: '',
      custom_audio_input_price_per_second: '',
      custom_audio_output_price_per_second: '',
      custom_video_input_price_per_second: '',
      custom_video_output_price_per_second: '',
      tpm_limit: '',
      rpm_limit: '',
      latency_ms: ''
    }
  }

  function serializeDraft(draft) {
    const normalized = normalizeDraftForMode(draft || {})
    return {
      id: normalized.id || null,
      model: String(normalized.model || ''),
      price_source: String(normalized.price_source || ''),
      price_source_name: normalized.price_source_name || '',
      price_source_category: normalized.price_source_category || '',
      price_source_endpoint_url: normalized.price_source_endpoint_url || '',
      is_configured: Boolean(normalized.is_configured),
      is_listed: Boolean(normalized.is_listed),
      price_mode: normalized.price_mode || 'channel_default',
      currency: String(normalized.currency || '').toUpperCase(),
      settlement_ratio: normalized.settlement_ratio || '',
      custom_input_price_per_million:
        normalized.custom_input_price_per_million || '',
      custom_output_price_per_million:
        normalized.custom_output_price_per_million || '',
      custom_audio_input_price_per_second:
        normalized.custom_audio_input_price_per_second || '',
      custom_audio_output_price_per_second:
        normalized.custom_audio_output_price_per_second || '',
      custom_video_input_price_per_second:
        normalized.custom_video_input_price_per_second || '',
      custom_video_output_price_per_second:
        normalized.custom_video_output_price_per_second || '',
      tpm_limit: normalized.tpm_limit || '',
      rpm_limit: normalized.rpm_limit || '',
      latency_ms: normalized.latency_ms || ''
    }
  }

  function isSerializedConfigured(draft) {
    return Boolean(
      draft?.id || draft?.is_configured || shouldPersist(draft || {})
    )
  }

  function serializedDraftChanged(left, right) {
    return JSON.stringify(left || {}) !== JSON.stringify(right || {})
  }

  function summarizeDraftChanges() {
    const summary = {
      added: 0,
      modified: 0,
      enabled: 0,
      disabled: 0,
      removed: 0
    }
    const modelIds = new Set([
      ...Object.keys(baselineDrafts.value || {}),
      ...Object.keys(drafts.value || {})
    ])
    modelIds.forEach((modelId) => {
      const baseline = baselineDrafts.value[modelId] || {}
      const current = serializeDraft(drafts.value[modelId] || {})
      const wasConfigured = isSerializedConfigured(baseline)
      const isConfigured = isSerializedConfigured(current)

      if (!wasConfigured && isConfigured) {
        summary.added += 1
        return
      }
      if (wasConfigured && !isConfigured) {
        summary.removed += 1
        return
      }
      if (!wasConfigured || !isConfigured) return

      if (Boolean(baseline.is_listed) !== Boolean(current.is_listed)) {
        if (current.is_listed) {
          summary.enabled += 1
        } else {
          summary.disabled += 1
        }
      }

      const baselineWithoutStatus = {
        ...baseline,
        is_listed: Boolean(current.is_listed)
      }
      if (serializedDraftChanged(baselineWithoutStatus, current)) {
        summary.modified += 1
      }
    })
    return summary
  }

  function draftDefaults(model, price) {
    const channel = getChannel()
    return {
      id: price?.id || null,
      channel: channel?.id || '',
      model: model.id,
      price_source: price?.price_source || model.source || '',
      price_source_name: price?.price_source_name || model.source_name || '',
      price_source_category:
        price?.price_source_category || getModelSourceCategory(model) || '',
      price_source_endpoint_url:
        price?.price_source_endpoint_url || model.source_endpoint_url || '',
      is_configured: Boolean(price?.id),
      is_listed: price?.is_listed || false,
      price_mode: priceModeFromDraft(price || {}),
      currency: price?.currency || '',
      settlement_ratio: price?.settlement_ratio || '',
      custom_input_price_per_million:
        price?.custom_input_price_per_million || '',
      custom_output_price_per_million:
        price?.custom_output_price_per_million || '',
      custom_audio_input_price_per_second:
        price?.custom_audio_input_price_per_second || '',
      custom_audio_output_price_per_second:
        price?.custom_audio_output_price_per_second || '',
      custom_video_input_price_per_second:
        price?.custom_video_input_price_per_second || '',
      custom_video_output_price_per_second:
        price?.custom_video_output_price_per_second || '',
      tpm_limit: price?.tpm_limit || '',
      rpm_limit: price?.rpm_limit || '',
      latency_ms: price?.latency_ms || ''
    }
  }

  function ratioPercent(value, fallback = null) {
    const rawValue =
      value === '' || value === null || value === undefined ? fallback : value
    const ratio = Number(rawValue)
    if (!Number.isFinite(ratio)) return '-'
    return `${(ratio * 100).toFixed(1)}%`
  }

  function ratioToPercentInput(value) {
    if (value === '' || value === null || value === undefined) return ''
    const ratio = Number(value)
    if (!Number.isFinite(ratio)) return ''
    return Number((ratio * 100).toFixed(4)).toString()
  }

  function percentInputToRatio(value) {
    if (value === '' || value === null || value === undefined) return ''
    const percent = Number(value)
    if (!Number.isFinite(percent)) return ''
    return String(percent / 100)
  }

  function updateSettlementPercent(draft, value) {
    draft.settlement_ratio = percentInputToRatio(value)
  }

  function priceRuleSummary(row) {
    const channel = getChannel()
    const draft = row?.draft || {}
    if (draft.price_mode === 'fixed') return '固定成本价'
    if (draft.price_mode === 'discount') {
      return `折扣 ${ratioPercent(draft.settlement_ratio)}`
    }
    return `默认折扣 ${ratioPercent(channel?.settlement_ratio, 1)}`
  }

  function costCurrencyTitle(currency) {
    const value = String(currency || '')
      .trim()
      .toUpperCase()
    if (value) {
      return `成本价保存为 ${value}；页面价格按全局显示货币换算。`
    }
    return `成本价跟随渠道结算币种 ${channelCurrency.value} 保存；页面价格按全局显示货币换算。`
  }

  function normalizePayload(payload, nullableFields = []) {
    const clean = { ...payload }
    const nullable = new Set(nullableFields)
    Object.keys(clean).forEach((key) => {
      if (clean[key] === '' && nullable.has(key)) {
        clean[key] = null
      }
    })
    clean.currency = String(clean.currency || '')
      .trim()
      .toUpperCase()
    delete clean.id
    delete clean.is_configured
    delete clean.price_mode
    delete clean.price_source_name
    delete clean.price_source_category
    delete clean.price_source_endpoint_url
    return clean
  }

  function payloadForDraft(draft) {
    const payload = normalizeDraftForMode(draft)
    return normalizePayload(
      {
        ...payload,
        channel: getChannel().id
      },
      [
        'settlement_ratio',
        'custom_input_price_per_million',
        'custom_output_price_per_million',
        'custom_audio_input_price_per_second',
        'custom_audio_output_price_per_second',
        'custom_video_input_price_per_second',
        'custom_video_output_price_per_second',
        ...performanceFieldKeys
      ]
    )
  }

  function shouldPersist(draft) {
    return Boolean(
      draft.id ||
        draft.is_configured ||
        draft.is_listed ||
        draft.settlement_ratio ||
        draft.currency ||
        draft.custom_input_price_per_million ||
        draft.custom_output_price_per_million ||
        draft.custom_audio_input_price_per_second ||
        draft.custom_audio_output_price_per_second ||
        draft.custom_video_input_price_per_second ||
        draft.custom_video_output_price_per_second ||
        performanceFieldKeys.some((key) => draft[key])
    )
  }

  function customPriceFields(model) {
    if (!model) return []
    if (model.modality === 'audio') {
      return [
        {
          key: 'custom_audio_input_price_per_second',
          label: '音频输入 / 秒',
          shortLabel: '音入'
        },
        {
          key: 'custom_audio_output_price_per_second',
          label: '音频输出 / 秒',
          shortLabel: '音出'
        }
      ]
    }
    if (model.modality === 'video') {
      return [
        {
          key: 'custom_video_input_price_per_second',
          label: '视频输入 / 秒',
          shortLabel: '视入'
        },
        {
          key: 'custom_video_output_price_per_second',
          label: '视频输出 / 秒',
          shortLabel: '视出'
        }
      ]
    }
    if (model.image_output_price_per_image && !hasTokenPricing(model)) {
      return []
    }
    return [
      {
        key: 'custom_input_price_per_million',
        label: '文本输入 / 百万 tokens',
        shortLabel: '文入'
      },
      {
        key: 'custom_output_price_per_million',
        label: '文本输出 / 百万 tokens',
        shortLabel: '文出'
      }
    ]
  }

  function hasTokenPricing(model) {
    return (
      Number(model.input_price_per_million || 0) > 0 ||
      Number(model.output_price_per_million || 0) > 0
    )
  }

  function priceModeFromDraft(draft) {
    if (hasCustomPrices(draft)) return 'fixed'
    if (draft.settlement_ratio) return 'discount'
    return 'channel_default'
  }

  function hasCustomPrices(draft) {
    return customPriceKeys.some((key) => Boolean(draft[key]))
  }

  function applyPriceMode(draft) {
    const normalized = normalizeDraftForMode(draft)
    Object.assign(draft, normalized)
  }

  function normalizeDraftForMode(draft) {
    const next = { ...draft }
    if (next.price_mode === 'channel_default') {
      next.settlement_ratio = ''
      customPriceKeys.forEach((key) => {
        next[key] = ''
      })
    }
    if (next.price_mode === 'discount') {
      customPriceKeys.forEach((key) => {
        next[key] = ''
      })
    }
    if (next.price_mode === 'fixed') {
      next.settlement_ratio = ''
    }
    return next
  }

  return {
    applyPriceMode,
    costCurrencyTitle,
    customPriceFields,
    draftDefaults,
    emptyNewDraft,
    normalizeDraftForMode,
    payloadForDraft,
    percentInputToRatio,
    performanceFields,
    priceModeFromDraft,
    priceRuleSummary,
    ratioPercent,
    ratioToPercentInput,
    serializeDraft,
    shouldPersist,
    summarizeDraftChanges,
    updateSettlementPercent
  }
}
