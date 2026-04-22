<template>
  <BaseModal
    :show="show"
    :title="t('cloudBilling.providers.editNotes')"
    @close="$emit('close')"
  >
    <form @submit.prevent="handleSubmit" class="space-y-4">
      <p class="text-sm text-gray-600">
        {{
          t('cloudBilling.providers.editNotesDesc', {
            name: providerDisplayName || ''
          })
        }}
      </p>

      <div class="space-y-2">
        <label
          for="providerTagInput"
          class="block text-sm font-medium text-gray-700"
        >
          {{ t('cloudBilling.providers.tags') }}
        </label>
        <div ref="tagDropdownRef" class="space-y-3">
          <div
            v-if="formData.tags.length"
            class="flex flex-wrap gap-2 rounded-lg border border-gray-200 bg-gray-50 p-3"
          >
            <span
              v-for="tag in formData.tags"
              :key="`selected-${tag}`"
              class="inline-flex items-center gap-1.5 rounded-full border border-primary-200 bg-white px-3 py-1 text-xs font-medium text-primary-700 shadow-sm"
            >
              {{ tag }}
              <button
                type="button"
                class="rounded-full text-primary-400 transition-colors hover:text-primary-700"
                @click="removeTag(tag)"
              >
                <svg
                  class="h-3.5 w-3.5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </span>
          </div>

          <div class="relative">
            <div class="flex items-center gap-2">
              <div
                class="flex min-h-[40px] min-w-0 flex-1 items-center gap-2 rounded-md border border-gray-300 bg-white px-3 py-2 shadow-sm transition-colors focus-within:border-primary-500 focus-within:ring-2 focus-within:ring-primary-500"
                @click="openTagDropdown"
              >
                <input
                  id="providerTagInput"
                  v-model="tagInput"
                  type="text"
                  :placeholder="t('cloudBilling.providers.tagsPlaceholder')"
                  class="w-full min-w-0 border-0 bg-transparent p-0 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-0"
                  @focus="openTagDropdown"
                  @keydown.enter.prevent="handleTagEnter"
                />
                <button
                  type="button"
                  class="shrink-0 text-gray-400 transition-colors hover:text-gray-600"
                  @click.stop="tagDropdownOpen = !tagDropdownOpen"
                >
                  <svg
                    class="h-4 w-4"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M19 9l-7 7-7-7"
                    />
                  </svg>
                </button>
              </div>
              <BaseButton
                type="button"
                variant="outline"
                size="sm"
                class="shrink-0 px-4"
                @click="addTag()"
              >
                {{ t('common.add') }}
              </BaseButton>
            </div>

            <div
              v-if="tagDropdownOpen"
              class="absolute z-20 mt-2 w-full rounded-lg border border-gray-200 bg-white p-2 shadow-lg"
            >
              <div
                v-if="filteredAvailableTags.length"
                class="max-h-48 space-y-1 overflow-y-auto"
              >
                <button
                  v-for="tag in filteredAvailableTags"
                  :key="`option-${tag}`"
                  type="button"
                  class="flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm transition-colors"
                  :class="
                    formData.tags.includes(tag)
                      ? 'bg-primary-50 text-primary-700'
                      : 'text-gray-700 hover:bg-gray-50'
                  "
                  @click="toggleTag(tag)"
                >
                  <span>{{ tag }}</span>
                  <svg
                    v-if="formData.tags.includes(tag)"
                    class="h-4 w-4"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M5 13l4 4L19 7"
                    />
                  </svg>
                </button>
              </div>
              <div v-else class="px-3 py-2 text-sm text-gray-400">
                {{ t('cloudBilling.providers.tagsEmpty') }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="space-y-2">
        <label
          for="providerNotes"
          class="block text-sm font-medium text-gray-700"
        >
          {{ t('cloudBilling.providers.notes') }}
        </label>
        <textarea
          id="providerNotes"
          v-model="formData.notes"
          rows="4"
          :placeholder="t('cloudBilling.providers.notesPlaceholder')"
          class="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500"
        />
      </div>
    </form>

    <template #footer>
      <div class="flex flex-col-reverse sm:flex-row justify-end gap-3">
        <BaseButton
          variant="outline"
          @click="$emit('close')"
          class="w-full sm:w-auto"
        >
          {{ t('common.cancel') }}
        </BaseButton>
        <BaseButton
          :loading="saving"
          @click="handleSubmit"
          class="w-full sm:w-auto"
        >
          {{ saving ? t('common.saving') : t('common.save') }}
        </BaseButton>
      </div>
    </template>
  </BaseModal>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToast } from '@/composables/useToast'
