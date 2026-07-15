<template>
  <section class="space-y-5">
    <DataQualityPanel :data-quality="dataQuality" :summary="summary" />
    <SyncJobHistory :jobs="recentJobs" :tables="tables" />
    <DataTable
      :columns="columns"
      :rows="tables"
      :empty-text="t('dataOps.empty.sync')"
    />
  </section>
</template>

<script setup>
import { useI18n } from 'vue-i18n'

import { DataTable } from './DataOpsPrimitives'
import DataQualityPanel from './DataQualityPanel.vue'
import SyncJobHistory from './SyncJobHistory.vue'

const { t } = useI18n()

defineProps({
  columns: { type: Array, required: true },
  dataQuality: { type: Object, default: null },
  recentJobs: { type: Array, default: () => [] },
  summary: { type: Object, default: null },
  tables: { type: Array, default: () => [] }
})
</script>
