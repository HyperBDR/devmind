<template>
  <section class="space-y-5" aria-labelledby="observation-explorer-title">
    <ObservationToolbar
      :can-run="canRun"
      :error="error"
      :feedback="feedback"
      :filters="filters"
      :run-loading="runLoading"
      @load="$emit('load')"
      @run="$emit('run', $event)"
      @update-filter="(key, value) => $emit('update-filter', key, value)"
    />

    <div class="grid min-h-[28rem] gap-5 xl:grid-cols-[minmax(0,1fr)_24rem]">
      <ObservationList
        :observations="observations"
        :page="page"
        :page-size="pageSize"
        :production="production"
        :filters="filters"
        :selected-id="selectedObservation?.id || ''"
        :total="total"
        @page-change="$emit('page-change', $event)"
        @select="$emit('select', $event)"
      />
      <ObservationDetailPanel
        :loading="detailLoading"
        :observation="selectedObservation"
      />
    </div>
  </section>
</template>

<script setup>
import ObservationDetailPanel from './ObservationDetailPanel.vue'
import ObservationList from './ObservationList.vue'
import ObservationToolbar from './ObservationToolbar.vue'

defineProps({
  canRun: { type: Boolean, default: false },
  detailLoading: { type: Boolean, default: false },
  error: { type: String, default: '' },
  feedback: { type: String, default: '' },
  filters: { type: Object, required: true },
  observations: { type: Array, default: () => [] },
  page: { type: Number, required: true },
  pageSize: { type: Number, required: true },
  production: { type: Object, default: () => ({ latest_runs: {} }) },
  runLoading: { type: Boolean, default: false },
  selectedObservation: { type: Object, default: null },
  total: { type: Number, required: true }
})

defineEmits(['load', 'page-change', 'run', 'select', 'update-filter'])
</script>
