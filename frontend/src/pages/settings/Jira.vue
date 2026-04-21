<template>
  <AppLayout>
    <div class="max-w-5xl mx-auto space-y-4">
      <!-- Page Header -->
      <div class="mb-3">
        <h2 class="text-lg font-semibold text-gray-900">
          {{ t('settings.jira.title') }}
        </h2>
        <p class="text-sm text-gray-600 mt-1">
          {{ t('settings.jira.subtitle') }}
        </p>
      </div>

      <!-- Loading State -->
      <BaseLoading v-if="loading" full-page size="lg" variant="primary" />

      <!-- Content -->
      <template v-else>
        <JiraConfigCard
          :modelValue="jiraConfig"
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
import JiraConfigCard from '@/components/settings/JiraConfigCard.vue'

const { t } = useI18n()
const loading = ref(true)

const jiraConfig = reactive({
  enable: false,
  server_url: '',
  username: '',
  api_token: '',
  project_key: ''
})

const handleConfigUpdate = (newValue) => {
  Object.assign(jiraConfig, newValue)
}

const loadConfig = async () => {
  loading.value = true
  try {
    const config = await settingsApi.getJiraConfig().catch(() => null)
    if (config) {
      Object.assign(jiraConfig, {
        enable: config.enable ?? false,
        server_url: config.server_url || '',
        username: config.username || '',
        api_token: config.api_token || '',
        project_key: config.project_key || ''
      })
    }
  } catch (error) {
    console.error('Failed to load JIRA config:', error)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadConfig()
})
</script>
