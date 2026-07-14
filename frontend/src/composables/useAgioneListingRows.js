import { computed, unref } from 'vue'

import { resolveCanonicalMetaOwner } from '@/utils/llmOpsMeta'
import { asArray } from '@/utils/llmOpsPagination'
import { formatRoundedPoints } from '@/utils/pointRounding'

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
  pointConversionRef,
  t
}) {
  const listingRows = computed(() => {
    const procurementByModel = new Map(
      asArray(unref(summaryRef)?.procurement).map((row) => [
        String(row.model_id),
        row
      ])
    )
    const listingsByModel = new Map()
    const platform = unref(agionePlatformRef)
    const listings = asArray(unref(listingsRef))
    listings
      .filter(
        (listing) =>
          !platform || String(listing.platform) === String(platform.id)
      )
      .forEach((listing) => {
        const key = String(listing.model)
        const rows = listingsByModel.get(key) || []
        rows.push(listing)
        listingsByModel.set(key, rows)
      })

    return asArray(unref(modelsRef)).flatMap((model) => {
      const modelId = String(model.id)
      const procurement = procurementByModel.get(modelId) || {}
      const options = asArray(procurement.options)
      const lowestOption = procurement.best_channel || null
      const modelListings = listingsByModel.get(modelId) || []
      if (!options.length && !modelListings.length) return []

      // Only models that have actually entered the resale-platform
      // workflow should appear in the platform list. Channel-priced
      // candidates stay available in the publishing workspace, but they
      // should not be auto-inserted into the platform board as
      // "unlisted" rows.
      if (!modelListings.length) return []

      return modelListings.map((listing) => {
        const isActive = listing.publish_status === 'online'
        const listingOptionData = listingOption(
          { ...listing, model, listings: [listing] },
          lowestOption,
          options
        )
        const cheapestActiveOption =
          isActive && listingOptionData ? listingOptionData : null
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
          price_gap: listingPriceGap(cheapestActiveOption, lowestOption)
        }
      })
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
      group.options.push(...asArray(row.options))
      group.listings.push(...asArray(row.listings))
      group.active_listings.push(...asArray(row.active_listings))
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
      const activeOptions = asArray(group.active_listings)
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
        {
          key: 'audio_input',
          label: t('llmOps.publishingWorkspace.metrics.audioInput')
        },
        {
          key: 'audio_output',
          label: t('llmOps.publishingWorkspace.metrics.audioOutput')
        }
      ]
    }
    if (model.modality === 'video') {
      return [
        {
          key: 'video_input',
          label: t('llmOps.publishingWorkspace.metrics.videoInput')
        },
        {
          key: 'video_output',
          label: t('llmOps.publishingWorkspace.metrics.videoOutput')
        }
      ]
    }
    if (
      model.image_output_price_per_image !== null &&
      model.image_output_price_per_image !== undefined &&
      model.image_output_price_per_image !== ''
    ) {
      return [
        { key: 'input', label: t('llmOps.publishingWorkspace.metrics.input') },
        {
          key: 'output',
          label: t('llmOps.publishingWorkspace.metrics.output')
        },
        {
          key: 'image_output',
          label: t('llmOps.publishingWorkspace.metrics.imageOutput')
        }
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
          label: option.channel_name || t('llmOps.channel.fallback'),
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
      label: option.channel_name || t('llmOps.channel.unnamed'),
      value: option.channel_id,
      description: metricPriceSummary(option.metric_values),
      badge:
        String(option.channel_id) ===
        String(lowestChannelPrice.value?.channel_id)
          ? t('llmOps.publishingWorkspace.supply.lowest')
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
      label: t('llmOps.publishingWorkspace.modelSelect.label'),
      value: '',
      description: t('llmOps.publishingWorkspace.modelSelect.description', {
        actionable: actionableTrendRows.value.length,
        unavailable: unavailableTrendRows.value.length
      })
    },
    {
      label: t('llmOps.publishingWorkspace.modelSelect.actionableGroup', {
        count: actionableTrendRows.value.length
      }),
      value: '__group_actionable_models',
      type: 'group'
    },
    ...actionableTrendRows.value.map((row) => trendModelOption(row)),
    ...(unavailableTrendRows.value.length
      ? [
          {
            label: t(
              'llmOps.publishingWorkspace.modelSelect.unavailableGroup',
              { count: unavailableTrendRows.value.length }
            ),
            value: '__group_unavailable_models',
            type: 'group'
          }
        ]
      : []),
    ...unavailableTrendRows.value.map((row) => ({
      ...trendModelOption(row),
      disabled: true,
      badge: t('llmOps.publishingWorkspace.modelSelect.needsChannel')
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
      const proposedValues = asArray(option.metric_values).map((item) => ({
        ...item,
        value: Number(item.value || 0) * (1 + normalizedRate / 100)
      }))
      const costValue = Number(option.value || 0)
      const proposedValue =
        proposedValues.find((item) => item.key === primaryMetricKey.value)
          ?.value ??
        proposedValues[0]?.value ??
        0
      const activeListing = asArray(
        selectedTrendRow.value?.active_listings
      ).find((listing) => String(listing.channel) === String(option.channel_id))
      const gapValue = Math.max(0, costValue - lowestValue)
      const gapPercent = lowestValue > 0 ? (gapValue / lowestValue) * 100 : 0
      return {
        ...option,
        key: `channel-${option.channel_id}`,
        label: option.channel_name || t('llmOps.channel.unnamed'),
        channel_name: option.channel_name || t('llmOps.channel.unnamed'),
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
          String(option.channel_id) ===
          String(unref(selectedTrendChannelIdRef)),
        gap_label:
          gapValue > 0
            ? t('llmOps.publishingWorkspace.supply.higherCost', {
                amount: money(gapValue, selectedTrendCurrency.value),
                percent: gapPercent.toFixed(1)
              })
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
    return asArray(selectedTrendRow.value.active_listings).some(
      (listing) =>
        String(listing.channel) === String(selectedTrendOption.value.channel_id)
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
    if (selectedOptionIsListed.value) {
      return t('llmOps.publishingWorkspace.actions.updatePrice')
    }
    return t('llmOps.publishingWorkspace.actions.appendListing')
  })

  const trendActionHint = computed(() => {
    if (!selectedTrendOption.value) {
      return t('llmOps.publishingWorkspace.actions.selectChannelFirst')
    }
    if (selectedOptionIsListed.value && selectedOptionIsLowest.value) {
      return t('llmOps.publishingWorkspace.actions.updateLowestListedHint')
    }
    if (selectedOptionIsListed.value) {
      return t('llmOps.publishingWorkspace.actions.updateListedHint')
    }
    if (canSwitchTrendListing.value) {
      return t('llmOps.publishingWorkspace.actions.switchAvailableHint')
    }
    return t('llmOps.publishingWorkspace.actions.appendListingHint')
  })

  const selectedDecisionStatusLabel = computed(() => {
    if (!selectedTrendOption.value) {
      return t('llmOps.publishingWorkspace.decision.noChannelSelected')
    }
    if (selectedOptionIsListed.value && selectedOptionIsLowest.value) {
      return t('llmOps.publishingWorkspace.decision.listedLowest')
    }
    if (selectedOptionIsListed.value) {
      return t('llmOps.publishingWorkspace.decision.currentlyListed')
    }
    if (selectedOptionIsLowest.value) {
      return t('llmOps.publishingWorkspace.decision.lowestProcurement')
    }
    return t('llmOps.publishingWorkspace.decision.notLowestProcurement')
  })

  const selectedPlanLabel = computed(() => {
    if (!selectedTrendOption.value) {
      return t('llmOps.publishingWorkspace.plan.notSelected')
    }
    if (selectedOptionIsListed.value && selectedOptionIsLowest.value) {
      return t('llmOps.publishingWorkspace.plan.listedLowestSource')
    }
    if (selectedOptionIsListed.value) {
      return t('llmOps.publishingWorkspace.plan.listed')
    }
    if (selectedOptionIsLowest.value) {
      return t('llmOps.publishingWorkspace.plan.lowestProcurementChannel')
    }
    return t('llmOps.publishingWorkspace.plan.notLowestSource')
  })

  const pointFormulaLabel = computed(() => {
    return (
      unref(pointConversionRef)?.formula_label ||
      t('llmOps.publishingWorkspace.fallback.notConfigured')
    )
  })

  function listingOption(listing, lowestOption, options) {
    if (!listing.channel) return lowestOption
    return asArray(options).find(
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
    asArray(options).forEach((option) => {
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
      { key: 'input', label: t('llmOps.publishingWorkspace.metrics.input') },
      {
        key: 'cache_input',
        label: t('llmOps.publishingWorkspace.metrics.cacheInput')
      },
      { key: 'output', label: t('llmOps.publishingWorkspace.metrics.output') }
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
      .map(
        (item) =>
          `${item.label} ${money(item.value, selectedTrendCurrency.value)}`
      )
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
          `${money(baseValue, selectedTrendCurrency.value)} × ${ratioLabel(
            ratio
          )}`,
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
    const listings = asArray(row?.active_listings)
    if (!listings.length) return '-'
    return listings
      .map(
        (listing) =>
          listing.channel_name || t?.('llmOps.channel.unspecified') || '-'
      )
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
    const rate = Number(
      unref(pointConversionRef)?.points_per_currency_unit || 0
    )
    if (!values.length || !Number.isFinite(rate) || rate <= 0) return ''
    return values
      .map((item) => {
        const platformAmount = displayAmountToPlatformCurrency(item.value)
        if (platformAmount === null) return null
        const points = formatRoundedPoints(
          platformAmount * rate,
          unref(pointConversionRef)
        )
        return `${item.label} ${points} ${
          unref(pointConversionRef)?.point_name ||
          t('llmOps.publishingWorkspace.fallback.points')
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
    return code && normalizeModelIdentity(code) !== normalizeModelIdentity(name)
      ? code
      : ''
  }

  function listingModelSubtitle(row) {
    const model = row?.model || {}
    const name = String(modelDisplayName(model) || '')
    const code = modelCodeDescription(model)
    const vendorName = metaVendorName(model)
    return [
      modelNameIncludesVendor(name, vendorName) ? '' : vendorName,
      code,
      row.source_count
        ? t('llmOps.monitor.sourceCount', { count: row.source_count })
        : ''
    ]
      .filter(Boolean)
      .join(' / ')
  }

  function metaVendorName(model) {
    const vendor = resolveCanonicalMetaOwner(model, unref(providersRef) || [])
    return vendor.name || ''
  }

  function normalizeModelIdentity(value) {
    return String(value || '')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '')
  }

  function modelNameIncludesVendor(name, vendorName) {
    const normalizedName = normalizeModelIdentity(name)
    const normalizedVendor = normalizeModelIdentity(vendorName)
    return Boolean(
      normalizedVendor && normalizedName.includes(normalizedVendor)
    )
  }

  function trendModelOption(row) {
    return {
      label: modelDisplayName(row.model),
      value: row.key,
      description: [
        modelCodeDescription(row.model),
        row.source_count > 1
          ? t?.('llmOps.monitor.sourceCount', {
              count: row.source_count
            }) || ''
          : '',
        row.options.length
          ? t?.('llmOps.monitor.procurementChannelCount', {
              count: row.options.length
            }) || ''
          : t?.('llmOps.monitor.noProcurementChannels') || ''
      ]
        .filter(Boolean)
        .join(' · '),
      badge: row.is_listed
        ? row.has_lowest_listing
          ? t?.('llmOps.status.listed') || ''
          : t?.('llmOps.status.needsHandling') || ''
        : t?.('llmOps.status.unlisted') || '',
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
    clean.currency = String(clean.currency || '')
      .trim()
      .toUpperCase()
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
