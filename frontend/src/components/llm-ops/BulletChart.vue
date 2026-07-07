<!--
  BulletChart — single-track price comparison.
  Renders a horizontal range bar with reference markers and a current-value
  marker, matching the visual style of demo.html (Section 3 / pricing).
-->
<template>
  <div
    ref="rangeRef"
    class="range-bar-wrapper"
    :class="{ 'is-dragging': isDragging }"
    @pointerdown="onTrackPointerDown"
  >
    <div
      v-if="hasBoundaryRange"
      class="range-bar-zone"
      :style="boundaryZoneStyle"
    />
    <div
      v-for="boundary in boundaryItems"
      :key="boundary.key"
      class="range-boundary-hit"
      :class="boundary.hitClass"
      :style="{ left: boundary.percent + '%' }"
      tabindex="0"
      :aria-label="boundaryTitle(boundary)"
      @pointerdown.stop
    >
      <span class="range-boundary-marker" :class="boundary.markerClass" />
      <span class="range-boundary-label">
        {{ boundaryCaption(boundary) }}
      </span>
      <span v-if="boundary.tooltip" class="range-boundary-tooltip">
        <span class="range-boundary-tooltip-title">
          {{ boundary.tooltip.title || boundary.title }}
        </span>
        <span class="range-boundary-tooltip-source">
          {{ boundary.tooltip.source }}
        </span>
        <span class="range-boundary-tooltip-rows">
          <span
            v-for="row in boundary.tooltip.rows || []"
            :key="`${boundary.key}-${row.label}`"
            class="range-boundary-tooltip-row"
          >
            <span>{{ row.label }}</span>
            <strong>{{ row.value }}</strong>
            <em>{{ row.source }}</em>
          </span>
        </span>
      </span>
    </div>
    <div
      v-for="tick in axisTicks"
      :key="tick.percent"
      class="range-axis-tick"
      :style="{ left: tick.percent + '%' }"
    >
      <span>{{ formatDisplayValue(tick.value) }}</span>
    </div>

    <template v-for="(ref, i) in refs" :key="`ref-${i}`">
      <div
        class="range-ref-marker"
        :style="{ left: getMarkerPos(ref.price) + '%' }"
        tabindex="0"
        :aria-label="refTitle(ref)"
      >
        <div class="range-ref-label">
          {{ ref.source }}
        </div>
        <span class="range-ref-tooltip">
          <span class="range-ref-tooltip-title">
            {{ ref.source }}
          </span>
          <span v-if="ref.rows?.length" class="range-ref-tooltip-rows">
            <span
              v-for="row in ref.rows"
              :key="`${ref.source}-${row.label}`"
              class="range-boundary-tooltip-row range-ref-tooltip-row-compact"
            >
              <span>{{ row.label }}</span>
              <strong>{{ row.value || refDisplayValue(ref) }}</strong>
              <em aria-hidden="true">&nbsp;</em>
            </span>
          </span>
          <strong v-else class="range-ref-tooltip-value">
            {{ refDisplayValue(ref) }}
          </strong>
          <span
            v-if="ref.titleValue && !ref.rows?.length"
            class="range-ref-tooltip-source"
          >
            {{ ref.titleValue }}
          </span>
        </span>
      </div>
    </template>

    <div
      class="range-bar-marker"
      role="slider"
      tabindex="0"
      :aria-label="label || t('llmOps.publishingWorkspace.margin.sliderLabel')"
      :aria-valuemin="axisMin"
      :aria-valuemax="axisMax"
      :aria-valuenow="Number(value) || 0"
      :style="{
        left: getMarkerPos(Number(value) || 0) + '%',
        backgroundColor: getMarkerColor(Number(value) || 0)
      }"
      @keydown="onMarkerKeydown"
      @pointerdown.stop="startValueDrag"
    />
    <div
      class="range-bar-value"
      :style="getValueLabelStyle(Number(value) || 0)"
      @pointerdown.stop="startValueDrag"
    >
      {{ label }}
    </div>
  </div>
</template>

<script setup>
import '@/components/llm-ops/bulletChart.css'
import { computed, onBeforeUnmount, ref } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  min: {
    type: Number,
    default: 0
  },
  max: {
    type: Number,
    default: 0
  },
  value: {
    type: [Number, String],
    default: 0
  },
  refs: {
    type: Array,
    default: () => []
  },
  lowerTooltip: {
    type: Object,
    default: null
  },
  upperTooltip: {
    type: Object,
    default: null
  },
  label: {
    type: String,
    default: ''
  },
  currencySymbol: {
    type: String,
    default: '¥'
  },
  valuePrefix: {
    type: String,
    default: null
  },
  valueSuffix: {
    type: String,
    default: ''
  },
  digits: {
    type: Number,
    default: null
  }
})

const emit = defineEmits(['change', 'update:value'])
const { t } = useI18n()

