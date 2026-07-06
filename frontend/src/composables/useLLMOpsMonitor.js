import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { asArray, asObject } from '@/utils/llmOpsPagination'

const monitorStatusLabelKeys = {
  currency_mismatch: 'llmOps.status.currencyMismatch',
  low_coverage: 'llmOps.status.lowCoverage',
  missing_channel: 'llmOps.status.missingChannel',
  not_lowest: 'llmOps.status.notLowest',
  ready: 'llmOps.status.readyShort',
  unlisted: 'llmOps.status.unlisted'
}

export function useLLMOpsMonitor({
  agionePlatform,
  channels,
  collectionRuns,
  listings,
  models,
  procurementRows,
  providerCollectionSources,
  summary
}) {
  const { t } = useI18n()

  const simulationChannel = ref('')
  const simulationStatus = ref('priority')

  const simulationStatusOptions = computed(() => [
    { label: t('llmOps.filters.priority'), value: 'priority' },
    { label: t('llmOps.filters.allModels'), value: 'all' },
    { label: t('llmOps.status.currencyMismatch'), value: 'currency_mismatch' },
    { label: t('llmOps.status.missingChannel'), value: 'missing_channel' },
    { label: t('llmOps.status.unlisted'), value: 'unlisted' },
    { label: t('llmOps.status.ready'), value: 'ready' }
  ])

  const simulationChannelOptions = computed(() => [
    { label: t('llmOps.filters.allChannels'), value: '' },
    ...asArray(channels.value).map((channel) => ({
      label: channel.name,
      value: channel.id
    }))
  ])

  const agioneDiagnostics = computed(() =>
    asArray(summary.value.agione?.diagnostics)
  )
  const summaryKpis = computed(() => asObject(summary.value.kpis))
  const diagnosticCounts = computed(() =>
    asObject(summary.value.agione?.diagnostic_counts)
  )

  const activeModels = computed(() =>
    asArray(models.value).filter((model) => model.is_active !== false)
  )

  const activeModelIds = computed(
    () => new Set(activeModels.value.map((model) => String(model.id)))
  )

  const operationalModelCount = computed(() =>
    numberOrFallback(summaryKpis.value.active_models, activeModels.value.length)
  )
  const operationalChannelCount = computed(() =>
    numberOrFallback(
      summaryKpis.value.active_channels,
      asArray(channels.value).length
    )
  )
  const enabledPriceSourceCount = computed(() =>
    numberOrFallback(
      summaryKpis.value.enabled_price_sources,
      asArray(providerCollectionSources.value).length
    )
  )
  const reconciliationAnomalyCount = computed(() =>
    numberOrFallback(summaryKpis.value.reconciliation_anomalies, 0)
  )

  const agioneListingRows = computed(() => {
    const agioneId = agionePlatform.value?.id
    if (!agioneId) return []
    return asArray(listings.value).filter(
      (listing) =>
        listing.is_active !== false &&
        String(listing.platform) === String(agioneId)
    )
  })

  const agioneListingModelIds = computed(() => {
    return new Set(
      agioneListingRows.value
        .filter((listing) => activeModelIds.value.has(String(listing.model)))
        .map((listing) => String(listing.model))
    )
  })

  const agioneListingsByModel = computed(() => {
    const rowsByModel = new Map()
    agioneListingRows.value.forEach((listing) => {
      const key = String(listing.model)
      const rows = rowsByModel.get(key) || []
      rows.push(listing)
      rowsByModel.set(key, rows)
    })
    return rowsByModel
  })

  const enrichedProcurementRows = computed(() =>
    (agioneDiagnostics.value.length
      ? agioneDiagnostics.value
      : procurementRows.value
    ).map((row) => {
      if (row.status) {
        const options = asArray(row.options)
        return {
          ...row,
          best_channel: row.best_channel || null,
          display_channel: row.best_channel || null,
          coverage_count: row.coverage_count ?? options.length,
          is_agione_listed: Boolean(row.is_agione_listed),
          has_lowest_listing: Boolean(row.has_lowest_listing),
          requires_currency_conversion: Boolean(
            row.requires_currency_conversion
          ),
          status_priority: row.status_priority || 5,
          status_label: localizedMonitorStatusLabel(row.status),
          status_tone: monitorStatusTone(row.status)
        }
      }
      const options = asArray(row.options)
      const bestChannel = row.best_channel || null
      const coverageCount = options.length
      const agioneListings =
        agioneListingsByModel.value.get(String(row.model_id)) || []
      const isAgioneListed = agioneListingModelIds.value.has(
        String(row.model_id)
      )
      const hasLowestListing = agioneListings.some((listing) =>
        isLowestListing(listing, bestChannel, options)
      )
      const status = resolveMonitorStatus({
        bestChannel,
        coverageCount,
        isAgioneListed,
        hasLowestListing,
        requiresCurrencyConversion: row.requires_currency_conversion || false
      })
      return {
        ...row,
        best_channel: bestChannel,
        display_channel: bestChannel,
        coverage_count: coverageCount,
        is_agione_listed: isAgioneListed,
        has_lowest_listing: hasLowestListing,
        requires_currency_conversion: row.requires_currency_conversion || false,
        ...status
      }
    })
  )

  const localListedCount = computed(() => agioneListingModelIds.value.size)
  const listedCount = computed(() =>
    numberOrFallback(
      summaryKpis.value.current_platform_listed_models,
      localListedCount.value
    )
  )
  const procuredCount = computed(
    () => enrichedProcurementRows.value.filter((row) => row.best_channel).length
  )
  const missingChannelRows = computed(() =>
    enrichedProcurementRows.value.filter((row) => !row.best_channel)
  )
  const currencyMismatchRows = computed(() =>
    enrichedProcurementRows.value.filter(
      (row) => row.requires_currency_conversion
    )
  )
  const unlistedRows = computed(() =>
    enrichedProcurementRows.value.filter((row) => !row.is_agione_listed)
  )
  const readyRows = computed(() =>
    enrichedProcurementRows.value.filter((row) => row.status_priority === 5)
  )
  const nonLowestRows = computed(() =>
    enrichedProcurementRows.value.filter(
      (row) =>
        row.best_channel && row.is_agione_listed && !row.has_lowest_listing
    )
  )
  const lowCoverageRows = computed(() =>
    enrichedProcurementRows.value.filter((row) => row.status_priority === 4)
  )
  const readyCount = computed(() =>
    numberOrFallback(summaryKpis.value.ready_models, readyRows.value.length)
  )
  const missingChannelCount = computed(() =>
    numberOrFallback(
      diagnosticCounts.value.missing_channel,
      missingChannelRows.value.length
    )
  )
  const currencyMismatchCount = computed(() =>
    numberOrFallback(
      diagnosticCounts.value.currency_mismatch,
      currencyMismatchRows.value.length
    )
  )
  const unlistedCount = computed(() =>
    numberOrFallback(diagnosticCounts.value.unlisted, unlistedRows.value.length)
  )
  const nonLowestCount = computed(() =>
    numberOrFallback(
      diagnosticCounts.value.not_lowest,
      nonLowestRows.value.length
    )
  )
  const lowCoverageCount = computed(() =>
    numberOrFallback(
      diagnosticCounts.value.low_coverage,
      lowCoverageRows.value.length
    )
  )

  const currentPlatformListingLabel = computed(() => {
    const platformName =
      summary.value.agione?.platform_name ||
      agionePlatform.value?.name ||
      'Agione'
    return t('llmOps.monitor.platformListed', { platform: platformName })
  })

  const kpiCards = computed(() => {
    const modelCount = operationalModelCount.value
    const channelCount = operationalChannelCount.value
    const procurementRate = percentage(procuredCount.value, modelCount)
    const listingRate = percentage(listedCount.value, modelCount)
    const readyRate = percentage(readyCount.value, modelCount)
    return [
      {
        label: t('llmOps.kpi.ready.label'),
        value: `${readyCount.value}/${modelCount}`,
        badge: `${readyRate}%`,
        hint: t('llmOps.kpi.ready.hint', { count: readyCount.value }),
        progress: readyRate,
        tone: readyRate >= 80 ? 'good' : 'warn',
        barClass: 'bg-emerald-500'
      },
      {
        label: t('llmOps.kpi.procurement.label'),
        value: `${procuredCount.value}/${modelCount}`,
        badge: `${procurementRate}%`,
        hint: t('llmOps.kpi.procurement.hint', {
          missing: missingChannelCount.value,
          currency: currencyMismatchCount.value
        }),
        progress: procurementRate,
        tone: procurementRate >= 80 ? 'good' : 'warn',
        barClass: 'bg-agione-500'
      },
      {
        label: t('llmOps.kpi.listing.label'),
        value: `${listedCount.value}/${modelCount}`,
        badge: `${listingRate}%`,
        hint: t('llmOps.kpi.listing.hint', {
          unlisted: unlistedCount.value,
          nonLowest: nonLowestCount.value
        }),
        progress: listingRate,
        tone: listingRate >= 80 ? 'good' : 'warn',
        barClass: 'bg-cyan-500'
      },
      {
        label: t('llmOps.kpi.channels.label'),
        value: channelCount,
        badge: t('llmOps.kpi.channels.badge', {
          count: enabledPriceSourceCount.value
        }),
        hint: t('llmOps.kpi.channels.hint'),
        progress: channelCount ? 100 : 0,
        tone: channelCount ? 'good' : 'danger',
        barClass: 'bg-violet-500'
      },
      {
        label: t('llmOps.kpi.reconciliation.label'),
        value: reconciliationAnomalyCount.value,
        badge: reconciliationAnomalyCount.value
          ? t('llmOps.status.needsHandling')
          : t('llmOps.status.normal'),
        hint: t('llmOps.kpi.reconciliation.hint'),
        progress: reconciliationAnomalyCount.value ? 100 : 0,
        tone: reconciliationAnomalyCount.value ? 'danger' : 'good',
        barClass: reconciliationAnomalyCount.value
          ? 'bg-rose-500'
          : 'bg-emerald-500'
      }
    ]
  })

  const actionItems = computed(() => [
    {
      label: t('llmOps.queue.fillChannelPrice.label'),
      hint: t('llmOps.queue.fillChannelPrice.hint'),
      value: missingChannelCount.value,
      tone: missingChannelCount.value ? 'danger' : 'good',
      section: 'channels'
    },
    {
      label: t('llmOps.queue.configureExchange.label'),
      hint: t('llmOps.queue.configureExchange.hint'),
      value: currencyMismatchCount.value,
      tone: currencyMismatchCount.value ? 'warn' : 'good',
      section: 'channels'
    },
    {
      label: t('llmOps.queue.publishToPlatform.label'),
      hint: t('llmOps.queue.publishToPlatform.hint'),
      value: unlistedCount.value,
      tone: unlistedCount.value ? 'warn' : 'good',
      section: 'reseller'
    },
    {
      label: t('llmOps.queue.switchLowestChannel.label'),
      hint: t('llmOps.queue.switchLowestChannel.hint'),
      value: nonLowestCount.value,
      tone: nonLowestCount.value ? 'warn' : 'good',
      section: 'reseller'
    },
    {
      label: t('llmOps.queue.addChannelCoverage.label'),
      hint: t('llmOps.queue.addChannelCoverage.hint'),
      value: lowCoverageCount.value,
      tone: lowCoverageCount.value ? 'warn' : 'good',
      section: 'channels'
    },
    {
      label: t('llmOps.queue.checkPriceSource.label'),
      hint: latestCollectionRun.value
        ? t('llmOps.queue.checkPriceSource.latestRun', {
            status: latestCollectionRun.value.status || '-',
            time: formatDateTime(
              latestCollectionRun.value.finished_at ||
                latestCollectionRun.value.started_at
            )
          })
        : t('llmOps.queue.checkPriceSource.empty'),
      value: collectionAttentionCount.value,
      tone: collectionAttentionCount.value ? 'danger' : 'good',
      section: 'taskLogs'
    },
    {
      label: t('llmOps.queue.handleReconciliation.label'),
      hint: t('llmOps.queue.handleReconciliation.hint'),
      value: reconciliationAnomalyCount.value,
      tone: reconciliationAnomalyCount.value ? 'danger' : 'good',
      section: 'reconciler'
    }
  ])

  const latestCollectionRun = computed(
    () =>
      asArray(collectionRuns.value)
        .slice()
        .sort(
          (left, right) =>
            new Date(
              right.finished_at || right.started_at || right.created_at || 0
            ).getTime() -
            new Date(
              left.finished_at || left.started_at || left.created_at || 0
            ).getTime()
        )[0] || null
  )

  const collectionAttentionCount = computed(
    () =>
      asArray(collectionRuns.value).filter((run) =>
        ['failed', 'running', 'pending', 'processing'].includes(run.status)
      ).length
  )

  const channelCoverageRows = computed(() =>
    asArray(channels.value)
      .map((channel) => {
        const covered = asArray(procurementRows.value).filter((row) =>
          asArray(row.options).some(
            (option) => String(option.channel_id) === String(channel.id)
          )
        ).length
        const bestCount = asArray(procurementRows.value).filter(
          (row) => String(row.best_channel?.channel_id) === String(channel.id)
        ).length
        return {
          ...channel,
          covered,
          best_count: bestCount,
          coverage_rate: percentage(covered, operationalModelCount.value)
        }
      })
      .sort((left, right) => right.covered - left.covered)
  )

  const providerCoverageRows = computed(() => {
    const rowsByProvider = new Map()
    enrichedProcurementRows.value.forEach((row) => {
      const providerName = row.provider_name || '-'
      const rows = rowsByProvider.get(providerName) || []
      rows.push(row)
      rowsByProvider.set(providerName, rows)
    })
    return Array.from(rowsByProvider.entries())
      .map(([providerName, providerRows]) => {
        const procured = providerRows.filter((row) => row.best_channel).length
        const listed = providerRows.filter((row) => row.is_agione_listed).length
        const ready = providerRows.filter(
          (row) => row.status_priority === 5
        ).length
        return {
          name: providerName,
          model_count: providerRows.length,
          procured_count: procured,
          listed_count: listed,
          todo_count: Math.max(providerRows.length - ready, 0),
          ready_rate: percentage(ready, providerRows.length)
        }
      })
      .sort((left, right) => right.model_count - left.model_count)
  })

  const filteredProcurementRows = computed(() => {
    const rows = enrichedProcurementRows.value
    if (!simulationChannel.value) {
      return rows.map((row) => ({ ...row, display_channel: row.best_channel }))
    }
    return rows
      .map((row) => {
        const option = row.options?.find(
          (item) => String(item.channel_id) === String(simulationChannel.value)
        )
        return { ...row, display_channel: option || null }
      })
      .filter((row) => row.display_channel)
  })

  const monitorTableRows = computed(() => {
    const rows = filteredProcurementRows.value.filter((row) => {
      if (simulationStatus.value === 'all') return true
      if (simulationStatus.value === 'currency_mismatch') {
        return row.requires_currency_conversion
      }
      if (simulationStatus.value === 'missing_channel') return !row.best_channel
      if (simulationStatus.value === 'unlisted') return !row.is_agione_listed
      if (simulationStatus.value === 'ready') {
        return (
          row.best_channel && row.is_agione_listed && row.has_lowest_listing
        )
      }
      return (
        !row.best_channel ||
        !row.is_agione_listed ||
        !row.has_lowest_listing ||
        row.coverage_count <= 1
      )
    })
    return rows.slice().sort((left, right) => {
      if (left.status_priority !== right.status_priority) {
        return left.status_priority - right.status_priority
      }
      return String(left.provider_name).localeCompare(
        String(right.provider_name)
      )
    })
  })

  function isLowestListing(listing, bestChannel, options) {
    if (!bestChannel) return false
    if (!listing.channel) return true
    const option = options.find(
      (item) => String(item.channel_id) === String(listing.channel)
    )
    return String(option?.channel_id) === String(bestChannel.channel_id)
  }

  function resolveMonitorStatus({
    bestChannel,
    coverageCount,
    isAgioneListed,
    hasLowestListing,
    requiresCurrencyConversion
  }) {
    if (requiresCurrencyConversion) {
      return {
        status_label: t('llmOps.status.currencyMismatch'),
        status_tone: 'info',
        status_priority: 1
      }
    }
    if (!bestChannel) {
      return {
        status_label: t('llmOps.status.missingChannel'),
        status_tone: 'danger',
        status_priority: 1
      }
    }
    if (!isAgioneListed) {
      return {
        status_label: t('llmOps.status.readyToList'),
        status_tone: 'warn',
        status_priority: 2
      }
    }
    if (!hasLowestListing) {
      return {
        status_label: t('llmOps.status.notLowest'),
        status_tone: 'warn',
        status_priority: 3
      }
    }
    if (coverageCount <= 1) {
      return {
        status_label: t('llmOps.status.lowCoverage'),
        status_tone: 'info',
        status_priority: 4
      }
    }
    return {
      status_label: t('llmOps.status.ready'),
      status_tone: 'success',
      status_priority: 5
    }
  }

  function monitorStatusTone(status) {
    const tones = {
      currency_mismatch: 'info',
      not_lowest: 'warn',
      missing_channel: 'danger',
      unlisted: 'warn',
      low_coverage: 'info',
      ready: 'success'
    }
    return tones[status] || 'success'
  }

  function localizedMonitorStatusLabel(status) {
    const labelKey = monitorStatusLabelKeys[status]
    return labelKey ? t(labelKey) : t('llmOps.status.readyShort')
  }

  return {
    actionItems,
    channelCoverageRows,
    currentPlatformListingLabel,
    kpiCards,
    monitorModelSubtitle,
    monitorTableRows,
    money,
    operationalChannelCount,
    providerCoverageRows,
    simulationChannel,
    simulationChannelOptions,
    simulationStatus,
    simulationStatusOptions
  }
}

function percentage(value, total) {
  if (!total) return 0
  return Math.round((Number(value || 0) / Number(total)) * 100)
}

function numberOrFallback(value, fallback = 0) {
  const numberValue = Number(value)
  if (Number.isFinite(numberValue)) return numberValue
  return Number(fallback || 0)
}

function monitorModelSubtitle(row) {
  const name = String(row.model_name || '').trim()
  const code = String(row.model_code || '').trim()
  if (code && code !== name) return code
  return ''
}

function money(value, currency = 'USD') {
  if (value === null || value === undefined || value === '') return '-'
  return `${currency || 'USD'} ${Number(value).toFixed(4)}`
}

function formatDateTime(value) {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}
