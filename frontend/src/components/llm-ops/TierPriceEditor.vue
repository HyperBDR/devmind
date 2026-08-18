<template>
  <div>
    <div
      class="flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-4"
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
        :point-label="pointLabel"
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
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Plus } from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'

import ResaleTierCard from '@/components/llm-ops/ResaleTierCard.vue'
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
  pointLabel: { type: Function, default: () => () => '' }
})

const emit = defineEmits(['update:modelValue'])
const { t } = useI18n()
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
    if (expandedIndex.value >= length) {
      expandedIndex.value = Math.max(0, length - 1)
    }
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
</script>