import { extractResponseData } from '@/utils/api'
import { cloudBillingApi } from '@/api/cloudBilling'
import BaseModal from '@/components/ui/BaseModal.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import { getLocalizedProviderDisplayName } from '@/utils/providerDisplay'

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  },
  provider: {
    type: Object,
    default: null
  },
  tagOptions: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['close', 'saved'])

const { t } = useI18n()
const { showSuccess, showError } = useToast()

const saving = ref(false)
const tagInput = ref('')
const tagDropdownOpen = ref(false)
const tagDropdownRef = ref(null)
const formData = reactive({
  notes: '',
  tags: []
})

const normalizeTag = (value) => String(value || '').trim()

const availableTags = computed(() => {
  const tagSet = new Set()
  ;(props.tagOptions || []).forEach((tag) => {
    const normalized = normalizeTag(tag)
    if (normalized) {
      tagSet.add(normalized)
    }
  })
  formData.tags.forEach((tag) => {
    const normalized = normalizeTag(tag)
    if (normalized) {
      tagSet.add(normalized)
    }
  })
  return Array.from(tagSet).sort((a, b) => a.localeCompare(b))
})

const filteredAvailableTags = computed(() => {
  const keyword = normalizeTag(tagInput.value).toLowerCase()
  if (!keyword) {
    return availableTags.value
  }
  return availableTags.value.filter((tag) =>
    tag.toLowerCase().includes(keyword)
  )
})

const providerDisplayName = computed(() =>
  getLocalizedProviderDisplayName(props.provider, t)
)

const toggleTag = (value) => {
  const tag = normalizeTag(value)
  if (!tag) {
    return
  }
  if (formData.tags.includes(tag)) {
    formData.tags = formData.tags.filter((item) => item !== tag)
    return
  }
  formData.tags = [...formData.tags, tag]
  tagDropdownOpen.value = true
}

const addTag = (value = tagInput.value) => {
  const tag = normalizeTag(value)
  if (!tag || formData.tags.includes(tag)) {
    tagInput.value = ''
    return
  }
  formData.tags = [...formData.tags, tag]
  tagInput.value = ''
  tagDropdownOpen.value = true
}

const removeTag = (value) => {
  const tag = normalizeTag(value)
  formData.tags = formData.tags.filter((item) => item !== tag)
}

const openTagDropdown = () => {
  tagDropdownOpen.value = true
}

const handleTagEnter = () => {
  const exactMatch = availableTags.value.find(
    (tag) => tag.toLowerCase() === normalizeTag(tagInput.value).toLowerCase()
  )
  if (exactMatch) {
    toggleTag(exactMatch)
    tagInput.value = ''
    return
  }
  addTag()
}

const handleClickOutside = (event) => {
  if (tagDropdownRef.value && !tagDropdownRef.value.contains(event.target)) {
    tagDropdownOpen.value = false
  }
}

watch(
  () => props.provider,
  (provider) => {
    formData.notes = provider?.notes || ''
    formData.tags = Array.isArray(provider?.tags) ? [...provider.tags] : []
    tagInput.value = ''
    tagDropdownOpen.value = false
  },
  { immediate: true }
)

onMounted(() => {
  document.addEventListener('pointerdown', handleClickOutside, true)
})

onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', handleClickOutside, true)
})

const handleSubmit = async () => {
  if (!props.provider || saving.value) return

  saving.value = true
  try {
    const response = await cloudBillingApi.patchProvider(props.provider.id, {
      notes: formData.notes,
      tags: [...formData.tags]
    })
    const providerData = extractResponseData(response)
    showSuccess(t('cloudBilling.providers.notesUpdateSuccess'))
    emit('saved', providerData)
  } catch (error) {
    console.error('Failed to update provider notes:', error)
    const responseData = extractResponseData(error?.response || error)
    showError(
      responseData?.detail || t('cloudBilling.providers.notesUpdateError')
    )
  } finally {
    saving.value = false
  }
}
</script>
