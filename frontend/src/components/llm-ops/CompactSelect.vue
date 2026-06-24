<template>
  <div ref="selectRef" class="compact-select" :class="className">
    <button
      ref="triggerRef"
      class="compact-select-trigger"
      :class="{
        'compact-select-sm': size === 'sm',
        'compact-select-disabled': disabled
      }"
      :title="title || selectedOption?.label || ''"
      :disabled="disabled"
      type="button"
      @click="toggle"
    >
      <span class="truncate">
        {{ selectedOption?.label || placeholder }}
      </span>
      <span class="compact-select-caret">⌄</span>
    </button>

    <div v-if="open" class="compact-select-menu" :style="menuStyle">
      <input
        v-if="searchable"
        ref="searchInputRef"
        v-model="search"
        class="compact-select-search"
        :placeholder="searchPlaceholder"
        @keydown.escape="open = false"
      />
      <button
        v-for="option in filteredOptions"
        :key="option.value"
        class="compact-select-option"
        :class="optionClasses(option)"
        :disabled="option.disabled || option.type === 'group'"
        type="button"
        @click="select(option.value)"
      >
        <span
          v-if="option.type === 'group'"
          class="compact-select-group-label"
        >
          {{ option.label }}
        </span>
        <span v-else class="min-w-0 flex-1">
          <span class="block truncate">{{ option.label }}</span>
          <span
            v-if="option.description"
            class="mt-0.5 block truncate text-[11px] font-normal text-slate-400"
          >
            {{ option.description }}
          </span>
        </span>
        <span v-if="option.badge" class="compact-select-badge">
          {{ option.badge }}
        </span>
        <span
          v-if="String(modelValue) === String(option.value)"
          class="compact-select-check"
        >
          ✓
        </span>
      </button>
      <div v-if="!filteredOptions.length" class="compact-select-empty">
        没有匹配的选项
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  modelValue: {
    type: [String, Number, Boolean],
    default: ''
  },
  options: {
    type: Array,
    required: true
  },
  placeholder: {
    type: String,
    default: '请选择'
  },
  size: {
    type: String,
    default: 'md'
  },
  title: {
    type: String,
    default: ''
  },
  className: {
    type: String,
    default: ''
  },
  searchable: {
    type: Boolean,
    default: false
  },
  disabled: {
    type: Boolean,
    default: false
  },
  searchPlaceholder: {
    type: String,
    default: '搜索选项'
  },
  menuMinWidth: {
    type: Number,
    default: 0
  }
})

const emit = defineEmits(['update:modelValue', 'change'])

const open = ref(false)
const selectRef = ref(null)
const triggerRef = ref(null)
const searchInputRef = ref(null)
const menuStyle = ref({})
const search = ref('')

const selectedOption = computed(() =>
  props.options.find(
    (option) => String(option.value) === String(props.modelValue)
  )
)

const filteredOptions = computed(() => {
  const keyword = normalizeSearch(search.value)
  if (!props.searchable || !keyword) return props.options
  return props.options.filter((option) => {
    const text = [
      option.label,
      option.description,
      option.badge,
      option.searchText
    ].join(' ')
    return normalizeSearch(text).includes(keyword)
  })
})

watch(open, (value) => {
  if (!value) {
    search.value = ''
    return
  }
  nextTick(() => {
    updateMenuPosition()
    searchInputRef.value?.focus()
  })
})

onMounted(() => {
  document.addEventListener('click', handleOutside)
  window.addEventListener('resize', updateMenuPosition)
  window.addEventListener('scroll', updateMenuPosition, true)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleOutside)
  window.removeEventListener('resize', updateMenuPosition)
  window.removeEventListener('scroll', updateMenuPosition, true)
})

function toggle() {
  if (props.disabled) return
  open.value = !open.value
  if (open.value) {
    nextTick(updateMenuPosition)
  }
}

function select(value) {
  const option = props.options.find(
    (item) => String(item.value) === String(value)
  )
  if (option?.disabled || option?.type === 'group') return
  emit('update:modelValue', value)
  emit('change', value)
  open.value = false
}

function optionClasses(option) {
  return {
    'compact-select-option-active':
      String(props.modelValue) === String(option.value),
    'compact-select-option-disabled': option.disabled,
    'compact-select-option-group': option.type === 'group'
  }
}

