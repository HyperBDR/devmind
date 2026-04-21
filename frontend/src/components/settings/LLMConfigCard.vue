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
            d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
          />
        </svg>
        <h3 class="text-sm font-semibold">
          {{ t('settings.llm.configTitle') }}
        </h3>
      </div>
    </div>
    <div class="p-4">
      <p class="text-xs text-gray-600 mb-3">
        {{ t('settings.llm.configDesc') }}
      </p>
      <form @submit.prevent="saveConfig" class="space-y-4">
        <!-- Provider Selection -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
          <div class="md:col-span-1">
            <label
              for="provider"
              class="block text-sm font-medium text-gray-700 mb-1"
            >
              {{ t('settings.llm.provider') }}
            </label>
            <p class="text-xs text-gray-500 mb-2 md:mb-0">
              {{ t('settings.llm.providerDesc') }}
            </p>
          </div>
          <div class="md:col-span-2">
            <select
              id="provider"
              v-model="localConfig.provider"
              class="block w-full px-3 py-2 text-sm border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
            >
              <option value="openai">
                {{ t('settings.llm.providerOpenAI') }}
              </option>
              <option value="azure_openai">
                {{ t('settings.llm.providerAzureOpenAI') }}
              </option>
            </select>
          </div>
        </div>

        <!-- OpenAI Configuration -->
        <div
          v-if="localConfig.provider === 'openai'"
          class="space-y-3 border-t border-gray-200 pt-4"
        >
          <h4 class="text-sm font-semibold text-gray-900 mb-3">
            {{ t('settings.llm.openaiConfig') }}
          </h4>

          <!-- API Key -->
          <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
            <div class="md:col-span-1">
              <label
                for="openaiApiKey"
                class="block text-sm font-medium text-gray-700 mb-1"
              >
                {{ t('settings.llm.apiKey') }}
              </label>
              <p class="text-xs text-gray-500 mb-2 md:mb-0">
                {{ t('settings.llm.apiKeyDesc') }}
              </p>
            </div>
            <div class="md:col-span-2">
              <input
                id="openaiApiKey"
                v-model="localConfig.openai.api_key"
                type="password"
                :placeholder="t('settings.llm.apiKeyPlaceholder')"
                class="block w-full px-3 py-2 text-sm border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              />
            </div>
          </div>

          <!-- Base URL -->
          <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
            <div class="md:col-span-1">
              <label
                for="openaiBaseUrl"
                class="block text-sm font-medium text-gray-700 mb-1"
              >
                {{ t('settings.llm.baseUrl') }}
              </label>
              <p class="text-xs text-gray-500 mb-2 md:mb-0">
                {{ t('settings.llm.baseUrlDesc') }}
              </p>
            </div>
            <div class="md:col-span-2">
              <input
                id="openaiBaseUrl"
                v-model="localConfig.openai.base_url"
                type="url"
                :placeholder="t('settings.llm.baseUrlPlaceholder')"
                class="block w-full px-3 py-2 text-sm border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              />
            </div>
          </div>

          <!-- Model -->
          <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
            <div class="md:col-span-1">
              <label
                for="openaiModel"
                class="block text-sm font-medium text-gray-700 mb-1"
              >
                {{ t('settings.llm.model') }}
              </label>
              <p class="text-xs text-gray-500 mb-2 md:mb-0">
                {{ t('settings.llm.modelDesc') }}
              </p>
            </div>
            <div class="md:col-span-2">
              <input
                id="openaiModel"
                v-model="localConfig.openai.model"
                type="text"
                :placeholder="t('settings.llm.modelPlaceholder')"
                class="block w-full px-3 py-2 text-sm border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              />
            </div>
          </div>
        </div>

        <!-- Azure OpenAI Configuration -->
        <div
          v-if="localConfig.provider === 'azure_openai'"
          class="space-y-3 border-t border-gray-200 pt-4"
        >
          <h4 class="text-sm font-semibold text-gray-900 mb-3">
            {{ t('settings.llm.azureOpenAIConfig') }}
          </h4>

          <!-- API Key -->
          <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
            <div class="md:col-span-1">
              <label
                for="azureApiKey"
                class="block text-sm font-medium text-gray-700 mb-1"
              >
                {{ t('settings.llm.apiKey') }}
              </label>
              <p class="text-xs text-gray-500 mb-2 md:mb-0">
                {{ t('settings.llm.apiKeyDesc') }}
              </p>
            </div>
            <div class="md:col-span-2">
              <input
                id="azureApiKey"
                v-model="localConfig.azure_openai.api_key"
                type="password"
                :placeholder="t('settings.llm.apiKeyPlaceholder')"
                class="block w-full px-3 py-2 text-sm border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              />
            </div>
          </div>

          <!-- Endpoint -->
          <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
            <div class="md:col-span-1">
              <label
                for="azureEndpoint"
                class="block text-sm font-medium text-gray-700 mb-1"
              >
                {{ t('settings.llm.endpoint') }}
              </label>
              <p class="text-xs text-gray-500 mb-2 md:mb-0">
                {{ t('settings.llm.endpointDesc') }}
              </p>
            </div>
            <div class="md:col-span-2">
              <input
                id="azureEndpoint"
                v-model="localConfig.azure_openai.endpoint"
                type="url"
                :placeholder="t('settings.llm.endpointPlaceholder')"
                class="block w-full px-3 py-2 text-sm border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              />
            </div>
          </div>

          <!-- Deployment Name -->
          <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
            <div class="md:col-span-1">
              <label
                for="azureDeploymentName"
                class="block text-sm font-medium text-gray-700 mb-1"
              >
                {{ t('settings.llm.deploymentName') }}
              </label>
              <p class="text-xs text-gray-500 mb-2 md:mb-0">
                {{ t('settings.llm.deploymentNameDesc') }}
              </p>
            </div>
            <div class="md:col-span-2">
              <input
                id="azureDeploymentName"
                v-model="localConfig.azure_openai.deployment_name"
                type="text"
                :placeholder="t('settings.llm.deploymentNamePlaceholder')"
                class="block w-full px-3 py-2 text-sm border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              />
            </div>
          </div>

          <!-- API Version -->
          <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
            <div class="md:col-span-1">
              <label
                for="azureApiVersion"
                class="block text-sm font-medium text-gray-700 mb-1"
              >
                {{ t('settings.llm.apiVersion') }}
              </label>
              <p class="text-xs text-gray-500 mb-2 md:mb-0">
                {{ t('settings.llm.apiVersionDesc') }}
              </p>
            </div>
            <div class="md:col-span-2">
              <input
                id="azureApiVersion"
                v-model="localConfig.azure_openai.api_version"
                type="text"
                :placeholder="t('settings.llm.apiVersionPlaceholder')"
                class="block w-full px-3 py-2 text-sm border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              />
            </div>
          </div>
        </div>

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
            {{ validating ? t('common.loading') : t('settings.llm.validate') }}
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

