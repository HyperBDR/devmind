<template>
  <section class="space-y-6">
    <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
      <div v-for="item in kpiCards" :key="item.label" class="kpi-card">
        <div class="flex items-start justify-between gap-3">
          <div>
            <p class="text-xs font-medium text-slate-500">
              {{ item.label }}
            </p>
            <p class="kpi-value mt-2 text-2xl font-semibold">
              {{ item.value }}
            </p>
          </div>
          <span :class="['kpi-tone', item.tone]">
            {{ item.badge }}
          </span>
        </div>
        <div class="mt-3 h-1.5 overflow-hidden rounded-full bg-slate-200">
          <div
            class="h-full rounded-full"
            :class="item.barClass"
            :style="{ width: `${item.progress}%` }"
          />
        </div>
        <p class="mt-2 text-xs text-slate-500">
          {{ item.hint }}
        </p>
      </div>
    </div>

    <div class="grid gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
      <div class="panel space-y-4">
        <div class="flex items-center justify-between gap-3">
          <div>
            <p
              class="text-xs font-semibold uppercase tracking-[0.18em] text-agione-600"
            >
              Action Queue
            </p>
            <h3 class="mt-2 text-lg font-semibold text-slate-900">
              {{ t('llmOps.monitor.actionQueueTitle') }}
            </h3>
          </div>
          <button
            type="button"
            class="btn-secondary btn-action-view"
            @click="$emit('navigate', 'reseller')"
          >
            {{ t('llmOps.actions.goResale') }}
          </button>
        </div>
        <div class="space-y-3">
          <button
            v-for="item in actionItems"
            :key="item.label"
            type="button"
            class="action-row"
            @click="$emit('navigate', item.section)"
          >
            <span :class="['action-dot', item.tone]" />
            <span class="min-w-0 flex-1">
              <span class="block text-sm font-medium text-slate-900">
                {{ item.label }}
              </span>
              <span class="mt-1 block text-xs text-slate-500">
                {{ item.hint }}
              </span>
            </span>
            <span class="font-mono text-lg font-semibold text-slate-900">
              {{ item.value }}
            </span>
          </button>
        </div>
      </div>

      <div class="panel space-y-4">
        <div
          class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"
        >
          <div>
            <p
              class="text-xs font-semibold uppercase tracking-[0.18em] text-agione-600"
            >
              Channel Coverage
            </p>
            <h3 class="mt-2 text-lg font-semibold text-slate-900">
              {{ t('llmOps.monitor.channelCoverageTitle') }}
            </h3>
          </div>
          <span class="text-sm text-slate-500">
            {{
              t('llmOps.monitor.channelCount', {
                count: operationalChannelCount
              })
            }}
          </span>
        </div>
        <div class="space-y-3">
          <div
            v-for="channel in channelCoverageRows"
            :key="channel.id"
            class="coverage-row"
          >
            <div class="flex items-center justify-between gap-4">
              <div class="min-w-0">
                <p class="truncate text-sm font-medium text-slate-900">
                  {{ channel.name }}
                </p>
                <p class="mt-1 text-xs text-slate-500">
                  {{
                    t('llmOps.monitor.channelCoverageMeta', {
                      covered: channel.covered,
                      best: channel.best_count
                    })
                  }}
                </p>
              </div>
              <span class="font-mono text-sm text-slate-700">
                {{ channel.coverage_rate }}%
              </span>
            </div>
            <div class="mt-2 h-2 overflow-hidden rounded-full bg-slate-100">
              <div
                class="h-full rounded-full bg-agione-500"
                :style="{ width: `${channel.coverage_rate}%` }"
              />
            </div>
          </div>
          <div
            v-if="!channelCoverageRows.length"
            class="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-center text-sm text-slate-500"
          >
            {{ t('llmOps.monitor.emptyChannelCoverage') }}
          </div>
        </div>
      </div>
    </div>

    <div class="panel space-y-4">
      <div
        class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"
      >
        <div>
          <p
            class="text-xs font-semibold uppercase tracking-[0.18em] text-agione-600"
          >
            Provider Matrix
          </p>
          <h3 class="mt-2 text-lg font-semibold text-slate-900">
            {{ t('llmOps.monitor.providerMatrixTitle') }}
          </h3>
        </div>
        <button
          type="button"
          class="btn-secondary btn-action-config"
          @click="$emit('navigate', 'providers')"
        >
          {{ t('llmOps.actions.manageProviders') }}
        </button>
      </div>
      <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        <div
          v-for="provider in providerCoverageRows"
          :key="provider.name"
          class="provider-card"
        >
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <p class="truncate text-sm font-semibold text-slate-900">
                {{ provider.name }}
              </p>
              <p class="mt-1 text-xs text-slate-500">
                {{
                  t('llmOps.monitor.modelCount', {
                    count: provider.model_count
                  })
                }}
              </p>
            </div>
            <span
              :class="provider.ready_rate >= 80 ? 'badge-ok' : 'badge-muted'"
            >
              {{ provider.ready_rate }}%
            </span>
          </div>
          <div class="mt-3 space-y-2">
            <div class="metric-line">
              <span>{{ t('llmOps.monitor.channelCoverage') }}</span>
              <strong>{{ provider.procured_count }}</strong>
            </div>
            <div class="metric-line">
              <span>{{ t('llmOps.monitor.agioneListed') }}</span>
              <strong>{{ provider.listed_count }}</strong>
            </div>
            <div class="metric-line">
              <span>{{ t('llmOps.monitor.todo') }}</span>
              <strong>{{ provider.todo_count }}</strong>
            </div>
          </div>
          <div class="mt-3 h-1.5 overflow-hidden rounded-full bg-slate-100">
            <div
              class="h-full rounded-full bg-emerald-500"
              :style="{ width: `${provider.ready_rate}%` }"
            />
          </div>
        </div>
      </div>
    </div>

    <div class="panel overflow-hidden p-0">
      <div class="table-toolbar">
        <div>
          <h3 class="panel-title">
            {{ t('llmOps.monitor.focusTableTitle') }}
          </h3>
          <p class="mt-1 text-xs text-slate-500">
            {{ t('llmOps.monitor.focusTableSubtitle') }}
          </p>
        </div>
        <div class="flex flex-col gap-2 sm:flex-row">
          <CompactSelect
            v-model="simulationChannelModel"
            :options="simulationChannelOptions"
            class-name="w-36"
            size="sm"
          />
          <CompactSelect
            v-model="simulationStatusModel"
            :options="simulationStatusOptions"
            class-name="w-32"
            size="sm"
          />
        </div>
      </div>
      <div class="overflow-x-auto">
        <table class="data-table">
          <thead>
            <tr>
              <th class="table-head">{{ t('llmOps.fields.model') }}</th>
              <th class="table-head">{{ t('llmOps.fields.provider') }}</th>
              <th class="table-head text-right">
                {{ t('llmOps.monitor.channelCoverage') }}
              </th>
              <th class="table-head">
                {{
                  simulationChannel
                    ? t('llmOps.monitor.filteredChannel')
                    : t('llmOps.monitor.lowestProcurementChannel')
                }}
              </th>
              <th class="table-head">
                {{ currentPlatformListingLabel }}
              </th>
              <th class="table-head text-right">
                {{
                  simulationChannel
                    ? t('llmOps.price.input')
                    : t('llmOps.price.lowestInput')
                }}
              </th>
              <th class="table-head text-right">
                {{
                  simulationChannel
                    ? t('llmOps.price.output')
                    : t('llmOps.price.lowestOutput')
                }}
              </th>
              <th class="table-head">{{ t('llmOps.fields.status') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in monitorTableRows" :key="row.model_id">
              <td class="table-cell">
                <p class="font-medium text-slate-900">
                  {{ row.model_name }}
                </p>
                <p
                  v-if="monitorModelSubtitle(row)"
                  class="mt-1 font-mono text-xs text-slate-500"
                >
                  {{ monitorModelSubtitle(row) }}
                </p>
              </td>
              <td class="table-cell">{{ row.provider_name }}</td>
              <td class="table-cell text-right font-mono">
                {{ row.coverage_count }} / {{ operationalChannelCount }}
              </td>
              <td class="table-cell">
                {{
                  row.display_channel?.channel_name ||
                  t('llmOps.status.noSupply')
                }}
              </td>
              <td class="table-cell">
                <span
                  :class="row.is_agione_listed ? 'badge-ok' : 'badge-muted'"
                >
                  {{
                    row.is_agione_listed
                      ? t('llmOps.status.listed')
                      : t('llmOps.status.unlisted')
                  }}
                </span>
              </td>
              <td class="table-cell text-right font-mono">
                {{
                  money(
                    row.display_channel?.input_price_per_million,
                    row.display_channel?.currency
                  )
                }}
              </td>
              <td class="table-cell text-right font-mono">
                {{
                  money(
                    row.display_channel?.output_price_per_million,
                    row.display_channel?.currency
                  )
                }}
              </td>
              <td class="table-cell">
                <span :class="['status-pill', row.status_tone]">
                  {{ row.status_label }}
                </span>
              </td>
            </tr>
            <tr v-if="!monitorTableRows.length">
              <td class="table-cell text-slate-500" colspan="8">
                {{ t('llmOps.monitor.emptyFocusRows') }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import CompactSelect from '@/components/llm-ops/CompactSelect.vue'

const props = defineProps({
  actionItems: {
    type: Array,
    required: true
  },
  channelCoverageRows: {
    type: Array,
    required: true
  },
  currentPlatformListingLabel: {
    type: String,
    required: true
  },
  kpiCards: {
    type: Array,
    required: true
  },
  monitorModelSubtitle: {
    type: Function,
    required: true
  },
  monitorTableRows: {
    type: Array,
    required: true
  },
  money: {
    type: Function,
    required: true
  },
  operationalChannelCount: {
    type: Number,
    required: true
  },
  providerCoverageRows: {
    type: Array,
    required: true
  },
  simulationChannel: {
    type: [String, Number],
    default: ''
  },
  simulationChannelOptions: {
    type: Array,
    required: true
  },
  simulationStatus: {
    type: String,
    required: true
  },
  simulationStatusOptions: {
    type: Array,
    required: true
  }
})

const emit = defineEmits([
  'navigate',
  'update:simulationChannel',
  'update:simulationStatus'
])

const { t } = useI18n()

const simulationChannelModel = computed({
  get: () => props.simulationChannel,
  set: (value) => emit('update:simulationChannel', value)
})

const simulationStatusModel = computed({
  get: () => props.simulationStatus,
  set: (value) => emit('update:simulationStatus', value)
})
</script>
