<template>
  <section class="space-y-4">
    <div class="grid gap-4 md:grid-cols-4">
      <div v-for="item in metrics" :key="item.label" class="kpi-card">
        <p class="text-xs font-medium text-slate-500">{{ item.label }}</p>
        <p class="kpi-value mt-2 text-2xl font-semibold">{{ item.value }}</p>
        <p class="mt-2 text-xs text-slate-500">{{ item.hint }}</p>
      </div>
    </div>

    <div class="panel overflow-hidden p-0">
      <div class="table-toolbar">
        <div>
          <h3 class="panel-title">挂售利润风险榜</h3>
          <p class="mt-1 text-xs text-slate-500">
            聚合低毛利、非最低采购、未挂售和币种换算风险。
          </p>
        </div>
        <CompactSelect
          v-model="riskFilter"
          :options="riskFilterOptions"
          class-name="w-36"
          size="sm"
        />
      </div>
      <div class="overflow-x-auto">
        <table class="data-table">
          <thead>
            <tr>
              <th class="table-head">模型</th>
              <th class="table-head">风险类型</th>
              <th class="table-head text-right">Input 毛利</th>
              <th class="table-head text-right">Output 毛利</th>
              <th class="table-head">当前渠道</th>
              <th class="table-head">建议动作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in filteredRows" :key="row.key">
              <td class="table-cell">
                <p class="font-medium text-slate-900">{{ row.model_name }}</p>
                <p class="mt-1 text-xs text-slate-500">
                  {{ row.provider_name }}
                </p>
              </td>
              <td class="table-cell">
                <span :class="['status-pill', row.tone]">
                  {{ row.risk_label }}
                </span>
              </td>
              <td class="table-cell text-right font-mono">
                {{ percent(row.input_margin) }}
              </td>
              <td class="table-cell text-right font-mono">
                {{ percent(row.output_margin) }}
              </td>
              <td class="table-cell">
                {{ row.channel_name || '-' }}
              </td>
              <td class="table-cell text-slate-600">
                {{ row.action }}
              </td>
            </tr>
            <tr v-if="!filteredRows.length">
              <td class="table-cell text-slate-500" colspan="6">
                当前筛选条件下没有风险项。
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
  summary: { type: Object, default: () => ({}) }
})

const riskFilter = ref('all')
const riskFilterOptions = [
  { label: '全部风险', value: 'all' },
  { label: '低毛利', value: 'margin' },
  { label: '非最低价', value: 'not_lowest' },
  { label: '未挂售', value: 'unlisted' },
  { label: '需要汇率', value: 'currency_mismatch' }
]

const diagnosticRows = computed(() => props.summary.agione?.diagnostics || [])
const selectedPlatformId = computed(() => props.summary.agione?.platform_id)
const listingRows = computed(() => {
  const rows = props.summary.listings || []
  if (!selectedPlatformId.value) return rows
  return rows.filter(
    (listing) =>
      String(listing.platform_id) === String(selectedPlatformId.value)
  )
})

const riskRows = computed(() => {
  const rows = []
  diagnosticRows.value.forEach((row) => {
    if (row.status === 'ready' || row.status === 'low_coverage') return
    rows.push({
      key: `diag-${row.model_id}-${row.status}`,
      model_id: row.model_id,
      model_name: row.model_name,
      provider_name: row.provider_name,
      risk: row.status,
      risk_label: statusLabel(row.status),
      tone: statusTone(row.status),
      input_margin: null,
      output_margin: null,
      channel_name: row.best_channel?.channel_name || '',
      action: actionText(row.status)
    })
  })
  listingRows.value.forEach((listing) => {
    const inputMargin = listing.input_margin?.margin_rate
    const outputMargin = listing.output_margin?.margin_rate
    if (!isLowMargin(inputMargin) && !isLowMargin(outputMargin)) return
    rows.push({
      key: `listing-${listing.listing_id}`,
      model_id: listing.model_id,
      model_name: listing.model_name,
      provider_name: listing.platform_name,
      risk: 'margin',
      risk_label: '低毛利',
      tone: 'danger',
      input_margin: inputMargin,
      output_margin: outputMargin,
      channel_name: listing.channel_name,
      action: '复核售价、服务费率或采购渠道'
    })
  })
  return rows.sort((left, right) => riskRank(left.risk) - riskRank(right.risk))
})

const filteredRows = computed(() => {
  if (riskFilter.value === 'all') return riskRows.value
  return riskRows.value.filter((row) => row.risk === riskFilter.value)
})

const metrics = computed(() => [
  {
    label: '风险总数',
    value: riskRows.value.length,
    hint: '当前平台可见的挂售和采购风险'
  },
  {
    label: '低毛利',
    value: riskRows.value.filter((row) => row.risk === 'margin').length,
    hint: 'Input 或 Output 毛利低于 10%'
  },
  {
    label: '非最低价',
    value: riskRows.value.filter((row) => row.risk === 'not_lowest').length,
    hint: '已挂售但未使用最低采购渠道'
  },
  {
    label: '未挂售',
    value: riskRows.value.filter((row) => row.risk === 'unlisted').length,
    hint: '已有供应但未进入当前平台'
  }
])

function isLowMargin(value) {
  if (value === null || value === undefined) return false
  return Number(value) < 0.1
}

function statusLabel(status) {
  return (
    {
      currency_mismatch: '需要汇率',
      missing_channel: '缺渠道价',
      unlisted: '未挂售',
      not_lowest: '非最低价'
    }[status] || status
  )
}

function statusTone(status) {
  return (
    {
      currency_mismatch: 'info',
      missing_channel: 'danger',
      unlisted: 'warn',
      not_lowest: 'warn'
    }[status] || 'info'
  )
}

function actionText(status) {
  return (
    {
      currency_mismatch: '补充汇率后重新比较采购价',
      missing_channel: '先为模型配置至少一个渠道采购价',
      unlisted: '进入挂售工作台创建平台上架记录',
      not_lowest: '评估切换到最低采购渠道'
    }[status] || '复核状态'
  )
}

function riskRank(status) {
  return (
    {
      margin: 1,
      missing_channel: 2,
      currency_mismatch: 3,
      not_lowest: 4,
      unlisted: 5
    }[status] || 9
  )
}

function percent(value) {
  if (value === null || value === undefined || value === '') return '-'
  return `${(Number(value) * 100).toFixed(2)}%`
}
</script>
