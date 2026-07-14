import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { asArray, asObject } from '@/utils/llmOpsPagination'

export function useLLMOpsMonitor({ channels, procurementRows, summary }) {
  const { t } = useI18n()

  const simulationStatus = ref('priority')

  const simulationStatusOptions = computed(() => [
    { label: t('llmOps.filters.priority'), value: 'priority' },
    { label: t('llmOps.filters.allModels'), value: 'all' },
    { label: t('llmOps.decision.status.no_supply'), value: 'no_supply' },
    {
      label: t('llmOps.decision.status.currency_unresolved'),
      value: 'currency_unresolved'
    },
    {
      label: t('llmOps.decision.status.platform_fee_unresolved'),
      value: 'platform_fee_unresolved'
    },
    { label: t('llmOps.decision.status.low_yield'), value: 'low_yield' },
    {
      label: t('llmOps.decision.status.not_lowest_channel'),
      value: 'not_lowest_channel'
    },
    { label: t('llmOps.decision.status.unlisted'), value: 'unlisted' },
    {
      label: t('llmOps.decision.status.single_channel'),
      value: 'single_channel'
    },
    { label: t('llmOps.decision.status.ready'), value: 'ready' }
  ])

  const agioneDiagnostics = computed(() =>
    asArray(summary.value.agione?.diagnostics)
  )
  const summaryKpis = computed(() => asObject(summary.value.kpis))

  const operationalChannelCount = computed(() =>
    numberOrFallback(
      summaryKpis.value.active_channels,
      asArray(channels.value).length
    )
  )

  const enrichedProcurementRows = computed(() =>
    (agioneDiagnostics.value.length
      ? agioneDiagnostics.value
      : procurementRows.value
    ).map((row) => {
      const options = asArray(row.options)
      const bestChannel = row.best_channel || null
      const decisionStatus = row.decision_status || 'ready'
      return {
        ...row,
        best_channel: bestChannel,
        display_channel: bestChannel,
        coverage_count: row.coverage_count ?? options.length,
        is_agione_listed: Boolean(row.is_agione_listed),
        has_lowest_listing: Boolean(row.has_lowest_listing),
        requires_currency_conversion: Boolean(row.requires_currency_conversion),
        decision_status: decisionStatus,
        decision_action: row.decision_action || '',
        decision_priority: row.decision_priority || 8,
        input_yield: row.yield_metrics?.input_yield ?? null,
        output_yield: row.yield_metrics?.output_yield ?? null,
        data_event_type: row.data_event_type || 'updated',
        last_data_event_at: row.last_data_event_at || null,
        status_label: '',
        status_tone: decisionTone(decisionStatus),
        status_priority: row.decision_priority || 8
      }
    })
  )

  const kpiCards = computed(() => {
    const total = enrichedProcurementRows.value.length || 1
    const pendingListing = enrichedProcurementRows.value.filter(
      (row) => row.decision_status === 'unlisted'
    ).length
    const missingChannel = enrichedProcurementRows.value.filter(
      (row) => row.decision_status === 'no_supply'
    ).length
    const lowYield = enrichedProcurementRows.value.filter(
      (row) => row.decision_status === 'low_yield'
    ).length
    const dataAnomaly = enrichedProcurementRows.value.filter(
      (row) => row.is_data_anomaly
    ).length
    return [
      {
        key: 'pending_listing',
        group: 'supply',
        label: t('llmOps.overview.kpi.pendingListing.label'),
        value: pendingListing,
        badge: `${percentage(pendingListing, total)}%`,
        hint: t('llmOps.overview.kpi.pendingListing.hint'),
        progress: percentage(pendingListing, total),
        tone: pendingListing ? 'warn' : 'good',
        barClass: 'bg-agione-500'
      },
      {
        key: 'missing_channel',
        group: 'supply',
        label: t('llmOps.overview.kpi.missingChannel.label'),
        value: missingChannel,
        badge: `${percentage(missingChannel, total)}%`,
        hint: t('llmOps.overview.kpi.missingChannel.hint'),
        progress: percentage(missingChannel, total),
        tone: missingChannel ? 'danger' : 'good',
        barClass: 'bg-rose-500'
      },
      {
        key: 'low_yield',
        group: 'yield',
        label: t('llmOps.overview.kpi.lowYield.label'),
        value: lowYield,
        badge: `${percentage(lowYield, total)}%`,
        hint: t('llmOps.overview.kpi.lowYield.hint'),
        progress: percentage(lowYield, total),
        tone: lowYield ? 'danger' : 'good',
        barClass: 'bg-amber-500'
      },
      {
        key: 'data_anomaly',
        group: 'data',
        label: t('llmOps.overview.kpi.dataAnomaly.label'),
        value: dataAnomaly,
        badge: dataAnomaly
          ? t('llmOps.status.needsHandling')
          : t('llmOps.status.normal'),
        hint: t('llmOps.overview.kpi.dataAnomaly.hint'),
        progress: dataAnomaly ? 100 : 0,
        tone: dataAnomaly ? 'danger' : 'good',
        barClass: dataAnomaly ? 'bg-rose-500' : 'bg-emerald-500'
      }
    ]
  })

  const filteredProcurementRows = computed(() => {
    return enrichedProcurementRows.value.map((row) => ({
      ...row,
      display_channel: row.best_channel
    }))
  })

  const monitorTableRows = computed(() => {
    const rows = filteredProcurementRows.value.filter((row) => {
      if (simulationStatus.value === 'all') return true
      return (
        row.decision_status === simulationStatus.value ||
        (simulationStatus.value === 'priority' &&
          (row.decision_priority < 8 || row.is_data_anomaly))
      )
    })
    const inputYieldMagnitude = (row) => {
      const value = Number(row.input_yield)
      if (Number.isFinite(value)) return Math.abs(value)
      return 0
    }
    return rows.slice().sort((left, right) => {
      if (left.decision_priority !== right.decision_priority) {
        return left.decision_priority - right.decision_priority
      }
      const yl = inputYieldMagnitude(right) - inputYieldMagnitude(left)
      if (yl !== 0) return yl
      const lt = left.last_data_event_at || ''
      const rt = right.last_data_event_at || ''
      if (lt !== rt) return lt.localeCompare(rt)
      return String(left.provider_name || '').localeCompare(
        String(right.provider_name || '')
      )
    })
  })

  const DECISION_TONE = {
    no_supply: 'danger',
    currency_unresolved: 'info',
    platform_fee_unresolved: 'info',
    low_yield: 'danger',
    not_lowest_channel: 'warn',
    unlisted: 'warn',
    single_channel: 'info',
    ready: 'success'
  }

  function decisionTone(status) {
    return DECISION_TONE[status] || 'info'
  }

  return {
    kpiCards,
    monitorModelSubtitle,
    monitorTableRows,
    operationalChannelCount,
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
