<template>
  <div class="bg-white border border-gray-200 rounded-xl shadow-sm">
    <div
      class="px-6 py-5 border-b border-gray-200 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between"
    >
      <div>
        <h1 class="text-xl font-semibold text-gray-900">{{ title }}</h1>
        <p class="mt-1 text-sm text-gray-500">{{ subtitle }}</p>
      </div>
      <div v-if="$slots.actions" class="flex flex-wrap items-center gap-3">
        <slot name="actions" />
      </div>
    </div>
    <div class="px-4 py-3">
      <router-link
        :to="{ name: 'OneProMonitorSettingsDataSources' }"
        class="inline-flex px-4 py-2 rounded-lg text-sm font-medium border transition-colors bg-primary-50 border-primary-200 text-primary-700"
      >
        {{ t('hyperbdrMonitor.nav.dataSources') }}
      </router-link>
    </div>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'

defineProps({
  title: {
    type: String,
    required: true
  },
  subtitle: {
    type: String,
    required: true
  }
})

const { t } = useI18n()
</script>
