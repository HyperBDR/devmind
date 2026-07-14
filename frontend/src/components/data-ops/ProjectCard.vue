<template>
  <div class="rounded-xl border border-slate-200 bg-slate-50 p-4">
    <div class="flex items-start justify-between gap-3">
      <div>
        <p class="font-semibold text-slate-900">
          {{ project.project_name || t('dataOps.project.unnamed') }}
        </p>
        <p class="mt-1 text-xs text-slate-500">
          {{ project.project_code || project.po_number || '-' }}
        </p>
      </div>
      <span class="status-pill bg-indigo-100 text-indigo-700">
        {{ project.project_scope }}
      </span>
    </div>
    <div class="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-500">
      <span>{{ project.sales_person || project.project_owner || '-' }}</span>
      <span class="text-right">
        {{ project.country || project.domestic_type || '-' }}
      </span>
      <span>
        {{
          formatAmount(
            project.estimated_amount || project.stat_amount_usd,
            project.currency,
            { locale }
          )
        }}
      </span>
      <span class="text-right">
        {{ project.status || project.order_status || '-' }}
      </span>
    </div>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'

import { formatAmount } from '@/composables/useDataOpsConsole'

const { locale, t } = useI18n()

defineProps({
  project: { type: Object, required: true },
})
</script>
