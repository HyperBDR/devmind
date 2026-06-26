<template>
  <div
    v-if="canChangePassword"
    class="bg-white rounded border border-gray-200 shadow-sm"
  >
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
            d="M16 11V7a4 4 0 00-8 0v4m-2 0h12a2 2 0 012
               2v6a2 2 0 01-2 2H6a2 2 0 01-2-2v-6a2
               2 0 012-2z"
          />
        </svg>
        <h3 class="text-sm font-semibold">
          {{ t('settings.changePassword.title') }}
        </h3>
      </div>
    </div>

    <form class="p-4 space-y-4" @submit.prevent="handleSubmit">
      <div
        v-if="successMessage"
        class="rounded-md border border-green-200 bg-green-50 p-3"
        role="status"
      >
        <p class="text-sm font-medium text-green-800">
          {{ successMessage }}
        </p>
      </div>

      <div
        v-if="errorMessage"
        class="rounded-md border border-red-200 bg-red-50 p-3"
        role="alert"
      >
        <p class="text-sm font-medium text-red-800">
          {{ errorMessage }}
        </p>
      </div>

      <div class="grid grid-cols-1 gap-4 md:grid-cols-3">
        <PasswordInput
          v-model="form.oldPassword"
          :label="t('settings.changePassword.oldPassword')"
          :placeholder="t('settings.changePassword.oldPasswordPlaceholder')"
          autocomplete="current-password"
          :error="fieldErrors.oldPassword"
          :disabled="submitting"
          required
        />

        <PasswordInput
          v-model="form.newPassword"
          :label="t('settings.changePassword.newPassword')"
          :placeholder="t('settings.changePassword.newPasswordPlaceholder')"
          autocomplete="new-password"
          :error="fieldErrors.newPassword"
          :disabled="submitting"
          required
        />

        <PasswordInput
          v-model="form.confirmPassword"
          :label="t('settings.changePassword.confirmPassword')"
          :placeholder="confirmPasswordPlaceholder"
          autocomplete="new-password"
          :error="fieldErrors.confirmPassword"
          :disabled="submitting"
          required
        />
      </div>

      <p class="text-xs text-gray-500">
        {{ t('settings.changePassword.requirements') }}
      </p>

      <div class="flex justify-end">
        <BaseButton
          type="submit"
          variant="primary"
          class="w-full sm:w-auto"
          :loading="submitting"
          :disabled="submitting"
        >
          {{ t('settings.changePassword.submit') }}
        </BaseButton>
      </div>
    </form>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { authApi } from '@/api/auth'
import { useUserStore } from '@/store/user'
import BaseButton from '@/components/ui/BaseButton.vue'
import PasswordInput from '@/components/ui/PasswordInput.vue'

const { t } = useI18n()
const userStore = useUserStore()

const form = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: ''
})

const fieldErrors = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: ''
})

const submitting = ref(false)
const errorMessage = ref('')
const successMessage = ref('')
const confirmPasswordPlaceholder = computed(() =>
  t('settings.changePassword.confirmPasswordPlaceholder')
)

const canChangePassword = computed(
  () => userStore.userInfo?.auth_info?.can_change_password === true
)

const clearMessages = () => {
  errorMessage.value = ''
  successMessage.value = ''
  fieldErrors.oldPassword = ''
  fieldErrors.newPassword = ''
  fieldErrors.confirmPassword = ''
}

const resetForm = () => {
  form.oldPassword = ''
  form.newPassword = ''
  form.confirmPassword = ''
}

const validateForm = () => {
  clearMessages()

  if (!form.oldPassword) {
    fieldErrors.oldPassword = t('settings.changePassword.oldPasswordRequired')
  }

  if (!form.newPassword) {
    fieldErrors.newPassword = t('settings.changePassword.newPasswordRequired')
  }

  if (!form.confirmPassword) {
    fieldErrors.confirmPassword = t(
      'settings.changePassword.confirmPasswordRequired'
    )
  }

  if (
    fieldErrors.oldPassword ||
    fieldErrors.newPassword ||
    fieldErrors.confirmPassword
  ) {
    return false
  }

  if (form.newPassword !== form.confirmPassword) {
    fieldErrors.confirmPassword = t('settings.changePassword.passwordMismatch')
    return false
  }

  if (form.newPassword.length < 8) {
    fieldErrors.newPassword = t('settings.changePassword.passwordTooShort')
    return false
  }

  if (form.newPassword.length > 32) {
    fieldErrors.newPassword = t('settings.changePassword.passwordTooLong')
    return false
  }

  if (!/[a-zA-Z]/.test(form.newPassword) || !/[0-9]/.test(form.newPassword)) {
    fieldErrors.newPassword = t('settings.changePassword.passwordRequirements')
    return false
  }

  return true
}

const normalizeError = (value) => {
  if (Array.isArray(value)) {
    return value
      .map((item) => normalizeError(item))
      .filter(Boolean)
      .join(', ')
  }

  if (typeof value === 'string') {
    return value
  }

  if (value && typeof value === 'object') {
    return Object.values(value)
      .map((item) => normalizeError(item))
      .filter(Boolean)
      .join(', ')
  }

  return ''
}

const findErrorMessage = (payload, keys) => {
  for (const key of keys) {
    const message = normalizeError(payload?.[key])
    if (message) {
      return message
    }
  }

  return ''
}

const applyApiErrors = (data) => {
  const responsePayload = data?.data || data || {}
  const payload = responsePayload.errors || responsePayload
  const fields = {
    oldPassword: [
      'oldPassword',
      'old_password',
      'currentPassword',
      'current_password'
    ],
    newPassword: [
      'newPassword1',
      'new_password1',
      'new_password_1',
      'newPassword',
      'new_password'
    ],
    confirmPassword: [
      'newPassword2',
      'new_password2',
      'new_password_2',
      'confirmPassword',
      'confirm_password'
    ]
  }

  Object.entries(fields).forEach(([formField, keys]) => {
    const message = findErrorMessage(payload, keys)
    if (message) {
      fieldErrors[formField] = message
    }
  })

  const fieldErrorMessage = [
    fieldErrors.oldPassword,
    fieldErrors.newPassword,
    fieldErrors.confirmPassword
  ].find(Boolean)

  errorMessage.value =
    normalizeError(payload.non_field_errors) ||
    normalizeError(payload.nonFieldErrors) ||
    fieldErrorMessage ||
    responsePayload.error ||
    responsePayload.error_detail ||
    responsePayload.detail ||
    responsePayload.message ||
    t('settings.changePassword.error')
}

const handleSubmit = async () => {
  if (!validateForm()) {
    return
  }

  submitting.value = true

  try {
    const response = await authApi.changePassword({
      oldPassword: form.oldPassword,
      newPassword1: form.newPassword,
      newPassword2: form.confirmPassword
    })

    resetForm()
    successMessage.value =
      response?.data?.detail ||
      response?.data?.message ||
      t('settings.changePassword.success')
  } catch (error) {
    applyApiErrors(error.response?.data)
  } finally {
    submitting.value = false
  }
}
</script>
