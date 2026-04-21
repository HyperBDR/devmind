<template>
  <BaseModal :show="show" :title="t('retry.dialogTitle')" @close="handleClose">
    <div class="space-y-4">
      <!-- Force Option -->
      <div class="border-t border-gray-200 pt-4">
        <div class="flex items-center gap-3">
          <div class="flex items-center flex-shrink-0">
            <input
              id="force-retry"
              :checked="effectiveForce"
              @change="handleForceChange"
              type="checkbox"
              class="focus:ring-primary-500 h-4 w-4 text-primary-600 border-gray-300 rounded"
              :disabled="loading || forceRequired"
            />
          </div>
          <div class="flex-1 min-w-0">
            <label
              for="force-retry"
              class="block text-sm font-medium text-gray-700 cursor-pointer"
            >
              {{ t('retry.forceMode') }}
            </label>
          </div>
        </div>
        <div class="mt-2">
          <div
            class="py-3 px-4 sm:px-6 bg-yellow-50 border border-yellow-200 rounded-md"
          >
            <div class="flex gap-2">
              <div class="flex-shrink-0">
                <svg
                  class="h-5 w-5 text-yellow-400"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path
                    fill-rule="evenodd"
                    d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
                    clip-rule="evenodd"
                  />
                </svg>
              </div>
              <div class="flex-1 min-w-0">
                <p class="text-sm text-yellow-800 leading-relaxed">
                  {{ t('retry.forceModeWarning') }}
                </p>
              </div>
            </div>
          </div>
        </div>
        <div v-if="forceRequired" class="mt-2">
          <p class="text-sm text-gray-600">
            {{ t('retry.forceRequiredHint') }}
          </p>
        </div>
      </div>
    </div>

    <template #footer>
      <div
        class="w-full flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-2"
      >
        <BaseButton
          variant="secondary"
          @click="handleClose"
          :disabled="loading"
          class="w-full sm:w-auto"
        >
          {{ t('common.cancel') }}
        </BaseButton>
        <BaseButton
          variant="primary"
          @click="handleRetry"
          :loading="loading"
          :disabled="!canRetry"
          class="w-full sm:w-auto"
        >
          {{ t('retry.confirmRetry') }}
        </BaseButton>
      </div>
    </template>
  </BaseModal>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseModal from '@/components/ui/BaseModal.vue'
import BaseButton from '@/components/ui/BaseButton.vue'

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  },
  status: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['close', 'confirm'])

const { t } = useI18n()

const loading = ref(false)
const localForce = ref(false)

// Check if force retry is required (for completed status)
const forceRequired = computed(() => {
  return props.status === 'completed'
})

// Computed property to get the effective force value
// For completed articles, always return true (force is required)
// For other articles, return the localForce value
const effectiveForce = computed(() => {
  if (forceRequired.value) {
    return true
  }
  return localForce.value
})

// Handle checkbox change event
const handleForceChange = (event) => {
  if (!forceRequired.value) {
    localForce.value = event.target.checked
  }
}

// Check if retry button can be clicked
const canRetry = computed(() => {
  // If force is required, must be checked (always true for completed)
  if (forceRequired.value) {
    return effectiveForce.value === true
  }
  // For other statuses, can retry with or without force
  return true
})

const handleClose = () => {
  emit('close')
  // Reset when dialog closes
  localForce.value = false
}

const handleRetry = () => {
  emit('confirm', {
    force: effectiveForce.value
  })
}

// Watch for dialog open and status changes - ensure force is set correctly
watch(
  () => [props.show, props.status],
  async ([show, status]) => {
    if (show) {
      // Wait for next tick to ensure all props are updated
      await nextTick()
      // For completed articles, force is always required
      // The effectiveForce computed will handle this automatically
      // But we still need to ensure localForce is set for consistency
      if (status === 'completed') {
        localForce.value = true
      } else {
        localForce.value = false
      }
    } else {
      // Reset when dialog closes
      localForce.value = false
    }
  },
  { immediate: false }
)
</script>
