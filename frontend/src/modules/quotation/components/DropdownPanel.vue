<script setup lang="ts">
withDefaults(
  defineProps<{
    testId?: string
    className?: string
  }>(),
  {
    className: '',
  },
)
</script>

<template>
  <ul
    :data-testid="testId"
    :class="`qmp-dropdown-panel absolute left-0 right-0 top-full z-30 mt-1 max-h-56 w-full overflow-y-auto py-1 ${className}`"
  >
    <slot />
  </ul>
</template>
