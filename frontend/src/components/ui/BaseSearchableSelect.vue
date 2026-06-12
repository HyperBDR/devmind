<template>
  <Combobox
    v-model="selectedOption"
    :disabled="disabled"
    nullable
    as="div"
    class="relative"
  >
    <div class="relative">
      <ComboboxInput
        class="block w-full rounded-md border border-gray-300 bg-white py-2 pl-3 pr-10 text-sm shadow-sm focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500 disabled:cursor-not-allowed disabled:bg-gray-100 disabled:text-gray-500"
        :display-value="displayOption"
        :placeholder="loading ? loadingText : placeholder"
        :disabled="disabled"
        autocomplete="off"
        @input="handleInput"
        @change="handleCustomChange"
        @focus="query = ''"
      />
      <ComboboxButton
        class="absolute inset-y-0 right-0 flex items-center px-2 text-gray-400 disabled:cursor-not-allowed"
      >
        <span class="text-xs">⌄</span>
      </ComboboxButton>
    </div>

    <Transition
      leave-active-class="transition duration-100 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
      @after-leave="query = ''"
    >
      <ComboboxOptions
        class="absolute z-50 mt-1 max-h-64 w-full overflow-auto rounded-md border border-gray-200 bg-white py-1 text-sm shadow-lg focus:outline-none"
      >
        <div v-if="loading" class="px-3 py-2 text-sm text-gray-500">
          {{ loadingText }}
        </div>
        <div
          v-else-if="filteredOptions.length === 0"
          class="px-3 py-2 text-sm text-gray-500"
        >
          {{ emptyText }}
        </div>
        <ComboboxOption
          v-for="option in filteredOptions"
          v-else
          :key="option.value"
          v-slot="{ active, selected }"
          :value="option"
          as="template"
        >
          <li
            :class="[
              'cursor-pointer px-3 py-2',
              active ? 'bg-primary-50 text-primary-700' : 'text-gray-900'
            ]"
          >
            <div class="flex items-center justify-between gap-3">
              <span class="truncate font-medium">
                {{ option.label }}
              </span>
              <span v-if="selected" class="shrink-0 text-xs text-primary-600">
                ✓
              </span>
            </div>
            <p
              v-if="option.description"
              class="mt-0.5 truncate text-xs text-gray-500"
            >
              {{ option.description }}
            </p>
          </li>
        </ComboboxOption>
      </ComboboxOptions>
    </Transition>
  </Combobox>
</template>

<script setup>
import { computed, ref } from 'vue'
import {
  Combobox,
  ComboboxButton,
  ComboboxInput,
  ComboboxOption,
  ComboboxOptions
} from '@headlessui/vue'

const props = defineProps({
  modelValue: {
    type: String,
    default: ''
  },
  options: {
    type: Array,
    default: () => []
  },
  placeholder: {
    type: String,
    default: ''
  },
  loadingText: {
    type: String,
    default: 'Loading...'
  },
  emptyText: {
    type: String,
    default: 'No results'
  },
  loading: {
    type: Boolean,
    default: false
  },
  disabled: {
    type: Boolean,
    default: false
  },
  allowCustom: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue', 'change'])
const query = ref('')

const selectedOption = computed({
  get() {
    const option =
      props.options.find((item) => item.value === props.modelValue) || null
    if (option || !props.allowCustom || !props.modelValue) return option
    return {
      value: props.modelValue,
      label: props.modelValue
    }
  },
  set(option) {
    const value = option?.value || ''
    emit('update:modelValue', value)
    emit('change', value)
  }
})

const filteredOptions = computed(() => {
  const text = query.value.trim().toLowerCase()
  if (!text) return props.options
  return props.options.filter((option) => {
    return [option.label, option.description, option.value, option.searchText]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(text))
  })
})

function displayOption(option) {
  return option?.label || ''
}

function handleInput(event) {
  const value = event?.target?.value || ''
  query.value = value
}

function handleCustomChange(event) {
  if (!props.allowCustom) return
  // Headless UI Combobox already keeps the displayed value in sync via the
  // v-model on `selectedOption`; we only step in for two cases:
  //   1. The input was cleared by the user → emit empty value.
  //   2. The current query is not in `options` and the field is `allowCustom`,
  //      in which case the user is explicitly committing a free-text value.
  const value = event?.target?.value || ''
  const matchedOption = props.options.find((option) => {
    return option.label === value || option.value === value
  })
  if (value === '') {
    emit('update:modelValue', '')
    emit('change', '')
    return
  }
  if (matchedOption) return
  if (query.value === value) {
    emit('update:modelValue', value)
    emit('change', value)
  }
}
</script>