const saving = ref(false)
const validating = ref(false)
const error = ref('')
const success = ref('')
const validationError = ref('')
const validationSuccess = ref('')

const hasRequiredFields = computed(() => {
  if (localConfig.provider === 'openai') {
    return (
      localConfig.openai?.api_key &&
      localConfig.openai?.base_url &&
      localConfig.openai?.model
    )
  } else if (localConfig.provider === 'azure_openai') {
    return (
      localConfig.azure_openai?.api_key &&
      localConfig.azure_openai?.endpoint &&
      localConfig.azure_openai?.deployment_name
    )
  }
  return false
})

watch(
  () => props.modelValue,
  (newValue) => {
    if (newValue) {
      Object.assign(localConfig, {
        provider: newValue.provider || 'openai',
        openai: {
          api_key: newValue.openai?.api_key || '',
          base_url: newValue.openai?.base_url || 'https://api.openai.com/v1',
          model: newValue.openai?.model || 'gpt-4'
        },
        azure_openai: {
          api_key: newValue.azure_openai?.api_key || '',
          endpoint: newValue.azure_openai?.endpoint || '',
          deployment_name: newValue.azure_openai?.deployment_name || '',
          api_version:
            newValue.azure_openai?.api_version || '2024-02-15-preview'
        }
      })
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
    const response = await settingsApi.validateLLMConfig(localConfig)
    const validation = response.data || response

    if (!validation.valid) {
      const errors = validation.errors || [
        validation.message || t('settings.llm.validateError')
      ]
      validationError.value = Array.isArray(errors) ? errors.join(', ') : errors
    } else {
      validationSuccess.value = t('settings.llm.validateSuccess')
      setTimeout(() => {
        validationSuccess.value = ''
      }, 3000)
    }
  } catch (err) {
    console.error('Failed to validate LLM config:', err)
    const errorData = err.response?.data
    if (errorData?.data?.errors) {
      const errors = errorData.data.errors
      validationError.value = Array.isArray(errors) ? errors.join(', ') : errors
    } else {
      validationError.value =
        errorData?.message || err.message || t('settings.llm.validateError')
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
    await settingsApi.updateLLMConfig(localConfig)
    success.value = t('settings.llm.saveSuccess')
    setTimeout(() => {
      success.value = ''
    }, 3000)
  } catch (err) {
    console.error('Failed to save LLM config:', err)
    error.value = err.response?.data?.message || t('settings.llm.saveError')
  } finally {
    saving.value = false
  }
}
</script>
