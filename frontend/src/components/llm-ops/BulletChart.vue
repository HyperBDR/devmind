<!--
  BulletChart — single-track price comparison.
  Renders a horizontal range bar with reference markers and a current-value
  marker, matching the visual style of demo.html (Section 3 / pricing).
-->
<template>
  <div class="range-bar-wrapper">
    <div
      v-if="hasRange"
      class="range-bar-zone"
      :style="{ left: '10%', width: '80%' }"
    />
    <div v-if="hasRange" class="range-bar-label" style="left: 10%">
      市场下限<br />{{ currencySymbol }}{{ formatNumber(min) }}
    </div>
    <div v-if="hasRange" class="range-bar-label" style="left: 90%">
      市场上限<br />{{ currencySymbol }}{{ formatNumber(max) }}
    </div>

    <template v-for="(ref, i) in refs" :key="`ref-${i}`">
      <div
        class="range-ref-marker"
        :style="{ left: getMarkerPos(ref.price) + '%' }"
        :title="`${ref.source}: ${currencySymbol}${formatNumber(ref.price)}`"
      >
        <div class="range-ref-label">
          {{ ref.source }}
        </div>
        <div class="range-ref-val">
          {{ currencySymbol }}{{ formatNumber(ref.price) }}
        </div>
      </div>
    </template>

    <div
      v-if="hasRange"
      class="range-bar-marker"
      :style="{
        left: getMarkerPos(Number(value) || 0) + '%',
        backgroundColor: getMarkerColor(Number(value) || 0)
      }"
    />
    <div
      v-if="hasRange"
      class="range-bar-value"
      :style="{
        left: getMarkerPos(Number(value) || 0) + '%',
        color: getMarkerColor(Number(value) || 0)
      }"
    >
      {{ label }}
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

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
  label: {
    type: String,
    default: ''
  },
  currencySymbol: {
    type: String,
    default: '¥'
  }
})

const hasRange = computed(() => props.max > props.min)

function getMarkerPos(price) {
  if (!hasRange.value) return 50
  const p = Number(price)
  const min = Number(props.min)
  const max = Number(props.max)
  if (!Number.isFinite(p) || max === min) return 50
  const pos = ((p - min) / (max - min)) * 90 + 5
  return Math.max(0, Math.min(pos, 100))
}

function getMarkerColor(price) {
  if (!hasRange.value) return '#94a3b8'
  const p = Number(price)
  const min = Number(props.min)
  const max = Number(props.max)
  if (!Number.isFinite(p)) return '#94a3b8'
  const avg = (min + max) / 2
  if (p <= avg) return '#10b981'
  if (p > max * 0.8) return '#f59e0b'
  return '#6366f1'
}

function formatNumber(value) {
  const num = Number(value)
  if (!Number.isFinite(num)) return '-'
  if (num >= 1) return num.toFixed(4)
  if (num >= 0.001) return num.toFixed(5)
  return num.toFixed(6)
}
</script>

<style scoped>
.range-bar-wrapper {
  position: relative;
  width: 100%;
  height: 6px;
  background: #e2e8f0;
  border-radius: 9999px;
  margin-top: 40px;
  margin-bottom: 28px;
}

.range-bar-zone {
  position: absolute;
  height: 100%;
  background: #6366f1;
  opacity: 0.1;
  border-radius: 9999px;
}

.range-bar-label {
  position: absolute;
  font-size: 10px;
  color: #64748b;
  bottom: -20px;
  transform: translateX(-50%);
  white-space: nowrap;
  line-height: 1.2;
  text-align: center;
}

.range-bar-marker {
  position: absolute;
  top: 50%;
  transform: translate(-50%, -50%);
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 2px solid #fff;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.15);
  z-index: 10;
}

.range-ref-marker {
  position: absolute;
  top: 50%;
  transform: translate(-50%, -50%);
  width: 2px;
  height: 14px;
  background-color: #94a3b8;
  z-index: 5;
}

.range-ref-label {
  position: absolute;
  font-size: 10px;
  font-weight: 600;
  color: #64748b;
  top: -26px;
  transform: translateX(-50%);
  white-space: nowrap;
}

.range-ref-val {
  position: absolute;
  font-size: 9px;
  color: #64748b;
  top: -12px;
  transform: translateX(-50%);
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

.range-bar-value {
  position: absolute;
  font-size: 11px;
  font-weight: 700;
  bottom: -24px;
  transform: translateX(-50%);
  white-space: nowrap;
}
</style>
