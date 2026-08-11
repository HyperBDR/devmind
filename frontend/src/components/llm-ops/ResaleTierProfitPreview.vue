<template>
  <p v-if="error" class="mt-3 text-xs text-rose-600">
    {{ error }}
  </p>
  <section
    v-if="preview"
    class="mt-4 overflow-hidden rounded-lg border border-agione-100 bg-agione-50/40"
  >
    <header
      class="flex flex-wrap items-center justify-between gap-2 px-3 py-2.5 text-xs"
    >
      <strong class="text-slate-800">
        {{ t('llmOps.publishingWorkspace.tiers.serverPreview') }}
      </strong>
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
                formatPercent(previousIntervalFor(interval)?.gross_margin_rate)
              }}
              → {{ formatPercent(interval.gross_margin_rate) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup>
import { useI18n } from 'vue-i18n'

const props = defineProps({
  currency: { type: String, default: 'USD' },
  error: { type: String, default: '' },
  previousPreview: { type: Object, default: null },
  preview: { type: Object, default: null }
})

const { t } = useI18n()

function formatPercent(value) {
  const amount = Number(value)
  return Number.isFinite(amount) ? `${(amount * 100).toFixed(2)}%` : '—'
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
