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
            d="M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129"
          />
        </svg>
        <h3 class="text-sm font-semibold">
          {{ t('settings.preferences.title') }}
        </h3>
      </div>
    </div>
    <div class="p-4">
      <p class="text-xs text-gray-600 mb-4">
        {{ t('settings.preferences.desc') }}
      </p>
      <form @submit.prevent="handleSave" class="space-y-4">
        <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
          <div class="md:col-span-1">
            <label
              for="globalLanguage"
              class="block text-sm font-medium text-gray-700 mb-1"
            >
              {{ t('settings.preferences.language') }}
            </label>
            <p class="text-xs text-gray-500">
              {{ t('settings.preferences.languageDesc') }}
            </p>
          </div>
          <div class="md:col-span-2">
            <select
              id="globalLanguage"
              v-model="form.language"
              class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500 text-sm"
            >
              <option value="zh-CN">
                {{ t('settings.preferences.languages.zh-CN') }}
              </option>
              <option value="en-US">
                {{ t('settings.preferences.languages.en') }}
              </option>
            </select>
          </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
          <div class="md:col-span-1">
            <label
              for="globalTimezone"
              class="block text-sm font-medium text-gray-700 mb-1"
            >
              {{ t('settings.preferences.timezone') }}
            </label>
            <p class="text-xs text-gray-500">
              {{ t('settings.preferences.timezoneDesc') }}
            </p>
          </div>
          <div class="md:col-span-2">
            <select
              id="globalTimezone"
              v-model="form.timezone"
              class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500 text-sm"
            >
              <option
                v-for="tz in timezoneOptions"
                :key="tz.value"
                :value="tz.value"
              >
                {{ tz.label }}
              </option>
            </select>
          </div>
        </div>

        <div class="flex justify-end">
          <BaseButton
            type="submit"
            variant="primary"
            size="sm"
            :loading="saving"
          >
            {{ t('settings.saveSettings') }}
          </BaseButton>
        </div>
      </form>
      <p
        v-if="saveMessage"
        class="mt-2 text-sm"
        :class="
          saveMessageType === 'success' ? 'text-green-600' : 'text-red-600'
        "
      >
        {{ saveMessage }}
      </p>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useUserStore } from '@/store/user'
import { getLocalizedTimezones } from '@/utils/timezones'
import BaseButton from '@/components/ui/BaseButton.vue'

const { t, locale } = useI18n()
const userStore = useUserStore()

const saving = ref(false)
const saveMessage = ref('')
const saveMessageType = ref('success')

const form = reactive({
  language: 'zh-CN',
  timezone: 'Asia/Shanghai'
})

const timezoneOptions = computed(() => {
  return getLocalizedTimezones(locale.value === 'zh-CN' ? 'zh-CN' : 'en')
})

function normalizeLanguage(value) {
  if (!value || typeof value !== 'string') return 'zh-CN'
  const v = value.trim()
  if (v === 'en' || v === 'en-US') return 'en-US'
  if (v === 'zh-CN' || v === 'zh') return 'zh-CN'
  return v
}

function syncFromProfile() {
  const profile = userStore.user?.profile
  if (profile) {
    form.language = normalizeLanguage(profile.language) || 'zh-CN'
    form.timezone = profile.timezone || 'Asia/Shanghai'
  }
}

watch(
  () => userStore.user?.profile,
  (profile) => {
    if (profile) syncFromProfile()
  },
  { deep: true }
)

syncFromProfile()

async function handleSave() {
  saving.value = true
  saveMessage.value = ''
  try {
    const backendLanguage = form.language
    await userStore.updateProfile({
      profile_language: backendLanguage,
      profile_timezone: form.timezone || 'Asia/Shanghai'
    })
    saveMessage.value = t('settings.settingsSaved')
    saveMessageType.value = 'success'
    setTimeout(() => {
      saveMessage.value = ''
    }, 3000)
  } catch (err) {
    saveMessage.value = t('settings.settingsError')
    saveMessageType.value = 'error'
  } finally {
    saving.value = false
  }
}
</script>