function handleOutside(event) {
  if (!open.value || !selectRef.value) return
  if (!selectRef.value.contains(event.target)) {
    open.value = false
  }
}

function updateMenuPosition() {
  if (!open.value || !triggerRef.value) return
  const rect = triggerRef.value.getBoundingClientRect()
  const gap = 4
  const viewportPadding = 12
  const spaceBelow = window.innerHeight - rect.bottom - gap
  const spaceAbove = rect.top - gap
  const opensUp = spaceBelow < 140 && spaceAbove > spaceBelow
  const desiredWidth = Math.max(rect.width, Number(props.menuMinWidth) || 0)
  const width = Math.min(
    desiredWidth,
    window.innerWidth - viewportPadding * 2
  )
  const left = Math.min(
    Math.max(viewportPadding, rect.left),
    window.innerWidth - width - viewportPadding
  )
  const maxHeight = Math.max(
    120,
    Math.min(260, opensUp ? spaceAbove - gap : spaceBelow - gap)
  )
  menuStyle.value = {
    left: `${left}px`,
    top: opensUp ? 'auto' : `${rect.bottom + gap}px`,
    bottom: opensUp
      ? `${window.innerHeight - rect.top + gap}px`
      : 'auto',
    width: `${width}px`,
    maxHeight: `${maxHeight}px`
  }
}

function normalizeSearch(value) {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '')
}
</script>

<style scoped>
.compact-select {
  @apply relative min-w-0;
}

.price-mode-select {
  width: 7.5rem;
}

.currency-select {
  width: 6.75rem;
}

.compact-select-trigger {
  @apply flex min-h-9 w-full items-center justify-between gap-2 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-left text-sm font-medium text-slate-700 outline-none transition hover:border-slate-300 focus:border-indigo-300 focus:ring-4 focus:ring-indigo-50;
}

.compact-select-sm {
  min-height: 1.75rem;
  padding: 0.25rem 0.4rem;
  font-size: 0.75rem;
  line-height: 1rem;
}

.meta-select .compact-select-trigger {
  @apply min-h-10 rounded-xl border-slate-200 bg-white px-3 py-2 text-slate-800 shadow-sm hover:border-slate-300 hover:bg-slate-50 focus:border-indigo-300 focus:bg-white focus:ring-indigo-100;
}

.meta-select .compact-select-menu {
  @apply rounded-xl border-slate-200 p-1.5 shadow-xl;
}

.meta-select .compact-select-search {
  @apply rounded-lg border-slate-200 bg-white;
}

.meta-select .compact-select-option {
  @apply rounded-lg px-3 py-2 text-slate-700;
}

.meta-select .compact-select-option-active {
  @apply bg-indigo-50 text-indigo-700;
}

.compact-select-caret {
  @apply shrink-0 text-xs leading-none text-slate-400;
}

.compact-select-menu {
  @apply fixed z-[70] overflow-y-auto rounded-lg border border-slate-200 bg-white p-1 shadow-lg;
}

.compact-select-search {
  @apply mb-1 w-full rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-sm text-slate-800 outline-none placeholder:text-slate-400 focus:border-indigo-300 focus:bg-white focus:ring-4 focus:ring-indigo-50;
}

.compact-select-option {
  @apply flex w-full items-center justify-between gap-2 rounded-md px-2.5 py-1.5 text-left text-sm font-medium text-slate-600 transition hover:bg-indigo-50 hover:text-indigo-700;
}

.compact-select-option-active {
  @apply bg-indigo-50 text-indigo-700;
}

.compact-select-disabled {
  @apply cursor-not-allowed bg-slate-50 text-slate-400 hover:border-slate-200 focus:border-slate-200 focus:ring-0;
}

.compact-select-option-disabled {
  @apply cursor-not-allowed text-slate-400 hover:bg-transparent hover:text-slate-400;
}

.compact-select-option-group {
  @apply cursor-default bg-transparent px-2 pb-1 pt-2 hover:bg-transparent;
}

.compact-select-group-label {
  @apply text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400;
}

.compact-select-check {
  @apply shrink-0 text-xs font-semibold text-indigo-600;
}

.compact-select-badge {
  @apply shrink-0 rounded-full border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-[10px] font-semibold text-slate-500;
}

.compact-select-empty {
  @apply px-3 py-5 text-center text-xs text-slate-400;
}
</style>
