<template>
  <section class="rounded-lg border px-4 py-3 text-sm" :class="bannerClass">
    <div class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
      <div>
        <p class="font-semibold">{{ title }}</p>
        <p class="mt-1">{{ text }}</p>
      </div>
      <div v-if="canManageSync" class="flex flex-wrap gap-2">
        <button
          v-for="item in actions"
          :key="item.key"
          type="button"
          class="rounded-md border border-current px-2 py-1 text-xs font-medium"
          :disabled="syncLoading"
          @click="$emit('incremental-sync', item.key)"
        >
          {{ item.label }}
        </button>
      </div>
    </div>
  </section>
</template>

<script setup>
defineProps({
  bannerClass: { type: String, required: true },
  canManageSync: { type: Boolean, default: false },
  syncLoading: { type: Boolean, default: false },
  text: { type: String, required: true },
  title: { type: String, required: true },
})

defineEmits(['incremental-sync'])

const actions = [
  { key: 'domestic', label: '国内增量' },
  { key: 'oversea', label: '海外增量' },
  { key: 'oversea_stats', label: '结算增量' },
]
</script>
