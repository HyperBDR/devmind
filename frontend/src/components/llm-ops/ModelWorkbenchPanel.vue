<template>
  <section class="space-y-4">
    <div class="panel">
      <div class="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div>
          <h3 class="panel-title">模型详情工作台</h3>
          <p class="mt-1 text-xs text-slate-500">
            集中查看单个模型的官方价格、渠道采购、挂售状态和对账记录。
          </p>
        </div>
        <CompactSelect
          v-model="selectedModelId"
          :options="modelSelectOptions"
          class-name="w-full lg:w-80"
          searchable
          :menu-min-width="360"
        />
      </div>
    </div>

    <div v-if="selectedModel" class="grid gap-4 xl:grid-cols-4">
      <div class="kpi-card">
        <p class="text-xs font-medium text-slate-500">元模型</p>
        <p class="mt-2 text-lg font-semibold text-slate-900">
          {{ selectedModel.meta_model_name || '-' }}
        </p>
        <p class="mt-2 font-mono text-xs text-slate-500">
          {{ selectedModel.code }}
        </p>
      </div>
      <div class="kpi-card">
        <p class="text-xs font-medium text-slate-500">渠道覆盖</p>
        <p class="kpi-value mt-2 text-2xl font-semibold">
          {{ selectedDiagnostic?.coverage_count || 0 }}
        </p>
        <p class="mt-2 text-xs text-slate-500">可用采购渠道数量</p>
      </div>
      <div class="kpi-card">
        <p class="text-xs font-medium text-slate-500">挂售链路</p>
        <p class="kpi-value mt-2 text-2xl font-semibold">
          {{ modelListings.length }}
        </p>
        <p class="mt-2 text-xs text-slate-500">当前平台及其他平台记录</p>
      </div>
      <div class="kpi-card">
        <p class="text-xs font-medium text-slate-500">对账异常</p>
        <p class="kpi-value mt-2 text-2xl font-semibold">
          {{ anomalyRecords.length }}
        </p>
        <p class="mt-2 text-xs text-slate-500">非 perfect 的对账记录</p>
      </div>
    </div>

    <div class="grid gap-4 xl:grid-cols-2">
      <div class="panel overflow-hidden p-0">
        <div class="table-toolbar">
          <h3 class="panel-title">标准价格项</h3>
        </div>
        <MiniTable
          :columns="['维度', '价格', '来源']"
          :rows="officialRows"
          empty-text="暂无标准价格项。"
        />
      </div>

      <div class="panel overflow-hidden p-0">
        <div class="table-toolbar">
          <h3 class="panel-title">渠道采购价</h3>
        </div>
        <MiniTable
          :columns="['渠道', '维度', '价格']"
          :rows="channelRows"
          empty-text="暂无渠道价格项。"
        />
      </div>
    </div>

    <div class="grid gap-4 xl:grid-cols-2">
      <div class="panel overflow-hidden p-0">
        <div class="table-toolbar">
          <h3 class="panel-title">挂售记录</h3>
        </div>
        <MiniTable
          :columns="['平台', '渠道', '状态']"
          :rows="listingRows"
          empty-text="暂无挂售记录。"
        />
      </div>

      <div class="panel overflow-hidden p-0">
        <div class="table-toolbar">
          <h3 class="panel-title">对账记录</h3>
        </div>
        <MiniTable
          :columns="['日期', '渠道', '差异']"
          :rows="reconciliationRows"
          empty-text="暂无对账记录。"
        />
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, defineComponent, h, ref, watch } from 'vue'

import CompactSelect from './CompactSelect.vue'

const MiniTable = defineComponent({
  props: {
    columns: { type: Array, default: () => [] },
    rows: { type: Array, default: () => [] },
    emptyText: { type: String, default: '暂无数据。' }
  },
  setup(props) {
    return () =>
      h('div', { class: 'overflow-x-auto' }, [
        h('table', { class: 'data-table' }, [
          h('thead', [
            h(
              'tr',
              props.columns.map((column) =>
                h('th', { class: 'table-head' }, column)
              )
            )
          ]),
          h('tbody', [
            ...props.rows.map((row, rowIndex) =>
              h(
                'tr',
                { key: rowIndex },
                row.map((cell, cellIndex) =>
                  h(
                    'td',
                    {
                      class:
                        cellIndex === row.length - 1
                          ? 'table-cell'
                          : 'table-cell font-mono text-xs'
                    },
                    cell
                  )
                )
              )
            ),
            props.rows.length
              ? null
              : h('tr', [
                  h(
                    'td',
                    {
                      class: 'table-cell text-slate-500',
                      colspan: props.columns.length
                    },
                    props.emptyText
                  )
                ])
          ])
        ])
      ])
  }
})

