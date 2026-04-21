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
            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
          />
        </svg>
        <h3 class="text-sm font-semibold">
          {{ t('settings.jira.configTitle') }}
        </h3>
      </div>
    </div>
    <div class="p-4">
      <p class="text-xs text-gray-600 mb-3">
        {{ t('settings.jira.configDesc') }}
      </p>
      <form @submit.prevent="saveConfig" class="space-y-3">
        <!-- Enable Toggle -->
        <div class="flex items-center justify-between">
          <div>
            <label class="text-sm font-medium text-gray-700">
              {{ t('settings.jira.enable') }}
            </label>
            <p class="text-xs text-gray-500 mt-0.5">
              {{ t('settings.jira.enableDesc') }}
            </p>
          </div>
          <label class="relative inline-flex items-center cursor-pointer">
            <input
              v-model="localConfig.enable"
              type="checkbox"
              class="sr-only peer"
            />
            <div
              class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-600"
            ></div>
          </label>
        </div>

        <template v-if="localConfig.enable">
          <!-- Server URL -->
          <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
            <div class="md:col-span-1">
              <label
                for="serverUrl"
                class="block text-sm font-medium text-gray-700 mb-1"
              >
                {{ t('settings.jira.serverUrl') }}
              </label>
              <p class="text-xs text-gray-500 mb-2 md:mb-0">
                {{ t('settings.jira.serverUrlDesc') }}
              </p>
            </div>
            <div class="md:col-span-2">
              <input
                id="serverUrl"
                v-model="localConfig.server_url"
                type="url"
                :placeholder="t('settings.jira.serverUrlPlaceholder')"
                class="block w-full px-3 py-2 text-sm border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              />
            </div>
          </div>

          <!-- Username -->
          <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
            <div class="md:col-span-1">
              <label
                for="username"
                class="block text-sm font-medium text-gray-700 mb-1"
              >
                {{ t('settings.jira.username') }}
              </label>
              <p class="text-xs text-gray-500 mb-2 md:mb-0">
                {{ t('settings.jira.usernameDesc') }}
              </p>
            </div>
            <div class="md:col-span-2">
              <input
                id="username"
                v-model="localConfig.username"
                type="text"
                :placeholder="t('settings.jira.usernamePlaceholder')"
                class="block w-full px-3 py-2 text-sm border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              />
            </div>
          </div>

          <!-- API Token -->
          <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
            <div class="md:col-span-1">
              <label
                for="apiToken"
                class="block text-sm font-medium text-gray-700 mb-1"
              >
                {{ t('settings.jira.apiToken') }}
              </label>
              <p class="text-xs text-gray-500 mb-2 md:mb-0">
                {{ t('settings.jira.apiTokenDesc') }}
              </p>
            </div>
            <div class="md:col-span-2">
              <input
                id="apiToken"
                v-model="localConfig.api_token"
                type="password"
                :placeholder="t('settings.jira.apiTokenPlaceholder')"
                class="block w-full px-3 py-2 text-sm border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              />
            </div>
          </div>

          <!-- Project Key -->
          <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
            <div class="md:col-span-1">
              <label
                for="projectKey"
                class="block text-sm font-medium text-gray-700 mb-1"
              >
                {{ t('settings.jira.projectKey') }}
              </label>
              <p class="text-xs text-gray-500 mb-2 md:mb-0">
                {{ t('settings.jira.projectKeyDesc') }}
              </p>
            </div>
            <div class="md:col-span-2">
              <input
                id="projectKey"
                v-model="localConfig.project_key"
                type="text"
                :placeholder="t('settings.jira.projectKeyPlaceholder')"
                class="block w-full px-3 py-2 text-sm border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              />
            </div>
          </div>
        </template>

        <div v-if="error" class="rounded-md bg-red-50 p-2.5">
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
                {{ error }}
              </p>
            </div>
          </div>
        </div>

        <div v-if="validationError" class="rounded-md bg-red-50 p-2.5">
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
                {{ validationError }}
              </p>
            </div>
          </div>
        </div>

        <div v-if="validationSuccess" class="rounded-md bg-green-50 p-2.5">
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
                {{ validationSuccess }}
              </p>
            </div>
          </div>
        </div>

        <div v-if="success" class="rounded-md bg-green-50 p-2.5">
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
                {{ success }}
              </p>
            </div>
          </div>
        </div>

        <div class="border-t border-gray-200 my-4"></div>

        <div class="flex justify-end gap-2">
          <BaseButton
            type="button"
            variant="secondary"
            class="w-full sm:w-auto"
            :loading="validating"
            :disabled="validating || saving || !hasRequiredFields"
            :title="
              !hasRequiredFields ? t('settings.pleaseFillRequiredFields') : ''
            "
            @click="handleValidate"
          >
            {{ validating ? t('common.loading') : t('settings.jira.validate') }}
          </BaseButton>
          <BaseButton
            type="submit"
            variant="primary"
            class="w-full sm:w-auto"
            :loading="saving"
            :disabled="saving || validating"
          >
            {{ saving ? t('common.saving') : t('common.save') }}
          </BaseButton>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, watch, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { settingsApi } from '@/api/settings'
import BaseButton from '@/components/ui/BaseButton.vue'

const props = defineProps({
  modelValue: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['update:modelValue'])

const { t } = useI18n()

const localConfig = reactive({
  enable: false,
  server_url: '',
  username: '',
  api_token: '',
  project_key: ''
})

const saving = ref(false)
const validating = ref(false)
const error = ref('')
const success = ref('')
const validationError = ref('')
const validationSuccess = ref('')

const hasRequiredFields = computed(() => {
  return (
    localConfig.server_url &&
    localConfig.username &&
    localConfig.api_token &&
    localConfig.project_key
  )
})

watch(
  () => props.modelValue,
  (newValue) => {
    if (newValue) {
      Object.assign(localConfig, newValue)
    }
  },
  { immediate: true, deep: true }
)

watch(
  localConfig,
  (newValue) => {
    emit('update:modelValue', { ...newValue })
  },
  { deep: true }
)

const handleValidate = async () => {
  validating.value = true
  validationError.value = ''
  validationSuccess.value = ''

  try {
    const response = await settingsApi.validateJiraConfig(localConfig)
    const validation = response.data || response

    if (!validation.valid) {
      const errors = validation.errors || [
        validation.message || t('settings.jira.validateError')
      ]
      validationError.value = Array.isArray(errors) ? errors.join(', ') : errors
    } else {
      validationSuccess.value = t('settings.jira.validateSuccess')
      setTimeout(() => {
        validationSuccess.value = ''
      }, 3000)
    }
  } catch (err) {
    console.error('Failed to validate JIRA config:', err)
    const errorData = err.response?.data
    if (errorData?.data?.errors) {
      const errors = errorData.data.errors
      validationError.value = Array.isArray(errors) ? errors.join(', ') : errors
    } else {
      validationError.value =
        errorData?.message || err.message || t('settings.jira.validateError')
    }
  } finally {
    validating.value = false
  }
}

const saveConfig = async () => {
  saving.value = true
  error.value = ''
  success.value = ''

  try {
    await settingsApi.updateJiraConfig(localConfig)
    success.value = t('settings.jira.saveSuccess')
    setTimeout(() => {
      success.value = ''
    }, 3000)
  } catch (err) {
    console.error('Failed to save JIRA config:', err)
    error.value = err.response?.data?.message || t('settings.jira.saveError')
  } finally {
    saving.value = false
  }
}
</script>
