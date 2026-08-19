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
            d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
          />
        </svg>
        <h3 class="text-sm font-semibold">
          {{ t('settings.displayNameCard.title') }}
        </h3>
      </div>
    </div>
    <div class="p-4">
      <p class="text-xs text-gray-600 mb-4">
        {{ t('settings.displayNameCard.desc') }}
      </p>
      <form @submit.prevent="handleSave" class="space-y-4">
        <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
          <div class="md:col-span-1">
            <label
              for="displayName"
              class="block text-sm font-medium text-gray-700 mb-1"
            >
              {{ t('settings.displayNameCard.label') }}
            </label>
          </div>
          <div class="md:col-span-2">
            <input
              id="displayName"
              v-model="form.display_name"
              type="text"
              maxlength="120"
              :placeholder="t('settings.displayNameCard.placeholder')"
              class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500 text-sm"
            />
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
import { reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useUserStore } from '@/store/user'
import BaseButton from '@/components/ui/BaseButton.vue'

const { t } = useI18n()
const userStore = useUserStore()

const saving = ref(false)
const saveMessage = ref('')
const saveMessageType = ref('success')

const form = reactive({
  display_name: ''
})

function syncFromProfile() {
  const userInfo = userStore.userInfo
  if (userInfo) {
    form.display_name = userInfo.display_name || ''
  }
}

watch(
  () => userStore.userInfo,
  (userInfo) => {
    if (userInfo) syncFromProfile()
  },
  { deep: true }
)

syncFromProfile()

async function handleSave() {
  saving.value = true
  saveMessage.value = ''
  try {
    await userStore.updateProfile({
      display_name: form.display_name.trim()
    })
    saveMessage.value = t('settings.displayNameCard.saved')
    saveMessageType.value = 'success'
    setTimeout(() => {
      saveMessage.value = ''
    }, 3000)
  } catch (err) {
    saveMessage.value = t('settings.displayNameCard.error')
    saveMessageType.value = 'error'
  } finally {
    saving.value = false
  }
}
</script>
