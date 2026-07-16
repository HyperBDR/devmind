<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import DropdownOption from './DropdownOption.vue'
import DropdownPanel from './DropdownPanel.vue'
import { bindClickOutside } from './useClickOutside'
import { getFormComboboxClass } from '../utils/formFieldClasses'

const { t } = useI18n()

export type HistoryOption =
  | string
  | {
      value: string
      label?: string
      key?: string
      meta?: unknown
    }

export interface NormalizedHistoryOption {
  value: string
  label?: string
  key: string
  meta?: unknown
}

const props = withDefaults(
  defineProps<{
    modelValue?: string
    value?: string
    options: HistoryOption[]
    placeholder?: string
    type?: 'text' | 'email'
    multiline?: boolean
    rows?: number
    className?: string
    inputClassName?: string
    error?: string
    helperText?: string
    testId?: string
  }>(),
  {
    type: 'text',
    multiline: false,
    rows: 2,
    className: '',
    inputClassName: '',
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: string]
  change: [value: string]
  selectOption: [option: NormalizedHistoryOption]
}>()

const open = ref(false)
const isFiltering = ref(false)
const containerRef = ref<HTMLElement | null>(null)
bindClickOutside(containerRef, () => {
  open.value = false
})

const currentValue = computed(() => props.modelValue ?? props.value ?? '')

function normalizeOption(option: HistoryOption): NormalizedHistoryOption {
  if (typeof option === 'string') {
    return { value: option, key: option }
  }
  return {
    value: option.value,
    label: option.label,
    key: option.key || `${option.value}|${option.label || ''}`,
    meta: option.meta,
  }
}

const normalizedOptions = computed(() => props.options.map(normalizeOption))

const filteredOptions = computed(() => {
  if (!isFiltering.value) return normalizedOptions.value

  const normalized = currentValue.value.trim().toLowerCase()
  if (!normalized) return normalizedOptions.value

  return normalizedOptions.value.filter((option) => {
    const valueMatch = option.value.toLowerCase().includes(normalized)
    const labelMatch = option.label?.toLowerCase().includes(normalized) ?? false
    return valueMatch || labelMatch
  })
})

const showDropdown = computed(() => open.value && filteredOptions.value.length > 0)
const resolvedInputClassName = computed(
  () => props.inputClassName || getFormComboboxClass(Boolean(props.error)),
)

function emitValue(next: string) {
  emit('update:modelValue', next)
  emit('change', next)
}

function openDropdown() {
  isFiltering.value = false
  open.value = true
}

function onInput(event: Event) {
  const target = event.target as HTMLInputElement | HTMLTextAreaElement
  isFiltering.value = true
  emitValue(target.value)
  open.value = true
}

function selectOption(option: NormalizedHistoryOption) {
  emitValue(option.value)
  emit('selectOption', option)
  isFiltering.value = false
  open.value = false
}

function toggleChevron() {
  if (open.value) {
    open.value = false
    return
  }
  openDropdown()
}
</script>

<template>
  <div ref="containerRef" :class="`relative ${className}`">
    <textarea
      v-if="multiline"
      :data-testid="testId"
      :value="currentValue"
      :placeholder="placeholder"
      :rows="rows"
      :class="`${resolvedInputClassName} resize-none`"
      @input="onInput"
      @focus="openDropdown"
    />
    <input
      v-else
      :data-testid="testId"
      :type="type"
      :value="currentValue"
      :placeholder="placeholder"
      :class="resolvedInputClassName"
      @input="onInput"
      @focus="openDropdown"
    />

    <button
      type="button"
      :aria-label="t('quotation.common.showHistory')"
      class="absolute right-0 w-10 cursor-pointer"
      :class="multiline ? 'top-2 h-8' : 'inset-y-0'"
      @mousedown.prevent
      @click="toggleChevron"
    />

    <DropdownPanel v-if="showDropdown" :test-id="testId ? `${testId}-history` : undefined">
      <li v-for="option in filteredOptions" :key="option.key">
        <DropdownOption
          :selected="option.value === currentValue.trim()"
          :subtitle="option.label"
          @click="selectOption(option)"
        >
          {{ option.value }}
        </DropdownOption>
      </li>
    </DropdownPanel>

    <p v-if="error" class="mt-1 text-[10px] text-red-500">{{ error }}</p>
    <p v-if="helperText" class="mt-1 text-[10px] font-medium text-slate-400">{{ helperText }}</p>
  </div>
</template>
