<template>
  <section
    class="mx-auto max-w-3xl rounded-lg border border-rose-200 bg-white p-6"
    role="alert"
  >
    <div class="flex flex-col gap-4 sm:flex-row sm:items-start">
      <div
        class="flex h-10 w-10 flex-none items-center justify-center rounded-full bg-rose-50 text-rose-600"
        aria-hidden="true"
      >
        <svg
          class="h-5 w-5"
          fill="none"
          stroke="currentColor"
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          viewBox="0 0 24 24"
        >
          <path d="M12 9v4" />
          <path d="M12 17h.01" />
          <path
            d="M10.3 3.7 2.6 17a2 2 0 0 0 1.7 3h15.4a2 2 0 0 0 1.7-3L13.7 3.7a2 2 0 0 0-3.4 0Z"
          />
        </svg>
      </div>
      <div class="min-w-0 flex-1">
        <h3 class="text-base font-semibold text-slate-900">
          {{ t('llmOps.errorState.title') }}
        </h3>
        <p class="mt-1 text-sm leading-6 text-slate-600">
          {{ message }}
        </p>
        <p class="mt-1 text-xs leading-5 text-slate-500">
          {{ t('llmOps.errorState.description') }}
        </p>
        <button
          type="button"
          class="btn-secondary btn-action-refresh mt-4"
          @click="emit('retry')"
        >
          {{ t('llmOps.errorState.retry') }}
        </button>
      </div>
    </div>
  </section>
</template>

<script setup>
import { useI18n } from 'vue-i18n'

defineProps({
  message: {
    type: String,
    required: true
  }
})

const emit = defineEmits(['retry'])
const { t } = useI18n()
</script>
