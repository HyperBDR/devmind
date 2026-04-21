<template>
  <AppLayout>
    <div class="max-w-5xl mx-auto space-y-4">
      <!-- Page Header -->
      <div class="mb-3">
        <h2 class="text-lg font-semibold text-gray-900">
          {{ t('settings.llm.title') }}
        </h2>
        <p class="text-sm text-gray-600 mt-1">
          {{ t('settings.llm.subtitle') }}
        </p>
      </div>

      <!-- Loading State -->
      <BaseLoading v-if="loading" full-page size="lg" variant="primary" />

      <!-- Content -->
      <template v-else>
        <LLMConfigCard
          :modelValue="llmConfig"
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
import LLMConfigCard from '@/components/settings/LLMConfigCard.vue'

const { t } = useI18n()
const loading = ref(true)

const llmConfig = reactive({
  provider: 'openai',
  openai: {
    api_key: '',
    base_url: 'https://api.openai.com/v1',
    model: 'gpt-4'
  },
  azure_openai: {
    api_key: '',
    endpoint: '',
    deployment_name: '',
    api_version: '2024-02-15-preview'
  }
})

const handleConfigUpdate = (newValue) => {
  Object.assign(llmConfig, newValue)
}

const loadConfig = async () => {
  loading.value = true
  try {
    const config = await settingsApi.getLLMConfig().catch(() => null)
    if (config) {
      Object.assign(llmConfig, {
        provider: config.provider || 'openai',
        openai: {
          api_key: config.openai?.api_key || '',
          base_url: config.openai?.base_url || 'https://api.openai.com/v1',
          model: config.openai?.model || 'gpt-4'
        },
        azure_openai: {
          api_key: config.azure_openai?.api_key || '',
          endpoint: config.azure_openai?.endpoint || '',
          deployment_name: config.azure_openai?.deployment_name || '',
          api_version: config.azure_openai?.api_version || '2024-02-15-preview'
        }
      })
    }
  } catch (error) {
    console.error('Failed to load LLM config:', error)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadConfig()
})
</script>
