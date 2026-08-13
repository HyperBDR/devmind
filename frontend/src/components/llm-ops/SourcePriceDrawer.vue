<template>
  <div
    v-if="source"
    class="fixed inset-0 z-50 flex justify-end bg-slate-950/30"
    @click.self="$emit('close')"
  >
    <aside
      class="h-full w-full max-w-[78rem] overflow-y-auto bg-white shadow-xl"
      role="dialog"
      aria-modal="true"
      aria-labelledby="source-price-drawer-title"
    >
      <header
        class="sticky top-0 z-10 border-b border-slate-200 bg-white px-5 py-4"
      >
        <div class="flex items-start justify-between gap-4">
          <div class="min-w-0">
            <p
              class="text-xs font-semibold uppercase tracking-[0.18em] text-indigo-600"
            >
              {{ t('llmOps.sourcePriceDrawer.catalogLabel') }}
            </p>
            <h3
              id="source-price-drawer-title"
              class="mt-2 truncate text-xl font-semibold text-slate-900"
            >
              {{ source.name }}
            </h3>
            <p class="mt-1 truncate font-mono text-xs text-slate-500">
              {{ source.slug }}
            </p>
          </div>
          <div class="flex shrink-0 items-center gap-2">
            <button
              type="button"
              class="btn-danger"
              :disabled="deleting"
              @click="$emit('delete', source)"
            >
              {{
                deleting
                  ? t('llmOps.sourcePriceDrawer.actions.deleting')
                  : t('llmOps.sourcePriceDrawer.actions.delete')
              }}
            </button>
            <button
              ref="closeButtonRef"
              type="button"
              class="btn-secondary"
              @click="closeDrawer"
            >
              {{ t('llmOps.sourcePriceDrawer.actions.close') }}
            </button>
          </div>
        </div>
      </header>

      <div class="space-y-5 px-5 py-5">
        <section class="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <SummaryMetric
            :label="t('llmOps.sourcePriceDrawer.summary.catalogModelCount')"
            :value="summary.catalog_model_count"
          />
          <SummaryMetric
            :label="t('llmOps.sourcePriceDrawer.summary.collectedSkuCount')"
            :value="summary.collected_sku_count"
          />
          <SummaryMetric
            :label="t('llmOps.sourcePriceDrawer.summary.coveredMetaModelCount')"
            :value="summary.covered_meta_model_count"
          />
          <SummaryMetric
            :label="t('llmOps.sourcePriceDrawer.summary.currentPriceItemCount')"
            :value="summary.current_price_item_count"
          />
          <SummaryMetric
            :label="t('llmOps.sourcePriceDrawer.summary.skippedModelCount')"
            :value="summary.skipped_model_count"
            tone="warning"
          />
        </section>

        <section class="source-info-grid">
          <div>
            <span>{{ t('llmOps.sourcePriceDrawer.info.owner') }}</span>
            <strong>{{ relationName }}</strong>
          </div>
          <div>
            <span>{{ t('llmOps.sourcePriceDrawer.info.updateMode') }}</span>
            <strong>{{ sourceConfigSummary }}</strong>
          </div>
          <div>
            <span>{{ t('llmOps.sourcePriceDrawer.info.latestRun') }}</span>
            <strong>
              {{ latestRunLabel }}
            </strong>
          </div>
          <div>
            <span>{{ t('llmOps.sourcePriceDrawer.info.priceUrl') }}</span>
            <a
              v-if="source.endpoint_url"
              class="source-link"
              :href="source.endpoint_url"
              rel="noopener noreferrer"
              target="_blank"
            >
              {{ sourceAddressLabel }}
            </a>
            <strong v-else>-</strong>
          </div>
        </section>

        <section class="panel overflow-hidden p-0">
          <div class="table-toolbar">
            <div>
              <h3 class="panel-title">
                {{ t('llmOps.sourcePriceDrawer.title') }}
              </h3>
              <p class="mt-1 text-xs text-slate-500">
                {{ t('llmOps.sourcePriceDrawer.subtitle') }}
              </p>
            </div>
            <input
              :value="search"
              class="field-input w-full md:w-80"
              type="search"
              :placeholder="t('llmOps.sourcePriceDrawer.searchPlaceholder')"
              @input="queueSearch($event.target.value)"
            />
          </div>

          <div v-if="loading" class="space-y-3 p-4" aria-busy="true">
            <div
              v-for="index in 3"
              :key="index"
              class="h-28 animate-pulse rounded-lg bg-slate-100"
            />
          </div>
          <div v-else-if="rows.length" class="divide-y divide-slate-100">
            <article v-for="row in rows" :key="row.meta_model_id" class="p-4">
              <div class="flex flex-col gap-4 xl:flex-row xl:items-start">
                <div class="min-w-0 xl:w-64 xl:shrink-0">
                  <h4 class="truncate font-semibold text-slate-900">
                    {{ row.meta_model_name }}
                  </h4>
                  <p class="mt-1 truncate font-mono text-xs text-slate-400">
                    {{ row.meta_model_code }} ·
                    {{ modalityLabel(row.modality) }}
                  </p>
                  <p class="mt-2 text-xs text-slate-500">
                    {{
                      t('llmOps.sourcePriceDrawer.priceItemCount', {
                        count: row.price_item_count
                      })
                    }}
                  </p>
                  <p class="mt-1 text-xs text-slate-400">
                    {{ formatDateTime(row.updated_at) }}
                  </p>
                </div>

                <div class="min-w-0 flex-1 space-y-3 price-schedule">
                  <section
                    v-for="variant in schedules(row.price_items)"
                    :key="variant.key"
                    class="overflow-hidden rounded-lg border border-slate-200"
                  >
                    <div
                      class="flex flex-wrap items-center justify-between gap-2 bg-slate-50 px-3 py-2"
                    >
                      <strong class="text-xs text-slate-700">
                        {{ variant.scope_label }}
                      </strong>
                      <span class="text-[11px] text-slate-400">
                        {{
                          t('llmOps.sourcePriceDrawer.tierCount', {
                            count: variant.tiers.length
                          })
                        }}
                      </span>
                    </div>
                    <div class="divide-y divide-slate-100">
                      <div
                        v-for="tier in variant.tiers"
                        :key="tier.key"
                        class="grid gap-2 px-3 py-2.5 lg:grid-cols-[13rem_minmax(0,1fr)] lg:items-center"
                      >
                        <span
                          class="font-mono text-xs font-semibold text-slate-600"
                        >
                          {{ tier.range_label }} ·
                          {{ billingUnitLabel(tier.billing_unit) }}
                        </span>
                        <div class="flex flex-wrap gap-2">
                          <span
                            v-for="price in tier.prices"
                            :key="price.dimension"
                            class="price-chip"
                          >
                            <span>{{ dimensionLabel(price.dimension) }}</span>
                            <strong>{{
                              money(price.unit_price, price.currency)
                            }}</strong>
                          </span>
                        </div>
                      </div>
                    </div>
                  </section>
                </div>
              </div>
            </article>
          </div>
          <div v-else class="px-4 py-12 text-center text-sm text-slate-500">
            {{
              search
                ? t('llmOps.sourcePriceDrawer.empty.noSearchResults')
                : t('llmOps.sourcePriceDrawer.empty.noRows')
            }}
          </div>

          <div v-if="totalItems" class="pagination-bar">
            <p class="text-xs text-slate-500">
              {{
                t('llmOps.sourcePriceDrawer.pagination.summary', {
                  page,
                  totalPages,
                  total: totalItems
                })
              }}
            </p>
            <div class="flex flex-wrap items-center gap-2">
              <label class="page-size-control">
                <span>{{
                  t('llmOps.sourcePriceDrawer.pagination.pageSize')
                }}</span>
                <select
                  class="page-size-select"
                  :value="pageSize"
                  :disabled="loading"
                  @change="
                    $emit('page-size-change', Number($event.target.value))
                  "
                >
                  <option
                    v-for="option in pageSizeOptions"
                    :key="option"
                    :value="option"
                  >
                    {{ option }}
                  </option>
                </select>
              </label>
              <button
                class="btn-secondary pagination-btn"
                type="button"
                :disabled="page <= 1 || loading"
                @click="$emit('page-change', page - 1)"
              >
                {{ t('common.previous') }}
              </button>
              <button
                class="btn-secondary pagination-btn"
                type="button"
                :disabled="page >= totalPages || loading"
                @click="$emit('page-change', page + 1)"
              >
                {{ t('common.next') }}
              </button>
            </div>
          </div>
        </section>
      </div>
    </aside>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import SummaryMetric from '@/components/llm-ops/SourcePriceSummaryMetric.vue'
