<template>
  <section class="space-y-5">
    <Panel title="同步任务">
      <div class="grid grid-cols-1 gap-3 lg:grid-cols-3">
        <div
          v-for="job in recentJobs"
          :key="job.id"
          class="rounded-lg border border-slate-200 bg-slate-50 p-3"
        >
          <div class="flex items-center justify-between">
            <p class="text-sm font-semibold text-slate-900">
              {{ job.source_key || 'full' }}
              <span v-if="job.table_key">/{{ job.table_key }}</span>
            </p>
            <span class="text-xs text-slate-500">{{ job.status }}</span>
          </div>
          <p class="mt-2 text-xs text-slate-500">
            {{ formatDateTime(job.started_at) }}
          </p>
        </div>
        <EmptyState v-if="!recentJobs.length" />
      </div>
    </Panel>
    <DataTable :columns="columns" :rows="tables" empty-text="暂无同步状态" />
  </section>
</template>

<script setup>
import { formatDateTime } from '@/composables/useDataOpsConsole'

import { DataTable, EmptyState, Panel } from './DataOpsPrimitives'

defineProps({
  columns: { type: Array, required: true },
  recentJobs: { type: Array, default: () => [] },
  tables: { type: Array, default: () => [] },
})
</script>
