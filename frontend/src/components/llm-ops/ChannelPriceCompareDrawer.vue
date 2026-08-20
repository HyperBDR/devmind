<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition-opacity duration-200"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition-opacity duration-150"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="open && row"
        class="fixed inset-0 z-[60] flex justify-end bg-slate-950/40"
        @click.self="close"
      >
        <aside
          class="compare-drawer flex h-full w-full max-w-2xl flex-col shadow-2xl"
          role="dialog"
          aria-modal="true"
          aria-labelledby="channel-compare-title"
        >
          <header class="compare-drawer-header">
            <div class="min-w-0">
              <p class="text-xs font-semibold text-agione-600">
                {{ t('llmOps.channelPriceMatrixPanel.drawer.eyebrow') }}
              </p>
              <h2
                id="channel-compare-title"
                class="mt-1 truncate text-lg font-semibold"
              >
                {{ row.model_name }}
              </h2>
              <p class="mt-1 text-xs text-slate-500">
                {{ dimensionLabel }} · {{ displayCurrency }} / 1M Tokens
              </p>
            </div>
            <button
              ref="closeButton"
              type="button"
              class="btn-secondary"
              @click="close"
            >
              {{ t('common.close') }}
            </button>
          </header>

          <div class="flex-1 space-y-5 overflow-y-auto p-5">
            <section class="grid gap-3 sm:grid-cols-3">
              <SummaryItem
                :label="t('llmOps.channelPriceMatrixPanel.drawer.lowestPrice')"
                :value="money(compareOffers[0])"
                tone="success"
              />
              <SummaryItem
                :label="
                  t('llmOps.channelPriceMatrixPanel.drawer.currentChannel')
                "
                :value="currentChannelName"
              />
              <SummaryItem
                :label="t('llmOps.channelPriceMatrixPanel.drawer.savings')"
                :value="savingsLabel"
                tone="primary"
              />
            </section>

            <div class="normalization-note">
              {{ t('llmOps.channelPriceMatrixPanel.drawer.normalizedHint') }}
            </div>

            <section class="space-y-3">
              <article
                v-for="offer in compareOffers"
                :key="offer.channel_id"
                :class="[
                  'compare-offer',
                  {
                    'is-selected': sameId(offer.channel_id, option?.channel_id),
                    'is-stale': freshness(offer).state === 'stale'
                  }
                ]"
              >
                <div class="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div class="flex flex-wrap items-center gap-2">
                      <h3 class="font-semibold text-slate-900">
                        {{ offer.channel_name }}
                      </h3>
                      <span
                        v-if="sameId(offer.channel_id, bestChannelId)"
                        class="status-pill success"
                      >
                        {{
                          t('llmOps.channelPriceMatrixPanel.tags.recommended')
                        }}
                      </span>
                      <span
                        v-if="sameId(offer.channel_id, currentChannelId)"
                        class="status-pill info"
                      >
                        {{ t('llmOps.channelPriceMatrixPanel.tags.current') }}
                      </span>
                      <span
                        v-if="freshness(offer).state === 'stale'"
                        class="status-pill warn"
                      >
                        {{ t('llmOps.channelPriceMatrixPanel.tags.stale') }}
                      </span>
                    </div>
                    <p class="mt-1 text-xs text-slate-500">
                      {{ contractContext(offer).offering }} ·
                      {{ contractContext(offer).version }}
                    </p>
                  </div>
                  <strong class="font-mono text-base text-slate-900">
                    {{ money(offer) }}
                  </strong>
                </div>

                <dl class="offer-context-grid">
                  <div>
                    <dt>
                      {{
                        t(
                          'llmOps.channelPriceMatrixPanel.drawer.effectiveWindow'
                        )
                      }}
                    </dt>
                    <dd>{{ contractContext(offer).effectiveWindow }}</dd>
                  </div>
                  <div>
                    <dt>
                      {{
                        t('llmOps.channelPriceMatrixPanel.drawer.pricingRule')
                      }}
                    </dt>
                    <dd>{{ contractContext(offer).pricingRule }}</dd>
                  </div>
                  <div>
                    <dt>
                      {{
                        t('llmOps.channelPriceMatrixPanel.drawer.contractFx')
                      }}
                    </dt>
                    <dd>{{ contractContext(offer).contractFx }}</dd>
                  </div>
                  <div>
                    <dt>
                      {{
                        t(
                          'llmOps.channelPriceMatrixPanel.drawer.settlementRatio'
                        )
                      }}
                    </dt>
                    <dd>{{ contractContext(offer).settlementRatio }}</dd>
                  </div>
                  <div>
                    <dt>
                      {{ t('llmOps.channelPriceMatrixPanel.drawer.freshness') }}
                    </dt>
                    <dd>{{ freshnessLabel(offer) }}</dd>
                  </div>
                </dl>
              </article>
            </section>
          </div>

          <footer class="compare-drawer-footer">
            <button type="button" class="btn-secondary" @click="openDetail">
              {{ t('llmOps.channelPriceMatrixPanel.drawer.viewDetail') }}
            </button>
            <button
              v-if="action !== 'keep'"
              type="button"
              class="btn-primary"
              @click="applyAction"
            >
              {{ actionText }}
            </button>
          </footer>
        </aside>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import {
  computed,
  defineComponent,
  h,
  nextTick,
  onMounted,
  onUnmounted,
  ref,
  watch
} from 'vue'
import { useI18n } from 'vue-i18n'

