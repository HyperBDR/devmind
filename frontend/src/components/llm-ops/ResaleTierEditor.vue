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
          {{ currency }} / 1M Tokens
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

    <div
      class="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-4"
    >
      <div>
        <h5 class="text-xs font-bold text-slate-800">
          {{ t('llmOps.publishingWorkspace.tiers.priceEntry') }}
        </h5>
        <p class="mt-0.5 text-[11px] text-slate-500">
          {{
            boundariesLocked
              ? t('llmOps.publishingWorkspace.tiers.upstreamHelp')
              : t('llmOps.publishingWorkspace.tiers.continuityHelp')
          }}
        </p>
      </div>
      <span class="text-[11px] text-slate-400">
        {{
          t('llmOps.publishingWorkspace.tiers.cardCount', {
            count: cards.length
          })
        }}
      </span>
    </div>

    <div class="mt-3 space-y-2.5">
      <ResaleTierCard
        v-for="(card, index) in cards"
        :key="index"
        :can-remove="cards.length > 1"
        :card="card"
        :currency="currency"
        :dimensions="dimensions"
        :errors="errorsForCard(index)"
        :expanded="expandedIndex === index"
        :index="index"
        :locked="boundariesLocked"
        @remove="removeCard(index)"
        @toggle="toggleCard(index)"
        @update:end="updateCard(index, 'end', $event)"
        @update:price="
          (dimension, value) => updateCardPrice(index, dimension, value)
        "
      />
    </div>

    <button
      v-if="!boundariesLocked"
      type="button"
      class="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-lg border border-dashed border-agione-300 bg-agione-50/40 px-3 py-2.5 text-xs font-bold text-agione-700 transition hover:border-agione-500 hover:bg-agione-50 focus:outline-none focus:ring-2 focus:ring-agione-200"
      @click="addCard"
    >
      <Plus class="h-4 w-4" aria-hidden="true" />
      {{ t('llmOps.publishingWorkspace.tiers.add') }}
    </button>

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
import { computed, ref, watch } from 'vue'
import { Eye, Plus, RefreshCw, SlidersHorizontal } from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'

import ResaleTierCard from '@/components/llm-ops/ResaleTierCard.vue'
import ResaleTierProfitPreview from '@/components/llm-ops/ResaleTierProfitPreview.vue'
import {
  addResaleTierCard,
  buildResaleTierCards,
  buildResaleTierDraftFromCards,
  removeResaleTierCard,
  updateResaleTierCard
} from '@/utils/resaleTierDraft'

const props = defineProps({
  boundariesLocked: { type: Boolean, default: false },
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
const expandedIndex = ref(0)

const dimensions = computed(() => [
  { key: 'input', label: 'llmOps.publishingWorkspace.metrics.input' },
  { key: 'output', label: 'llmOps.publishingWorkspace.metrics.output' },
  { key: 'cache', label: 'llmOps.publishingWorkspace.metrics.cacheInput' }
])
const cards = computed(() => buildResaleTierCards(props.modelValue))

watch(
  () => cards.value.length,
  (length) => {
    if (expandedIndex.value >= length)
      expandedIndex.value = Math.max(0, length - 1)
  }
)

function commitCards(nextCards) {
  emit('update:modelValue', buildResaleTierDraftFromCards(nextCards))
}

function addCard() {
  const nextCards = addResaleTierCard(cards.value)
  expandedIndex.value = Math.max(0, nextCards.length - 1)
  commitCards(nextCards)
}

function removeCard(index) {
  commitCards(removeResaleTierCard(cards.value, index))
}

function toggleCard(index) {
  expandedIndex.value = expandedIndex.value === index ? -1 : index
}

function updateCard(index, field, value) {
  commitCards(updateResaleTierCard(cards.value, index, field, value))
}

function updateCardPrice(index, dimension, value) {
  commitCards(updateResaleTierCard(cards.value, index, dimension, value))
}

function errorsForCard(index) {
  const rangeError = dimensions.value
    .map(
      ({ key }) =>
        props.errors?.[`${key}:${index}:end`] ||
        props.errors?.[`${key}:${index}:start`]
    )
    .find(Boolean)
  return {
    cache: props.errors?.[`cache:${index}:price`] || '',
    end: rangeError || '',
    input: props.errors?.[`input:${index}:price`] || '',
    output: props.errors?.[`output:${index}:price`] || ''
  }
}

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
