<template>
  <section
    class="overflow-hidden rounded-xl border border-slate-200 bg-white"
    aria-labelledby="sync-job-history-title"
  >
    <header
      class="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 px-4 py-3"
    >
      <div>
        <h3
          id="sync-job-history-title"
          class="text-sm font-bold text-slate-950"
        >
          {{ t('dataOps.sync.records.title') }}
        </h3>
        <p class="mt-1 text-xs text-slate-500">
          {{ t('dataOps.sync.records.subtitle') }}
        </p>
      </div>
      <span class="text-xs font-semibold text-slate-400">
        {{ t('dataOps.sync.records.recent', { count: jobs.length }) }}
      </span>
    </header>

    <p
      v-if="!jobViews.length"
      class="px-4 py-8 text-center text-sm text-slate-400"
    >
      {{ t('dataOps.sync.records.empty') }}
    </p>

    <div v-else class="divide-y divide-slate-100">
      <details v-for="item in jobViews" :key="item.job.id" class="group">
        <summary
          class="grid cursor-pointer list-none gap-3 px-4 py-3 transition-colors hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-slate-400 sm:grid-cols-[minmax(0,1fr)_minmax(240px,auto)_auto] sm:items-center [&::-webkit-details-marker]:hidden"
        >
          <div class="min-w-0">
            <div class="flex flex-wrap items-center gap-2">
              <span
                class="rounded-full px-2 py-0.5 text-xs font-bold"
                :class="statusMeta(item.job.status).className"
              >
                {{ statusMeta(item.job.status).label }}
              </span>
              <strong class="truncate text-sm text-slate-900">
                {{ item.scope }}
              </strong>
            </div>
            <p class="mt-1 truncate text-xs text-slate-500">
              {{ formatDateTime(item.job.started_at, locale) }}
              <span v-if="item.duration"> · {{ item.duration }}</span>
            </p>
          </div>

          <div class="flex flex-wrap gap-x-4 gap-y-1 text-xs">
            <span class="text-emerald-700">
              {{ t('dataOps.sync.records.created') }}
              <strong>{{ item.summary.created }}</strong>
            </span>
            <span class="text-sky-700">
              {{ t('dataOps.sync.records.updated') }}
              <strong>{{ item.summary.updated }}</strong>
            </span>
            <span class="text-rose-700">
              {{ t('dataOps.sync.records.deleted') }}
              <strong>{{ item.summary.deleted }}</strong>
            </span>
            <span class="text-slate-500">
              {{ t('dataOps.sync.records.read') }}
              <strong>{{ item.summary.sourceRecords }}</strong>
            </span>
          </div>

          <span
            class="inline-flex items-center gap-1 text-xs font-semibold text-slate-500"
          >
            {{ t('dataOps.sync.records.viewDetails') }}
            <svg
              aria-hidden="true"
              class="h-4 w-4 transition-transform group-open:rotate-180"
              fill="none"
              stroke="currentColor"
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="1.8"
              viewBox="0 0 24 24"
            >
              <path d="m6 9 6 6 6-6" />
            </svg>
          </span>
        </summary>

        <div class="border-t border-slate-100 bg-slate-50 px-4 py-4">
          <div class="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-6">
            <div
              v-for="metric in detailMetrics(item.summary)"
              :key="metric.label"
              class="rounded-lg bg-white px-3 py-2"
            >
              <p class="text-xs text-slate-500">{{ metric.label }}</p>
              <p class="mt-1 text-sm font-bold text-slate-900">
                {{ metric.value }}
              </p>
            </div>
          </div>

          <p
            v-if="item.job.error_message"
            class="mt-3 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700"
          >
            {{ item.job.error_message }}
          </p>

          <div v-if="item.rows.length" class="mt-4 space-y-2">
            <article
              v-for="row in item.rows"
              :key="row.key"
              class="rounded-lg border border-slate-200 bg-white px-3 py-3"
            >
              <div class="flex flex-wrap items-center justify-between gap-2">
                <strong class="text-sm text-slate-900">
                  {{ row.tableName }}
                </strong>
                <span class="text-xs font-semibold text-slate-500">
                  {{
                    row.skipped
                      ? t('dataOps.sync.records.skipped')
                      : statusMeta(row.status).label
                  }}
                </span>
              </div>
              <div
                class="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500"
              >
                <span>
                  {{ t('dataOps.sync.records.read') }} {{ row.sourceRecords }}
                </span>
                <span>
                  {{ t('dataOps.sync.records.created') }} {{ row.created }}
                </span>
                <span>
                  {{ t('dataOps.sync.records.updated') }} {{ row.updated }}
                </span>
                <span>
                  {{ t('dataOps.sync.records.deleted') }} {{ row.deleted }}
                </span>
                <span>
                  {{ t('dataOps.sync.records.restored') }} {{ row.restored }}
                </span>
                <span>
                  {{ t('dataOps.sync.records.unchanged') }} {{ row.unchanged }}
                </span>
              </div>
              <p
                v-if="row.message"
                class="mt-2 text-xs"
                :class="
                  row.status === 'failed' ? 'text-rose-700' : 'text-slate-500'
                "
              >
                {{ row.message }}
              </p>
            </article>
          </div>

          <p v-else class="mt-3 text-sm text-slate-400">
            {{ t('dataOps.sync.records.noResult') }}
          </p>
        </div>
      </details>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { formatDateTime } from '@/composables/useDataOpsConsole'