import { currentContractVersion } from '@/utils/channelContractRelations'
import {
  compareChannelOptions,
  optionFreshness,
  savingsPercent
} from '@/utils/llmOpsChannelPriceMatrix'

const SummaryItem = defineComponent({
  props: {
    label: { type: String, default: '' },
    tone: { type: String, default: '' },
    value: { type: String, default: '-' }
  },
  setup(props) {
    return () =>
      h('div', { class: ['compare-summary-item', props.tone] }, [
        h('p', { class: 'compare-summary-label' }, props.label),
        h('p', { class: 'compare-summary-value' }, props.value)
      ])
  }
})

const props = defineProps({
  open: { type: Boolean, default: false },
  row: { type: Object, default: null },
  option: { type: Object, default: null },
  dimension: { type: String, default: 'input' },
  action: { type: String, default: 'keep' },
  actionText: { type: String, default: '' },
  channelOfferings: { type: Array, default: () => [] },
  priceVersions: { type: Array, default: () => [] }
})

const emit = defineEmits(['apply', 'close', 'view-detail'])
const { t } = useI18n()
const closeButton = ref(null)

const priceField = computed(() =>
  props.dimension === 'output'
    ? 'output_price_per_million'
    : 'input_price_per_million'
)
const compareOffers = computed(() =>
  compareChannelOptions(props.row || {}, props.dimension)
)
const displayCurrency = computed(
  () => compareOffers.value[0]?.currency || props.row?.currency || 'CNY'
)
const dimensionLabel = computed(() =>
  props.dimension === 'output'
    ? t('llmOps.price.output')
    : t('llmOps.price.input')
)
const bestChannelId = computed(() => props.row?.best_channel?.channel_id)
const currentChannelId = computed(() => props.row?.current_listing?.channel_id)
const currentChannelName = computed(() => {
  if (!props.row?.current_listing?.is_listed) {
    return t('llmOps.status.unlisted')
  }
  return props.row.current_listing.channel_name || t('llmOps.channel.autoBest')
})
const savingsLabel = computed(() => {
  const value = savingsPercent(props.row || {}, props.dimension)
  return value === null ? '-' : `${value.toFixed(1)}%`
})

function money(offer) {
  const value = offer?.[priceField.value]
  if (value === null || value === undefined || value === '') return '-'
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return '-'
  return `${offer.currency || displayCurrency.value} ${parsed.toFixed(4)}`
}

function freshness(offer) {
  return optionFreshness(offer)
}

function freshnessLabel(offer) {
  const result = freshness(offer)
  if (result.state === 'unknown') {
    return t('llmOps.channelPriceMatrixPanel.freshness.unknown')
  }
  const hours = Math.floor(result.ageMs / (60 * 60 * 1000))
  if (hours < 1) {
    const minutes = Math.max(1, Math.floor(result.ageMs / (60 * 1000)))
    return t('llmOps.channelPriceMatrixPanel.freshness.minutes', {
      count: minutes
    })
  }
  if (hours < 24) {
    return t('llmOps.channelPriceMatrixPanel.freshness.hours', {
      count: hours
    })
  }
  return t('llmOps.channelPriceMatrixPanel.freshness.days', {
    count: Math.floor(hours / 24)
  })
}

