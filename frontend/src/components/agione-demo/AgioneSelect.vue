<template>
  <Listbox :model-value="modelValue" :disabled="disabled" @update:model-value="$emit('update:modelValue', $event)">
    <div ref="container" class="agione-select">
      <ListboxButton class="agione-select-button" :aria-label="label" @click="positionMenu" @keydown="positionMenu">
        <span>{{ options.find(option => option.value === modelValue)?.label || placeholder }}</span>
        <svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="m6 8 4 4 4-4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" /></svg>
      </ListboxButton>
      <Teleport v-if="menuTarget" :to="menuTarget">
      <ListboxOptions class="agione-select-options" :style="menuStyle">
        <ListboxOption v-for="option in options" :key="option.value" v-slot="{ selected, active }" as="template" :value="option.value" :disabled="option.disabled">
          <li :class="{ selected, active }">
            <span>{{ option.label }}</span>
            <svg v-if="selected" viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="m5 10 3 3 7-7" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" /></svg>
          </li>
        </ListboxOption>
      </ListboxOptions>
      </Teleport>
    </div>
  </Listbox>
</template>

<script setup>
import { Listbox, ListboxButton, ListboxOption, ListboxOptions } from '@headlessui/vue'
import { onBeforeUnmount, onMounted, ref } from 'vue'

const container = ref(null)
const menuTarget = ref(null)
const menuStyle = ref({})

function positionMenu () {
  const button = container.value?.querySelector('button')
  if (!button) return
  const rect = button.getBoundingClientRect()
  const gap = 6
  const margin = 8
  const above = rect.top - margin - gap
  const below = window.innerHeight - rect.bottom - margin - gap
  const upward = below < 240 && above > below
  const height = Math.max(0, Math.min(240, upward ? above : below))
  menuStyle.value = {
    left: `${rect.left}px`,
    width: `${rect.width}px`,
    maxHeight: `${height}px`,
    ...(upward
      ? { bottom: `${window.innerHeight - rect.top + gap}px` }
      : { top: `${rect.bottom + gap}px` })
  }
}

onMounted(() => {
  menuTarget.value = container.value.closest('dialog') || document.body
  window.addEventListener('resize', positionMenu)
  window.addEventListener('scroll', positionMenu, true)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', positionMenu)
  window.removeEventListener('scroll', positionMenu, true)
})

defineProps({
  modelValue: { type: [String, Number], default: null },
  options: { type: Array, required: true },
  label: { type: String, required: true },
  placeholder: { type: String, default: '请选择' },
  disabled: { type: Boolean, default: false }
})
defineEmits(['update:modelValue'])
</script>

<style scoped>
.agione-select { position: relative; width: 100%; min-width: 0; }
.agione-select-button { display: flex; align-items: center; justify-content: space-between; gap: 10px; width: 100%; min-height: 42px; padding: 9px 11px; border: 1px solid #dce3ee; border-radius: 7px; background: #fff; color: #17233b; font: inherit; font-size: 13px; text-align: left; cursor: pointer; }
.agione-select-button span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.agione-select-button svg, .agione-select-options svg { width: 16px; height: 16px; flex: none; }
.agione-select-button svg { color: #75859d; }
.agione-select-button:focus-visible, .agione-select-button[aria-expanded=true] { outline: 0; border-color: #2563eb; box-shadow: 0 0 0 3px #2563eb12; }
.agione-select-button:disabled { opacity: .55; cursor: not-allowed; }
.agione-select-options { position: fixed; z-index: 20; box-sizing: border-box; overflow: auto; margin: 0; padding: 5px; list-style: none; border: 1px solid #dce3ee; border-radius: 9px; background: #fff; box-shadow: 0 12px 32px #172b491a, 0 2px 6px #172b4908; }
.agione-select-options li { display: flex; justify-content: space-between; align-items: center; gap: 12px; min-height: 36px; box-sizing: border-box; padding: 8px 10px; border-radius: 5px; color: #17233b; font-size: 13px; font-weight: 400; cursor: pointer; }
.agione-select-options li.active { background: #f4f7fb; }
.agione-select-options li.selected { background: #eff6ff; color: #2563eb; font-weight: 500; }
.agione-select-options li[aria-disabled=true] { opacity: .5; cursor: not-allowed; }
</style>
