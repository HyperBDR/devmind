<template>
  <article
    class="overflow-hidden rounded-lg border bg-white transition"
    :class="expanded ? 'border-agione-300 shadow-sm' : 'border-slate-200'"
  >
    <header
      class="flex flex-wrap items-center gap-3 px-3 py-3 sm:flex-nowrap sm:px-4"
      :class="expanded ? 'bg-agione-50/70' : 'bg-white'"
    >
      <span
        class="inline-flex shrink-0 items-center rounded-full bg-agione-600 px-2.5 py-1 text-[11px] font-bold text-white"
      >
        {{
          t('llmOps.publishingWorkspace.tiers.tierLabel', { value: index + 1 })
        }}
      </span>

      <div
        v-if="card.flat"
        class="min-w-0 flex-1 text-xs font-semibold text-slate-700"
      >
        {{ t('llmOps.publishingWorkspace.tiers.allUsage') }}
      </div>
      <div v-else class="flex min-w-0 flex-1 flex-wrap items-center gap-2">
        <span class="font-mono text-xs font-semibold text-slate-700">
          {{ formatBoundary(card.start) }}
        </span>
        <span class="text-xs text-slate-400">
          {{ t('llmOps.publishingWorkspace.tiers.to') }}
        </span>
        <div v-if="card.end !== null" class="flex items-center gap-1.5">
          <input
            :aria-label="`${t('llmOps.publishingWorkspace.tiers.end')} ${index + 1}`"
            class="w-24 rounded-md border border-slate-300 bg-white px-2 py-1.5 text-right font-mono text-xs font-semibold text-slate-900 outline-none transition focus:border-agione-500 focus:ring-2 focus:ring-agione-100 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-500"
            :disabled="locked"
            min="0"
            step="1"
            type="number"
            :value="endInThousands"
            @input="emitEnd($event.target.value)"
          />
          <span class="whitespace-nowrap text-[11px] text-slate-500">
            K Tokens
          </span>
        </div>
        <span v-else class="font-mono text-sm font-bold text-slate-700">
          ∞
        </span>
        <p v-if="errors.end" class="w-full text-xs text-rose-600">
          {{ errors.end }}
        </p>
      </div>

      <p
        v-if="!expanded"
        class="hidden truncate text-[11px] text-slate-500 lg:block"
      >
        {{ collapsedSummary }}
      </p>
      <div class="ml-auto flex shrink-0 items-center gap-1">
        <button
          type="button"
          class="inline-flex h-8 w-8 items-center justify-center rounded-md text-slate-500 transition hover:bg-white hover:text-agione-700 focus:outline-none focus:ring-2 focus:ring-agione-200"
          :aria-expanded="expanded"
          :aria-label="
            expanded
              ? t('llmOps.publishingWorkspace.tiers.collapse')
              : t('llmOps.publishingWorkspace.tiers.expand')
          "
          @click="$emit('toggle')"
        >
          <ChevronUp v-if="expanded" class="h-4 w-4" aria-hidden="true" />
          <ChevronDown v-else class="h-4 w-4" aria-hidden="true" />
        </button>
        <button
          v-if="!locked && !card.flat && canRemove"
          type="button"
          class="inline-flex h-8 w-8 items-center justify-center rounded-md text-slate-400 transition hover:bg-rose-50 hover:text-rose-600 focus:outline-none focus:ring-2 focus:ring-rose-200"
          :aria-label="`${t('llmOps.publishingWorkspace.tiers.remove')} ${index + 1}`"
          @click="$emit('remove')"
        >
          <Trash2 class="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
    </header>

    <div
      v-if="expanded"
      class="grid gap-3 border-t border-slate-100 bg-white p-3 md:grid-cols-3 md:p-4"
    >
      <label
        v-for="dimension in dimensions"
        :key="dimension.key"
        class="rounded-lg border border-slate-200 bg-slate-50/60 p-3"
      >
        <span class="flex items-center justify-between gap-2">
          <span class="text-xs font-bold text-slate-800">
            {{ t(dimension.label) }}
          </span>
          <span class="text-[10px] font-medium uppercase text-slate-400">
            {{ currency }} / 1M
          </span>
        </span>
        <input
          :aria-label="`${t(dimension.label)} ${index + 1}`"
          class="mt-2 w-full rounded-md border border-slate-300 bg-white px-3 py-2 font-mono text-sm font-semibold text-slate-900 outline-none transition focus:border-agione-500 focus:ring-2 focus:ring-agione-100"
          min="0"
          step="0.000001"
          type="number"
          :value="card.prices?.[dimension.key]"
          @input="$emit('update:price', dimension.key, $event.target.value)"
        />
        <span
          v-if="errors[dimension.key]"
          class="mt-1.5 block text-xs text-rose-600"
        >
          {{ errors[dimension.key] }}
        </span>
      </label>
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import { ChevronDown, ChevronUp, Trash2 } from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  canRemove: { type: Boolean, default: false },
  card: { type: Object, required: true },
  currency: { type: String, default: 'USD' },
  dimensions: { type: Array, required: true },
  errors: { type: Object, default: () => ({}) },
  expanded: { type: Boolean, default: false },
  index: { type: Number, required: true },
  locked: { type: Boolean, default: false }
})

const emit = defineEmits(['remove', 'toggle', 'update:end', 'update:price'])
const { locale, t } = useI18n()

const endInThousands = computed(() => {
  const value = Number(props.card.end)
  return Number.isFinite(value) ? value / 1000 : ''
})

const collapsedSummary = computed(() =>
  props.dimensions
    .map((dimension) => {
      const value = props.card.prices?.[dimension.key]
      return `${t(dimension.label)} ${value || '—'}`
    })
    .join(' · ')
)

function emitEnd(value) {
  if (value === '') {
    emit('update:end', null)
    return
  }
  const amount = Number(value)
  emit('update:end', Number.isFinite(amount) ? String(amount * 1000) : value)
}

function formatBoundary(value) {
  const amount = Number(value)
  if (!Number.isFinite(amount)) return String(value ?? '—')
  return `${new Intl.NumberFormat(locale.value, {
    maximumFractionDigits: 3
  }).format(amount / 1000)}K`
}
</script>