function contractContext(offer) {
  const modelVersions = props.priceVersions.filter((version) =>
    sameId(version.model, props.row?.model_id)
  )
  const candidates = props.channelOfferings.filter((item) =>
    sameId(item.channel, offer.channel_id)
  )
  const relation = candidates
    .map((offering) => ({
      offering,
      version: currentContractVersion(modelVersions, offering.id)
    }))
    .filter((item) => item.version)
    .sort((left, right) => right.version.version - left.version.version)[0]
  const offering =
    relation?.offering ||
    candidates.find((item) => sameId(item.model, props.row?.model_id))
  const version = relation?.version || null
  const start = version?.effective_from
    ? new Date(version.effective_from).toLocaleString()
    : '-'
  const end = version?.effective_to
    ? new Date(version.effective_to).toLocaleString()
    : t('llmOps.channelPriceMatrixPanel.drawer.openEnded')
  const pricingRule =
    version?.discount_type && version.discount_type !== 'none'
      ? [version.discount_basis, version.discount_type, version.discount_value]
          .filter((item) => item !== null && item !== undefined && item !== '')
          .join(' / ')
      : t('llmOps.channelPriceMatrixPanel.drawer.flatRule')
  const ratio = Number(offer.settlement_ratio)
  return {
    offering: offering?.display_name || offering?.offering_key || '-',
    version: version?.version ? `v${version.version}` : '-',
    effectiveWindow: version ? `${start} — ${end}` : '-',
    pricingRule,
    contractFx: version?.contract_exchange_rate || offer.exchange_rate || '-',
    settlementRatio: Number.isFinite(ratio)
      ? `${(ratio * 100).toFixed(2)}%`
      : '-'
  }
}

function sameId(left, right) {
  if (left === null || left === undefined) return false
  if (right === null || right === undefined) return false
  return String(left) === String(right)
}

function close() {
  emit('close')
}

function openDetail() {
  emit('view-detail', props.row)
}

function applyAction() {
  emit('apply', props.row)
}

function handleKeydown(event) {
  if (event.key === 'Escape' && props.open) close()
}

onMounted(() => document.addEventListener('keydown', handleKeydown))
onUnmounted(() => document.removeEventListener('keydown', handleKeydown))

watch(
  () => props.open,
  (open) => {
    if (open) nextTick(() => closeButton.value?.focus())
  }
)
</script>

<style scoped>
.compare-drawer {
  background: var(--ui-bg-page, #fff);
  color: var(--ui-text-primary, #18181b);
}
.compare-drawer-header,
.compare-drawer-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  border-color: var(--ui-border-default, #dedee3);
  background: var(--ui-bg-card, #fff);
  padding: 1rem 1.25rem;
}
.compare-drawer-header {
  border-bottom-width: 1px;
}
.compare-drawer-footer {
  justify-content: flex-end;
  border-top-width: 1px;
}
.compare-summary-item,
.compare-offer {
  border: 1px solid var(--ui-border-default, #dedee3);
  border-radius: 0.75rem;
  background: var(--ui-bg-card, #fff);
}
.compare-summary-item {
  padding: 0.875rem;
}
.compare-summary-label,
.offer-context-grid dt {
  color: var(--ui-text-muted, #71717a);
  font-size: 0.7rem;
}
.compare-summary-value {
  margin-top: 0.4rem;
  color: var(--ui-text-primary, #18181b);
  font-size: 1rem;
  font-weight: 700;
}
.compare-summary-item.success .compare-summary-value {
  color: var(--ui-color-success, #059669);
}
.compare-summary-item.primary .compare-summary-value {
  color: var(--ui-color-primary, #5f4ecf);
}
.normalization-note {
  border-radius: 0.5rem;
  background: var(--ui-color-info-subtle, #eff6ff);
  color: var(--ui-color-info, #2563eb);
  padding: 0.75rem 0.875rem;
  font-size: 0.75rem;
}
.compare-offer {
  padding: 1rem;
}
.compare-offer.is-selected {
  border-color: var(--ui-color-primary, #5f4ecf);
  box-shadow: inset 3px 0 0 var(--ui-color-primary, #5f4ecf);
}
.compare-offer.is-stale {
  border-color: var(--ui-color-warning, #d97706);
}
.offer-context-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem 1rem;
  margin-top: 1rem;
  border-top: 1px solid var(--ui-border-soft, #ededf0);
  padding-top: 0.875rem;
}
.offer-context-grid dd {
  margin-top: 0.2rem;
  color: var(--ui-text-secondary, #3f3f46);
  font-family: var(--ui-font-mono, ui-monospace);
  font-size: 0.72rem;
  word-break: break-word;
}
@media (max-width: 640px) {
  .offer-context-grid {
    grid-template-columns: 1fr;
  }
  .compare-drawer-footer > button {
    flex: 1;
  }
}
</style>
