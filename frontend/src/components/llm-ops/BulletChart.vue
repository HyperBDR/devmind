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
/* === Base utility classes (hardcoded, Tailwind fallback) === */
.bg-white {
  background-color: #ffffff;
}
.bg-slate-50 {
  background-color: #f8fafc;
}
.bg-slate-100 {
  background-color: #f1f5f9;
}
.bg-slate-200 {
  background-color: #e2e8f0;
}
.bg-slate-950 {
  background-color: #020617;
}
.bg-transparent {
  background-color: transparent;
}
.bg-emerald-50 {
  background-color: #ecfdf5;
}
.bg-emerald-500 {
  background-color: #10b981;
}
.bg-amber-50 {
  background-color: #fffbeb;
}
.bg-amber-500 {
  background-color: #f59e0b;
}
.bg-rose-50 {
  background-color: #fff1f2;
}
.bg-rose-500 {
  background-color: #f43f5e;
}
.bg-violet-500 {
  background-color: #8b5cf6;
}
.bg-sky-500 {
  background-color: #0ea5e9;
}
.bg-indigo-50 {
  background-color: #eef2ff;
}
.bg-indigo-100 {
  background-color: #e0e7ff;
}
.bg-agione-50 {
  background-color: #ece9f9;
}
.bg-agione-100 {
  background-color: #d8d2f0;
}
.bg-agione-200 {
  background-color: #b3a8e2;
}
.bg-agione-300 {
  background-color: #8b7dd1;
}
.bg-agione-400 {
  background-color: #7a6ac4;
}
.bg-agione-500 {
  background-color: #6a5ac7;
}
.bg-agione-600 {
  background-color: #5f4ecf;
}
.bg-agione-700 {
  background-color: #4a3eb0;
}
.bg-agione-800 {
  background-color: #3d3399;
}
.bg-agione-900 {
  background-color: #312870;
}
.text-white {
  color: #ffffff;
}
.text-slate-500 {
  color: #64748b;
}
.text-slate-600 {
  color: #475569;
}
.text-slate-700 {
  color: #334155;
}
.text-slate-900 {
  color: #0f172a;
}
.text-emerald-600 {
  color: #059669;
}
.text-emerald-700 {
  color: #047857;
}
.text-amber-600 {
  color: #d97706;
}
.text-amber-700 {
  color: #b45309;
}
.text-rose-500 {
  color: #f43f5e;
}
.text-rose-600 {
  color: #e11d48;
}
.text-rose-700 {
  color: #be123c;
}
.text-agione-50 {
  color: #ece9f9;
}
.text-agione-100 {
  color: #d8d2f0;
}
.text-agione-300 {
  color: #8b7dd1;
}
.text-agione-500 {
  color: #6a5ac7;
}
.text-agione-600 {
  color: #5f4ecf;
}
.text-agione-700 {
  color: #4a3eb0;
}
.text-agione-800 {
  color: #3d3399;
}
.border-slate-200 {
  border-color: #e2e8f0;
}
.border-slate-300 {
  border-color: #cbd5e1;
}
.border-emerald-100 {
  border-color: #d1fae5;
}
.border-emerald-200 {
  border-color: #a7f3d0;
}
.border-amber-100 {
  border-color: #fef3c7;
}
.border-amber-200 {
  border-color: #fde68a;
}
.border-rose-100 {
  border-color: #ffe4e6;
}
.border-rose-200 {
  border-color: #fecdd3;
}
.border-agione-100 {
  border-color: #d8d2f0;
}
.border-agione-200 {
  border-color: #b3a8e2;
}
.border-agione-300 {
  border-color: #8b7dd1;
}
.border-agione-400 {
  border-color: #7a6ac4;
}
.border-agione-500 {
  border-color: #6a5ac7;
}
.focus\:border-agione-300:focus {
  border-color: #8b7dd1;
}
.focus\:border-agione-400:focus {
  border-color: #7a6ac4;
}
.focus\:ring-2:focus {
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.3);
}
.focus\:ring-4:focus {
  box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.3);
}
.focus\:ring-agione-100:focus {
  box-shadow: 0 0 0 2px #d8d2f0;
}
.focus\:ring-agione-200:focus {
  box-shadow: 0 0 0 2px #b3a8e2;
}
.hover\:bg-slate-50:hover {
  background-color: #f8fafc;
}
.hover\:bg-agione-600:hover {
  background-color: #5f4ecf;
}
.hover\:bg-agione-700:hover {
  background-color: #4a3eb0;
}
.hover\:border-slate-300:hover {
  border-color: #cbd5e1;
}
.hover\:text-agione-700:hover {
  color: #4a3eb0;
}
.hover\:text-slate-500:hover {
  color: #64748b;
}
.disabled\:cursor-not-allowed:disabled {
  cursor: not-allowed;
}
.disabled\:opacity-50:disabled {
  opacity: 0.5;
}
.disabled\:opacity-60:disabled {
  opacity: 0.6;
}
.text-xs {
  font-size: 0.75rem;
  line-height: 1rem;
}
.text-sm {
  font-size: 0.875rem;
  line-height: 1.25rem;
}
.text-base {
  font-size: 1rem;
  line-height: 1.5rem;
}
.text-lg {
  font-size: 1.125rem;
  line-height: 1.75rem;
}
.text-xl {
  font-size: 1.25rem;
  line-height: 1.75rem;
}
.text-2xl {
  font-size: 1.5rem;
  line-height: 2rem;
}
.text-3xl {
  font-size: 1.875rem;
  line-height: 2.25rem;
}
.text-4xl {
  font-size: 2.25rem;
  line-height: 2.5rem;
}
.text-\[10px\] {
  font-size: 10px;
}
.text-\[11px\] {
  font-size: 11px;
}
.text-\[12px\] {
  font-size: 12px;
}
.text-\[13px\] {
  font-size: 13px;
}
.text-\[14px\] {
  font-size: 14px;
}
.text-\[15px\] {
  font-size: 15px;
}
.text-\[18px\] {
  font-size: 18px;
}
.text-\[24px\] {
  font-size: 24px;
}
.top-0 {
  top: 0;
}
.z-10 {
  z-index: 10;
}
.z-20 {
  z-index: 20;
}
.z-50 {
  z-index: 50;
}
.max-w-\[20rem\] {
  max-width: 20rem;
}
.w-60 {
  width: 15rem;
}
.w-72 {
  width: 18rem;
}
.w-80 {
  width: 20rem;
}
.w-36 {
  width: 9rem;
}
.w-32 {
  width: 8rem;
}
.h-9 {
  height: 2.25rem;
}
.h-7 {
  height: 1.75rem;
}
.h-8 {
  height: 2rem;
}
.text-left {
  text-align: left;
}
.text-right {
  text-align: right;
}
.text-center {
  text-align: center;
}
.border {
  border-width: 1px;
}
.bg-indigo-50 {
  background-color: #eef2ff;
}
.bg-indigo-100 {
  background-color: #e0e7ff;
}
.bg-indigo-500 {
  background-color: #6366f1;
}
.bg-indigo-600 {
  background-color: #4f46e5;
}
.bg-indigo-700 {
  background-color: #4338ca;
}
.text-indigo-300 {
  color: #a5b4fc;
}
.text-indigo-500 {
  color: #6366f1;
}
.text-indigo-600 {
  color: #4f46e5;
}
.text-indigo-700 {
  color: #4338ca;
}
.border-indigo-200 {
  border-color: #c7d2fe;
}
.border-indigo-300 {
  border-color: #a5b4fc;
}
.border-indigo-400 {
  border-color: #818cf8;
}
.focus\:border-indigo-300:focus {
  border-color: #a5b4fc;
}
.focus\:ring-indigo-100:focus {
  box-shadow: 0 0 0 2px #e0e7ff;
}

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
