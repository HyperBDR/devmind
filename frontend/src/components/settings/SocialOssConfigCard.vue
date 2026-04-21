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
            d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01"
          />
        </svg>
        <h3 class="text-sm font-semibold">
          {{ t('settings.socialOssConfig') }}
        </h3>
      </div>
    </div>
    <div class="p-4">
      <p class="text-xs text-gray-600 mb-3">
        {{ t('settings.socialOssConfigDesc') }}
      </p>
      <form @submit.prevent="handleSave" class="space-y-3">
        <!-- Enable Toggle -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-center">
          <div class="md:col-span-1">
            <label
              for="ossEnable"
              class="block text-sm font-medium text-gray-700 mb-1"
            >
              {{ t('settings.enableOssStorage') }}
            </label>
            <p class="text-xs text-gray-500">
              {{ t('settings.enableOssStorageDesc') }}
            </p>
          </div>
          <div class="md:col-span-2">
            <label class="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                id="ossEnable"
                v-model="config.enable"
                class="sr-only peer"
              />
              <div
                class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-600"
              ></div>
              <span class="ml-3 text-sm text-gray-700">
                {{ config.enable ? t('common.enabled') : t('common.disabled') }}
              </span>
            </label>
          </div>
        </div>

        <template v-if="config.enable">
          <!-- Access Key ID -->
          <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
            <div class="md:col-span-1">
              <label
                for="accessKeyId"
                class="block text-sm font-medium text-gray-700 mb-1"
              >
                {{ t('settings.accessKeyId') }}
                <span class="text-red-500">*</span>
              </label>
              <p class="text-xs text-gray-500">
                {{ t('settings.accessKeyIdDesc') }}
              </p>
            </div>
            <div class="md:col-span-2">
              <BaseInput
                id="accessKeyId"
                v-model="config.access_key_id"
                type="text"
                :placeholder="t('settings.accessKeyIdPlaceholder')"
                :class="{
                  'border-red-300': validationErrors.includes(
                    'Access Key ID is required'
                  )
                }"
              />
            </div>
          </div>

          <!-- Access Key Secret -->
          <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
            <div class="md:col-span-1">
              <label
                for="accessKeySecret"
                class="block text-sm font-medium text-gray-700 mb-1"
              >
                {{ t('settings.accessKeySecret') }}
                <span class="text-red-500">*</span>
              </label>
              <p class="text-xs text-gray-500">
                {{ t('settings.accessKeySecretDesc') }}
              </p>
            </div>
            <div class="md:col-span-2">
              <BaseInput
                id="accessKeySecret"
                v-model="config.access_key_secret"
                type="password"
                :placeholder="t('settings.accessKeySecretPlaceholder')"
                :class="{
                  'border-red-300': validationErrors.includes(
                    'Access Key Secret is required'
                  )
                }"
              />
            </div>
          </div>

          <!-- Bucket Name -->
          <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
            <div class="md:col-span-1">
              <label
                for="bucketName"
                class="block text-sm font-medium text-gray-700 mb-1"
              >
                {{ t('settings.bucketName') }}
                <span class="text-red-500">*</span>
              </label>
              <p class="text-xs text-gray-500">
                {{ t('settings.bucketNameDesc') }}
              </p>
            </div>
            <div class="md:col-span-2">
              <BaseInput
                id="bucketName"
                v-model="config.bucket_name"
                type="text"
                :placeholder="t('settings.bucketNamePlaceholder')"
                :class="{
                  'border-red-300': validationErrors.includes(
                    'Bucket Name is required'
                  )
                }"
              />
            </div>
          </div>

          <!-- Endpoint -->
          <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
            <div class="md:col-span-1">
              <label
                for="endpoint"
                class="block text-sm font-medium text-gray-700 mb-1"
              >
                {{ t('settings.endpoint') }}
                <span class="text-red-500">*</span>
              </label>
              <p class="text-xs text-gray-500">
                {{ t('settings.endpointDesc') }}
              </p>
            </div>
            <div class="md:col-span-2">
              <BaseInput
                id="endpoint"
                v-model="config.endpoint"
                type="text"
                :placeholder="t('settings.endpointPlaceholder')"
                :class="{
                  'border-red-300': validationErrors.includes(
                    'Endpoint is required'
                  )
                }"
              />
            </div>
          </div>

          <!-- Region -->
          <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
            <div class="md:col-span-1">
              <label
                for="region"
                class="block text-sm font-medium text-gray-700 mb-1"
              >
                {{ t('settings.region') }}
              </label>
              <p class="text-xs text-gray-500">
                {{ t('settings.regionDesc') }}
              </p>
            </div>
            <div class="md:col-span-2">
              <BaseInput
                id="region"
                v-model="config.region"
                type="text"
                :placeholder="t('settings.regionPlaceholder')"
              />
            </div>
          </div>

          <!-- Use Virtual Style -->
          <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-center">
            <div class="md:col-span-1">
              <label
                for="useVirtualStyle"
                class="block text-sm font-medium text-gray-700 mb-1"
              >
                {{ t('settings.useVirtualStyle') }}
              </label>
              <p class="text-xs text-gray-500">
                {{ t('settings.useVirtualStyleDesc') }}
              </p>
            </div>
            <div class="md:col-span-2">
              <label class="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  id="useVirtualStyle"
                  v-model="config.use_virtual_style"
                  class="sr-only peer"
                />
                <div
                  class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-600"
                ></div>
                <span class="ml-3 text-sm text-gray-700">
                  {{
                    config.use_virtual_style
                      ? t('common.enabled')
                      : t('common.disabled')
                  }}
                </span>
              </label>
            </div>
          </div>
        </template>

        <div
          v-if="validationErrors.length > 0"
          class="rounded-md bg-red-50 p-2.5"
        >
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
              <p class="text-xs font-medium text-red-800 mb-1">
                {{ t('settings.validationErrors') }}
              </p>
              <div class="text-xs text-red-700 space-y-1">
                <div
                  v-for="(error, index) in validationErrors"
                  :key="index"
                  :class="{
                    'font-semibold': error.trim() === '可能的原因：',
                    'ml-4': error.trim().startsWith('•'),
                    'mt-2': error.trim() === '可能的原因：'
                  }"
                >
                  {{ error }}
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-if="successMessage" class="rounded-md bg-green-50 p-2.5">
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
                {{ successMessage }}
              </p>
            </div>
          </div>
        </div>

        <div v-if="validationSuccess" class="rounded-md bg-green-50 p-2.5 mb-3">
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

        <div class="flex justify-end gap-2 mt-4">
          <BaseButton
            v-if="
              config.enable &&
              (config.access_key_id ||
                config.access_key_secret ||
                config.bucket_name ||
                config.endpoint)
            "
            type="button"
            variant="secondary"
            class="w-full sm:w-auto"
            :loading="validating"
            :disabled="validating || saving"
            @click="handleValidate"
          >
            {{
              validating ? t('common.loading') : t('settings.validateConfig')
            }}
          </BaseButton>
          <BaseButton
            type="submit"
            variant="primary"
            class="w-full sm:w-auto"
            :loading="saving"
            :disabled="saving || validating || (config.enable && !isValidated)"
            :title="
              config.enable && !isValidated
                ? t('settings.pleaseValidateConfigFirst')
                : ''
            "
          >
            {{ saving ? t('common.loading') : t('settings.saveSettings') }}
          </BaseButton>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import { settingsApi } from '@/api/settings'

