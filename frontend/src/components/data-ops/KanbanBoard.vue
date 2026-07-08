<template>
  <section class="space-y-3">
    <h3 class="text-sm font-bold text-slate-950">{{ title }}</h3>
    <div class="flex min-h-[560px] gap-4 overflow-x-auto pb-4">
      <div
        v-for="[group, groupCards] in groupedCards"
        :key="group"
        class="flex w-72 shrink-0 flex-col rounded-xl bg-slate-100"
      >
        <div class="border-b border-slate-200 px-4 py-3">
          <div class="flex items-center justify-between">
            <h4 class="text-sm font-bold text-slate-800">{{ group }}</h4>
            <span
              class="rounded-full bg-white px-2 py-0.5 text-xs font-bold text-slate-500"
            >
              {{ groupCards.length }}
            </span>
          </div>
        </div>
        <div class="flex-1 space-y-3 overflow-y-auto p-3">
          <div
            v-for="card in groupCards"
            :key="card.id || card[subtitleKey] || card[titleKey]"
            class="space-y-2 rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
          >
            <p class="truncate text-sm font-semibold text-slate-800">
              {{ card[titleKey] || '未知' }}
            </p>
            <p class="text-[10px] font-mono text-slate-400">
              {{ card[subtitleKey] || '-' }}
            </p>
            <div class="flex justify-between text-xs">
              <span class="text-slate-500">
                {{
                  card.sales_person ||
                  card.project_owner ||
                  card.region ||
                  '-'
                }}
              </span>
              <strong class="text-slate-800">
                {{ formatAmount(card[amountKey], card.currency) }}
              </strong>
            </div>
          </div>
        </div>
      </div>
    </div>
    <EmptyState v-if="!cards.length" />
  </section>
</template>

<script setup>
import { computed } from 'vue'

import { formatAmount } from '@/composables/useDataOpsConsole'

import { EmptyState } from './DataOpsPrimitives'

const props = defineProps({
  amountKey: { type: String, required: true },
  cards: { type: Array, default: () => [] },
  groupKey: { type: String, required: true },
  subtitleKey: { type: String, required: true },
  title: { type: String, required: true },
  titleKey: { type: String, required: true },
})

const groupedCards = computed(() => {
  const groups = props.cards.reduce((acc, card) => {
    const key = card[props.groupKey] || '未知'
    acc[key] = acc[key] || []
    acc[key].push(card)
    return acc
  }, {})
  return Object.entries(groups)
})
</script>
