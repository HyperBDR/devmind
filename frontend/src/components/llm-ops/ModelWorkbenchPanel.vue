<template>
  <section class="space-y-4">
    <div class="panel">
      <div class="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div>
          <h3 class="panel-title">
            {{ t('llmOps.modelWorkbenchPanel.title') }}
          </h3>
          <p class="mt-1 text-xs text-slate-500">
            {{ t('llmOps.modelWorkbenchPanel.subtitle') }}
          </p>
        </div>
        <div class="flex flex-col gap-2 sm:flex-row lg:justify-end">
          <CompactSelect
            v-model="catalogScope"
            :options="catalogScopeOptions"
            class-name="w-full sm:w-44"
          />
          <CompactSelect
            v-model="selectedModelId"
            :options="modelSelectOptions"
            class-name="w-full lg:w-80"
            searchable
            :menu-min-width="360"
          />
        </div>
      </div>
    </div>

    <div v-if="selectedModel" class="grid gap-4 xl:grid-cols-4">
      <div class="kpi-card">
        <p class="text-xs font-medium text-slate-500">
          {{ t('llmOps.modelWorkbenchPanel.kpi.metaModel') }}
        </p>
        <p class="mt-2 text-lg font-semibold text-slate-900">
          {{ selectedModel.meta_model_name || '-' }}
        </p>
        <p class="mt-2 font-mono text-xs text-slate-500">
          {{ selectedModel.code }}
        </p>
      </div>
      <div class="kpi-card">
        <p class="text-xs font-medium text-slate-500">
          {{ t('llmOps.modelWorkbenchPanel.kpi.channelCoverage') }}
        </p>
        <p class="kpi-value mt-2 text-2xl font-semibold">
          {{ selectedDiagnostic?.coverage_count || 0 }}
        </p>
        <p class="mt-2 text-xs text-slate-500">
          {{ t('llmOps.modelWorkbenchPanel.kpi.channelCoverageHint') }}
        </p>
      </div>
      <div class="kpi-card">
        <p class="text-xs font-medium text-slate-500">
          {{ t('llmOps.modelWorkbenchPanel.kpi.listingLinks') }}
        </p>
        <p class="kpi-value mt-2 text-2xl font-semibold">
          {{ modelListings.length }}
        </p>
        <p class="mt-2 text-xs text-slate-500">
          {{ t('llmOps.modelWorkbenchPanel.kpi.listingLinksHint') }}
        </p>
      </div>
      <div class="kpi-card">
        <p class="text-xs font-medium text-slate-500">
          {{ t('llmOps.modelWorkbenchPanel.kpi.reconciliationAnomalies') }}
        </p>
        <p class="kpi-value mt-2 text-2xl font-semibold">
          {{ anomalyRecords.length }}
        </p>
        <p class="mt-2 text-xs text-slate-500">
          {{ t('llmOps.modelWorkbenchPanel.kpi.reconciliationAnomaliesHint') }}
        </p>
      </div>
    </div>

    <div class="grid gap-4 xl:grid-cols-2">
      <div class="panel overflow-hidden p-0">
        <div class="table-toolbar">
          <h3 class="panel-title">
            {{ t('llmOps.modelWorkbenchPanel.standardPrices') }}
          </h3>
        </div>
        <MiniTable
          :columns="officialColumns"
          :rows="officialRows"
          :empty-text="t('llmOps.modelWorkbenchPanel.emptyStandardPrices')"
        />
      </div>

      <div class="panel overflow-hidden p-0">
        <div class="table-toolbar">
          <h3 class="panel-title">
            {{ t('llmOps.modelWorkbenchPanel.channelPrices') }}
          </h3>
        </div>
        <MiniTable
          :columns="channelColumns"
          :rows="channelRows"
          :empty-text="t('llmOps.modelWorkbenchPanel.emptyChannelPrices')"
        />
      </div>
    </div>

    <div class="grid gap-4 xl:grid-cols-2">
      <div class="panel overflow-hidden p-0">
        <div class="table-toolbar">
          <h3 class="panel-title">
            {{ t('llmOps.modelWorkbenchPanel.listingRecords') }}
          </h3>
        </div>
        <MiniTable
          :columns="listingColumns"
          :rows="listingRows"
          :empty-text="t('llmOps.modelWorkbenchPanel.emptyListingRecords')"
        />
      </div>

      <div class="panel overflow-hidden p-0">
        <div class="table-toolbar">
          <h3 class="panel-title">
            {{ t('llmOps.modelWorkbenchPanel.reconciliationRecords') }}
          </h3>
        </div>
        <MiniTable
          :columns="reconciliationColumns"
          :rows="reconciliationRows"
          :empty-text="
            t('llmOps.modelWorkbenchPanel.emptyReconciliationRecords')
          "
        />
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, defineComponent, h, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import CompactSelect from './CompactSelect.vue'