const rangeRef = ref(null)
const isDragging = ref(false)
const fallbackCenter = ref(0)

const AXIS_START_PERCENT = 10
const AXIS_END_PERCENT = 90
const AXIS_WIDTH_PERCENT = AXIS_END_PERCENT - AXIS_START_PERCENT

const boundaryMin = computed(() => Number(props.min))
const boundaryMax = computed(() => Number(props.max))
const hasBoundaryRange = computed(
  () => Number.isFinite(boundaryMin.value) && Number.isFinite(boundaryMax.value)
)

const axisRange = computed(() => {
  const value = Number(props.value)
  const refValues = props.refs.map((ref) => Number(ref.price))
  if (hasBoundaryRange.value) {
    const candidates = [
      boundaryMin.value,
      boundaryMax.value,
      value,
      ...refValues
    ].filter((item) => Number.isFinite(item))
    const rawMin = Math.min(...candidates)
    const rawMax = Math.max(...candidates)
    if (rawMax === rawMin) {
      const padding = Math.max(Math.abs(rawMax) * 0.2, 1)
      return {
        min: Math.max(0, rawMin - padding),
        max: rawMax + padding
      }
    }
    const span = rawMax - rawMin
    const leftPadding = Math.max(span * 0.04, 1)
    const rightPadding = Math.max(span * 0.14, 10)
    return {
      min: Math.max(0, Math.floor((rawMin - leftPadding) / 5) * 5),
      max: Math.ceil((rawMax + rightPadding) / 5) * 5
    }
  }

  const candidates = [value, ...refValues].filter((item) =>
    Number.isFinite(item)
  )

  if (!candidates.length) {
    if (!fallbackCenter.value && Number.isFinite(value) && value > 0) {
      fallbackCenter.value = value
    }
    const center = fallbackCenter.value || 1
    const padding = Math.max(center * 0.5, 0.0001)
    return {
      min: Math.max(0, center - padding),
      max: center + padding
    }
  }

  const rawMin = Math.min(...candidates)
  const rawMax = Math.max(...candidates)
  if (rawMax === rawMin) {
    const padding = Math.max(Math.abs(rawMax) * 0.2, 1)
    return {
      min: Math.max(0, rawMin - padding),
      max: rawMax + padding
    }
  }

  const span = rawMax - rawMin
  const padding = Math.max(span * 0.08, 1)
  return {
    min: Math.max(0, Math.floor((rawMin - padding) / 5) * 5),
    max: Math.ceil((rawMax + padding) / 5) * 5
  }
})

const axisMin = computed(() => axisRange.value.min)
const axisMax = computed(() => axisRange.value.max)
const boundaryLabel = computed(() =>
  hasBoundaryRange.value
    ? t('llmOps.publishingWorkspace.margin.boundaryMarket')
    : t('llmOps.publishingWorkspace.margin.boundaryReference')
)

const boundaryZoneStyle = computed(() => {
  if (!hasBoundaryRange.value) return {}
  const start = Math.min(
    getMarkerPos(boundaryMin.value),
    getMarkerPos(boundaryMax.value)
  )
  const end = Math.max(
    getMarkerPos(boundaryMin.value),
    getMarkerPos(boundaryMax.value)
  )
  return {
    left: `${start}%`,
    width: `${Math.max(end - start, 1.5)}%`
  }
})

const boundaryItems = computed(() => [
  {
    key: 'min',
    title: t('llmOps.publishingWorkspace.margin.boundaryTitle', {
      scope: boundaryLabel.value,
      boundary: t('llmOps.publishingWorkspace.margin.boundaryLower')
    }),
    value: boundaryMin.value,
    displayValue: props.lowerTooltip?.displayValue,
    percent: getMarkerPos(boundaryMin.value),
    markerClass: 'range-boundary-min',
    hitClass: 'range-boundary-hit-min',
    tooltip: props.lowerTooltip
  },
  {
    key: 'max',
    title: t('llmOps.publishingWorkspace.margin.boundaryTitle', {
      scope: boundaryLabel.value,
      boundary: t('llmOps.publishingWorkspace.margin.boundaryUpper')
    }),
    value: boundaryMax.value,
    displayValue: props.upperTooltip?.displayValue,
    percent: getMarkerPos(boundaryMax.value),
    markerClass: 'range-boundary-max',
    hitClass: 'range-boundary-hit-max',
    tooltip: props.upperTooltip
  }
])

const axisTicks = computed(() => {
  return [25, 50, 75].map((percent) => ({
    percent: AXIS_START_PERCENT + (percent / 100) * AXIS_WIDTH_PERCENT,
    value: axisMin.value + (percent / 100) * (axisMax.value - axisMin.value)
  }))
})

