<template>
  <AppLayout>
    <div class="w-full max-w-full p-6">
      <div class="mb-4">
        <h1 class="text-lg font-semibold text-gray-900">
          {{ t('dataCollector.settings.title') }}
        </h1>
        <p class="mt-1 text-sm text-gray-500">
          {{ t('dataCollector.settings.subtitle') }}
        </p>
      </div>

      <div class="bg-white rounded border border-gray-200 shadow-sm">
        <CollectorConfigList />
      </div>
    </div>
  </AppLayout>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import AppLayout from '@/components/layout/AppLayout.vue'
import CollectorConfigList from '@/components/data-collector/CollectorConfigList.vue'

const { t } = useI18n()
</script>
