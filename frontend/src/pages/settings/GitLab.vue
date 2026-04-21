<template>
  <AppLayout>
    <div class="max-w-5xl mx-auto space-y-4">
      <!-- Page Header -->
      <div class="mb-3">
        <h2 class="text-lg font-semibold text-gray-900">
          {{ t('settings.gitlab.title') }}
        </h2>
        <p class="text-sm text-gray-600 mt-1">
          {{ t('settings.gitlab.subtitle') }}
        </p>
      </div>

      <!-- Loading State -->
      <BaseLoading v-if="loading" full-page size="lg" variant="primary" />

      <!-- Content -->
      <template v-else>
        <GitLabConfigCard
          :modelValue="gitlabConfig"
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
import GitLabConfigCard from '@/components/settings/GitLabConfigCard.vue'

const { t } = useI18n()
const loading = ref(true)

const gitlabConfig = reactive({
  enable: false,
  server_url: '',
  access_token: '',
  project_id: ''
})

const handleConfigUpdate = (newValue) => {
  Object.assign(gitlabConfig, newValue)
}

const loadConfig = async () => {
  loading.value = true
  try {
    const config = await settingsApi.getGitLabConfig().catch(() => null)
    if (config) {
      Object.assign(gitlabConfig, {
        enable: config.enable ?? false,
        server_url: config.server_url || '',
        access_token: config.access_token || '',
        project_id: config.project_id || ''
      })
    }
  } catch (error) {
    console.error('Failed to load GitLab config:', error)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadConfig()
})
</script>
