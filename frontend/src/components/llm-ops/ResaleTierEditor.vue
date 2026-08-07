<template>
  <section class="rounded-lg border border-slate-200 bg-slate-50 p-4">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h4 class="text-sm font-bold text-slate-900">
          {{ t('llmOps.publishingWorkspace.tiers.title') }}
        </h4>
        <p class="mt-1 text-xs text-slate-500">
          {{ t('llmOps.publishingWorkspace.tiers.intervalHelp') }}
        </p>
      </div>
      <span
        class="rounded bg-white px-2 py-1 text-xs font-medium text-slate-600"
      >
        {{ currency }} / 1M
      </span>
      <button
        type="button"
        class="text-xs font-semibold text-agione-700 hover:text-agione-800"
        :disabled="previewLoading"
        @click="$emit('preview')"
      >
        {{
          previewLoading
            ? t('common.loading')
            : t('llmOps.publishingWorkspace.tiers.preview')
        }}
      </button>
    </div>

    <div class="mt-4 space-y-4">
      <section
        v-for="spec in dimensions"
        :key="spec.key"
        class="overflow-hidden rounded border border-slate-200 bg-white"
      >
        <header
          class="flex items-center justify-between gap-3 border-b border-slate-100 px-3 py-2"
        >
          <div>
            <h5 class="text-xs font-bold text-slate-800">
              {{ t(spec.label) }}
            </h5>
            <p class="mt-0.5 text-[11px] text-slate-500">
              {{ t('llmOps.publishingWorkspace.tiers.continuityHelp') }}
            </p>
          </div>
          <button
            type="button"
            class="text-xs font-semibold text-agione-700 hover:text-agione-800"
            @click="addTier(spec.key)"
          >
            {{ t('llmOps.publishingWorkspace.tiers.add') }}
          </button>
        </header>
        <div class="border-b border-slate-100 bg-slate-50/70 px-3 py-3">
          <p
            class="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500"
          >
            {{ t('llmOps.publishingWorkspace.tiers.rangePreview') }}
          </p>
          <div
            class="mt-2 flex min-w-max items-center"
            role="list"
            :aria-label="t('llmOps.publishingWorkspace.tiers.rangePreview')"
          >
            <template
              v-for="(row, index) in rowsFor(spec.key)"
              :key="`${spec.key}-preview-${index}`"
            >
              <div
                class="min-w-[148px] rounded border border-slate-200 bg-white px-3 py-2 shadow-sm"
                role="listitem"
              >
                <div class="flex items-center justify-between gap-2">
                  <span class="text-[11px] font-semibold text-slate-500">
                    {{
                      t('llmOps.publishingWorkspace.tiers.tierLabel', {
                        value: index + 1
                      })
                    }}
                  </span>
                  <span class="text-[11px] font-semibold text-agione-700">
                    {{ rangeLabel(row) }}
                  </span>
                </div>
                <p class="mt-1 text-xs font-bold text-slate-900">
                  {{ priceLabel(row) }}
                </p>
              </div>
              <div
                v-if="index < rowsFor(spec.key).length - 1"
                class="flex items-center px-1"
                :aria-label="t('llmOps.publishingWorkspace.tiers.connected')"
                role="img"
              >
                <span class="h-0.5 w-5 bg-agione-300"></span>
                <span class="-ml-0.5 text-sm font-bold text-agione-500">›</span>
              </div>
            </template>
          </div>
        </div>
        <div class="overflow-x-auto">
          <table class="min-w-full text-left text-xs">
            <thead class="bg-slate-50 text-slate-500">
              <tr>
                <th class="w-16 px-3 py-2 font-medium">
                  {{ t('llmOps.publishingWorkspace.tiers.tier') }}
                </th>
                <th class="px-3 py-2 font-medium">
                  {{ t('llmOps.publishingWorkspace.tiers.start') }}
                </th>
                <th class="px-3 py-2 font-medium">
                  {{ t('llmOps.publishingWorkspace.tiers.end') }}
                </th>
                <th class="px-3 py-2 font-medium">
                  {{ t('llmOps.publishingWorkspace.tiers.price') }}
                </th>
                <th class="px-3 py-2 text-right font-medium">
                  {{ t('llmOps.publishingWorkspace.tiers.actions') }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(row, index) in rowsFor(spec.key)"
                :key="`${spec.key}-${index}`"
                class="border-t border-slate-100"
              >
                <td class="px-3 py-2 align-top">
                  <span
                    class="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-agione-50 px-1.5 text-[11px] font-bold text-agione-700"
                  >
                    {{ index + 1 }}
                  </span>
                </td>
                <td class="px-3 py-2">
                  <span v-if="row.flat" class="text-slate-500">{{
                    t('llmOps.publishingWorkspace.tiers.allUsage')
                  }}</span>
                  <input
                    v-else
                    :value="row.start"
                    :aria-label="`${t('llmOps.publishingWorkspace.tiers.start')} ${
                      index + 1
                    }`"
                    class="w-28 rounded border border-slate-300 px-2 py-1 text-slate-900"
                    min="0"
                    type="number"
                    @input="
                      updateRow(spec.key, index, 'start', $event.target.value)
                    "
                  />
                  <p
                    v-if="errorFor(spec.key, index, 'start')"
                    class="mt-1 text-rose-600"
                  >
                    {{ errorFor(spec.key, index, 'start') }}
                  </p>
                </td>
                <td class="px-3 py-2">
                  <span v-if="row.flat" class="text-slate-500">—</span>
                  <template v-else>
                    <input
                      :value="row.end"
                      :aria-label="`${t('llmOps.publishingWorkspace.tiers.end')} ${
                        index + 1
                      }`"
                      class="w-28 rounded border border-slate-300 px-2 py-1 text-slate-900"
                      min="0"
                      :placeholder="
                        t('llmOps.publishingWorkspace.tiers.unbounded')
                      "
                      type="number"
                      @input="
                        updateRow(
                          spec.key,
                          index,
                          'end',
                          $event.target.value || null
                        )
                      "
                    />
                    <p
                      v-if="errorFor(spec.key, index, 'end')"
                      class="mt-1 text-rose-600"
                    >
                      {{ errorFor(spec.key, index, 'end') }}
                    </p>
                  </template>
                </td>
                <td class="px-3 py-2">
                  <input
                    :value="row.price"
                    :aria-label="`${t('llmOps.publishingWorkspace.tiers.price')} ${
                      index + 1
                    }`"
                    class="w-28 rounded border border-slate-300 px-2 py-1 text-slate-900"
                    min="0"
                    step="0.000001"
                    type="number"
                    @input="
                      updateRow(spec.key, index, 'price', $event.target.value)
                    "
                  />
                  <p
                    v-if="errorFor(spec.key, index, 'price')"
                    class="mt-1 text-rose-600"
                  >
                    {{ errorFor(spec.key, index, 'price') }}
                  </p>
                </td>
                <td class="px-3 py-2 text-right">
                  <button
                    v-if="!row.flat && rowsFor(spec.key).length > 1"
                    type="button"
                    class="text-xs font-medium text-rose-600 hover:text-rose-700"
                    @click="removeTier(spec.key, index)"
                  >
                    {{ t('llmOps.publishingWorkspace.tiers.remove') }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
    <p v-if="previewError" class="mt-3 text-xs text-rose-600">
      {{ previewError }}
    </p>
    <section
      v-if="preview"
      class="mt-4 overflow-hidden rounded border border-agione-100 bg-agione-50/40"
    >
      <header
        class="flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-xs"
      >
        <strong class="text-slate-800">{{
          t('llmOps.publishingWorkspace.tiers.serverPreview')
        }}</strong>
        <span
          :class="
            preview.approval?.eligible ? 'text-emerald-700' : 'text-amber-700'
          "
        >
          {{
            preview.approval?.eligible
              ? t('llmOps.publishingWorkspace.tiers.autoApproved')
              : t('llmOps.publishingWorkspace.tiers.manualApproval')
          }}
        </span>
      </header>
      <p class="border-t border-agione-100 px-3 py-2 text-xs text-slate-600">
        {{
          t('llmOps.publishingWorkspace.tiers.minimumMargin', {
            value: formatPercent(preview.profitability?.minimum_gross_margin)
          })
        }}
      </p>
      <div class="overflow-x-auto border-t border-agione-100">
        <table class="min-w-full text-left text-xs text-slate-600">
          <thead class="bg-white/70 text-slate-500">
            <tr>
              <th class="px-3 py-2 font-medium">
                {{ t('llmOps.publishingWorkspace.tiers.interval') }}
              </th>
              <th class="px-3 py-2 font-medium">
                {{ t('llmOps.publishingWorkspace.tiers.oldCost') }}
              </th>
              <th class="px-3 py-2 font-medium">
                {{ t('llmOps.publishingWorkspace.tiers.newCost') }}
              </th>
              <th class="px-3 py-2 font-medium">
                {{ t('llmOps.publishingWorkspace.tiers.oldPrice') }}
              </th>
              <th class="px-3 py-2 font-medium">
                {{ t('llmOps.publishingWorkspace.tiers.newPrice') }}
              </th>
              <th class="px-3 py-2 font-medium">
                {{ t('llmOps.publishingWorkspace.tiers.marginChange') }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="interval in preview.profitability?.intervals || []"
              :key="intervalKey(interval)"
              class="border-t border-agione-100"
            >
              <td class="px-3 py-2">{{ intervalLabel(interval) }}</td>
              <td class="px-3 py-2">
                {{ money(previousIntervalFor(interval)?.cost) }}
              </td>
              <td class="px-3 py-2">{{ money(interval.cost) }}</td>
              <td class="px-3 py-2">
                {{ money(previousIntervalFor(interval)?.gross_revenue) }}
              </td>
              <td class="px-3 py-2">{{ money(interval.gross_revenue) }}</td>
              <td class="px-3 py-2">
                {{
                  formatPercent(
                    previousIntervalFor(interval)?.gross_margin_rate
                  )
                }}
                → {{ formatPercent(interval.gross_margin_rate) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import {
  removeResaleTierRow,
  updateResaleTierRows
} from '@/utils/resaleTierDraft'

const props = defineProps({
  currency: { type: String, default: 'USD' },
  errors: { type: Object, default: () => ({}) },
  modelValue: { type: Object, required: true },
  previousPreview: { type: Object, default: null },
  preview: { type: Object, default: null },
  previewError: { type: String, default: '' },
  previewLoading: { type: Boolean, default: false }
})

const emit = defineEmits(['preview', 'update:modelValue'])
const { locale, t } = useI18n()

const dimensions = computed(() => [
  { key: 'input', label: 'llmOps.publishingWorkspace.metrics.input' },
  { key: 'output', label: 'llmOps.publishingWorkspace.metrics.output' },
  { key: 'cache', label: 'llmOps.publishingWorkspace.metrics.cacheInput' }
])

function rowsFor(key) {
  return props.modelValue?.[key] || []
}

function setRows(key, rows) {
  emit('update:modelValue', { ...props.modelValue, [key]: rows })
}

function updateRow(key, index, field, value) {
  setRows(key, updateResaleTierRows(rowsFor(key), index, field, value))
}

function addTier(key) {
  const rows = rowsFor(key)
  if (rows.length === 1 && rows[0].flat) {
    const price = rows[0].price
    setRows(key, [
      { end: '1000000', flat: false, price, start: '0' },
      { end: null, flat: false, price, start: '1000000' }
    ])
    return
  }
  const last = rows[rows.length - 1]
  const start = Number(last?.start || 0) + 1000000
  setRows(key, [
    ...rows.slice(0, -1),
    { ...last, end: String(start), flat: false },
    { end: null, flat: false, price: last?.price || '', start: String(start) }
  ])
}

function removeTier(key, index) {
  setRows(key, removeResaleTierRow(rowsFor(key), index))
}

function errorFor(key, index, field) {
  return props.errors?.[`${key}:${index}:${field}`] || ''
}

function formatPercent(value) {
  const amount = Number(value)
  return Number.isFinite(amount) ? `${(amount * 100).toFixed(2)}%` : '—'
}

function formatUsage(value) {
  if (value === null || value === undefined || value === '') return '—'
  const amount = Number(value)
  return Number.isFinite(amount)
    ? new Intl.NumberFormat(locale.value, {
        maximumFractionDigits: 6
      }).format(amount)
    : String(value)
}

function rangeLabel(row) {
  if (row.flat) return t('llmOps.publishingWorkspace.tiers.allUsage')
  const end = row.end === null ? '∞' : formatUsage(row.end)
  return `[${formatUsage(row.start)}, ${end})`
}

function priceLabel(row) {
  const amount = Number(row.price)
  const price = Number.isFinite(amount) ? amount.toFixed(6) : row.price || '—'
  return `${props.currency} ${price} / 1M`
}

function money(value) {
  const amount = Number(value)
  return Number.isFinite(amount)
    ? `${props.currency} ${amount.toFixed(6)}`
    : '—'
}

function intervalKey(interval) {
  return [interval.dimension, interval.tier_start, interval.tier_end].join(':')
}

function intervalLabel(interval) {
  const end = interval.tier_end === null ? '∞' : interval.tier_end
  return `${interval.dimension}: [${interval.tier_start}, ${end})`
}

function previousIntervalFor(interval) {
  const intervals = props.previousPreview?.profitability?.intervals || []
  return intervals.find((item) => intervalKey(item) === intervalKey(interval))
}
</script>
