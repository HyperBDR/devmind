<template>
  <aside class="hidden min-h-0 overflow-y-auto bg-slate-50 p-4 lg:block">
    <Panel title="当前上下文">
      <div class="space-y-3 text-sm text-slate-600">
        <DataRow
          label="合同"
          :value="context?.contract?.contract_count || 0"
        />
        <DataRow
          label="合同金额"
          :value="
            formatAmountByCurrency(
              context?.contract?.total_amount,
              context?.contract?.total_amount_by_currency
            )
          "
        />
        <DataRow
          label="待回款"
          :value="
            formatAmountByCurrency(
              context?.ledger?.outstanding,
              context?.ledger?.outstanding_by_currency
            )
          "
        />
        <DataRow
          label="海外项目"
          :value="context?.oversea_project?.project_count || 0"
        />
      </div>
    </Panel>

    <div class="mt-4">
      <Panel title="助手 Skills">
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

import { formatAmountByCurrency } from '@/composables/useDataOpsConsole'

import { DataRow, Panel } from './DataOpsPrimitives'

const props = defineProps({
  context: { type: Object, default: null },
})

const assistantProfile = computed(() => props.context?.assistant || {})
const skills = computed(() => assistantProfile.value.skills || [])
</script>