import {
  priceSourceCollectionMethod,
  priceSourceOwnerType
} from '@/utils/llmOpsPriceSources'
import { buildSourcePriceSchedules } from '@/utils/sourcePriceCatalog'

const emit = defineEmits([
  'close',
  'delete',
  'page-change',
  'page-size-change',
  'search'
])

const props = defineProps({
  source: { type: Object, default: null },
  catalog: { type: Object, default: () => ({ results: [], summary: {} }) },
  search: { type: String, default: '' },
  deleting: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  page: { type: Number, default: 1 },
  pageSize: { type: Number, default: 10 },
  totalItems: { type: Number, default: 0 }
})

const pageSizeOptions = [10, 20, 50]
const { t, locale } = useI18n()
const closeButtonRef = ref(null)
let searchTimer = null

const rows = computed(() => props.catalog?.results || [])
const summary = computed(() => props.catalog?.summary || {})
const totalPages = computed(() =>
  Math.max(1, Math.ceil(Number(props.totalItems || 0) / props.pageSize))
)
const relationName = computed(
  () =>
    props.source?.provider_name ||
    props.source?.channel_name ||
    t('llmOps.sourcePriceDrawer.fallback.unbound')
)
const sourceConfigSummary = computed(() =>
  [
    sourceOwnerTypeLabel(priceSourceOwnerType(props.source)),
    sourceModeLabel(props.source),
    props.source?.currency
  ]
    .filter(Boolean)
    .join(' · ')
)
const sourceAddressLabel = computed(() => {
  const value = props.source?.endpoint_url
  if (!value) return ''
  try {
    const url = new URL(value)
    return `${url.hostname}${url.pathname === '/' ? '' : url.pathname}`
  } catch {
    return String(value)
  }
})
const latestRunLabel = computed(() => {
  const run = props.catalog?.latest_run
  if (!run) return '-'
  return `${run.status} · ${formatDateTime(run.finished_at || run.started_at)}`
})

