<template>
  <section class="space-y-4">
    <div class="panel">
      <div
        class="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between"
      >
        <div>
          <h3 class="panel-title">渠道横向比价矩阵</h3>
          <p class="mt-1 text-xs text-slate-500">
            按模型比较各渠道采购价格、最低价命中和覆盖缺口。
          </p>
        </div>
        <div class="flex flex-col gap-2 sm:flex-row">
          <input
            v-model="keyword"
            class="llm-ops-input h-9 w-full sm:w-64"
            placeholder="搜索模型或厂商"
            type="search"
          />
          <CompactSelect
            v-model="statusFilter"
            :options="statusFilterOptions"
            class-name="w-full sm:w-36"
            size="sm"
          />
        </div>
      </div>
    </div>

    <div class="grid gap-4 md:grid-cols-4">
      <div v-for="item in metrics" :key="item.label" class="kpi-card">
        <p class="text-xs font-medium text-slate-500">{{ item.label }}</p>
        <p class="kpi-value mt-2 text-2xl font-semibold">{{ item.value }}</p>
        <p class="mt-2 text-xs text-slate-500">{{ item.hint }}</p>
      </div>
    </div>

    <div class="panel overflow-hidden p-0">
      <div class="overflow-x-auto">
        <table class="data-table min-w-[980px]">
          <thead>
            <tr>
              <th class="table-head sticky left-0 z-10 bg-white">模型</th>
              <th
                v-for="channel in visibleChannels"
                :key="channel.id"
                class="table-head text-right"
              >
                {{ channel.name }}
              </th>
              <th class="table-head text-right">覆盖</th>
              <th class="table-head">最低价渠道</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in filteredRows" :key="row.model_id">
              <td class="table-cell sticky left-0 z-10 bg-white">
                <p class="font-medium text-slate-900">{{ row.model_name }}</p>
                <p class="mt-1 text-xs text-slate-500">
                  {{ row.provider_name }}
                </p>
              </td>
              <td
                v-for="channel in visibleChannels"
                :key="`${row.model_id}-${channel.id}`"
                class="table-cell text-right"
              >
                <span
                  v-if="optionFor(row, channel)"
                  :class="[
                    'font-mono text-xs',
                    isBest(row, channel) ? 'text-emerald-700' : 'text-slate-700'
                  ]"
                >
                  {{ priceSummary(optionFor(row, channel)) }}
                </span>
                <span v-else class="text-xs text-slate-400">-</span>
              </td>
              <td class="table-cell text-right font-mono">
                {{ row.coverage_count || 0 }} / {{ visibleChannels.length }}
              </td>
              <td class="table-cell">
                <span v-if="row.best_channel" class="status-pill success">
                  {{ row.best_channel.channel_name }}
                </span>
                <span v-else class="status-pill danger">缺渠道价</span>
              </td>
            </tr>
            <tr v-if="!filteredRows.length">
              <td
                class="table-cell text-slate-500"
                :colspan="visibleChannels.length + 3"
              >
                当前筛选条件下没有模型。
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
  summary: { type: Object, default: () => ({}) },
  channels: { type: Array, default: () => [] }
})

const keyword = ref('')
const statusFilter = ref('all')
const statusFilterOptions = [
  { label: '全部状态', value: 'all' },
  { label: '缺渠道价', value: 'missing' },
  { label: '单渠道覆盖', value: 'single' },
  { label: '多渠道覆盖', value: 'ready' }
]

const rows = computed(() => props.summary.agione?.diagnostics || [])
const visibleChannels = computed(() =>
  props.channels.filter((channel) => channel.is_active !== false)
)

const filteredRows = computed(() => {
  const query = keyword.value.trim().toLowerCase()
  return rows.value.filter((row) => {
    const matchesKeyword =
      !query ||
      String(row.model_name || '')
        .toLowerCase()
        .includes(query) ||
      String(row.model_code || '')
        .toLowerCase()
        .includes(query) ||
      String(row.provider_name || '')
        .toLowerCase()
        .includes(query)
    if (!matchesKeyword) return false
    if (statusFilter.value === 'missing') return !row.best_channel
    if (statusFilter.value === 'single') return row.coverage_count === 1
    if (statusFilter.value === 'ready') return row.coverage_count > 1
    return true
  })
})

const metrics = computed(() => {
  const total = rows.value.length
  const covered = rows.value.filter((row) => row.best_channel).length
  const single = rows.value.filter((row) => row.coverage_count === 1).length
  const missing = rows.value.filter((row) => !row.best_channel).length
  return [
    {
      label: '模型总数',
      value: total,
      hint: '参与渠道比价的活跃模型'
    },
    {
      label: '有渠道价',
      value: covered,
      hint: `覆盖率 ${percentage(covered, total)}%`
    },
    {
      label: '单渠道风险',
      value: single,
      hint: '只有一个采购渠道，缺少备选'
    },
    {
      label: '缺渠道价',
      value: missing,
      hint: '无法计算采购成本'
    }
  ]
})

function optionFor(row, channel) {
  return (row.options || []).find(
    (option) => String(option.channel_id) === String(channel.id)
  )
}

function isBest(row, channel) {
  return String(row.best_channel?.channel_id) === String(channel.id)
}

function priceSummary(option) {
  const input = money(option.input_price_per_million, option.currency)
  const output = money(option.output_price_per_million, option.currency)
  return `In ${input} / Out ${output}`
}

function money(value, currency) {
  if (value === null || value === undefined || value === '') return '-'
  return `${currency || ''} ${Number(value).toFixed(4)}`
}

function percentage(value, total) {
  if (!total) return 0
  return Math.round((Number(value || 0) / Number(total)) * 100)
}
</script>
