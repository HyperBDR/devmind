<template>
  <AppLayout>
    <div class="w-full max-w-full p-6">
      <div class="mb-4">
        <h1 class="text-lg font-semibold text-gray-900">
          {{ t('cloudBilling.alerts.rules.title') }}
        </h1>
      </div>
      <div class="bg-white rounded-lg border border-gray-200 shadow-sm p-4">
        <p class="text-sm text-gray-600">
          {{ t('cloudBilling.alerts.rules.comingSoon') }}
        </p>
      </div>
    </div>
  </AppLayout>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import AppLayout from '@/components/layout/AppLayout.vue'

const { t } = useI18n()
</script>