const { t } = useI18n()

const props = defineProps({
  modelValue: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['update:modelValue'])

const config = reactive({ ...props.modelValue })

const saving = ref(false)
const validating = ref(false)
const validationErrors = ref([])
const successMessage = ref('')
const validationSuccess = ref('')
const isValidated = ref(false)

const loadConfig = async () => {
  // Skip loading if data is already provided via props
  // (parent component has already loaded the data)
  // Check for _loaded flag which indicates parent has loaded the data
  if (props.modelValue && props.modelValue._loaded) {
    return
  }

  try {
    const loadedConfig = await settingsApi.getSocialOssConfig()
    Object.assign(config, {
      enable: loadedConfig.enable ?? false,
      access_key_id: loadedConfig.access_key_id || '',
      access_key_secret: loadedConfig.access_key_secret || '',
      bucket_name: loadedConfig.bucket_name || '',
      endpoint: loadedConfig.endpoint || '',
      region: loadedConfig.region || '',
      use_virtual_style: loadedConfig.use_virtual_style || false
    })
    isValidated.value = false
  } catch (error) {
    console.error('Failed to load Social OSS config:', error)
  }
}

onMounted(() => {
  loadConfig()
})

watch(
  () => props.modelValue,
  (newValue) => {
    Object.assign(config, newValue)
  },
  { deep: true }
)

watch(
  () => [
    config.enable,
    config.access_key_id,
    config.access_key_secret,
    config.bucket_name,
    config.endpoint,
    config.region,
    config.use_virtual_style
  ],
  () => {
    if (config.enable) {
      isValidated.value = false
      validationSuccess.value = ''
      validationErrors.value = []
    }
  }
)

const handleValidate = async () => {
  validating.value = true
  validationErrors.value = []
  validationSuccess.value = ''

  try {
    const response = await settingsApi.validateSocialOssConfig(config)
    const validation = response.data || response

    if (validation.skipped) {
      validationSuccess.value = t('settings.socialOssConfigValid')
      isValidated.value = true
      setTimeout(() => {
        validationSuccess.value = ''
      }, 3000)
      return
    }

    if (!validation.valid) {
      const errors = validation.errors || [
        response.message || t('settings.socialOssConfigError')
      ]
      const expandedErrors = []
      errors.forEach((error) => {
        if (typeof error === 'string' && error.includes('\n')) {
          const lines = error.split('\n').filter((line) => line.trim())
          expandedErrors.push(...lines)
        } else if (typeof error === 'string' && error.trim()) {
          expandedErrors.push(error)
        }
      })
      validationErrors.value = expandedErrors
      isValidated.value = false
    } else {
      validationSuccess.value = t('settings.socialOssConfigValid')
      isValidated.value = true
      setTimeout(() => {
        validationSuccess.value = ''
      }, 3000)
    }
  } catch (error) {
    console.error('Failed to validate Social OSS config:', error)
    const errorData = error.response?.data
    if (errorData?.data?.errors) {
      const errors = errorData.data.errors
      const expandedErrors = []
      errors.forEach((err) => {
        if (typeof err === 'string' && err.includes('\n')) {
          const lines = err.split('\n').filter((line) => line.trim())
          expandedErrors.push(...lines)
        } else if (typeof err === 'string' && err.trim()) {
          expandedErrors.push(err)
        }
      })
      validationErrors.value = expandedErrors
    } else {
      validationErrors.value = [
        errorData?.message ||
          error.message ||
          t('settings.socialOssConfigError')
      ]
    }
    isValidated.value = false
  } finally {
    validating.value = false
  }
}

const handleSave = async () => {
  if (config.enable && !isValidated.value) {
    validationErrors.value = [t('settings.pleaseValidateConfigFirst')]
    return
  }

  saving.value = true
  validationErrors.value = []
  successMessage.value = ''
  validationSuccess.value = ''

  try {
    const validationResponse = await settingsApi.validateSocialOssConfig(config)
    const validation = validationResponse.data || validationResponse

    if (!validation.valid && !validation.skipped) {
      const errors = validation.errors || [
        validation.message || t('settings.socialOssConfigError')
      ]
      const expandedErrors = []
      errors.forEach((error) => {
        if (typeof error === 'string' && error.includes('\n')) {
          const lines = error.split('\n').filter((line) => line.trim())
          expandedErrors.push(...lines)
        } else if (typeof error === 'string' && error.trim()) {
          expandedErrors.push(error)
        }
      })
      validationErrors.value = expandedErrors
      isValidated.value = false
      saving.value = false
      return
    }

    // Remove _loaded flag before sending to API
    const { _loaded, ...configForApi } = config
    await settingsApi.updateSocialOssConfig(configForApi)
    // Emit with _loaded flag to maintain state
    emit('update:modelValue', { ...configForApi, _loaded: true })
    successMessage.value = t('settings.socialOssConfigSaved')
    isValidated.value = false
    setTimeout(() => {
      successMessage.value = ''
    }, 3000)
  } catch (error) {
    console.error('Failed to save Social OSS config:', error)
    const errorData = error.response?.data
    if (errorData?.data?.errors) {
      const errors = errorData.data.errors
      const expandedErrors = []
      errors.forEach((err) => {
        if (typeof err === 'string' && err.includes('\n')) {
          const lines = err.split('\n').filter((line) => line.trim())
          expandedErrors.push(...lines)
        } else if (typeof err === 'string' && err.trim()) {
          expandedErrors.push(err)
        }
      })
      validationErrors.value = expandedErrors
    } else {
      validationErrors.value = [
        errorData?.message ||
          error.message ||
          t('settings.socialOssConfigError')
      ]
    }
    isValidated.value = false
  } finally {
    saving.value = false
  }
}
</script>
