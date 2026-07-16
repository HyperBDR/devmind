<script setup lang="ts">
import { computed, ref } from 'vue'
import DropdownOption from './DropdownOption.vue'
import DropdownPanel from './DropdownPanel.vue'
import { bindClickOutside } from './useClickOutside'
import { FORM_SELECT_CLASS, FORM_SELECT_DISABLED_CLASS } from '../utils/formFieldClasses'

export interface FormSelectOption {
  value: string
  label: string
  disabled?: boolean
}

const props = withDefaults(
  defineProps<{
    modelValue?: string
    value?: string
    options: FormSelectOption[]
    disabled?: boolean
    className?: string
    triggerClassName?: string
    testId?: string
    placeholder?: string
  }>(),
  {
    disabled: false,
    className: '',
    triggerClassName: '',
    placeholder: '请选择',
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: string]
  change: [value: string]
}>()

const open = ref(false)
const containerRef = ref<HTMLElement | null>(null)
bindClickOutside(containerRef, () => {
  open.value = false
})

const currentValue = computed(() => props.modelValue ?? props.value ?? '')

const selectedOption = computed(() =>
  props.options.find((option) => option.value === currentValue.value),
)
const displayLabel = computed(() => selectedOption.value?.label || props.placeholder)

function toggleOpen() {
  if (!props.disabled) open.value = !open.value
}

function selectOption(option: FormSelectOption) {
  if (option.disabled) return
  emit('update:modelValue', option.value)
  emit('change', option.value)
  open.value = false
}
</script>

<template>
  <div ref="containerRef" :class="`relative ${className}`">
    <button
      type="button"
      :data-testid="testId"
      :disabled="disabled"
      :class="`${FORM_SELECT_CLASS} ${FORM_SELECT_DISABLED_CLASS} text-left ${triggerClassName} ${
        disabled ? 'cursor-not-allowed' : 'cursor-pointer'
      }`"
      @click="toggleOpen"
    >
      <span class="block truncate">{{ displayLabel }}</span>
    </button>

    <DropdownPanel v-if="open && !disabled" :test-id="testId ? `${testId}-menu` : undefined">
      <li v-for="option in options" :key="option.value">
        <DropdownOption
          :selected="option.value === currentValue"
          @click="selectOption(option)"
        >
          {{ option.label }}
        </DropdownOption>
      </li>
    </DropdownPanel>
  </div>
</template>
