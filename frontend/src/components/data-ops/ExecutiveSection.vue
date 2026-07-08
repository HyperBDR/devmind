<template>
  <section class="space-y-6">
    <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">
      <Kpi
        v-for="item in kpiCards"
        :key="item.label"
        :label="item.label"
        :value="item.value"
      />
    </div>

    <div class="grid grid-cols-1 gap-6 xl:grid-cols-2">
      <Panel title="经营风险">
        <div class="space-y-3">
          <DataRow
            v-for="risk in riskItems"
            :key="risk.title || risk.customer || risk.id"
            :label="risk.title || risk.customer || '风险项'"
            :value="risk.detail || risk.recommendation || risk.severity || '-'"
          />
          <EmptyState v-if="!riskItems.length" />
        </div>
      </Panel>

      <Panel title="业务机会">
        <div class="space-y-3">
          <DataRow
            v-for="item in opportunityItems"
            :key="item.title || item.customer || item.id"
            :label="item.title || item.customer || '机会项'"
            :value="item.detail || item.recommendation || item.amount || '-'"
          />
          <EmptyState v-if="!opportunityItems.length" />
        </div>
      </Panel>
    </div>

    <Panel title="数据洞察">
      <div class="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <MiniList
          title="月度签约"
          :items="insights?.monthly_signings || []"
          label-key="month"
          value-key="amount"
        />
        <MiniList
          title="合同状态"
          :items="insights?.contract_status_distribution || []"
          label-key="status"
          value-key="count"
        />
        <MiniList
          title="海外国家 Top"
          :items="insights?.oversea_projects_by_country_top10 || []"
          label-key="country"
          value-key="total_amount_usd"
        />
      </div>
    </Panel>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import {
  DataRow,
  EmptyState,
  Kpi,
  MiniList,
  Panel,
} from './DataOpsPrimitives'

const props = defineProps({
  insights: { type: Object, default: null },
  kpiCards: { type: Array, default: () => [] },
  opportunities: { type: Object, default: null },
  risks: { type: Object, default: null },
})

const riskItems = computed(() => props.risks?.items || props.risks?.risks || [])
const opportunityItems = computed(
  () => props.opportunities?.items || props.opportunities?.opportunities || []
)
</script>