const props = defineProps({
  summary: { type: Object, default: () => ({}) },
  models: { type: Array, default: () => [] },
  channels: { type: Array, default: () => [] },
  priceItems: { type: Array, default: () => [] },
  channelPriceItems: { type: Array, default: () => [] },
  listings: { type: Array, default: () => [] },
  records: { type: Array, default: () => [] }
})

const selectedModelId = ref('')

const diagnostics = computed(() => props.summary.agione?.diagnostics || [])
const modelOptions = computed(() =>
  diagnostics.value.map((row) => ({
    id: row.model_id,
    name: row.model_name,
    code: row.model_code,
    provider_name: row.provider_name,
    meta_model_name: row.meta_model_name
  }))
)

const modelSelectOptions = computed(() =>
  modelOptions.value.map((model) => ({
    label: `${model.provider_name} / ${model.name}`,
    searchText: `${model.provider_name} ${model.name} ${model.code}`,
    value: String(model.id)
  }))
)

watch(
  modelOptions,
  (options) => {
    if (!options.length) {
      selectedModelId.value = ''
      return
    }
    const exists = options.some(
      (option) => String(option.id) === String(selectedModelId.value)
    )
    if (!exists) selectedModelId.value = String(options[0].id)
  },
  { immediate: true }
)

const selectedModel = computed(() =>
  modelOptions.value.find(
    (model) => String(model.id) === String(selectedModelId.value)
  )
)

const selectedDiagnostic = computed(() =>
  diagnostics.value.find(
    (row) => String(row.model_id) === String(selectedModelId.value)
  )
)

const modelListings = computed(() =>
  props.listings.filter(
    (listing) => String(listing.model) === String(selectedModelId.value)
  )
)

const modelRecords = computed(() =>
  props.records.filter(
    (record) => String(record.model) === String(selectedModelId.value)
  )
)

const anomalyRecords = computed(() =>
  modelRecords.value.filter((record) => record.status !== 'perfect')
)

const officialRows = computed(() =>
  props.priceItems
    .filter((item) => String(item.model) === String(selectedModelId.value))
    .slice(0, 12)
    .map((item) => [
      dimensionLabel(item.dimension),
      money(item.unit_price, item.currency),
      item.source_name || item.price_role || '-'
    ])
)

const channelRows = computed(() =>
  props.channelPriceItems
    .filter((item) => String(item.model) === String(selectedModelId.value))
    .slice(0, 12)
    .map((item) => [
      item.channel_name || channelName(item.channel),
      dimensionLabel(item.dimension),
      money(item.unit_price, item.currency)
    ])
)

const listingRows = computed(() =>
  modelListings.value.map((listing) => [
    listing.platform_name || `平台 ${listing.platform}`,
    listing.channel_name || '自动最优',
    `${workflowLabel(listing.workflow_status)} / ${publishLabel(
      listing.publish_status
    )}`
  ])
)

const reconciliationRows = computed(() =>
  modelRecords.value
    .slice(0, 12)
    .map((record) => [
      record.date,
      record.channel_name || channelName(record.channel),
      `${money(record.discrepancy, '')} · ${record.status}`
    ])
)

function channelName(channelId) {
  return (
    props.channels.find((channel) => String(channel.id) === String(channelId))
      ?.name || '-'
  )
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

function workflowLabel(value) {
  return (
    {
      draft: '草稿',
      pending_publish: '待发布',
      online: '在线',
      update_draft: '更新草稿',
      pending_update: '待更新',
      pending_offline: '待下架',
      offline_exception: '下架异常',
      offline: '已下架',
      deleted: '已删除'
    }[value] || value
  )
}

function publishLabel(value) {
  return (
    {
      none: '未发布',
      online: '已发布',
      offline: '已下架',
      deleted: '已删除'
    }[value] || value
  )
}

function money(value, currency) {
  if (value === null || value === undefined || value === '') return '-'
  const prefix = currency ? `${currency} ` : ''
  return `${prefix}${Number(value).toFixed(6)}`
}
</script>
