<template>
  <section class="space-y-6">
    <div class="grid grid-cols-1 gap-6 xl:grid-cols-2">
      <KanbanBoard
        title="合同看板"
        :cards="contractCards"
        group-key="status"
        title-key="customer_name"
        subtitle-key="contract_number"
        amount-key="total_amount"
      />
      <KanbanBoard
        title="海外结算"
        :cards="settlementCards"
        group-key="project_progress"
        title-key="project_name_cn"
        subtitle-key="project_code"
        amount-key="actual_revenue"
      />
    </div>
  </section>
</template>

<script setup>
import KanbanBoard from './KanbanBoard.vue'

defineProps({
  contractCards: { type: Array, default: () => [] },
  settlementCards: { type: Array, default: () => [] },
})
</script>