function getMarkerPos(price) {
  const p = Number(price)
  const min = axisMin.value
  const max = axisMax.value
  if (!Number.isFinite(p) || max === min) return 50
  const pos =
    ((p - min) / (max - min)) * AXIS_WIDTH_PERCENT + AXIS_START_PERCENT
  return Math.max(0, Math.min(pos, 100))
}

function getMarkerColor(price) {
  const p = Number(price)
  const min = axisMin.value
  const max = axisMax.value
  if (!Number.isFinite(p)) return '#94a3b8'
  const avg = (min + max) / 2
  if (p <= avg) return '#10b981'
  if (p > max * 0.8) return '#f59e0b'
  return '#6366f1'
}

function boundaryCaption(boundary) {
  const prefix = boundaryCaptionPrefix(boundary)
  if (boundary.tooltip?.captionKind === 'floor') return prefix
  return `${prefix} ${boundaryDisplayValue(boundary)}`
}

function boundaryCaptionPrefix(boundary) {
  if (boundary.tooltip?.captionKind === 'auto_approve') {
    return t('llmOps.publishingWorkspace.margin.boundaryAutoApprove')
  }
  if (boundary.tooltip?.captionKind === 'floor') {
    return t('llmOps.publishingWorkspace.margin.boundaryFloor')
  }
  return boundary.key === 'min'
    ? t('llmOps.publishingWorkspace.margin.boundaryLower')
    : t('llmOps.publishingWorkspace.margin.boundaryUpper')
}

function boundaryDisplayValue(boundary) {
  return boundary.displayValue || formatDisplayValue(boundary.value)
}

function refDisplayValue(ref) {
  return ref.displayValue || formatDisplayValue(ref.price)
}

function boundaryTitle(boundary) {
  return `${boundary.title}: ${boundaryDisplayValue(boundary)}`
}

function refTitle(ref) {
  return `${ref.source}: ${ref.titleValue || refDisplayValue(ref)}`
}

function getValueLabelStyle(price) {
  const pos = getMarkerPos(price)
  const color = getMarkerColor(price)
  if (pos < 12) {
    return {
      left: '0%',
      color,
      transform: 'translateX(0)'
    }
  }
  if (pos > 88) {
    return {
      left: '100%',
      color,
      transform: 'translateX(-100%)'
    }
  }
  return {
    left: `${pos}%`,
    color,
    transform: 'translateX(-50%)'
  }
}

function getPriceFromPointer(event) {
  const el = rangeRef.value
  if (!el) return null
  const rect = el.getBoundingClientRect()
  const percent = ((event.clientX - rect.left) / rect.width) * 100
  const clamped = Math.max(
    AXIS_START_PERCENT,
    Math.min(percent, AXIS_END_PERCENT)
  )
  const ratio = (clamped - AXIS_START_PERCENT) / AXIS_WIDTH_PERCENT
  const price = axisMin.value + ratio * (axisMax.value - axisMin.value)
  return Number(price.toFixed(4))
}

function emitPrice(price) {
  if (!Number.isFinite(price)) return
  emit('update:value', price)
  emit('change', price)
}

function handleValueDrag(event) {
  const price = getPriceFromPointer(event)
  if (price !== null) emitPrice(price)
}

function stopValueDrag() {
  if (!isDragging.value) return
  isDragging.value = false
  document.removeEventListener('pointermove', handleValueDrag)
  document.removeEventListener('pointerup', stopValueDrag)
}

function startValueDrag(event) {
  if (event?.button > 0) return
  event.preventDefault()
  isDragging.value = true
  handleValueDrag(event)
  document.addEventListener('pointermove', handleValueDrag)
  document.addEventListener('pointerup', stopValueDrag)
}

function onTrackPointerDown(event) {
  if (event.target?.closest('.range-ref-marker, .range-boundary-hit')) return
  startValueDrag(event)
}

function onMarkerKeydown(event) {
  const step = Math.max((axisMax.value - axisMin.value) / 100, 0.0001)
  if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return
  event.preventDefault()
  const direction = event.key === 'ArrowRight' ? 1 : -1
  const next = Number(props.value || 0) + step * direction
  const clamped = Math.max(axisMin.value, Math.min(next, axisMax.value))
  emitPrice(Number(clamped.toFixed(4)))
}

onBeforeUnmount(() => {
  stopValueDrag()
})

function formatNumber(value) {
  const num = Number(value)
  if (!Number.isFinite(num)) return '-'
  if (props.digits !== null) {
    return num.toFixed(props.digits).replace(/\.?0+$/, '')
  }
  if (num >= 1) return num.toFixed(4)
  if (num >= 0.001) return num.toFixed(5)
  return num.toFixed(6)
}

function formatDisplayValue(value) {
  const formatted = formatNumber(value)
  if (formatted === '-') return '-'
  const prefix = props.valuePrefix ?? props.currencySymbol
  return `${prefix}${formatted}${props.valueSuffix}`
}
</script>
