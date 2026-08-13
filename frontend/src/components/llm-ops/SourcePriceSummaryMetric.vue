<template>
  <div
    class="rounded-lg border px-3 py-2"
    :class="
      tone === 'warning'
        ? 'border-amber-200 bg-amber-50'
        : 'border-slate-200 bg-slate-50'
    "
  >
    <p class="text-xs text-slate-500">{{ label }}</p>
    <strong class="mt-1 block font-mono text-lg text-slate-800">
      {{ value ?? 0 }}
    </strong>
  </div>
</template>

<script setup>
defineProps({
  label: { type: String, required: true },
  value: { type: [Number, String], default: 0 },
  tone: { type: String, default: 'default' }
})
</script>
