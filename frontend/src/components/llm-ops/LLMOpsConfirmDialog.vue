<template>
  <div
    v-if="open"
    class="fixed inset-0 z-[70] flex items-center justify-center bg-slate-950/40 px-4"
    @click.self="$emit('cancel')"
  >
    <div
      class="w-full max-w-md rounded-xl border border-slate-200 bg-white shadow-2xl"
      role="dialog"
      aria-modal="true"
      aria-labelledby="llm-ops-confirm-title"
    >
      <div class="border-b border-slate-200 px-5 py-4">
        <h3
          id="llm-ops-confirm-title"
          class="text-base font-semibold text-slate-900"
        >
          {{ title }}
        </h3>
      </div>
      <div class="px-5 py-5">
        <p class="whitespace-pre-line text-sm leading-6 text-slate-600">
          {{ message }}
        </p>
      </div>
      <div
        class="flex justify-end gap-2 border-t border-slate-200 bg-slate-50 px-5 py-4"
      >
        <button
          type="button"
          class="btn-secondary"
          :disabled="busy"
          @click="$emit('cancel')"
        >
          {{ cancelLabel }}
        </button>
        <button
          type="button"
          class="btn-primary"
          :class="{ 'btn-danger': danger }"
          :disabled="busy"
          @click="$emit('confirm')"
        >
          {{ busy ? busyLabel : confirmLabel }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  open: {
    type: Boolean,
    default: false
  },
  title: {
    type: String,
    default: ''
  },
  message: {
    type: String,
    default: ''
  },
  confirmLabel: {
    type: String,
    default: 'Confirm'
  },
  cancelLabel: {
    type: String,
    default: 'Cancel'
  },
  busyLabel: {
    type: String,
    default: 'Processing…'
  },
  danger: {
    type: Boolean,
    default: false
  },
  busy: {
    type: Boolean,
    default: false
  }
})

defineEmits(['cancel', 'confirm'])
</script>
