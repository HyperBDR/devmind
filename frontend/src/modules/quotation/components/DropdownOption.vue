<script setup lang="ts">
import { Check } from 'lucide-vue-next'

withDefaults(
  defineProps<{
    selected: boolean
    subtitle?: string
    compact?: boolean
  }>(),
  {
    compact: false,
  },
)

const emit = defineEmits<{
  click: []
}>()
</script>

<template>
  <button
    type="button"
    :class="[
      'qmp-dropdown-option',
      selected ? 'qmp-dropdown-option--selected' : '',
      compact ? '!items-center !gap-0 !px-2 !py-1.5' : '',
    ]"
    @mousedown.prevent
    @click="emit('click')"
  >
    <span
      v-if="!compact"
      class="mt-0.5 inline-flex w-4 shrink-0 justify-center"
    >
      <Check v-if="selected" class="h-3.5 w-3.5" :stroke-width="3" />
    </span>
    <span class="min-w-0 flex-1">
      <span
        class="block text-sm leading-5"
        :class="compact ? 'text-center' : ''"
      >
        <slot />
      </span>
      <span
        v-if="subtitle"
        class="qmp-dropdown-option-subtitle block text-xs leading-4 text-dm-text-tertiary"
      >
        {{ subtitle }}
      </span>
    </span>
  </button>
</template>