const MiniTable = defineComponent({
  props: {
    columns: { type: Array, default: () => [] },
    rows: { type: Array, default: () => [] },
    emptyText: { type: String, default: '' }
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
  focusModelId: { type: [Number, String], default: null },
  listings: { type: Array, default: () => [] },
  records: { type: Array, default: () => [] }
})

const { t } = useI18n()
const catalogScope = ref('all')
const selectedModelId = ref('')

const catalogScopeOptions = computed(() => [
  {
    label: t('llmOps.modelWorkbenchPanel.filters.all'),
    value: 'all'
  },
  {
    label: t('llmOps.modelWorkbenchPanel.filters.operational'),
    value: 'operational'
  },
  {
    label: t('llmOps.modelWorkbenchPanel.filters.marketReference'),
    value: 'market_reference'
  }
])

const officialColumns = computed(() => [
  t('llmOps.modelWorkbenchPanel.columns.dimension'),
  t('llmOps.modelWorkbenchPanel.columns.price'),
  t('llmOps.modelWorkbenchPanel.columns.source')
])

const channelColumns = computed(() => [
  t('llmOps.modelWorkbenchPanel.columns.channel'),
  t('llmOps.modelWorkbenchPanel.columns.dimension'),
  t('llmOps.modelWorkbenchPanel.columns.price')
])

const listingColumns = computed(() => [
  t('llmOps.modelWorkbenchPanel.columns.platform'),
  t('llmOps.modelWorkbenchPanel.columns.channel'),
  t('llmOps.modelWorkbenchPanel.columns.status')
])

const reconciliationColumns = computed(() => [
  t('llmOps.modelWorkbenchPanel.columns.date'),
  t('llmOps.modelWorkbenchPanel.columns.channel'),
  t('llmOps.modelWorkbenchPanel.columns.variance')
])

const diagnostics = computed(() => props.summary.agione?.diagnostics || [])
const modelOptions = computed(() =>
  diagnostics.value.map((row) => ({
    id: row.model_id,
    name: row.model_name,
    code: row.model_code,
    operation_scope: row.operation_scope,
    provider_name: row.provider_name,
    meta_model_name: row.meta_model_name
  }))
)

const filteredModelOptions = computed(() => {
  if (catalogScope.value === 'all') return modelOptions.value
  return modelOptions.value.filter(
    (model) => model.operation_scope === catalogScope.value
  )
})

const modelSelectOptions = computed(() =>
  filteredModelOptions.value.map((model) => ({
    label: `${model.provider_name} / ${model.name}`,
    searchText: `${model.provider_name} ${model.name} ${model.code}`,
    value: String(model.id)
  }))
)

watch(
  [filteredModelOptions, () => props.focusModelId],
  ([options, focusModelId]) => {
    if (!options.length) {
      selectedModelId.value = ''
      return
    }
    const focusExists = options.some(
      (option) => String(option.id) === String(focusModelId)
    )
    if (focusModelId && focusExists) {
      selectedModelId.value = String(focusModelId)
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
    listing.platform_name ||
      t('llmOps.modelWorkbenchPanel.platformFallback', {
        id: listing.platform
      }),
    channelDisplayName(listing),
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

function channelDisplayName(value) {
  if (value.channel_type === 'auto_best' || value.channel === null) {
    return t('llmOps.channel.autoBest')
  }
  return value.channel_name || channelName(value.channel)
}

function dimensionLabel(value) {
  return (
    {
      text_input: t('llmOps.modelWorkbenchPanel.dimension.textInput'),
      text_output: t('llmOps.modelWorkbenchPanel.dimension.textOutput'),
      cache_input: t('llmOps.modelWorkbenchPanel.dimension.cacheInput'),
      image_output: t('llmOps.modelWorkbenchPanel.dimension.imageOutput'),
      audio_input: t('llmOps.modelWorkbenchPanel.dimension.audioInput'),
      audio_output: t('llmOps.modelWorkbenchPanel.dimension.audioOutput'),
      video_input: t('llmOps.modelWorkbenchPanel.dimension.videoInput'),
      video_output: t('llmOps.modelWorkbenchPanel.dimension.videoOutput')
    }[value] || value
  )
}

function workflowLabel(value) {
  return (
    {
      draft: t('llmOps.modelWorkbenchPanel.workflowStatus.draft'),
      pending_publish: t(
        'llmOps.modelWorkbenchPanel.workflowStatus.pendingPublish'
      ),
      online: t('llmOps.modelWorkbenchPanel.workflowStatus.online'),
      update_draft: t('llmOps.modelWorkbenchPanel.workflowStatus.updateDraft'),
      pending_update: t(
        'llmOps.modelWorkbenchPanel.workflowStatus.pendingUpdate'
      ),
      pending_offline: t(
        'llmOps.modelWorkbenchPanel.workflowStatus.pendingOffline'
      ),
      offline_exception: t(
        'llmOps.modelWorkbenchPanel.workflowStatus.offlineException'
      ),
      offline: t('llmOps.modelWorkbenchPanel.workflowStatus.offline'),
      deleted: t('llmOps.modelWorkbenchPanel.workflowStatus.deleted')
    }[value] || value
  )
}

function publishLabel(value) {
  return (
    {
      none: t('llmOps.modelWorkbenchPanel.publishStatus.none'),
      online: t('llmOps.modelWorkbenchPanel.publishStatus.online'),
      offline: t('llmOps.modelWorkbenchPanel.publishStatus.offline'),
      deleted: t('llmOps.modelWorkbenchPanel.publishStatus.deleted')
    }[value] || value
  )
}

function money(value, currency) {
  if (value === null || value === undefined || value === '') return '-'
  const prefix = currency ? `${currency} ` : ''
  return `${prefix}${Number(value).toFixed(6)}`
}
</script>
