<template>
  <AppLayout>
    <div class="max-w-5xl mx-auto space-y-4">
      <!-- Page Header -->
      <div class="mb-3">
        <h2 class="text-lg font-semibold text-gray-900">
          {{ t('settings.feishu.title') }}
        </h2>
        <p class="text-sm text-gray-600 mt-1">
          {{ t('settings.feishu.subtitle') }}
        </p>
      </div>

      <!-- Loading State -->
      <BaseLoading v-if="loading" full-page size="lg" variant="primary" />

      <!-- Content -->
      <template v-else>
        <FeishuConfigCard
          :modelValue="feishuConfig"
          @update:modelValue="handleConfigUpdate"
        />
      </template>
    </div>
  </AppLayout>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { settingsApi } from '@/api/settings'
import AppLayout from '@/components/layout/AppLayout.vue'
import BaseLoading from '@/components/ui/BaseLoading.vue'
import FeishuConfigCard from '@/components/settings/FeishuConfigCard.vue'

const { t } = useI18n()
const loading = ref(true)

const feishuConfig = reactive({
  enable: false,
  app_id: '',
  app_secret: '',
  webhook_url: ''
})

const handleConfigUpdate = (newValue) => {
  Object.assign(feishuConfig, newValue)
}

const loadConfig = async () => {
  loading.value = true
  try {
    const config = await settingsApi.getFeishuConfig().catch(() => null)
    if (config) {
      Object.assign(feishuConfig, {
        enable: config.enable ?? false,
        app_id: config.app_id || '',
        app_secret: config.app_secret || '',
        webhook_url: config.webhook_url || ''
      })
    }
  } catch (error) {
    console.error('Failed to load Feishu config:', error)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadConfig()
})
</script>
