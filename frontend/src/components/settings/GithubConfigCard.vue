<template>
  <div class="bg-white rounded border border-gray-200 shadow-sm">
    <div class="px-4 py-3 border-b border-gray-200 bg-gray-50">
      <div class="flex items-center gap-2 text-gray-800">
        <svg
          class="w-4 h-4 flex-none"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"
          />
        </svg>
        <h3 class="text-sm font-semibold">
          {{ t('settings.githubConfig') }}
        </h3>
      </div>
    </div>
    <div class="p-4">
      <p class="text-xs text-gray-600 mb-3">
        {{ t('settings.githubConfigDesc') }}
      </p>
      <form @submit.prevent="saveGithubConfig" class="space-y-3">
        <!-- GitHub Token -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
          <div class="md:col-span-1">
            <label
              for="githubToken"
              class="block text-sm font-medium text-gray-700 mb-1"
            >
              {{ t('settings.githubToken') }}
            </label>
            <p class="text-xs text-gray-500 mb-2 md:mb-0">
              {{ t('settings.githubTokenDesc') }}
            </p>
          </div>
          <div class="md:col-span-2">
            <input
              id="githubToken"
              v-model="githubConfig.github_token"
              type="password"
              :placeholder="t('settings.githubTokenPlaceholder')"
              class="block w-full px-3 py-2 text-sm border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
            />
          </div>
        </div>

        <div v-if="githubError" class="rounded-md bg-red-50 p-2.5">
          <div class="flex gap-2">
            <div class="flex-shrink-0 pt-0.5">
              <svg
                class="h-4 w-4 text-red-400"
                viewBox="0 0 20 20"
                fill="currentColor"
              >
                <path
                  fill-rule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                  clip-rule="evenodd"
                />
              </svg>
            </div>
            <div class="flex-1">
              <p class="text-xs font-medium text-red-800">
                {{ githubError }}
              </p>
            </div>
          </div>
        </div>

        <div v-if="githubSuccess" class="rounded-md bg-green-50 p-2.5">
          <div class="flex gap-2">
            <div class="flex-shrink-0 pt-0.5">
              <svg
                class="h-4 w-4 text-green-400"
                viewBox="0 0 20 20"
                fill="currentColor"
              >
                <path
                  fill-rule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                  clip-rule="evenodd"
                />
              </svg>
            </div>
            <div class="flex-1">
              <p class="text-xs font-medium text-green-800">
                {{ githubSuccess }}
              </p>
            </div>
          </div>
        </div>

        <div class="flex justify-end mt-4">
          <BaseButton
            type="submit"
            variant="primary"
            class="w-full sm:w-auto"
            :loading="savingGithub"
            :disabled="savingGithub"
          >
            {{
              savingGithub ? t('common.loading') : t('settings.saveSettings')
            }}
          </BaseButton>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { settingsApi } from '@/api/settings'
import BaseButton from '@/components/ui/BaseButton.vue'

const { t } = useI18n()

const githubConfig = reactive({
  github_token: ''
})

const savingGithub = ref(false)
const githubError = ref('')
const githubSuccess = ref('')

const loadGithubConfig = async () => {
  try {
    const config = await settingsApi.getGithubConfig()
    githubConfig.github_token = config.github_token || ''
  } catch (error) {
    console.error('Failed to load GitHub config:', error)
    githubError.value = t('settings.githubConfigLoadError')
  }
}

const saveGithubConfig = async () => {
  savingGithub.value = true
  githubError.value = ''
  githubSuccess.value = ''

  try {
    await settingsApi.updateGithubConfig({
      github_token: githubConfig.github_token
    })

    githubSuccess.value = t('settings.githubConfigSaved')
    setTimeout(() => {
      githubSuccess.value = ''
    }, 3000)
  } catch (error) {
    console.error('Failed to save GitHub config:', error)
    githubError.value =
      error.response?.data?.message || t('settings.githubConfigError')
  } finally {
    savingGithub.value = false
  }
}

onMounted(() => {
  loadGithubConfig()
})
</script>
