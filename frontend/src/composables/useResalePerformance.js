import { computed } from 'vue'

export function useResalePerformance({ selectedChainRows, t }) {
  const perfCompareRows = computed(() =>
    selectedChainRows.value.map((row) => ({
      id: row.uniqueId,
      name: performanceRowName(row),
      rpm: row.rpmLimit,
      tpm: row.tpmLimit,
      latency: row.latencyMs
    }))
  )

  const perfMetrics = computed(() => {
    const rpmMax = Math.max(1, ...perfCompareRows.value.map((r) => r.rpm))
    const tpmMax = Math.max(1, ...perfCompareRows.value.map((r) => r.tpm))
    const latMax = Math.max(1, ...perfCompareRows.value.map((r) => r.latency))
    return [
      {
        key: 'rpm',
        label: t('llmOps.publishingWorkspace.performance.rpm'),
        max: rpmMax,
        format: (v) => formatPerformanceValue(v, 'K', 1000),
        barClass: () => 'bg-violet-500'
      },
      {
        key: 'tpm',
        label: t('llmOps.publishingWorkspace.performance.tpm'),
        max: tpmMax,
        format: (v) => formatPerformanceValue(v, 'M', 1000000),
        barClass: () => 'bg-emerald-500'
      },
      {
        key: 'latency',
        label: t('llmOps.publishingWorkspace.performance.latency'),
        max: latMax,
        format: (v) => (Number.isFinite(v) ? `${v}ms` : '-'),
        barClass: () => 'bg-amber-500'
      }
    ]
  })

  function performanceRowName(row) {
    const channelName = row.channelName || row.supplierName || row.source
    const modelName = row.skuModelName || row.modelName
    if (!channelName) {
      return modelName || t('llmOps.publishingWorkspace.supply.chainFallback')
    }
    if (!modelName || modelName === row.modelName) return channelName
    return `${channelName} · ${modelName}`
  }

  function numberOrNull(value) {
    if (value === null || value === undefined || value === '') return null
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : null
  }

  function formatPerformanceValue(value, suffix, divisor) {
    if (!Number.isFinite(value)) return '-'
    if (!value) return '0'
    return `${(value / divisor).toFixed(1)}${suffix}`
  }

  function barWidth(value, max) {
    if (!Number.isFinite(value) || !Number.isFinite(max) || max <= 0) {
      return '0%'
    }
    return `${Math.max(2, (value / max) * 100)}%`
  }

  return {
    barWidth,
    numberOrNull,
    perfCompareRows,
    perfMetrics
  }
}
