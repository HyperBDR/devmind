<template>
  <aside class="hidden min-h-0 overflow-y-auto bg-slate-50 p-4 lg:block">
    <Panel :title="t('dataOps.context.title')">
      <div class="space-y-3 text-sm text-slate-600">
        <DataRow
          :label="t('dataOps.context.contracts')"
          :value="context?.contract?.contract_count || 0"
        />
        <DataRow
          :label="t('dataOps.context.contractAmount')"
          :value="
            formatAmountByCurrency(
              context?.contract?.total_amount,
              context?.contract?.total_amount_by_currency
            )
          "
        />
        <DataRow
          :label="t('dataOps.context.outstanding')"
          :value="
            formatAmountByCurrency(
              context?.ledger?.outstanding,
              context?.ledger?.outstanding_by_currency
            )
          "
        />
        <DataRow
          :label="t('dataOps.context.overseasProjects')"
          :value="context?.oversea_project?.project_count || 0"
        />
      </div>
    </Panel>

    <div class="mt-4">
      <Panel :title="t('dataOps.context.skills')">
        <div class="space-y-3">
          <article
            v-for="skill in skills"
            :key="skill.key"
            class="rounded-lg border border-slate-100 bg-white p-3"
          >
            <p class="text-xs font-bold text-slate-800">
              {{ skill.title }}
            </p>
            <p class="mt-1 text-xs leading-5 text-slate-500">
              {{ skill.objective }}
            </p>
          </article>
        </div>
      </Panel>
    </div>
  </aside>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { formatAmountByCurrency } from '@/composables/useDataOpsConsole'

import { DataRow, Panel } from './DataOpsPrimitives'

const { t } = useI18n()

const props = defineProps({
  context: { type: Object, default: null },
})

const assistantProfile = computed(() => props.context?.assistant || {})
const skills = computed(() => assistantProfile.value.skills || [])
</script>