import {
  buildSyncJobSummary,
  buildSyncResultRows,
  formatSyncJobScope
} from '@/utils/syncJobs'

const props = defineProps({
  jobs: { type: Array, default: () => [] },
  tables: { type: Array, default: () => [] }
})

const { locale, t } = useI18n()

const jobViews = computed(() =>
  props.jobs.map((job) => ({
    job,
    scope: formatSyncJobScope(job, props.tables, {
      all: t('dataOps.sync.scope.all'),
      domestic: t('dataOps.sync.scope.domestic'),
      oversea: t('dataOps.sync.scope.oversea'),
      oversea_stats: t('dataOps.sync.scope.settlement')
    }),
    summary: buildSyncJobSummary(job),
    rows: buildSyncResultRows(job, props.tables),
    duration: formatDuration(job)
  }))
)

function detailMetrics(summary) {
  return [
    { label: t('dataOps.sync.records.read'), value: summary.sourceRecords },
    { label: t('dataOps.sync.records.created'), value: summary.created },
    { label: t('dataOps.sync.records.updated'), value: summary.updated },
    { label: t('dataOps.sync.records.deleted'), value: summary.deleted },
    { label: t('dataOps.sync.records.restored'), value: summary.restored },
    {
      label: t('dataOps.sync.records.changeEvents'),
      value: summary.changeEvents
    }
  ]
}

function statusMeta(status) {
  return (
    {
      ok: {
        label: t('dataOps.sync.status.ok'),
        className: 'bg-emerald-100 text-emerald-700'
      },
      warning: {
        label: t('dataOps.sync.status.warning'),
        className: 'bg-amber-100 text-amber-700'
      },
      failed: {
        label: t('dataOps.sync.status.failed'),
        className: 'bg-rose-100 text-rose-700'
      },
      running: {
        label: t('dataOps.sync.status.running'),
        className: 'bg-sky-100 text-sky-700'
      },
      pending: {
        label: t('dataOps.sync.status.pending'),
        className: 'bg-slate-100 text-slate-600'
      }
    }[status] || {
      label: status || t('dataOps.sync.status.unknown'),
      className: 'bg-slate-100 text-slate-600'
    }
  )
}

function formatDuration(job) {
  if (!job.started_at || !job.finished_at) return ''
  const milliseconds = new Date(job.finished_at) - new Date(job.started_at)
  if (!Number.isFinite(milliseconds) || milliseconds < 0) return ''
  const seconds = Math.round(milliseconds / 1000)
  if (seconds < 60) {
    return t('dataOps.sync.records.durationSeconds', { seconds })
  }
  const minutes = Math.floor(seconds / 60)
  return t('dataOps.sync.records.durationMinutes', {
    minutes,
    seconds: seconds % 60
  })
}
</script>
