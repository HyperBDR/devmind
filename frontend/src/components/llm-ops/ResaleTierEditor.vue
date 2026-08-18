<template>
  <section class="rounded-lg border border-slate-200 bg-white p-4">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div class="min-w-0">
        <div class="flex items-center gap-2">
          <span
            class="inline-flex h-8 w-8 items-center justify-center rounded-full bg-slate-100 text-slate-500"
          >
            <SlidersHorizontal class="h-4 w-4" aria-hidden="true" />
          </span>
          <div>
            <h4 class="text-sm font-bold text-slate-900">
              {{ t('llmOps.publishingWorkspace.tiers.title') }}
            </h4>
            <p class="mt-0.5 text-xs text-slate-500">
              {{ t('llmOps.publishingWorkspace.tiers.sharedScheduleHelp') }}
            </p>
          </div>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <span
          class="rounded-md bg-slate-100 px-2.5 py-1.5 font-mono text-[11px] font-semibold text-slate-600"
        >
          {{ currency }} {{ t('llmOps.resaleTier.pricePerMillionTokens') }}
        </span>
        <button
          type="button"
          class="inline-flex items-center gap-1.5 rounded-md border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:border-agione-300 hover:text-agione-700 disabled:cursor-not-allowed disabled:opacity-50"
          :disabled="previewLoading"
          @click="$emit('preview')"
        >
          <RefreshCw
            class="h-3.5 w-3.5"
            :class="previewLoading ? 'animate-spin' : ''"
            aria-hidden="true"
          />
          {{
            previewLoading
              ? t('common.loading')
              : t('llmOps.publishingWorkspace.tiers.preview')
          }}
        </button>
      </div>
    </div>

    <TierPriceEditor
      class="mt-4"
      :boundaries-locked="boundariesLocked"
      :currency="currency"
      :errors="errors"
      :model-value="modelValue"
      :point-label="pointLabel"
      @update:model-value="$emit('update:modelValue', $event)"
    />

    <section
      class="mt-4 rounded-lg border border-slate-200 bg-slate-50/70 p-3"
      aria-live="polite"
    >
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div class="flex items-center gap-2">
          <Eye class="h-4 w-4 text-slate-500" aria-hidden="true" />
          <h5 class="text-xs font-bold text-slate-800">
            {{ t('llmOps.publishingWorkspace.tiers.customerPreview') }}
          </h5>
        </div>
        <span class="text-[10px] uppercase tracking-[0.12em] text-slate-400">
          {{ t('llmOps.publishingWorkspace.tiers.rangePreview') }}
        </span>
      </div>
      <div class="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
        <article
          v-for="(card, index) in cards"
          :key="`preview-${card.start}-${card.end}-${index}`"
          class="rounded-md border border-slate-200 bg-white p-3"
        >
          <div class="flex items-center justify-between gap-2">
            <span class="text-[11px] font-bold text-agione-700">
              {{
                t('llmOps.publishingWorkspace.tiers.tierLabel', {
                  value: index + 1
                })
              }}
            </span>
            <span class="font-mono text-[11px] text-slate-500">
              {{ rangeLabel(card) }}
            </span>
          </div>
          <dl class="mt-2 grid grid-cols-3 gap-2">
            <div v-for="dimension in dimensions" :key="dimension.key">
              <dt class="truncate text-[10px] text-slate-400">
                {{ t(dimension.label) }}
              </dt>
              <dd
                class="mt-0.5 truncate font-mono text-xs font-bold text-slate-800"
              >
                {{ priceLabel(card.prices?.[dimension.key]) }}
              </dd>
            </div>
          </dl>
        </article>
      </div>
    </section>

    <ResaleTierProfitPreview
      :currency="currency"
      :error="previewError"
      :previous-preview="previousPreview"
      :preview="preview"
    />
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { Eye, RefreshCw, SlidersHorizontal } from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'

import ResaleTierProfitPreview from '@/components/llm-ops/ResaleTierProfitPreview.vue'
import TierPriceEditor from '@/components/llm-ops/TierPriceEditor.vue'
import { buildResaleTierCards } from '@/utils/resaleTierDraft'

const props = defineProps({
  boundariesLocked: { type: Boolean, default: false },
  currency: { type: String, default: 'USD' },
  errors: { type: Object, default: () => ({}) },
  modelValue: { type: Object, required: true },
  pointLabel: { type: Function, default: () => () => '' },
  previousPreview: { type: Object, default: null },
  preview: { type: Object, default: null },
  previewError: { type: String, default: '' },
  previewLoading: { type: Boolean, default: false }
})

defineEmits(['preview', 'update:modelValue'])
const { locale, t } = useI18n()

const dimensions = computed(() => [
  { key: 'input', label: 'llmOps.publishingWorkspace.metrics.input' },
  { key: 'output', label: 'llmOps.publishingWorkspace.metrics.output' },
  { key: 'cache', label: 'llmOps.publishingWorkspace.metrics.cacheInput' }
])
const cards = computed(() => buildResaleTierCards(props.modelValue))

function formatUsage(value) {
  const amount = Number(value)
  if (!Number.isFinite(amount)) return String(value ?? '—')
  return `${new Intl.NumberFormat(locale.value, {
    maximumFractionDigits: 3
  }).format(amount / 1000)}K`
}

function rangeLabel(card) {
  if (card.flat) return t('llmOps.publishingWorkspace.tiers.allUsage')
  return `${formatUsage(card.start)} - ${card.end === null ? '∞' : formatUsage(card.end)}`
}

function priceLabel(value) {
  if (value === null || value === undefined || value === '') return '—'
  const amount = Number(value)
  return Number.isFinite(amount) ? amount.toFixed(4) : value || '—'
}
</script>
