<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { ChevronDown } from 'lucide-vue-next'
import type { QuoteStatus } from '../types'
import { useQuotationI18n } from '../composables/useQuotationI18n'
import DropdownOption from './DropdownOption.vue'

const props = defineProps<{
  modelValue: QuoteStatus
  options: QuoteStatus[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: QuoteStatus]
  change: [value: QuoteStatus]
}>()

const { quoteStatusLabel } = useQuotationI18n()

const open = ref(false)
const triggerRef = ref<HTMLElement | null>(null)
const menuStyle = ref({ top: '0px', left: '0px', minWidth: '0px' })

const MENU_WIDTH = 188

function getStatusStyle(val: QuoteStatus): string {
  switch (val) {
    case 'Draft':
      return 'bg-[#fafafa] text-dm-text-secondary border-dm-border hover:bg-slate-100'
    case 'Generated':
      return 'bg-dm-primary-bg text-blue-700 border-blue-200 hover:bg-blue-100/60'
    case 'Uploaded':
      return 'bg-[#e6fffb] text-[#08979c] border-[#87e8de] hover:bg-[#b5f5ec]/60'
    case 'Sent':
      return 'bg-purple-50 text-purple-700 border-purple-200 hover:bg-purple-100/60'
    case 'Accepted':
      return 'bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100/60 font-bold'
    case 'Rejected':
      return 'bg-red-50 text-red-700 border-red-200 hover:bg-red-100/60'
    case 'Expired':
      return 'bg-amber-50 text-amber-700 border-amber-200 hover:bg-amber-100/60'
    case 'Cancelled':
      return 'bg-slate-100 text-dm-text-tertiary border-slate-250 hover:bg-slate-150'
    default:
      return 'bg-[#fafafa] text-dm-text-secondary border-dm-border hover:bg-slate-100'
  }
}

function updateMenuPosition() {
  const trigger = triggerRef.value
  if (!trigger) return

  const rect = trigger.getBoundingClientRect()
  const estimatedHeight = Math.min(
    props.options.length * 36 + 8,
    Math.min(320, window.innerHeight - 24),
  )
  let top = rect.bottom + 4
  if (top + estimatedHeight > window.innerHeight - 8) {
    top = rect.top - estimatedHeight - 4
  }

  menuStyle.value = {
    top: `${Math.max(8, top)}px`,
    left: `${Math.max(8, rect.left + rect.width / 2 - MENU_WIDTH / 2)}px`,
    minWidth: `${MENU_WIDTH}px`,
  }
}

function close() {
  open.value = false
}

function toggleOpen() {
  open.value = !open.value
  if (open.value) {
    updateMenuPosition()
  }
}

function selectStatus(status: QuoteStatus) {
  if (status !== props.modelValue) {
    emit('update:modelValue', status)
    emit('change', status)
  }
  close()
}

function handleOutsideClick(event: MouseEvent) {
  const target = event.target as HTMLElement | null
  if (!target?.closest('[data-status-select]')) {
    close()
  }
}

onMounted(() => {
  document.addEventListener('mousedown', handleOutsideClick)
  window.addEventListener('scroll', close, true)
  window.addEventListener('resize', close)
})

onBeforeUnmount(() => {
  document.removeEventListener('mousedown', handleOutsideClick)
  window.removeEventListener('scroll', close, true)
  window.removeEventListener('resize', close)
})
</script>

<template>
  <div data-status-select class="relative inline-block text-left">
    <button
      ref="triggerRef"
      type="button"
      :class="`inline-flex items-center gap-1 px-2.5 py-0.5 text-[11px] font-semibold rounded-full border shadow-2xs transition-all duration-150 cursor-pointer focus:outline-hidden focus:ring-1 focus:ring-blue-500 focus:border-blue-500 ${getStatusStyle(modelValue)}`"
      @click="toggleOpen"
    >
      <span>{{ quoteStatusLabel(modelValue) }}</span>
      <ChevronDown class="h-3 w-3 shrink-0 opacity-70" />
    </button>

    <Teleport to="body">
      <ul
        v-if="open"
        data-status-select
        class="qmp-dropdown-panel fixed z-50 max-h-[min(20rem,calc(100vh-24px))] overflow-y-auto overscroll-contain py-1"
        :style="menuStyle"
      >
        <li v-for="status in options" :key="status">
          <DropdownOption
            :selected="status === modelValue"
            @click="selectStatus(status)"
          >
            {{ quoteStatusLabel(status) }}
          </DropdownOption>
        </li>
      </ul>
    </Teleport>
  </div>
</template>
