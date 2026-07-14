<template>
  <section class="space-y-4">
    <div class="grid gap-4 md:grid-cols-4">
      <div v-for="item in metrics" :key="item.label" class="kpi-card">
        <p class="text-xs font-medium text-slate-500">{{ item.label }}</p>
        <div class="mt-2 flex items-end justify-between gap-3">
          <p class="kpi-value text-2xl font-semibold">{{ item.value }}</p>
          <span :class="['kpi-tone', item.tone]">{{ item.badge }}</span>
        </div>
        <p class="mt-2 text-xs text-slate-500">{{ item.hint }}</p>
      </div>
    </div>

    <div class="panel overflow-hidden p-0">
      <div class="table-toolbar">
        <div>
          <h3 class="panel-title">
            {{ t('llmOps.collectionHealthPanel.title') }}
          </h3>
          <p class="mt-1 text-xs text-slate-500">
            {{ t('llmOps.collectionHealthPanel.subtitle') }}
          </p>
        </div>
      </div>
      <div class="overflow-x-auto">
        <table class="data-table">
          <thead>
            <tr>
              <th class="table-head">
                {{ t('llmOps.collectionHealthPanel.columns.source') }}
              </th>
              <th class="table-head">
                {{ t('llmOps.collectionHealthPanel.columns.type') }}
              </th>
              <th class="table-head">
                {{ t('llmOps.collectionHealthPanel.columns.latestStatus') }}
              </th>
              <th class="table-head text-right">
                {{ t('llmOps.collectionHealthPanel.columns.successRate') }}
              </th>
              <th class="table-head text-right">
                {{
                  t('llmOps.collectionHealthPanel.columns.consecutiveFailures')
                }}
              </th>
              <th class="table-head">
                {{ t('llmOps.collectionHealthPanel.columns.lastCollected') }}
              </th>
              <th class="table-head">
                {{ t('llmOps.collectionHealthPanel.columns.health') }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in sourceRows" :key="row.id">
              <td class="table-cell">
                <p class="font-medium text-slate-900">{{ row.name }}</p>
                <p class="mt-1 font-mono text-xs text-slate-500">
                  {{ row.slug }}
                </p>
              </td>
              <td class="table-cell">{{ sourceCategoryLabel(row) }}</td>
              <td class="table-cell">
                <span :class="['status-pill', statusTone(row.latestStatus)]">
                  {{ statusLabel(row.latestStatus) }}
                </span>
              </td>
              <td class="table-cell text-right font-mono">
                {{ row.successRate }}%
              </td>
              <td class="table-cell text-right font-mono">
                {{ row.consecutiveFailures }}
              </td>
              <td class="table-cell">
                {{ formatDateTime(row.lastCollectedAt) }}
              </td>
              <td class="table-cell">
                <span :class="['status-pill', row.healthTone]">
                  {{ row.healthLabel }}
                </span>
              </td>
            </tr>
            <tr v-if="!sourceRows.length">
              <td class="table-cell text-slate-500" colspan="7">
                {{ t('llmOps.collectionHealthPanel.empty') }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import {
  priceSourceCollectionMethod,
  priceSourceCollectionMethodLabel
} from '@/utils/llmOpsPriceSources'

const props = defineProps({
  sources: { type: Array, default: () => [] },
  runs: { type: Array, default: () => [] }
})

const { t } = useI18n()

const sourceRows = computed(() =>
  props.sources
    .filter((source) => source.source_type !== 'agione')
    .map((source) => {
      const runs = props.runs
        .filter((run) => String(run.source) === String(source.id))
        .sort((left, right) => runTime(right) - runTime(left))
      const succeeded = runs.filter((run) => run.status === 'succeeded').length
      const latestRun = runs[0] || null
      const lastCollectedAt =
        source.last_collected_at ||
        latestRun?.finished_at ||
        latestRun?.started_at ||
        null
      const stale = isStale(lastCollectedAt)
      const failures = consecutiveFailures(runs)
      const health = healthState({
        enabled: source.is_enabled !== false,
        stale,
        failures,
        latestStatus: latestRun?.status || ''
      })
      return {
        ...source,
        latestStatus: latestRun?.status || '',
        successRate: percentage(succeeded, runs.length),
        consecutiveFailures: failures,
        lastCollectedAt,
        healthLabel: health.label,
        healthTone: health.tone
      }
    })
    .sort((left, right) => {
      if (left.healthTone !== right.healthTone) {
        return healthRank(left.healthTone) - healthRank(right.healthTone)
      }
      return String(left.name).localeCompare(String(right.name))
    })
)

const metrics = computed(() => {
  const total = sourceRows.value.length
  const healthy = sourceRows.value.filter(
    (row) => row.healthTone === 'success'
  ).length
  const failed = sourceRows.value.filter(
    (row) => row.healthTone === 'danger'
  ).length
  const stale = sourceRows.value.filter(
    (row) => row.healthTone === 'warn'
  ).length
  return [
    {
      label: t('llmOps.collectionHealthPanel.metrics.total.label'),
      value: total,
      badge: `${percentage(healthy, total)}%`,
      hint: t('llmOps.collectionHealthPanel.metrics.total.hint'),
      tone: healthy === total && total ? 'good' : 'warn'
    },
    {
      label: t('llmOps.collectionHealthPanel.metrics.healthy.label'),
      value: healthy,
      badge: t('llmOps.collectionHealthPanel.badges.normal'),
      hint: t('llmOps.collectionHealthPanel.metrics.healthy.hint'),
      tone: healthy ? 'good' : 'warn'
    },
    {
      label: t('llmOps.collectionHealthPanel.metrics.failed.label'),
      value: failed,
      badge: failed
        ? t('llmOps.collectionHealthPanel.badges.needsHandling')
        : t('llmOps.collectionHealthPanel.badges.normal'),
      hint: t('llmOps.collectionHealthPanel.metrics.failed.hint'),
      tone: failed ? 'danger' : 'good'
    },
    {
      label: t('llmOps.collectionHealthPanel.metrics.stale.label'),
      value: stale,
      badge: t('llmOps.collectionHealthPanel.badges.sevenDayThreshold'),
      hint: t('llmOps.collectionHealthPanel.metrics.stale.hint'),
      tone: stale ? 'warn' : 'good'
    }
  ]
})

function runTime(run) {
  return new Date(
    run.finished_at || run.started_at || run.created_at || 0
  ).getTime()
}

function consecutiveFailures(runs) {
  let count = 0
  for (const run of runs) {
    if (run.status !== 'failed') break
    count += 1
  }
  return count
}

function isStale(value) {
  if (!value) return true
  const ageMs = Date.now() - new Date(value).getTime()
  return ageMs > 7 * 24 * 60 * 60 * 1000
}

function healthState({ enabled, stale, failures, latestStatus }) {
  if (!enabled) {
    return {
      label: t('llmOps.collectionHealthPanel.health.disabled'),
      tone: 'info'
    }
  }
  if (failures > 0 || latestStatus === 'failed') {
    return {
      label: t('llmOps.collectionHealthPanel.health.failed'),
      tone: 'danger'
    }
  }
  if (stale) {
    return {
      label: t('llmOps.collectionHealthPanel.health.stale'),
      tone: 'warn'
    }
  }
  return {
    label: t('llmOps.collectionHealthPanel.health.healthy'),
    tone: 'success'
  }
}

function healthRank(tone) {
  return { danger: 1, warn: 2, info: 3, success: 4 }[tone] || 5
}

function sourceCategoryLabel(source) {
  const method = priceSourceCollectionMethod(source)
  return priceSourceCollectionMethodLabel(method, collectionMethodLabels())
}

function statusLabel(status) {
  return (
    {
      succeeded: t('llmOps.collectionHealthPanel.runStatus.succeeded'),
      failed: t('llmOps.collectionHealthPanel.runStatus.failed'),
      running: t('llmOps.collectionHealthPanel.runStatus.running')
    }[status] || t('llmOps.collectionHealthPanel.runStatus.none')
  )
}

function collectionMethodLabels() {
  return {
    auto_collect: t(
      'llmOps.collectionHealthPanel.collectionMethod.autoCollect'
    ),
    api_sync: t('llmOps.collectionHealthPanel.collectionMethod.apiSync'),
    manual_entry: t(
      'llmOps.collectionHealthPanel.collectionMethod.manualEntry'
    ),
    manual_import: t(
      'llmOps.collectionHealthPanel.collectionMethod.manualImport'
    ),
    unknown: t('llmOps.collectionHealthPanel.collectionMethod.unknown')
  }
}

function statusTone(status) {
  return (
    {
      succeeded: 'success',
      failed: 'danger',
      running: 'info'
    }[status] || 'info'
  )
}

function percentage(value, total) {
  if (!total) return 0
  return Math.round((Number(value || 0) / Number(total)) * 100)
}

function formatDateTime(value) {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}
</script>
