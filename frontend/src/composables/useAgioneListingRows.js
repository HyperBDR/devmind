import { computed, unref } from 'vue'
import { resolveCanonicalMetaVendor } from '@/utils/llmOpsMeta'

/**
 * Centralized derived state for the Agione resale listing workbench.
 *
 * Status board and action drawer both consume this composable to keep
 * the listing rows / decision-table / proposed-price derivations
 * computed exactly once. All inputs are passed as refs / getters so
 * reactivity tracks through the parent props correctly.
 *
 * Form-state refs (selectedTrendModelId / selectedTrendChannelId /
 * trendProfitRate) are owned by the consumer components — the
 * composable only reads them via injected refs and produces read-only
 * computed values.
 */
export function useAgioneListingRows({
  agionePlatformRef,
  providersRef,
  modelsRef,
  listingsRef,
  summaryRef,
  displayCurrencyRef,
  exchangeRateRef,
  selectedTrendModelIdRef,
  selectedTrendChannelIdRef,
  trendProfitRateRef,
  pointConversionRef
}) {
  const listingRows = computed(() => {
    const procurementByModel = new Map(
      ((unref(summaryRef)?.procurement) || []).map((row) => [
        String(row.model_id),
        row
      ])
    )
    const listingsByModel = new Map()
    const platform = unref(agionePlatformRef)
    const listings = unref(listingsRef) || []
    listings
      .filter(
        (listing) =>
          !platform ||
          String(listing.platform) === String(platform.id)
      )
      .forEach((listing) => {
        const key = String(listing.model)
        const rows = listingsByModel.get(key) || []
        rows.push(listing)
        listingsByModel.set(key, rows)
      })

    return (unref(modelsRef) || []).flatMap((model) => {
      const modelId = String(model.id)
      const procurement = procurementByModel.get(modelId) || {}
      const options = procurement.options || []
      const lowestOption = procurement.best_channel || null
      const modelListings = listingsByModel.get(modelId) || []
      if (!options.length && !modelListings.length) return []

      const rows = modelListings.length
        ? modelListings.map((listing) => {
            const isActive = listing.publish_status === 'online'
            const listingOptionData = listingOption(
              { ...listing, model, listings: [listing] },
              lowestOption,
              options
            )
            const cheapestActiveOption = isActive && listingOptionData
              ? listingOptionData
              : null
            return {
              model,
              procurement,
              options,
              listings: [listing],
              status_listing: listing,
              active_listings: isActive ? [listing] : [],
              publish_status: listing.publish_status,
              workflow_status: listing.workflow_status,
              is_listed: isActive,
              is_removed: false,
              lowest_option: lowestOption,
              requires_currency_conversion:
                procurement.requires_currency_conversion || false,
              has_lowest_listing:
                isActive &&
                lowestOption &&
                String(listing.channel) === String(lowestOption.channel_id),
              price_gap: listingPriceGap(cheapestActiveOption, lowestOption),
            }
          })
        : [{
            model,
            procurement,
            options,
            listings: [],
            status_listing: null,
            active_listings: [],
            publish_status: 'none',
            workflow_status: 'draft',
            is_listed: false,
            is_removed: false,
            lowest_option: lowestOption,
            requires_currency_conversion:
              procurement.requires_currency_conversion || false,
            has_lowest_listing: false,
            price_gap: null,
          }]

      return rows
    })
  })

  const trendRows = computed(() => {
    const groups = new Map()
    listingRows.value.forEach((row) => {
      const key = trendRowKey(row.model)
      const group = groups.get(key) || {
        key,
        model: row.model,
        rows: [],
        procurement: {},
        options: [],
        listings: [],
        active_listings: [],
        is_listed: false,
        lowest_option: null,
        requires_currency_conversion: false,
        has_lowest_listing: false,
        price_gap: null,
        source_count: 0
      }
      group.rows.push(row)
      group.options.push(...row.options)
      group.listings.push(...row.listings)
      group.active_listings.push(...row.active_listings)
      group.is_listed = group.is_listed || row.is_listed
      group.requires_currency_conversion =
        group.requires_currency_conversion || row.requires_currency_conversion
      group.has_lowest_listing =
        group.has_lowest_listing || row.has_lowest_listing
      groups.set(key, group)
    })

    return Array.from(groups.values()).map((group) => {
      const options = uniqueTrendOptions(group.options)
      const lowestOption =
        options
          .slice()
          .sort(
            (left, right) =>
              Number(left.estimated_cost || 0) -
              Number(right.estimated_cost || 0)
          )[0] || null
      const activeOptions = group.active_listings
        .map((listing) => listingOption(listing, lowestOption, options))
        .filter(Boolean)
      const cheapestActiveOption =
        activeOptions
          .slice()
          .sort(
            (left, right) =>
              Number(left.estimated_cost || 0) -
              Number(right.estimated_cost || 0)
          )[0] || null
      return {
        ...group,
        options,
        lowest_option: lowestOption,
        source_count: group.rows.length,
        has_lowest_listing: activeOptions.some(
          (option) =>
            lowestOption &&
            String(option.channel_id) === String(lowestOption.channel_id)
        ),
        price_gap: listingPriceGap(cheapestActiveOption, lowestOption)
      }
    })
  })

  const actionableTrendRows = computed(() =>
    trendRows.value.filter((row) => row.options.length)
  )

  const unavailableTrendRows = computed(() =>
    trendRows.value.filter((row) => !row.options.length)
  )

  const selectedTrendRow = computed(
    () =>
      trendRows.value.find(
        (row) => String(row.key) === String(unref(selectedTrendModelIdRef))
      ) || null
  )

  const selectedTrendModel = computed(
    () => selectedTrendRow.value?.model || null
  )

  const selectedTrendCurrency = computed(
    () => unref(displayCurrencyRef) || 'CNY'
  )

  const priceMetricOptions = computed(() => {
    const model = selectedTrendModel.value
    if (!model) {
      return tokenMetricOptions()
    }
    if (model.modality === 'audio') {
      return [
        { key: 'audio_input', label: '音频输入' },
        { key: 'audio_output', label: '音频输出' }
      ]
    }
    if (model.modality === 'video') {
      return [
        { key: 'video_input', label: '视频输入' },
        { key: 'video_output', label: '视频输出' }
      ]
    }
    if (
      model.image_output_price_per_image !== null &&
      model.image_output_price_per_image !== undefined &&
      model.image_output_price_per_image !== ''
    ) {
      return [
        { key: 'input', label: '输入价' },
        { key: 'output', label: '输出价' },
        { key: 'image_output', label: '图片输出' }
      ]
    }
    return tokenMetricOptions()
  })

  const primaryMetricKey = computed(
    () => priceMetricOptions.value[0]?.key || 'input'
  )

  const channelReferencePrices = computed(() => {
    if (!selectedTrendRow.value) return []
    return selectedTrendRow.value.options
      .map((option) => {
        const metricValues = metricValuesForRow(
          option,
          channelMetricFields(),
          option.currency
        )
        const primaryValue = metricValues.find(
          (item) => item.key === primaryMetricKey.value
        )?.value
        const fallbackValue = metricValues[0]?.value ?? null
        return {
          ...option,
          label: option.channel_name || '渠道',
          metric_values: metricValues,
          metric_price: primaryValue ?? fallbackValue,
          value: primaryValue ?? fallbackValue,
          original_currency: option.currency,
          currency: selectedTrendCurrency.value
        }
      })
      .filter((item) => item.metric_values.length)
      .sort((left, right) => Number(left.value || 0) - Number(right.value || 0))
  })

  const lowestChannelPrice = computed(
    () => channelReferencePrices.value[0] || null
  )

  const trendChannelOptions = computed(() => channelReferencePrices.value)

  const trendChannelSelectOptions = computed(() =>
    trendChannelOptions.value.map((option) => ({
      label: option.channel_name || '未命名渠道',
      value: option.channel_id,
      description: metricPriceSummary(option.metric_values),
      badge:
        String(option.channel_id) === String(lowestChannelPrice.value?.channel_id)
          ? '最低'
          : '',
      searchText: [
        option.channel_name,
        option.currency,
        metricPriceSummary(option.metric_values)
      ]
        .filter(Boolean)
        .join(' ')
    }))
  )

  const trendModelOptions = computed(() => [
    {
      label: '选择模型',
      value: '',
      description: `${actionableTrendRows.value.length} 个可决策模型 · ${unavailableTrendRows.value.length} 个待配置渠道`
    },
    {
      label: `可选模型（已配置渠道 ${actionableTrendRows.value.length}）`,
      value: '__group_actionable_models',
      type: 'group'
    },
    ...actionableTrendRows.value.map((row) => trendModelOption(row)),
    ...(
      unavailableTrendRows.value.length
        ? [{
            label: `不可选模型（暂无渠道 ${unavailableTrendRows.value.length}）`,
            value: '__group_unavailable_models',
            type: 'group'
          }]
        : []
    ),
    ...unavailableTrendRows.value.map((row) => ({
      ...trendModelOption(row),
      disabled: true,
      badge: '需配置渠道'
    }))
  ])

  const selectedTrendOption = computed(() => {
    if (!selectedTrendRow.value) return null
    return (
      trendChannelOptions.value.find(
        (option) =>
          String(option.channel_id) === String(unref(selectedTrendChannelIdRef))
      ) ||
      lowestChannelPrice.value ||
      null
    )
  })

  const proposedListingPrice = computed(() => {
    const basePrice = Number(selectedTrendOption.value?.value)
    const profitRate = Number(unref(trendProfitRateRef) || 0)
    if (!Number.isFinite(basePrice) || !Number.isFinite(profitRate)) return null
    return basePrice * (1 + profitRate / 100)
  })

  const proposedListingPrices = computed(() => {
    const profitRate = Number(unref(trendProfitRateRef) || 0)
    if (!Number.isFinite(profitRate)) return []
    return (selectedTrendOption.value?.metric_values || []).map((item) => ({
      ...item,
      value: Number(item.value || 0) * (1 + profitRate / 100)
    }))
  })

  const supplyDecisionRows = computed(() => {
    const profitRate = Number(unref(trendProfitRateRef) || 0)
    const normalizedRate = Number.isFinite(profitRate) ? profitRate : 0
    const lowestValue = Number(lowestChannelPrice.value?.value || 0)
    return trendChannelOptions.value.map((option) => {
      const proposedValues = option.metric_values.map((item) => ({
        ...item,
        value: Number(item.value || 0) * (1 + normalizedRate / 100)
      }))
      const costValue = Number(option.value || 0)
      const proposedValue =
        proposedValues.find((item) => item.key === primaryMetricKey.value)
          ?.value ?? proposedValues[0]?.value ?? 0
      const activeListing = selectedTrendRow.value?.active_listings.find(
        (listing) => String(listing.channel) === String(option.channel_id)
      )
      const gapValue = Math.max(0, costValue - lowestValue)
      const gapPercent =
        lowestValue > 0 ? (gapValue / lowestValue) * 100 : 0
      return {
        ...option,
        key: `channel-${option.channel_id}`,
        label: option.channel_name || '未命名渠道',
        channel_name: option.channel_name || '未命名渠道',
        cost_value: costValue,
        cost_summary: metricPriceSummary(option.metric_values),
        cost_breakdown_summary: metricCostBreakdownSummary(
          option.metric_values
        ),
        proposed_value: proposedValue,
        proposed_summary: metricPriceSummary(proposedValues),
        is_lowest:
          String(option.channel_id) ===
          String(lowestChannelPrice.value?.channel_id),
        is_listed: Boolean(activeListing),
        is_selected:
          String(option.channel_id) === String(unref(selectedTrendChannelIdRef)),
        gap_label:
          gapValue > 0
            ? `高 ${money(gapValue, selectedTrendCurrency.value)} · ${gapPercent.toFixed(1)}%`
            : ''
      }
    })
  })

  const selectedOptionIsLowest = computed(() => {
    if (!selectedTrendOption.value || !lowestChannelPrice.value) return false
    return (
      String(selectedTrendOption.value.channel_id) ===
      String(lowestChannelPrice.value.channel_id)
    )
  })

  const selectedOptionIsListed = computed(() => {
    if (!selectedTrendOption.value || !selectedTrendRow.value) return false
    return selectedTrendRow.value.active_listings.some(
      (listing) =>
        String(listing.channel) ===
        String(selectedTrendOption.value.channel_id)
    )
  })

  const canSaveTrendListing = computed(
    () =>
      unref(agionePlatformRef) &&
      selectedTrendRow.value &&
      selectedTrendOption.value &&
      proposedListingPrices.value.some((item) => Number(item.value) > 0)
  )

  const canSwitchTrendListing = computed(
    () =>
      canSaveTrendListing.value &&
      selectedTrendRow.value?.is_listed &&
      !selectedOptionIsListed.value
  )

  const trendPrimaryActionLabel = computed(() => {
    if (selectedOptionIsListed.value) return '更新价格'
    return '追加上架'
  })

  const trendActionHint = computed(() => {
    if (!selectedTrendOption.value) return '先选择采购渠道后再生成上架价格。'
    if (selectedOptionIsListed.value && selectedOptionIsLowest.value) {
      return '当前渠道已经上架且是最低采购渠道，可直接更新利润率后的售价。'
    }
    if (selectedOptionIsListed.value) {
      return '当前渠道已经上架，本次操作会更新该渠道的挂售价格。'
    }
    if (canSwitchTrendListing.value) {
      return '追加会保留现有渠道；切换会下架同平台其他渠道，仅保留当前渠道。'
    }
    return '追加会新增当前渠道的挂售价格，不会影响已有上架渠道。'
  })

  const selectedDecisionStatusLabel = computed(() => {
    if (!selectedTrendOption.value) return '未选择渠道'
    if (selectedOptionIsListed.value && selectedOptionIsLowest.value) {
      return '已上架最低价'
    }
    if (selectedOptionIsListed.value) return '当前已上架'
    if (selectedOptionIsLowest.value) return '最低采购价'
    return '非最低采购价'
  })

  const selectedPlanLabel = computed(() => {
    if (!selectedTrendOption.value) return '未选择'
    if (selectedOptionIsListed.value && selectedOptionIsLowest.value) {
      return '已上架最低源'
    }
    if (selectedOptionIsListed.value) return '已上架'
    if (selectedOptionIsLowest.value) return '最低采购渠道'
    return '非最低源'
  })

  const pointFormulaLabel = computed(() => {
    return unref(pointConversionRef)?.formula_label || '未配置'
  })

  function listingOption(listing, lowestOption, options) {
    if (!listing.channel) return lowestOption
    return options.find(
      (option) => String(option.channel_id) === String(listing.channel)
    )
  }

  function trendRowKey(model) {
    return [
      model.meta_model || model.meta_model_code || model.code || model.name,
      model.modality || 'text'
    ]
      .filter(Boolean)
      .join('|')
      .toLowerCase()
  }

  function uniqueTrendOptions(options) {
    const byChannel = new Map()
    options.forEach((option) => {
      const key = String(option.channel_id || '')
      if (!key) return
      const current = byChannel.get(key)
      if (
        !current ||
        Number(option.estimated_cost || 0) < Number(current.estimated_cost || 0)
      ) {
        byChannel.set(key, option)
      }
    })
    return Array.from(byChannel.values())
  }

  function listingPriceGap(activeOption, lowestOption) {
    if (!activeOption || !lowestOption) return null
    return Math.max(
      0,
      Number(activeOption.estimated_cost || 0) -
        Number(lowestOption.estimated_cost || 0)
    )
  }

  function primaryStatusListing(modelListings, activeListings) {
    const pendingListing = modelListings.find((listing) =>
      [
        'draft',
        'pending_publish',
        'update_draft',
        'pending_update',
        'pending_offline',
        'offline_exception',
        'offline',
      ].includes(listing.workflow_status)
    )
    if (pendingListing) return pendingListing
    if (activeListings.length) return activeListings[0]
    return (
      modelListings
        .slice()
        .sort((left, right) => {
          const leftTime = new Date(left.updated_at || left.created_at || 0)
          const rightTime = new Date(right.updated_at || right.created_at || 0)
          return rightTime.getTime() - leftTime.getTime()
        })[0] || null
    )
  }

  function listingRetailPrice(cost, profitRate) {
    const costValue = Number(cost || 0)
    const profitRateValue = Number(profitRate || 0)
    if (!Number.isFinite(costValue) || !Number.isFinite(profitRateValue)) {
      return '0'
    }
    return (costValue * (1 + profitRateValue / 100)).toFixed(6)
  }

  function listingRetailPriceByProfit(cost, sourceCurrency) {
    const displayCost = convertCurrencyAmount(cost, sourceCurrency)
    const profitRate = Number(unref(trendProfitRateRef) || 0)
    if (!Number.isFinite(displayCost) || !Number.isFinite(profitRate)) {
      return '0'
    }
    return (displayCost * (1 + profitRate / 100)).toFixed(6)
  }

  function numeric(value) {
    if (value === null || value === undefined || value === '') return null
    const numberValue = Number(value)
    return Number.isFinite(numberValue) ? numberValue : null
  }

  function tokenMetricOptions() {
    return [
      { key: 'input', label: '输入价' },
      { key: 'cache_input', label: '缓存输入价' },
      { key: 'output', label: '输出价' }
    ]
  }

  function channelMetricFields() {
    return {
      input: 'input_price_per_million',
      cache_input: 'cache_input_price_per_million',
      output: 'output_price_per_million',
      image_output: 'image_output_price_per_image',
      audio_input: 'audio_input_price_per_second',
      audio_output: 'audio_output_price_per_second',
      video_input: 'video_input_price_per_second',
      video_output: 'video_output_price_per_second'
    }
  }

  function resaleListingMetricFields() {
    return {
      input: 'retail_input_price_per_million',
      cache_input: 'retail_cache_input_price_per_million',
      output: 'retail_output_price_per_million',
      image_output: 'retail_image_output_price_per_image',
      audio_input: 'retail_audio_input_price_per_second',
      audio_output: 'retail_audio_output_price_per_second',
      video_input: 'retail_video_input_price_per_second',
      video_output: 'retail_video_output_price_per_second'
    }
  }

  function metricValue(row, fields, metricKey = primaryMetricKey.value) {
    const field = fields[metricKey]
    return field ? numeric(row?.[field]) : null
  }

  function metricValuesForRow(row, fields, currency) {
    return priceMetricOptions.value
      .map((option) => {
        const field = fields[option.key]
        const value = convertCurrencyAmount(
          metricValue(row, fields, option.key),
          currency
        )
        const baseValue = convertCurrencyAmount(
          field ? numeric(row?.[`base_${field}`]) : null,
          currency
        )
        const discountRatio = field
          ? numeric(row?.[`${field}_settlement_ratio`])
          : null
        return {
          ...option,
          value,
          base_value: baseValue,
          discount_ratio: discountRatio
        }
      })
      .filter((item) => item.value !== null)
  }

  function convertCurrencyAmount(value, sourceCurrency = 'USD') {
    if (value === null || value === undefined || value === '') return null
    const source = String(sourceCurrency || '').toUpperCase()
    const target = String(unref(displayCurrencyRef) || 'CNY').toUpperCase()
    const amount = Number(value)
    if (!Number.isFinite(amount)) return null
    if (source === target) return amount
    const rate = Number(unref(exchangeRateRef) || 7.15)
    if (source === 'USD' && target === 'CNY') {
      return amount * rate
    }
    if (source === 'CNY' && target === 'USD') {
      return amount / rate
    }
    return null
  }

  function displayAmountToPlatformCurrency(value) {
    const amount = Number(value)
    if (!Number.isFinite(amount)) return null
    const source = String(unref(displayCurrencyRef) || 'CNY').toUpperCase()
    const target = String(
      unref(pointConversionRef)?.currency || source
    ).toUpperCase()
    if (source === target) return amount
    const rate = Number(unref(exchangeRateRef) || 7.15)
    if (source === 'USD' && target === 'CNY') return amount * rate
    if (source === 'CNY' && target === 'USD') return amount / rate
    return null
  }

  function money(value, currency) {
    if (value === null || value === undefined || value === '') return '-'
    const unit = currency || unref(displayCurrencyRef) || 'CNY'
    return `${unit} ${Number(value).toFixed(4)}`
  }

  function metricPriceSummary(items, emptyLabel = '-') {
    if (!items?.length) return emptyLabel
    return items
      .map((item) => `${item.label} ${money(item.value, selectedTrendCurrency.value)}`)
      .join(' / ')
  }

  function metricCostBreakdownSummary(items, emptyLabel = '-') {
    if (!items?.length) return emptyLabel
    return items
      .map((item) => {
        const baseValue = Number.isFinite(item.base_value)
          ? item.base_value
          : item.value
        const ratio = Number.isFinite(item.discount_ratio)
          ? item.discount_ratio
          : 1
        return [
          item.label,
          `${money(baseValue, selectedTrendCurrency.value)} × ${ratioLabel(ratio)}`,
          `= ${money(item.value, selectedTrendCurrency.value)}`
        ].join(' ')
      })
      .join(' / ')
  }

  function ratioLabel(value) {
    const numberValue = Number(value)
    if (!Number.isFinite(numberValue)) return '1.0000'
    return numberValue.toFixed(4)
  }

  function activeListingChannels(row) {
    const listings = row?.active_listings || []
    if (!listings.length) return '-'
    return listings
      .map((listing) => listing.channel_name || '未指定渠道')
      .filter(Boolean)
      .join(' / ')
  }

  function activeListingPriceSummary(row) {
    const listing = row?.active_listings?.[0]
    if (!listing) return '-'
    const values = metricValuesForRow(
      listing,
      resaleListingMetricFields(),
      listing.currency
    )
    return metricPriceSummary(values)
  }

  function activeListingPointSummary(row) {
    const listing = row?.active_listings?.[0]
    if (!listing) return ''
    const values = metricValuesForRow(
      listing,
      resaleListingMetricFields(),
      listing.currency
    )
    const rate = Number(unref(pointConversionRef)?.points_per_currency_unit || 0)
    if (!values.length || !Number.isFinite(rate) || rate <= 0) return ''
    return values
      .map((item) => {
        const platformAmount = displayAmountToPlatformCurrency(item.value)
        if (platformAmount === null) return null
        return `${item.label} ${Math.round(platformAmount * rate)} ${
          unref(pointConversionRef)?.point_name || '积分'
        }`
      })
      .filter(Boolean)
      .join(' / ')
  }

  function modelDisplayName(model) {
    return model?.meta_model_name || model?.name || model?.code || ''
  }

  function modelCodeDescription(model) {
    const name = String(modelDisplayName(model) || '').trim()
    const code = String(model?.meta_model_code || model?.code || '').trim()
    return code && code !== name ? code : ''
  }

  function listingModelSubtitle(row) {
    const model = row?.model || {}
    const code = modelCodeDescription(model)
    const vendorName = metaVendorName(model)
    return [
      vendorName,
      code,
      row.source_count ? `${row.source_count} 个价格源` : ''
    ]
      .filter(Boolean)
      .join(' / ')
  }

  function metaVendorName(model) {
    const vendor = resolveCanonicalMetaVendor(model, unref(providersRef) || [])
    return vendor.name || ''
  }

  function trendModelOption(row) {
    return {
      label: modelDisplayName(row.model),
      value: row.key,
      description: [
        modelCodeDescription(row.model),
        row.source_count > 1 ? `${row.source_count} 个价格源` : '',
        row.options.length ? `${row.options.length} 个采购渠道` : '暂无采购渠道'
      ]
        .filter(Boolean)
        .join(' · '),
      badge: row.is_listed
        ? row.has_lowest_listing
          ? '已上架'
          : '待处理'
        : '未上架',
      searchText: [
        modelDisplayName(row.model),
        row.model.code,
        metaVendorName(row.model)
      ]
        .filter(Boolean)
        .join(' ')
    }
  }

  function defaultTrendRow() {
    return (
      actionableTrendRows.value.find(
        (row) => row.is_listed && !row.has_lowest_listing
      ) ||
      actionableTrendRows.value.find((row) => row.is_listed) ||
      actionableTrendRows.value.find((row) => row.lowest_option) ||
      actionableTrendRows.value[0] ||
      null
    )
  }

  function ensureSelectedTrendChannel() {
    const options = trendChannelOptions.value
    if (!options.length) {
      return ''
    }
    const current = unref(selectedTrendChannelIdRef)
    const hasSelected = options.some(
      (option) => String(option.channel_id) === String(current)
    )
    if (!hasSelected) {
      return lowestChannelPrice.value?.channel_id || ''
    }
    return current
  }

  function normalizePayload(payload, nullableFields = []) {
    const clean = { ...payload }
    const nullable = new Set(nullableFields)
    Object.keys(clean).forEach((key) => {
      if (clean[key] === '' && nullable.has(key)) {
        clean[key] = null
      }
    })
    clean.currency = String(clean.currency || '').trim().toUpperCase()
    delete clean.id
    return clean
  }

  function buildTrendListingPayload() {
    const row = selectedTrendRow.value
    const option = selectedTrendOption.value
    return normalizePayload(
      {
        platform: unref(agionePlatformRef).id,
        model: row.model.id,
        channel: option?.channel_id || '',
        currency: selectedTrendCurrency.value,
        display_name: modelDisplayName(row.model),
        retail_input_price_per_million: listingRetailPriceByProfit(
          option?.input_price_per_million,
          option?.original_currency
        ),
        retail_output_price_per_million: listingRetailPriceByProfit(
          option?.output_price_per_million,
          option?.original_currency
        ),
        retail_image_output_price_per_image: listingRetailPriceByProfit(
          option?.image_output_price_per_image,
          option?.original_currency
        ),
        retail_audio_input_price_per_second: listingRetailPriceByProfit(
          option?.audio_input_price_per_second,
          option?.original_currency
        ),
        retail_audio_output_price_per_second: listingRetailPriceByProfit(
          option?.audio_output_price_per_second,
          option?.original_currency
        ),
        retail_video_input_price_per_second: listingRetailPriceByProfit(
          option?.video_input_price_per_second,
          option?.original_currency
        ),
        retail_video_output_price_per_second: listingRetailPriceByProfit(
          option?.video_output_price_per_second,
          option?.original_currency
        ),
        is_active: true
      },
      ['channel']
    )
  }

  return {
    listingRows,
    trendRows,
    actionableTrendRows,
    unavailableTrendRows,
    selectedTrendRow,
    selectedTrendModel,
    selectedTrendCurrency,
    selectedTrendOption,
    selectedOptionIsLowest,
    selectedOptionIsListed,
    canSaveTrendListing,
    canSwitchTrendListing,
    trendPrimaryActionLabel,
    trendActionHint,
    trendModelOptions,
    trendChannelOptions,
    trendChannelSelectOptions,
    supplyDecisionRows,
    priceMetricOptions,
    primaryMetricKey,
    lowestChannelPrice,
    channelReferencePrices,
    proposedListingPrice,
    proposedListingPrices,
    selectedDecisionStatusLabel,
    selectedPlanLabel,
    pointFormulaLabel,
    modelDisplayName,
    modelCodeDescription,
    listingModelSubtitle,
    activeListingChannels,
    activeListingPriceSummary,
    activeListingPointSummary,
    trendModelOption,
    defaultTrendRow,
    ensureSelectedTrendChannel,
    buildTrendListingPayload,
    money,
    metricPriceSummary,
    metricCostBreakdownSummary,
    convertCurrencyAmount,
    listingRetailPrice,
    listingPriceGap
  }
}
