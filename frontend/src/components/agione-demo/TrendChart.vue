<template>
  <div v-for="(line, index) in series" :key="index" class="trend-chart">
    <div class="trend-toolbar">
      <b>{{ line.label || '全部' }}</b>
      <div class="trend-legend">
        <span class="trend-key">当前</span
        ><span v-if="previous.length" class="trend-key previous-key"
          >已缓存前期</span
        >
      </div>
    </div>
    <div class="trend-layout">
      <div class="trend-yaxis">
        <span
          v-for="tick in chart(line, index).ticks"
          :key="tick"
          :style="{ top: `${100 - (100 * tick) / chart(line, index).max}%` }"
          >{{ fmt(tick) }}</span
        >
      </div>
      <div
        class="trend-visual"
        role="group"
        :aria-label="`${line.label || '全部'}趋势`"
      >
        <svg
          viewBox="0 0 600 180"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <path
            v-for="tick in chart(line, index).ticks"
            :key="tick"
            class="plot-grid"
            :d="`M0 ${180 - (180 * tick) / chart(line, index).max}H600`"
          />
          <polyline
            v-for="(segment, i) in chart(line, index).previous"
            :key="`p${i}`"
            class="plot-previous"
            :points="points(segment)"
          />
          <polyline
            v-for="(segment, i) in chart(line, index).current"
            :key="i"
            class="plot-current"
            :points="points(segment)"
          /></svg
        ><span
          v-for="dot in chart(line, index).current.flat()"
          :key="dot.index"
          class="trend-dot"
          tabindex="0"
          role="img"
          :style="{ left: `${dot.x}%`, top: `${dot.y}%` }"
          :aria-label="`${line.points?.[dot.index]?.bucketStart}: ${fmt(dot.value)}`"
          :title="`${line.points?.[dot.index]?.bucketStart}: ${fmt(dot.value)}`"
        ></span>
      </div>
    </div>
    <div class="trend-xaxis">
      <span class="first-tick" style="left: 0">{{
        line.points?.[0]?.bucketStart?.slice(0, 10)
      }}</span
      ><span class="last-tick" style="left: 100%">{{
        line.points?.at(-1)?.bucketStart?.slice(0, 10)
      }}</span>
    </div>
  </div>
  <div v-if="!series.length" class="empty">
    当前快照未提供趋势，不补造数据。
  </div>
</template>
<script setup>
import { trendPlot } from './core.mjs'
const props = defineProps({
  series: { type: Array, default: () => [] },
  previous: { type: Array, default: () => [] },
  metric: { type: String, default: 'requestCount' }
})
const fmt = (x) =>
  typeof x === 'number'
    ? new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 }).format(x)
    : '—'
const chart = (line, index) =>
  trendPlot(
    line.points || [],
    props.previous[index]?.points || [],
    props.metric
  )
const points = (segment) =>
  segment.map((p) => `${p.x * 6},${p.y * 1.8}`).join(' ')
</script>
