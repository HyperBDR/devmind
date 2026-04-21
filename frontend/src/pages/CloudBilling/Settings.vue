<template>
  <AppLayout>
    <div class="w-full max-w-full p-6">
      <div class="mb-4 flex items-center justify-between">
        <div>
          <h1 class="text-lg font-semibold text-gray-900">
            {{ t('cloudBilling.settings.title') }}
          </h1>
          <p class="mt-1 text-sm text-gray-500">
            {{ t('cloudBilling.settings.subtitle') }}
          </p>
        </div>
      </div>

      <div class="bg-white rounded border border-gray-200 shadow-sm">
        <ProviderAuthentication />
      </div>
    </div>
  </AppLayout>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import AppLayout from '@/components/layout/AppLayout.vue'
import ProviderAuthentication from '@/components/cloud-billing/ProviderAuthentication.vue'

const { t } = useI18n()
</script>
