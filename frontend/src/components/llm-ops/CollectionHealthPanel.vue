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
          <h3 class="panel-title">采集健康度看板</h3>
          <p class="mt-1 text-xs text-slate-500">
            按价格源查看最近采集、连续失败和数据新鲜度。
          </p>
        </div>
      </div>
      <div class="overflow-x-auto">
        <table class="data-table">
          <thead>
            <tr>
              <th class="table-head">价格源</th>
              <th class="table-head">类型</th>
              <th class="table-head">最近状态</th>
              <th class="table-head text-right">成功率</th>
              <th class="table-head text-right">连续失败</th>
              <th class="table-head">最近采集</th>
              <th class="table-head">健康状态</th>
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
                暂无价格源。
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

const props = defineProps({
  sources: { type: Array, default: () => [] },
  runs: { type: Array, default: () => [] }
})

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
      label: '价格源总数',
      value: total,
      badge: `${percentage(healthy, total)}%`,
      hint: '启用的官方、供应商和手工价格源',
      tone: healthy === total && total ? 'good' : 'warn'
    },
    {
      label: '健康价格源',
      value: healthy,
      badge: '正常',
      hint: '最近一次采集成功且未超过新鲜度窗口',
      tone: healthy ? 'good' : 'warn'
    },
    {
      label: '采集失败',
      value: failed,
      badge: failed ? '需处理' : '正常',
      hint: '最近任务失败或存在连续失败',
      tone: failed ? 'danger' : 'good'
    },
    {
      label: '数据过期',
      value: stale,
      badge: '7天阈值',
      hint: '最近采集时间超过 7 天',
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
  if (!enabled) return { label: '已停用', tone: 'info' }
  if (failures > 0 || latestStatus === 'failed') {
    return { label: '采集失败', tone: 'danger' }
  }
  if (stale) return { label: '数据过期', tone: 'warn' }
  return { label: '健康', tone: 'success' }
}

function healthRank(tone) {
  return { danger: 1, warn: 2, info: 3, success: 4 }[tone] || 5
}

function sourceCategoryLabel(source) {
  const labels = {
    official_provider: '官方源',
    supplier: '供应商',
    manual: '手工',
    unknown: '未知'
  }
  return labels[source.source_category] || source.source_category || '-'
}

function statusLabel(status) {
  return (
    {
      succeeded: '成功',
      failed: '失败',
      running: '运行中'
    }[status] || '暂无'
  )
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
