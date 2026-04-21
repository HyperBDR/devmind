<template>
  <span
    v-if="location"
    class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-100 text-blue-800 border border-blue-200 shadow-sm"
  >
    <svg
      class="w-3.5 h-3.5 flex-shrink-0"
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
    >
      <path
        stroke-linecap="round"
        stroke-linejoin="round"
        stroke-width="2"
        d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2M9 6h6m-6 4h6m-2 4h.01M9 16h.01"
      />
    </svg>
    {{ location }}
  </span>
</template>

<script setup>
defineProps({
  location: {
    type: String,
    default: ''
  }
})
</script>
