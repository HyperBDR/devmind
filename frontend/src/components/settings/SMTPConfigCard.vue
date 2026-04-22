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
            d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
          />
        </svg>
        <h3 class="text-sm font-semibold">
          {{ t('settings.notifications.smtpConfigTitle') }}
        </h3>
      </div>
    </div>
    <div class="p-4">
      <p class="text-xs text-gray-600 mb-3">
        {{ t('settings.notifications.smtpConfigDesc') }}
      </p>
      <form @submit.prevent="saveConfig" class="space-y-3">
        <!-- Enable Toggle -->
        <div class="flex items-center justify-between">
          <div>
            <label class="text-sm font-medium text-gray-700">
              {{ t('settings.notifications.smtpEnable') }}
            </label>
            <p class="text-xs text-gray-500 mt-0.5">
              {{ t('settings.notifications.smtpEnableDesc') }}
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
          <!-- SMTP Host -->
          <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
            <div class="md:col-span-1">
              <label
                for="smtpHost"
                class="block text-sm font-medium text-gray-700 mb-1"
              >
                {{ t('settings.notifications.smtpHost') }}
              </label>
              <p class="text-xs text-gray-500 mb-2 md:mb-0">
                {{ t('settings.notifications.smtpHostDesc') }}
              </p>
            </div>
            <div class="md:col-span-2">
              <input
                id="smtpHost"
                v-model="localConfig.host"
                type="text"
                :placeholder="t('settings.notifications.smtpHostPlaceholder')"
                class="block w-full px-3 py-2 text-sm border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              />
            </div>
          </div>

          <!-- SMTP Port -->
          <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
            <div class="md:col-span-1">
              <label
                for="smtpPort"
                class="block text-sm font-medium text-gray-700 mb-1"
              >
                {{ t('settings.notifications.smtpPort') }}
              </label>
              <p class="text-xs text-gray-500 mb-2 md:mb-0">
                {{ t('settings.notifications.smtpPortDesc') }}
              </p>
            </div>
            <div class="md:col-span-2">
              <input
                id="smtpPort"
                v-model.number="localConfig.port"
                type="number"
                min="1"
                max="65535"
                :placeholder="t('settings.notifications.smtpPortPlaceholder')"
                class="block w-full px-3 py-2 text-sm border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              />
            </div>
          </div>

          <!-- Username -->
          <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
            <div class="md:col-span-1">
              <label
                for="smtpUsername"
                class="block text-sm font-medium text-gray-700 mb-1"
              >
                {{ t('settings.notifications.smtpUsername') }}
              </label>
              <p class="text-xs text-gray-500 mb-2 md:mb-0">
                {{ t('settings.notifications.smtpUsernameDesc') }}
              </p>
            </div>
            <div class="md:col-span-2">
              <input
                id="smtpUsername"
                v-model="localConfig.username"
                type="text"
                :placeholder="
                  t('settings.notifications.smtpUsernamePlaceholder')
                "
                class="block w-full px-3 py-2 text-sm border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              />
            </div>
          </div>

          <!-- Password -->
          <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
            <div class="md:col-span-1">
              <label
                for="smtpPassword"
                class="block text-sm font-medium text-gray-700 mb-1"
              >
                {{ t('settings.notifications.smtpPassword') }}
              </label>
              <p class="text-xs text-gray-500 mb-2 md:mb-0">
                {{ t('settings.notifications.smtpPasswordDesc') }}
              </p>
            </div>
            <div class="md:col-span-2">
              <input
                id="smtpPassword"
                v-model="localConfig.password"
                type="password"
                :placeholder="
                  t('settings.notifications.smtpPasswordPlaceholder')
                "
                class="block w-full px-3 py-2 text-sm border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              />
            </div>
          </div>

          <!-- Use TLS -->
          <div class="flex items-center justify-between">
            <div>
              <label class="text-sm font-medium text-gray-700">
                {{ t('settings.notifications.smtpUseTLS') }}
              </label>
              <p class="text-xs text-gray-500 mt-0.5">
                {{ t('settings.notifications.smtpUseTLSDesc') }}
              </p>
            </div>
            <label class="relative inline-flex items-center cursor-pointer">
              <input
                v-model="localConfig.use_tls"
                type="checkbox"
                class="sr-only peer"
                @change="localConfig.use_ssl = false"
              />
              <div
                class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-600"
              ></div>
            </label>
          </div>

          <!-- Use SSL -->
          <div class="flex items-center justify-between">
            <div>
              <label class="text-sm font-medium text-gray-700">
                {{ t('settings.notifications.smtpUseSSL') }}
              </label>
              <p class="text-xs text-gray-500 mt-0.5">
                {{ t('settings.notifications.smtpUseSSLDesc') }}
              </p>
            </div>
            <label class="relative inline-flex items-center cursor-pointer">
              <input
                v-model="localConfig.use_ssl"
                type="checkbox"
                class="sr-only peer"
                @change="localConfig.use_tls = false"
              />
              <div
                class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-600"
              ></div>
            </label>
          </div>

          <!-- From Email -->
          <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
            <div class="md:col-span-1">
              <label
                for="smtpFromEmail"
                class="block text-sm font-medium text-gray-700 mb-1"
              >
                {{ t('settings.notifications.smtpFromEmail') }}
              </label>
              <p class="text-xs text-gray-500 mb-2 md:mb-0">
                {{ t('settings.notifications.smtpFromEmailDesc') }}
              </p>
            </div>
            <div class="md:col-span-2">
              <input
                id="smtpFromEmail"
                v-model="localConfig.from_email"
                type="email"
                :placeholder="
                  t('settings.notifications.smtpFromEmailPlaceholder')
                "
                class="block w-full px-3 py-2 text-sm border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              />
            </div>
          </div>

          <!-- From Name -->
          <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
            <div class="md:col-span-1">
              <label
                for="smtpFromName"
                class="block text-sm font-medium text-gray-700 mb-1"
              >
                {{ t('settings.notifications.smtpFromName') }}
              </label>
              <p class="text-xs text-gray-500 mb-2 md:mb-0">
                {{ t('settings.notifications.smtpFromNameDesc') }}
              </p>
            </div>
            <div class="md:col-span-2">
              <input
                id="smtpFromName"
                v-model="localConfig.from_name"
                type="text"
                :placeholder="
                  t('settings.notifications.smtpFromNamePlaceholder')
                "
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
            {{
              validating
                ? t('common.loading')
                : t('settings.notifications.smtpValidate')
            }}
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
  host: '',
  port: 587,
  username: '',
  password: '',
  use_tls: true,
  use_ssl: false,
  from_email: '',
  from_name: ''
})