function closeDrawer() {
  emit('close')
}

function handleKeydown(event) {
  if (event.key === 'Escape' && props.source) closeDrawer()
}

onMounted(() => document.addEventListener('keydown', handleKeydown))

onBeforeUnmount(() => {
  clearTimeout(searchTimer)
  document.removeEventListener('keydown', handleKeydown)
})

watch(
  () => props.source,
  async (source) => {
    if (!source) return
    await nextTick()
    closeButtonRef.value?.focus()
  }
)

function queueSearch(value) {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => emit('search', String(value).trim()), 250)
}

function schedules(priceItems) {
  return buildSourcePriceSchedules(priceItems, {
    defaultScope: t('llmOps.sourcePriceDrawer.defaultScope'),
    flat: t('llmOps.sourcePriceDrawer.allUsage')
  })
}

function money(value, currency = 'USD') {
  if (value === null || value === undefined || value === '') return '-'
  return `${currency || 'USD'} ${Number(value).toFixed(4)}`
}

function dimensionLabel(dimension) {
  const labels = {
    text_input: t('llmOps.sourcePriceDrawer.dimensions.textInput'),
    text_output: t('llmOps.sourcePriceDrawer.dimensions.textOutput'),
    cache_input: t('llmOps.sourcePriceDrawer.dimensions.cacheInput'),
    image_input: t('llmOps.sourcePriceDrawer.dimensions.imageInput'),
    image_output: t('llmOps.sourcePriceDrawer.dimensions.imageOutput'),
    audio_input: t('llmOps.sourcePriceDrawer.dimensions.audioInput'),
    audio_output: t('llmOps.sourcePriceDrawer.dimensions.audioOutput'),
    video_input: t('llmOps.sourcePriceDrawer.dimensions.videoInput'),
    video_output: t('llmOps.sourcePriceDrawer.dimensions.videoOutput')
  }
  return labels[dimension] || dimension || '-'
}

