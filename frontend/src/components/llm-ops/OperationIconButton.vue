<template>
  <button
    class="operation-icon-button inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-transparent bg-transparent p-0 transition hover:-translate-y-px disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:translate-y-0"
    :class="toneClass"
    :aria-label="label"
    :aria-describedby="tooltipId"
    :disabled="disabled"
    :type="type"
    @click="$emit('click', $event)"
  >
    <svg
      aria-hidden="true"
      class="operation-icon"
      fill="none"
      stroke="currentColor"
      stroke-linecap="round"
      stroke-linejoin="round"
      stroke-width="2"
      viewBox="0 0 24 24"
    >
      <path v-for="path in iconPaths" :key="path" :d="path" />
    </svg>
    <span v-if="visibleLabel" class="operation-icon-label">
      {{ visibleLabel }}
    </span>
    <span :id="tooltipId" class="operation-icon-tooltip" role="tooltip">
      {{ label }}
    </span>
  </button>
</template>

<script setup>
import { computed, getCurrentInstance } from 'vue'

const props = defineProps({
  disabled: {
    type: Boolean,
    default: false
  },
  icon: {
    type: String,
    default: 'edit'
  },
  label: {
    type: String,
    required: true
  },
  visibleLabel: {
    type: String,
    default: ''
  },
  tone: {
    type: String,
    default: 'default'
  },
  type: {
    type: String,
    default: 'button'
  }
})

defineEmits(['click'])

const instance = getCurrentInstance()
const tooltipId = `operation-icon-tooltip-${instance?.uid || 'fallback'}`

const iconMap = {
  add: ['M12 5v14', 'M5 12h14'],
  approve: ['M20 6 9 17l-5-5'],
  back: ['M15 18l-6-6 6-6'],
  collect: ['M21 12a9 9 0 1 1-2.64-6.36', 'M21 3v6h-6'],
  config: [
    'M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z',
    'M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.07a2 2 0 1 1-2.83 2.83l-.07-.06A1.7 1.7 0 0 0 15 19.4a1.7 1.7 0 0 0-1 .3 1.7 1.7 0 0 0-.7 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-.7-1.5 1.7 1.7 0 0 0-1-.3 1.7 1.7 0 0 0-1.88.34l-.07.06a2 2 0 1 1-2.83-2.83l.06-.07A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-.3-1 1.7 1.7 0 0 0-1.5-.7H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-.7 1.7 1.7 0 0 0 .3-1 1.7 1.7 0 0 0-.34-1.88l-.06-.07a2 2 0 1 1 2.83-2.83l.07.06A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-.3 1.7 1.7 0 0 0 .7-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 .7 1.5 1.7 1.7 0 0 0 1 .3 1.7 1.7 0 0 0 1.88-.34l.07-.06a2 2 0 1 1 2.83 2.83l-.06.07A1.7 1.7 0 0 0 19.4 9c0 .36.1.7.3 1a1.7 1.7 0 0 0 1.5.7h.1a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5.7 1.7 1.7 0 0 0-.3 1Z'
  ],
  delete: ['M3 6h18', 'M8 6V4h8v2', 'M6 6l1 14h10l1-14'],
  edit: ['M12 20h9', 'M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z'],
  import: ['M12 3v12', 'M7 10l5 5 5-5', 'M5 21h14', 'M5 17h14'],
  manual: [
    'M8 6h13',
    'M8 12h13',
    'M8 18h13',
    'M3 6h.01',
    'M3 12h.01',
    'M3 18h.01'
  ],
  offline: ['M5 12h14'],
  offlineRequest: ['M12 8v5l3 2', 'M21 12a9 9 0 1 1-9-9'],
  powerOff: ['M12 2v10', 'M18.4 6.6a9 9 0 1 1-12.8 0'],
  price: ['M12 1v22', 'M17 5H9.5a3.5 3.5 0 0 0 0 7H14a3.5 3.5 0 0 1 0 7H6'],
  reject: ['M18 6 6 18', 'M6 6l12 12'],
  remove: ['M18 6 6 18', 'M6 6l12 12'],
  reset: ['M21 12a9 9 0 1 1-2.64-6.36', 'M21 3v6h-6', 'M12 7v5l3 2'],
  submit: ['M22 2 11 13', 'M22 2 15 22l-4-9-9-4Z'],
  toggleOff: ['M18 12H6'],
  toggleOn: ['M5 12l4 4L19 6'],
  view: [
    'M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z',
    'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z'
  ],
  withdraw: ['M9 14 4 9l5-5', 'M4 9h11a5 5 0 0 1 0 10h-1']
}