const saving = ref(false)
const validating = ref(false)
const error = ref('')
const success = ref('')
const validationError = ref('')
const validationSuccess = ref('')

const hasRequiredFields = computed(() => {
  return (
    localConfig.host &&
    localConfig.port &&
    localConfig.username &&
    localConfig.password &&
    localConfig.from_email
  )
})

watch(
  () => props.modelValue,
  (newValue) => {
    if (newValue) {
      Object.assign(localConfig, {
        enable: newValue.enable ?? false,
        host: newValue.host || '',
        port: newValue.port || 587,
        username: newValue.username || '',
        password: newValue.password || '',
        use_tls: newValue.use_tls ?? true,
        use_ssl: newValue.use_ssl ?? false,
        from_email: newValue.from_email || '',
        from_name: newValue.from_name || ''
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
    const response = await settingsApi.validateSMTPConfig(localConfig)
    const validation = response.data || response

    if (!validation.valid) {
      const errors = validation.errors || [
        validation.message || t('settings.notifications.smtpValidateError')
      ]
      validationError.value = Array.isArray(errors) ? errors.join(', ') : errors
    } else {
      validationSuccess.value = t('settings.notifications.smtpValidateSuccess')
      setTimeout(() => {
        validationSuccess.value = ''
      }, 3000)
    }
  } catch (err) {
    console.error('Failed to validate SMTP config:', err)
    const errorData = err.response?.data
    if (errorData?.data?.errors) {
      const errors = errorData.data.errors
      validationError.value = Array.isArray(errors) ? errors.join(', ') : errors
    } else {
      validationError.value =
        errorData?.message ||
        err.message ||
        t('settings.notifications.smtpValidateError')
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
    await settingsApi.updateSMTPConfig(localConfig)
    success.value = t('settings.notifications.smtpSaveSuccess')
    setTimeout(() => {
      success.value = ''
    }, 3000)
  } catch (err) {
    console.error('Failed to save SMTP config:', err)
    error.value =
      err.response?.data?.message || t('settings.notifications.smtpSaveError')
  } finally {
    saving.value = false
  }
}
</script>
