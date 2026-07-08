<template>
  <section class="space-y-6">
    <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <Kpi label="项目总数" :value="summary?.total_projects || 0" />
      <Kpi label="国内项目" :value="summary?.domestic_projects || 0" />
      <Kpi label="海外项目" :value="summary?.oversea_projects || 0" />
      <Kpi label="风险预警" :value="summary?.at_risk || 0" />
    </div>

    <div class="grid grid-cols-1 gap-6 xl:grid-cols-[1.4fr_1fr]">
      <Panel title="Pipeline 项目">
        <div class="grid grid-cols-1 gap-3 lg:grid-cols-2">
          <ProjectCard
            v-for="project in projects"
            :key="project.id"
            :project="project"
          />
          <EmptyState v-if="!projects.length" />
        </div>
      </Panel>

      <Panel title="预警洞察">
        <MiniList
          title="合同到期"
          :items="insights?.upcoming_renewals || []"
          label-key="customer"
          value-key="days_left"
        />
        <div class="mt-5">
          <MiniList
            title="License 到期"
            :items="insights?.license_expiry_upcoming || []"
            label-key="project_name"
            value-key="days_left"
          />
        </div>
      </Panel>
    </div>
  </section>
</template>

<script setup>
import { EmptyState, Kpi, MiniList, Panel } from './DataOpsPrimitives'
import ProjectCard from './ProjectCard.vue'

defineProps({
  insights: { type: Object, default: null },
  projects: { type: Array, default: () => [] },
  summary: { type: Object, default: null },
})
</script>
