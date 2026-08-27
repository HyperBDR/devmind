import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import {
  isMonitorRowVisible,
  operationScopeForRow,
  summarizeMonitorRows
} from '@/utils/llmOpsMonitor'
import { asArray } from '@/utils/llmOpsPagination'

export function useLLMOpsMonitor({ summary }) {
  const { t } = useI18n()

  const simulationStatus = ref('priority')

  const simulationStatusOptions = computed(() => [
    {
      label: t('llmOps.overview.filters.operationalPriority'),
      value: 'priority'
    },
    {
      label: t('llmOps.overview.filters.operational'),
      value: 'operational'
    },
    {
      label: t('llmOps.decision.status.ready'),
      value: 'ready'
    },
    {
      label: t('llmOps.overview.filters.marketReference'),
      value: 'market_reference'
    }
  ])

  const agioneDiagnostics = computed(() =>
    asArray(summary.value.agione?.diagnostics)
  )
  const enrichedProcurementRows = computed(() =>
    agioneDiagnostics.value.map((row) => {
      const operationScope = operationScopeForRow(row)
      const decisionStatus = row.decision_status || 'ready'
      const decisionPriority = row.decision_priority ?? 8
      return {
        ...row,
        operation_scope: operationScope,
        decision_status: decisionStatus,
        decision_priority: decisionPriority,
        input_yield: row.yield_metrics?.input_yield ?? null,
        output_yield: row.yield_metrics?.output_yield ?? null,
        data_event_type: row.data_event_type || 'updated',
        last_data_event_at: row.last_data_event_at || null,
        status_tone: decisionTone(decisionStatus)
      }
    })
  )

  const kpiCards = computed(() => {
    const counts = summarizeMonitorRows(enrichedProcurementRows.value)
    const overview = summary.value.agione?.overview || {}
    return [
      {
        key: 'active_model_skus',
        label: t('llmOps.overview.kpi.activeModelSkus.label'),
        value: Number(overview.active_model_skus || 0),
        section: 'modelWorkbench',
        tone: 'info'
      },
      {
        key: 'operational_models',
        label: t('llmOps.overview.kpi.operationalModels.label'),
        value: Number(overview.operational_models || 0),
        filter: 'operational',
        tone: 'info'
      },
      {
        key: 'channel_coverage_rate',
        label: t('llmOps.overview.kpi.channelCoverageRate.label'),
        value: formatPercent(overview.channel_coverage_rate),
        section: 'channelMatrix',
        tone: rateTone(overview.channel_coverage_rate)
      },
      {
        key: 'listing_coverage_rate',
        label: t('llmOps.overview.kpi.listingCoverageRate.label'),
        value: formatPercent(overview.listing_coverage_rate),
        section: 'listingRisk',
        tone: rateTone(overview.listing_coverage_rate)
      },
      {
        key: 'unlisted_models',
        label: t('llmOps.overview.kpi.unlistedModels.label'),
        value: Number(overview.unlisted_models || 0),
        filter: 'unlisted',
        tone: Number(overview.unlisted_models || 0) ? 'warn' : 'success'
      },
      {
        key: 'meta_models',
        label: t('llmOps.overview.kpi.metaModels.label'),
        value: Number(overview.meta_models || 0),
        section: 'metaModels',
        tone: 'info'
      },
      {
        key: 'price_sources',
        label: t('llmOps.overview.kpi.priceSources.label'),
        value: Number(overview.enabled_price_sources || 0),
        section: 'providers',
        tone: 'info'
      },
      {
        key: 'channels',
        label: t('llmOps.overview.kpi.channels.label'),
        value: Number(overview.active_channels || 0),
        section: 'channels',
        tone: 'info'
      },
      {
        key: 'listings',
        label: t('llmOps.overview.kpi.activeListings.label'),
        value: Number(overview.active_listings || 0),
        section: 'listingRisk',
        tone: 'success'
      },
      {
        key: 'overall_yield',
        label: t('llmOps.overview.kpi.overallYield.label'),
        value: formatPercent(overview.overall_yield),
        section: 'listingRisk',
        tone: overview.overall_yield === null ? 'info' : 'success'
      },
      {
        key: 'median_yield',
        label: t('llmOps.overview.kpi.medianYield.label'),
        value: formatPercent(overview.median_yield),
        section: 'listingRisk',
        tone: overview.median_yield === null ? 'info' : 'success'
      },
      {
        key: 'unresolved_yield_models',
        label: t('llmOps.overview.kpi.unresolvedYieldModels.label'),
        value: Number(overview.unresolved_yield_models || 0),
        filter: 'priority',
        tone: Number(overview.unresolved_yield_models || 0)
          ? 'warn'
          : 'success'
      },
      {
        key: 'price_source_health_rate',
        label: t('llmOps.overview.kpi.priceSourceHealthRate.label'),
        value: formatPercent(overview.price_source_health_rate),
        section: 'collectionHealth',
        tone: rateTone(overview.price_source_health_rate)
      },
      {
        key: 'risk_points',
        label: t('llmOps.overview.kpi.riskPoints.label'),
        value: Number(overview.risk_points || 0),
        filter: 'priority',
        tone: Number(overview.risk_points || 0) ? 'danger' : 'success'
      },
      {
        key: 'needs_action',
        label: t('llmOps.overview.kpi.needsAction.label'),
        value: counts.needsAction,
        filter: 'priority',
        tone: counts.needsAction ? 'warn' : 'success'
      },
      {
        key: 'missing_channel',
        label: t('llmOps.overview.kpi.missingChannel.label'),
        value: counts.missingChannel,
        filter: 'no_supply',
        tone: counts.missingChannel ? 'danger' : 'success'
      },
      {
        key: 'pending_listing',
        label: t('llmOps.overview.kpi.pendingListing.label'),
        value: counts.pendingListing,
        filter: 'unlisted',
        tone: counts.pendingListing ? 'warn' : 'success'
      },
      {
        key: 'low_yield',
        label: t('llmOps.overview.kpi.lowYield.label'),
        value: counts.lowYield,
        filter: 'low_yield',
        tone: counts.lowYield ? 'danger' : 'success'
      }
    ]
  })

  const monitorTableRows = computed(() => {
    const rows = enrichedProcurementRows.value.filter((row) =>
      isMonitorRowVisible(row, simulationStatus.value)
    )
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
    ready: 'success',
    market_reference: 'info'
  }

  function decisionTone(status) {
    return DECISION_TONE[status] || 'info'
  }

  return {
    kpiCards,
    monitorModelSubtitle,
    monitorTableRows,
    simulationStatus,
    simulationStatusOptions
  }
}

function formatPercent(value) {
  if (value === null || value === undefined || value === '') return '-'
  const numericValue = Number(value)
  if (!Number.isFinite(numericValue)) return '-'
  return `${(numericValue * 100).toFixed(1)}%`
}

function rateTone(value) {
  if (value === null || value === undefined || value === '') return 'info'
  return Number(value) < 1 ? 'warn' : 'success'
}

function monitorModelSubtitle(row) {
  const name = String(row.model_name || '').trim()
  const code = String(row.model_code || '').trim()
  if (code && code !== name) return code
  return ''
}
