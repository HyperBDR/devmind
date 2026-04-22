<template>
  <!-- Overlay -->
  <Transition
    enter-active-class="transition-opacity duration-200"
    enter-from-class="opacity-0"
    enter-to-class="opacity-100"
    leave-active-class="transition-opacity duration-150"
    leave-from-class="opacity-100"
    leave-to-class="opacity-0"
  >
    <div
      v-if="show"
      @click="handleClose"
      class="fixed inset-0 bg-gray-900 bg-opacity-50 z-40"
    />
  </Transition>

  <!-- Filter Panel -->
  <Transition
    enter-active-class="transition-transform duration-300 ease-out"
    enter-from-class="translate-x-full"
    enter-to-class="translate-x-0"
    leave-active-class="transition-transform duration-250 ease-in"
    leave-from-class="translate-x-0"
    leave-to-class="translate-x-full"
  >
    <div
      v-if="show"
      class="fixed inset-y-0 right-0 w-full max-w-sm bg-white shadow-xl z-50 flex flex-col md:max-w-xs"
    >
      <!-- Header -->
      <div
        class="flex items-center justify-between px-4 py-3 md:px-6 md:py-4 border-b border-gray-200 bg-gradient-to-r from-gray-50 to-gray-100 flex-shrink-0"
      >
        <h2 class="text-base md:text-lg font-semibold text-gray-900">
          {{ title || t('common.filter') }}
        </h2>
        <button
          @click="handleClose"
          class="p-1.5 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
        >
          <svg
            class="w-5 h-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      </div>

      <!-- Filter Content -->
      <div
        class="flex-1 overflow-y-auto px-4 py-3 md:px-6 md:py-4 space-y-4 md:space-y-6"
      >
        <div v-for="filter in filters" :key="filter.key">
          <label class="block text-sm font-medium text-gray-700 mb-2 md:mb-3">
            {{ filter.label }}
          </label>
          <div class="space-y-1 md:space-y-2">
            <label
              v-for="option in filter.options"
              :key="option.value"
              class="flex items-center cursor-pointer hover:bg-gray-50 rounded-md p-1.5 md:p-2 -ml-1 md:-ml-2"
            >
              <input
                type="radio"
                :value="option.value"
                :checked="localFilters[filter.key] === option.value"
                @change="handleFilterChange(filter.key, option.value)"
                class="h-3.5 w-3.5 md:h-4 md:w-4 text-primary-600 focus:ring-primary-500 border-gray-300"
              />
              <span class="ml-2 md:ml-3 text-sm text-gray-700">
                {{ option.label }}
              </span>
            </label>
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div
        class="flex-shrink-0 px-4 py-3 md:px-6 md:py-4 border-t border-gray-200 bg-gray-50 space-y-2 md:space-y-3"
      >
        <BaseButton variant="outline" block size="sm" @click="handleClearAll">
          {{ t('articles.filter.clearAll') }}
        </BaseButton>
        <BaseButton variant="primary" block size="sm" @click="handleApply">
          {{ t('articles.filter.apply') }}
        </BaseButton>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/ui/BaseButton.vue'

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  },
  title: {
    type: String,
    default: ''
  },
  filters: {
    type: Array,
    required: true
    // Each filter should have: { key: string, label: string, options: [{ value: any, label: string }] }
  },
  modelValue: {
    type: Object,
    default: () => ({})
  }
})

const emit = defineEmits(['update:modelValue', 'close', 'apply', 'clear'])

const { t } = useI18n()

const localFilters = ref({})

// Initialize local filters from modelValue
watch(
  () => props.modelValue,
  (newValue) => {
    localFilters.value = { ...newValue }
  },
  { immediate: true, deep: true }
)

// Initialize from filters config
watch(
  () => props.filters,
  (newFilters) => {
    if (newFilters && newFilters.length > 0) {
      const initialFilters = {}
      newFilters.forEach((filter) => {
        if (!(filter.key in localFilters.value)) {
          initialFilters[filter.key] = filter.options[0]?.value || ''
        }
      })
      localFilters.value = { ...localFilters.value, ...initialFilters }
    }
  },
  { immediate: true }
)

const handleClose = () => {
  emit('close')
}

const handleFilterChange = (key, value) => {
  localFilters.value[key] = value
}

const handleApply = () => {
  emit('update:modelValue', { ...localFilters.value })
  emit('apply', { ...localFilters.value })
  handleClose()
}

const handleClearAll = () => {
  const clearedFilters = {}
  props.filters.forEach((filter) => {
    clearedFilters[filter.key] = filter.options[0]?.value || ''
  })
  localFilters.value = clearedFilters
  emit('update:modelValue', clearedFilters)
  emit('clear')
  handleClose()
}
</script>
