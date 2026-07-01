<template>
  <section class="space-y-4">
    <div class="grid gap-4 md:grid-cols-3">
      <div v-for="item in metrics" :key="item.label" class="kpi-card">
        <p class="text-xs font-medium text-slate-500">{{ item.label }}</p>
        <p class="kpi-value mt-2 text-2xl font-semibold">{{ item.value }}</p>
        <p class="mt-2 text-xs text-slate-500">{{ item.hint }}</p>
      </div>
    </div>

    <div class="panel overflow-hidden p-0">
      <div class="table-toolbar">
        <div>
          <h3 class="panel-title">价格变化看板</h3>
          <p class="mt-1 text-xs text-slate-500">
            汇总渠道采购价、挂售价和标准价格项的最近变化。
          </p>
        </div>
        <CompactSelect
          v-model="typeFilter"
          :options="typeFilterOptions"
          class-name="w-36"
          size="sm"
        />
      </div>
      <div class="overflow-x-auto">
        <table class="data-table">
          <thead>
            <tr>
              <th class="table-head">对象</th>
              <th class="table-head">类型</th>
              <th class="table-head text-right">Input</th>
              <th class="table-head text-right">Output</th>
              <th class="table-head">币种</th>
              <th class="table-head">时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in filteredRows" :key="row.key">
              <td class="table-cell">
                <p class="font-medium text-slate-900">{{ row.name }}</p>
                <p class="mt-1 text-xs text-slate-500">{{ row.context }}</p>
              </td>
              <td class="table-cell">
                <span :class="['status-pill', row.tone]">
                  {{ row.type_label }}
                </span>
              </td>
              <td class="table-cell text-right font-mono">
                {{ money(row.input, row.currency) }}
              </td>
              <td class="table-cell text-right font-mono">
                {{ money(row.output, row.currency) }}
              </td>
              <td class="table-cell">{{ row.currency || '-' }}</td>
              <td class="table-cell">{{ formatDateTime(row.time) }}</td>
            </tr>
            <tr v-if="!filteredRows.length">
              <td class="table-cell text-slate-500" colspan="6">
                暂无价格变化记录。
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'

import CompactSelect from './CompactSelect.vue'

const props = defineProps({
  channelHistory: { type: Array, default: () => [] },
  listingHistory: { type: Array, default: () => [] },
  priceItems: { type: Array, default: () => [] }
})

const typeFilter = ref('all')
const typeFilterOptions = [
  { label: '全部价格', value: 'all' },
  { label: '渠道采购价', value: 'channel' },
  { label: '平台挂售价', value: 'listing' },
  { label: '标准价格项', value: 'official' }
]

const changeRows = computed(() => {
  const channelRows = props.channelHistory.map((item) => ({
    key: `channel-${item.id}`,
    type: 'channel',
    type_label: '渠道采购价',
    tone: 'info',
    name: item.model_name || `模型 ${item.model}`,
    context: item.channel_name || `渠道 ${item.channel}`,
    input: item.input_price_per_million,
    output: item.output_price_per_million,
    currency: item.currency,
    time: item.effective_from || item.created_at
  }))
  const listingRows = props.listingHistory.map((item) => ({
    key: `listing-${item.id}`,
    type: 'listing',
    type_label: '平台挂售价',
    tone: 'warn',
    name: item.model_name || `模型 ${item.model}`,
    context: item.platform_name || `平台 ${item.platform}`,
    input: item.retail_input_price_per_million,
    output: item.retail_output_price_per_million,
    currency: item.currency,
    time: item.effective_from || item.created_at
  }))
  const officialRows = recentOfficialRows()
  return [...channelRows, ...listingRows, ...officialRows].sort(
    (left, right) => new Date(right.time || 0) - new Date(left.time || 0)
  )
})

const filteredRows = computed(() => {
  const rows = changeRows.value.slice(0, 120)
  if (typeFilter.value === 'all') return rows
  return rows.filter((row) => row.type === typeFilter.value)
})

const metrics = computed(() => [
  {
    label: '渠道价历史',
    value: props.channelHistory.length,
    hint: '采购渠道价格版本记录'
  },
  {
    label: '挂售价历史',
    value: props.listingHistory.length,
    hint: '平台挂售价格版本记录'
  },
  {
    label: '标准价格项',
    value: props.priceItems.length,
    hint: '当前标准价格维度数量'
  }
])

function recentOfficialRows() {
  return props.priceItems.slice(0, 80).map((item) => ({
    key: `official-${item.id}`,
    type: 'official',
    type_label: '标准价格项',
    tone: 'success',
    name: item.model_name || `模型 ${item.model}`,
    context: dimensionLabel(item.dimension),
    input: item.dimension === 'text_input' ? item.unit_price : null,
    output: item.dimension === 'text_output' ? item.unit_price : null,
    currency: item.currency,
    time: item.effective_from || item.updated_at || item.created_at
  }))
}

function dimensionLabel(value) {
  return (
    {
      text_input: '文本输入',
      text_output: '文本输出',
      cache_input: '缓存输入',
      image_output: '图片输出',
      audio_input: '音频输入',
      audio_output: '音频输出',
      video_input: '视频输入',
      video_output: '视频输出'
    }[value] || value
  )
}

function money(value, currency) {
  if (value === null || value === undefined || value === '') return '-'
  return `${currency || ''} ${Number(value).toFixed(6)}`
}

function formatDateTime(value) {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}
</script>