const iconPaths = computed(() => iconMap[props.icon] || iconMap.edit)

const toneClass = computed(() => {
  if (props.tone === 'danger') return 'operation-icon-danger'
  if (props.tone === 'success') return 'operation-icon-success'
  if (props.tone === 'warn') return 'operation-icon-warn'
  if (props.tone === 'primary') return 'operation-icon-primary'
  return 'operation-icon-default'
})
</script>

<style scoped>
.operation-icon-button {
  display: inline-flex;
  position: relative;
  width: 2rem;
  height: 2rem;
  align-items: center;
  justify-content: center;
  border: 1px solid transparent;
  border-radius: 0.625rem;
  background: transparent;
  padding: 0;
  transition:
    background-color 150ms ease,
    border-color 150ms ease,
    color 150ms ease,
    transform 150ms ease;
}

.operation-icon-button:hover:not(:disabled) {
  transform: translateY(-1px);
}

.operation-icon-button:disabled {
  cursor: not-allowed;
  opacity: 0.5;
  transform: none;
}

.operation-icon-button:hover:not(:disabled) .operation-icon-tooltip,
.operation-icon-button:focus-visible .operation-icon-tooltip {
  opacity: 1;
  transform: translate(-50%, -0.375rem);
  visibility: visible;
}

.operation-icon {
  width: 1rem;
  height: 1rem;
  flex: 0 0 auto;
}

.operation-icon-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
}

.operation-icon-tooltip {
  position: absolute;
  bottom: 100%;
  left: 50%;
  z-index: 20;
  max-width: 8rem;
  overflow: hidden;
  border-radius: 0.375rem;
  background: #111827;
  color: #ffffff;
  font-size: 11px;
  font-weight: 600;
  line-height: 1.4;
  opacity: 0;
  padding: 0.25rem 0.5rem;
  pointer-events: none;
  text-overflow: ellipsis;
  transform: translate(-50%, -0.125rem);
  transition:
    opacity 120ms ease,
    transform 120ms ease,
    visibility 120ms ease;
  visibility: hidden;
  white-space: nowrap;
}

.operation-icon-tooltip::after {
  position: absolute;
  top: 100%;
  left: 50%;
  width: 0;
  height: 0;
  border-color: #111827 transparent transparent;
  border-style: solid;
  border-width: 0.25rem 0.25rem 0;
  content: '';
  transform: translateX(-50%);
}

.operation-icon-default {
  color: #475569;
}

.operation-icon-primary {
  color: #4f46e5;
}

.operation-icon-primary:hover:not(:disabled) {
  border-color: #c7d2fe;
  background: #eef2ff;
  color: #4338ca;
}

.operation-icon-default:hover:not(:disabled) {
  border-color: #cbd5e1;
  background: #f8fafc;
  color: #0f172a;
}

.operation-icon-success {
  color: #059669;
}

.operation-icon-success:hover:not(:disabled) {
  border-color: #a7f3d0;
  background: #ecfdf5;
  color: #047857;
}

.operation-icon-warn {
  color: #d97706;
}

.operation-icon-warn:hover:not(:disabled) {
  border-color: #fed7aa;
  background: #fff7ed;
  color: #b45309;
}

.operation-icon-danger {
  color: #e11d48;
}

.operation-icon-danger:hover:not(:disabled) {
  border-color: #fecdd3;
  background: #fff1f2;
  color: #be123c;
}
</style>