function billingUnitLabel(unit) {
  const labels = {
    per_1m_tokens: t('llmOps.sourcePriceDrawer.billingUnits.per1mTokens'),
    per_image: t('llmOps.sourcePriceDrawer.billingUnits.perImage'),
    per_second: t('llmOps.sourcePriceDrawer.billingUnits.perSecond'),
    per_generation: t('llmOps.sourcePriceDrawer.billingUnits.perGeneration')
  }
  return labels[unit] || unit || '-'
}

function modalityLabel(modality) {
  const labels = {
    text: t('llmOps.sourcePriceDrawer.modalities.text'),
    audio: t('llmOps.sourcePriceDrawer.modalities.audio'),
    video: t('llmOps.sourcePriceDrawer.modalities.video'),
    multimodal: t('llmOps.sourcePriceDrawer.modalities.multimodal')
  }
  return labels[modality] || modality || ''
}

function sourceOwnerTypeLabel(ownerType) {
  const labels = {
    model_provider_official: t(
      'llmOps.sourcePriceDrawer.sourceOwnerTypes.modelProvider'
    ),
    cloud_provider_official: t(
      'llmOps.sourcePriceDrawer.sourceOwnerTypes.cloudProvider'
    ),
    supplier: t('llmOps.sourcePriceDrawer.sourceOwnerTypes.supplier'),
    internal: t('llmOps.sourcePriceDrawer.sourceOwnerTypes.internal'),
    unknown: t('llmOps.sourcePriceDrawer.sourceOwnerTypes.unknown')
  }
  return labels[ownerType] || labels.unknown
}

function sourceModeLabel(source) {
  const method = priceSourceCollectionMethod(source)
  const labels = {
    auto_collect: 'autoCollect',
    manual_entry: 'manualMaintenance',
    manual_import: 'manualImport',
    api_sync: 'apiSync'
  }
  return t(`llmOps.sourcePriceDrawer.sourceMode.${labels[method] || 'pending'}`)
}

function formatDateTime(value) {
  if (!value) return '-'
  return new Intl.DateTimeFormat(locale.value, {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  }).format(new Date(value))
}
</script>

<style scoped>
.source-info-grid {
  @apply grid gap-3 sm:grid-cols-2 xl:grid-cols-4;
}
.source-info-grid div {
  @apply min-w-0 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2;
}
.source-info-grid span {
  @apply block text-xs text-slate-500;
}
.source-info-grid strong,
.source-info-grid a {
  @apply mt-1 block truncate text-sm font-medium text-slate-800;
}
.source-link {
  @apply text-indigo-600 hover:text-indigo-700 hover:underline;
}
.table-toolbar {
  @apply flex flex-col gap-3 border-b border-slate-200 px-4 py-3 md:flex-row md:items-center md:justify-between;
}
.price-chip {
  @apply inline-flex items-center gap-2 rounded-md border border-slate-200 bg-white px-2 py-1 text-xs;
}
.price-chip span {
  @apply text-slate-400;
}
.price-chip strong {
  @apply font-mono font-semibold text-slate-800;
}
.pagination-bar {
  @apply flex flex-col gap-3 border-t border-slate-100 px-4 py-3 sm:flex-row sm:items-center sm:justify-between;
}
.pagination-btn {
  @apply px-3 py-1.5 text-xs;
}
.page-size-control {
  @apply inline-flex items-center gap-2 text-xs font-medium text-slate-500;
}
.page-size-select {
  @apply h-8 rounded-lg border border-slate-200 bg-white px-2 text-xs text-slate-700;
}
</style>
