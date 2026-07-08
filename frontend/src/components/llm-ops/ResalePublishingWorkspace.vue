<!--
  ResalePublishingWorkspace — immersive resale publishing workspace
  re-implements demo.html "model publishing workspace" using the
  existing llm-ops procurement rows as the chain-of-supply source.
-->
<template>
  <div class="resale-publishing-workspace workspace-shell">
    <section class="workspace-section workspace-toolbar">
      <div class="workspace-filter-grid">
        <label class="filter-field">
          <span>{{ t('llmOps.publishingWorkspace.filters.platform') }}</span>
          <CompactSelect
            v-model="form.platformId"
            :options="platformSelectOptions"
            class-name="w-full workspace-select"
            :menu-min-width="220"
            size="sm"
          />
        </label>
        <label class="filter-field">
          <span>{{ t('llmOps.publishingWorkspace.filters.vendor') }}</span>
          <CompactSelect
            v-model="form.metaVendorId"
            :options="metaVendorSelectOptions"
            class-name="w-full workspace-select"
            :menu-min-width="280"
            searchable
            size="sm"
            @change="onMetaVendorChange"
          />
        </label>
        <label class="filter-field">
          <span>{{ t('llmOps.publishingWorkspace.filters.metaModel') }}</span>
          <CompactSelect
            v-model="form.modelId"
            :options="baseModelSelectOptions"
            class-name="w-full workspace-select workspace-select-model"
            :menu-min-width="380"
            searchable
            size="sm"
            @change="onModelChange"
          />
        </label>
        <label class="filter-field">
          <span>{{ t('llmOps.publishingWorkspace.filters.supplier') }}</span>
          <CompactSelect
            v-model="form.supplierId"
            :disabled="!form.modelId"
            :options="supplierSelectOptions"
            class-name="w-full workspace-select"
            :menu-min-width="280"
            size="sm"
          />
        </label>
      </div>
      <div class="pricing-context">
        <div class="pricing-segment">
          <span class="pricing-segment-label">
            {{ t('llmOps.publishingWorkspace.context.platformCurrency') }}
          </span>
          <strong class="pricing-segment-value">
            {{ platformCurrencyLabel }}
          </strong>
        </div>
        <div class="pricing-segment">
          <span class="pricing-segment-label">
            {{ t('llmOps.publishingWorkspace.context.exchangeRate') }}
          </span>
          <strong class="pricing-segment-value">
            1 USD =
            {{ formatReadonlyNumber(globalPricing.exchangeRate, 4) }}
            CNY
          </strong>
        </div>
        <div class="pricing-segment">
          <span class="pricing-segment-label">
            {{
              t('llmOps.publishingWorkspace.context.pointConversion', {
                point: pointUnitLabel
              })
            }}
          </span>
          <strong class="pricing-segment-value">
            1 {{ platformCurrencyLabel }} =
            {{ formatReadonlyNumber(globalPricing.creditRatio, 2) }}
            {{ pointUnitLabel }}
          </strong>
        </div>
      </div>
    </section>

    <section v-if="form.modelId" class="workspace-section overflow-hidden p-0">
      <header
        class="flex flex-col gap-2 border-b border-slate-200 px-5 py-4 sm:flex-row sm:items-center sm:justify-between"
      >
        <h3 class="flex items-center gap-2 text-sm font-bold text-slate-900">
          <span class="inline-block h-2 w-2 rounded-full bg-agione-500" />
          {{ t('llmOps.publishingWorkspace.supply.title') }}
        </h3>
        <div class="flex items-center gap-3 text-xs">
          <span
            v-if="!isSupplyChainExpanded"
            class="rounded bg-agione-50 px-2 py-1 font-semibold text-agione-700"
          >
            {{
              t('llmOps.publishingWorkspace.supply.selectedCount', {
                count: selectedChainRows.length
              })
            }}
          </span>
          <span v-else class="text-slate-500">
            {{
              t('llmOps.publishingWorkspace.supply.availableCount', {
                count: chainRows.length
              })
            }}
          </span>
          <button
            type="button"
            class="btn-secondary btn-action-view !px-2.5 !py-1.5 !text-xs"
            @click="isSupplyChainExpanded = !isSupplyChainExpanded"
          >
            {{
              isSupplyChainExpanded
                ? t('llmOps.publishingWorkspace.supply.collapse')
                : t('llmOps.publishingWorkspace.supply.expand')
            }}
          </button>
        </div>
      </header>

      <div v-show="isSupplyChainExpanded">
        <div class="supply-grid supply-grid-header">
          <div>{{ t('llmOps.publishingWorkspace.supply.chain') }}</div>
          <div
            v-for="dimension in supplyCostDimensions"
            :key="`supply-head-${dimension.key}`"
          >
            {{ dimension.label }}
          </div>
        </div>

        <div
          v-if="!chainRows.length"
          class="bg-white p-8 text-center text-sm text-slate-500"
        >
          {{ t('llmOps.publishingWorkspace.supply.empty') }}
        </div>

        <div
          v-for="group in groupedChainRows"
          v-else
          :key="group.supplierName"
          class="border-b border-slate-200 bg-white last:border-b-0"
        >
          <div
            class="flex items-center gap-2 border-b border-slate-200 bg-slate-50 px-4 py-2 text-[13px] font-bold text-slate-700"
          >
            <span class="inline-block h-1.5 w-1.5 rounded-full bg-agione-500" />
            {{
              t('llmOps.publishingWorkspace.supply.supplierPrefix', {
                name: group.supplierName
              })
            }}
          </div>
          <div
            v-for="srcGroup in group.sources"
            :key="`${group.supplierName}-${srcGroup.source}`"
            class="border-b border-dashed border-slate-200 last:border-b-0"
          >
            <div
              class="flex items-center gap-2 bg-slate-50/60 px-4 py-1.5 pl-10 text-[12px] font-medium text-slate-500"
            >
              <span class="inline-block h-1 w-1 rounded-full bg-slate-400" />
              {{
                t('llmOps.publishingWorkspace.supply.sourcePrefix', {
                  name: srcGroup.source
                })
              }}
            </div>
            <div
              v-for="row in srcGroup.models"
              :key="row.uniqueId"
              class="supply-grid supply-grid-row"
              :class="{ 'bg-agione-50/30': row.selected }"
            >
              <label class="supply-model-cell">
                <input
                  :checked="row.selected"
                  type="checkbox"
                  class="h-4 w-4 rounded border-slate-300 text-agione-600 focus:ring-agione-500"
                  @change="handleChainSelection(row, $event)"
                />
                <span class="font-mono text-[13px] font-bold text-slate-900">{{
                  row.skuModelName
                }}</span>
                <span
                  v-if="row.skuModelName !== row.modelName"
                  class="rounded border border-slate-200 bg-white px-1.5 py-0.5 text-[10px] font-medium text-slate-500"
                >
                  {{ row.modelName }}
                </span>
                <span
                  v-if="row.isLowest"
                  class="rounded-full border border-emerald-100 bg-emerald-50 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-700"
                >
                  {{ t('llmOps.publishingWorkspace.supply.lowest') }}
                </span>
              </label>

              <div
                v-for="dim in priceDimensions(row)"
                :key="`cost-${row.uniqueId}-${dim.key}`"
                class="supply-cost-cell"
              >
                <span class="supply-metric-label">
                  {{ dim.label }}
                </span>
                <span class="supply-metric-value text-slate-900">
                  {{ dim.costText }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section
      v-if="selectedChainRows.length"
      class="publishing-workbench-grid"
      :class="{ 'is-resizing-sidebar': isResizingSidebar }"
      :style="workbenchGridStyle"
    >
      <aside class="workspace-section performance-sidebar overflow-hidden p-0">
        <header class="performance-sidebar-header">
          <span class="performance-sidebar-dot" />
          <h3>{{ t('llmOps.publishingWorkspace.performance.title') }}</h3>
        </header>
        <div class="performance-sidebar-body">
          <section
            v-for="metric in perfMetrics"
            :key="metric.key"
            class="perf-metric-section"
          >
            <div class="perf-metric-title">
              {{ metric.label }}
            </div>
            <div class="perf-metric-rows">
              <div
                v-for="item in perfCompareRows"
                :key="`${metric.key}-${item.id}`"
                class="perf-metric-row"
              >
                <div class="perf-metric-name" :title="item.name">
                  {{ item.name }}
                </div>
                <div class="perf-metric-track">
                  <div
                    class="perf-metric-bar"
                    :class="metric.barClass()"
                    :style="{ width: barWidth(item[metric.key], metric.max) }"
                  />
                </div>
                <div class="perf-metric-value">
                  {{ metric.format(item[metric.key]) }}
                </div>
              </div>
              <p v-if="!perfCompareRows.length" class="perf-empty">
                {{ t('llmOps.publishingWorkspace.performance.empty') }}
              </p>
            </div>
          </section>
        </div>
        <button
          type="button"
          class="performance-sidebar-resize"
          :aria-label="t('llmOps.publishingWorkspace.performance.resize')"
          @pointerdown="startSidebarResize"
        />
      </aside>

      <div class="pricing-workbench-main space-y-4">
        <article
          v-for="row in selectedChainRows"
          :key="row.uniqueId"
          class="workspace-section overflow-hidden p-0"
        >
          <header
            class="flex flex-col gap-2 border-b border-slate-200 bg-slate-50 px-5 py-3 sm:flex-row sm:items-center sm:justify-between"
          >
            <div
              class="flex flex-wrap items-center gap-2 text-[13px] font-bold text-slate-900"
            >
              {{ row.skuModelName }}
              <span
                v-if="row.skuModelName !== row.modelName"
                class="rounded border border-slate-200 bg-white px-1.5 py-0.5 text-[10px] font-medium text-slate-500"
                >{{ row.modelName }}</span
              >
              <span
                class="rounded border border-slate-200 bg-white px-1.5 py-0.5 text-[10px] font-medium text-slate-500"
                >{{ row.provider }}</span
              >
              <span
                class="rounded border border-slate-200 bg-white px-1.5 py-0.5 text-[10px] font-medium text-slate-500"
                >{{ row.source }}</span
              >
            </div>
            <span
              v-if="row.isLowest"
              class="rounded-full border border-emerald-100 bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-700"
              >{{ t('llmOps.publishingWorkspace.supply.lowestProcurement') }}
            </span>
          </header>
          <div class="space-y-6 p-5">
            <div class="unified-margin-row">
              <div>
                <div class="flex flex-wrap items-center gap-2">
                  <p class="text-[11px] font-semibold text-slate-500">
                    {{ t('llmOps.publishingWorkspace.margin.title') }}
                  </p>
                  <span
                    v-if="selectedPlatformAutoApproveLimit !== null"
                    class="unified-margin-status"
                    :class="
                      autoApproveStatus(row.margin).ok
                        ? 'text-emerald-600'
                        : 'text-amber-600'
                    "
                  >
                    {{ autoApproveStatus(row.margin).label }}
                  </span>
                </div>
                <p class="mt-0.5 text-[11px] text-slate-400">
                  {{ t('llmOps.publishingWorkspace.margin.description') }}
                </p>
              </div>
              <div class="unified-margin-input">
                <input
                  :value="row.margin"
                  type="number"
                  :aria-label="t('llmOps.publishingWorkspace.margin.input')"
                  name="unified_margin_rate"
                  step="0.1"
                  min="0"
                  @input="onMarginInput(row, $event)"
                  @change="onMarginCommit(row, $event)"
                />
                <span>%</span>
              </div>
            </div>

            <div class="pricing-matrix">
              <div class="pricing-matrix-head pricing-matrix-label" />
              <div class="pricing-matrix-head">
                {{ t('llmOps.publishingWorkspace.pricing.cost') }}
              </div>
              <div class="pricing-matrix-head">
                {{ t('llmOps.publishingWorkspace.pricing.price') }}
              </div>
              <div class="pricing-matrix-head">{{ pointUnitLabel }}</div>
              <template
                v-for="dimension in priceDimensions(row)"
                :key="`${row.uniqueId}-${dimension.key}`"
              >
                <div class="pricing-matrix-label">
                  {{ dimension.label }}
                </div>
                <div class="pricing-matrix-card cost-formula-cell">
                  <p class="pricing-card-caption">
                    {{ t('llmOps.publishingWorkspace.pricing.costPrice') }}
                  </p>
                  <p class="font-mono text-[13px] font-bold text-slate-900">
                    {{ currencySymbol }}{{ dimension.costText }}
                  </p>
                  <p
                    class="cost-formula-text"
                    :title="costFormulaTitle(row, dimension.key)"
                  >
                    {{ costFormulaText(row, dimension.key) }}
                  </p>
                </div>
                <div class="pricing-matrix-card terminal-price-card">
                  <div class="terminal-price-main">
                    <p class="pricing-card-caption text-emerald-600">
                      {{ t('llmOps.publishingWorkspace.pricing.retailPrice') }}
                    </p>
                    <div
                      class="terminal-price-control"
                      :class="
                        isBelowReferencePrice(
                          dimension.priceRaw,
                          dimension.referencePriceRaw
                        )
                          ? 'terminal-price-control-error'
                          : ''
                      "
                    >
                      <span>{{ currencySymbol }}</span>
                      <input
                        :value="dimension.priceText"
                        type="number"
                        step="0.01"
                        min="0"
                        :aria-invalid="
                          isBelowReferencePrice(
                            dimension.priceRaw,
                            dimension.referencePriceRaw
                          )
                            ? 'true'
                            : 'false'
                        "
                        @input="onPriceInput(row, dimension.key, $event)"
                        @change="onPriceCommit(row, dimension.key, $event)"
                      />
                    </div>
                    <p
                      v-if="
                        isBelowReferencePrice(
                          dimension.priceRaw,
                          dimension.referencePriceRaw
                        )
                      "
                      class="terminal-price-error"
                    >
                      {{
                        t('llmOps.publishingWorkspace.pricing.belowFloor', {
                          value: currencySymbol + dimension.referencePriceText
                        })
                      }}
                    </p>
                  </div>
                  <div class="terminal-price-meta">
                    <p
                      :class="
                        isBelowReferencePrice(
                          dimension.priceRaw,
                          dimension.referencePriceRaw
                        )
                          ? 'text-amber-600'
                          : 'text-slate-500'
                      "
                      :title="referencePriceTitle(dimension)"
                    >
                      {{
                        t('llmOps.publishingWorkspace.pricing.floor', {
                          value: currencySymbol + dimension.referencePriceText
                        })
                      }}
                    </p>
                    <p>
                      {{ t('llmOps.publishingWorkspace.pricing.average') }}
                      <strong>{{
                        marketAverageText(dimension.marketAverage)
                      }}</strong>
                    </p>
                    <p
                      :class="
                        priceDiffClass(
                          dimension.priceRaw,
                          dimension.marketAverage
                        )
                      "
                      :title="
                        priceDiffTitle(
                          dimension.priceRaw,
                          dimension.marketAverage
                        )
                      "
                    >
                      {{
                        priceDiffText(
                          dimension.priceRaw,
                          dimension.marketAverage
                        )
                      }}
                      <span
                        v-if="
                          priceDiffAmountText(
                            dimension.priceRaw,
                            dimension.marketAverage
                          )
                        "
                      >
                        ·
                        {{
                          priceDiffAmountText(
                            dimension.priceRaw,
                            dimension.marketAverage
                          )
                        }}
                      </span>
                    </p>
                  </div>
                </div>
                <div class="pricing-matrix-card final-credit-card">
                  <p class="pricing-card-caption">
                    {{
                      t('llmOps.publishingWorkspace.pricing.finalPoint', {
                        point: pointUnitLabel
                      })
                    }}
                  </p>
                  <p class="font-mono text-[13px] font-bold text-agione-700">
                    {{ formatCredit(dimension.priceRaw) }}
                  </p>
                </div>
              </template>
            </div>
            <div class="pricing-axis-block compact-pricing-axis">
              <BulletChart
                :min="marginAxisRangeFor(row).min"
                :max="marginAxisRangeFor(row).max"
                :value="row.margin"
                :refs="marketMarginRefsFor(row)"
                :lower-tooltip="marginPolicyTooltip('min', row)"
                :upper-tooltip="marginPolicyTooltip('max')"
                :label="
                  t('llmOps.publishingWorkspace.margin.axisLabel', {
                    value: formatPercent(row.margin)
                  })
                "
                value-prefix=""
                value-suffix="%"
                :digits="1"
                @change="onMarginAxisChange(row, $event)"
              />
              <p class="pricing-axis-reference">
                {{ marketMarginReferenceText(row) }}
              </p>
            </div>
          </div>
        </article>
      </div>
    </section>

    <div
      v-else-if="form.modelId"
      class="rounded-lg border border-dashed border-slate-200 bg-slate-50 p-8 text-center text-sm text-slate-500"
    >
      {{ t('llmOps.publishingWorkspace.supply.selectRequired') }}
    </div>
  </div>
</template>

<script setup>
import '@/components/llm-ops/resalePublishingWorkspace.css'

import { computed, nextTick, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import BulletChart from '@/components/llm-ops/BulletChart.vue'
import CompactSelect from '@/components/llm-ops/CompactSelect.vue'
import { useResaleChainRows } from '@/composables/useResaleChainRows'
import { useResaleMarketAverages } from '@/composables/useResaleMarketAverages'
import { useResalePerformance } from '@/composables/useResalePerformance'
import { useResalePricing } from '@/composables/useResalePricing'
import { useResaleWorkspaceForm } from '@/composables/useResaleWorkspaceForm'
import { useResaleWorkspaceOptions } from '@/composables/useResaleWorkspaceOptions'
import { useResizableSidebar } from '@/composables/useResizableSidebar'
import { RESALE_PRICE_DIMENSION_SPECS } from '@/utils/resalePricing'

const props = defineProps({
  initialModelId: {
    type: [String, Number],
    default: null
  },
  agionePlatform: {
    type: Object,
    default: null
  },
  platforms: {
    type: Array,
    required: true
  },
  providers: {
    type: Array,
    required: true
  },
  metaModels: {
    type: Array,
    required: true
  },
  models: {
    type: Array,
    required: true
  },
  channels: {
    type: Array,
    required: true
  },
  procurementRows: {
    type: Array,
    default: () => []
  },
  priceItems: {
    type: Array,
    default: () => []
  },
  channelPriceItems: {
    type: Array,
    default: () => []
  },
  listings: {
    type: Array,
    default: () => []
  },
  pointConversion: {
    type: Object,
    default: null
  },
  displayCurrency: {
    type: String,
    default: 'CNY'
  },
  exchangeRate: {
    type: Number,
    default: 7.15
  },
  workflowConfig: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['change'])
const { t } = useI18n()

const {
  form,
  globalPricing,
  isSupplyChainExpanded,
  onMetaVendorChange,
  onModelChange
} = useResaleWorkspaceForm({ props })

const chainState = ref({})

const supplyCostDimensions = RESALE_PRICE_DIMENSION_SPECS.map((item) => ({
  key: item.key,
  label: item.label
}))

const {
  gridStyle: workbenchGridStyle,
  isResizingSidebar,
  startSidebarResize
} = useResizableSidebar({
  cssVariable: '--performance-sidebar-width',
  initialWidth: 380,
  maxWidth: 560,
  minWidth: 340
})

const currencyLabel = computed(() => String(props.displayCurrency || 'CNY'))
const currencySymbol = computed(() =>
  currencyLabel.value === 'USD' ? '$' : '¥'
)

const {
  baseModelSelectOptions,
  channelPriceItemsByKey,
  metaModelById,
  metaModelRows,
  metaVendorSelectOptions,
  modelById,
  platformCurrencyLabel,
  platformSelectOptions,
  pointUnitLabel,
  selectedMetaModel,
  selectedMetaModelProcurements,
  selectedPlatform,
  selectedPlatformAutoApproveLimit,
  selectedPlatformFeeRate,
  selectedPlatformLabel,
  selectedPlatformServiceFeeRate,
  supplierOptions,
  supplierSelectOptions,
  supportedSupplierIds,
  workflowAutoApproveEnabled
} = useResaleWorkspaceOptions({ form, props, t })

const {
  addMarketSample,
  autoApproveStatus,
  averageMarketSamples,
  basePriceFromRatio,
  convertCurrencyAmount,
  convertToDisplay,
  costFormulaText,
  costFormulaTitle,
  editablePriceInputText,
  formatCredit,
  formatEditablePrice,
  formatPercent,
  formatReadonlyNumber,
  isBelowReferencePrice,
  marginAxisRangeFor,
  marginFromListingPrices,
  marginFromRowPrices,
  marginPolicyTooltip,
  marketAverageText,
  marketMarginRefsFor,
  marketMarginReferenceText,
  normalizeDiscountRatio,
  normalizeMargin,
  priceDiffAmountText,
  priceDiffClass,
  priceDiffTitle,
  priceDiffText,
  priceDimensions,
  priceFromMargin,
  pricePatchForMargin,
  priceSpecForItemDimension,
  referencePriceTitle,
  rowHasBelowReferencePrice
} = useResalePricing({
  currencyLabel,
  currencySymbol,
  getMarketAvg: () => marketAvg.value,
  globalPricing,
  platformCurrencyLabel,
  props,
  selectedPlatformAutoApproveLimit,
  selectedPlatformFeeRate,
  selectedPlatformLabel,
  selectedPlatformServiceFeeRate,
  t,
  workflowAutoApproveEnabled
})

watch(
  () => props.displayCurrency,
  (next, previous) => {
    migrateChainStateCurrency(previous, next)
  }
)

watch(
  () => supplierOptions.value.map((item) => item.id).join(','),
  () => {
    if (
      form.value.supplierId &&
      !supportedSupplierIds.value.has(String(form.value.supplierId))
    ) {
      form.value.supplierId = ''
      emitChange()
    }
  }
)

const { chainRows, channelPriceValue, groupedChainRows, selectedChainRows } =
  useResaleChainRows({
    basePriceFromRatio,
    channelPriceItemsByKey,
    convertToDisplay,
    editablePriceInputText,
    form,
    getChainState,
    modelById,
    normalizeDiscountRatio,
    normalizeMargin,
    priceFromMargin,
    selectedMetaModel,
    selectedMetaModelProcurements,
    supportedSupplierIds,
    t
  })

const { barWidth, perfCompareRows, perfMetrics } = useResalePerformance({
  selectedChainRows,
  t
})

const workspaceHasChanges = computed(() =>
  selectedChainRows.value.some((row) => listingRowHasChanges(row))
)

watch(
  [
    () => props.initialModelId,
    () => metaModelRows.value.length,
    () => props.models.length,
    () => props.listings.length
  ],
  () => {
    // ponytail: defer until v-model binds and computed deps are ready
    nextTick(() => hydrateInitialModel())
  },
  { immediate: true }
)

function syncSelectedChain() {
  const nextState = { ...chainState.value }
  selectedChainRows.value.forEach((row) => {
    const state = { ...(nextState[row.uniqueId] || {}) }
    const margin = normalizeMargin(state.margin ?? row.margin)
    state.margin = margin
    state.currency = currencyLabel.value.toUpperCase()
    if (state.priceInRaw === null || state.priceInRaw === undefined) {
      state.priceInRaw = priceFromMargin(row.costInRaw, margin)
    }
    if (state.priceOutRaw === null || state.priceOutRaw === undefined) {
      state.priceOutRaw = priceFromMargin(row.costOutRaw, margin)
    }
    if (state.priceCacheInRaw === null || state.priceCacheInRaw === undefined) {
      state.priceCacheInRaw = priceFromMargin(row.costCacheInRaw, margin)
    }
    nextState[row.uniqueId] = state
  })
  chainState.value = nextState
  emitChange()
}

function getChainState(uniqueId) {
  return chainState.value[uniqueId] || {}
}

function updateChainState(row, patch) {
  chainState.value = {
    ...chainState.value,
    [row.uniqueId]: {
      ...getChainState(row.uniqueId),
      currency: currencyLabel.value.toUpperCase(),
      ...patch
    }
  }
}

function migrateChainStateCurrency(previousCurrency, nextCurrency) {
  const source = String(previousCurrency || '').toUpperCase()
  const target = String(nextCurrency || '').toUpperCase()
  if (!source || !target || source === target) return
  const nextState = {}
  const priceFields = ['priceInRaw', 'priceOutRaw', 'priceCacheInRaw']
  Object.entries(chainState.value).forEach(([key, state]) => {
    const stateCurrency = String(state.currency || source).toUpperCase()
    const migrated = { ...state, currency: target }
    priceFields.forEach((field) => {
      const converted = convertCurrencyAmount(
        state[field],
        stateCurrency,
        target
      )
      if (converted !== null) {
        migrated[field] = formatEditablePrice(converted)
      }
    })
    nextState[key] = migrated
  })
  chainState.value = nextState
  emitChange()
}

function handleChainSelection(row, event) {
  const selected = Boolean(event?.target?.checked)
  updateChainState(row, { selected })
  syncSelectedChain()
}

function hydrateInitialModel() {
  const initialModelId = props.initialModelId
  if (!initialModelId) return
  if (!props.models.length || !metaModelRows.value.length) return
  const skuModel = modelById.value.get(String(initialModelId))
  const metaModelId = skuModel?.meta_model || initialModelId
  const metaModel = metaModelById.value.get(String(metaModelId))
  form.value.metaVendorId = metaModel?.owner_key
    ? String(metaModel.owner_key)
    : skuModel?.provider
      ? String(skuModel.provider)
      : ''
  form.value.modelId = String(metaModelId)
  form.value.supplierId = ''
  isSupplyChainExpanded.value = true
  hydrateInitialListings(initialModelId)
}

function hydrateInitialListings(initialModelId) {
  const platformId = String(selectedPlatform.value?.id || '')
  const nextState = { ...chainState.value }
  chainRows.value
    .filter((row) => String(row.modelId) === String(initialModelId))
    .forEach((row) => {
      const listing = (props.listings || []).find(
        (item) =>
          String(item.model) === String(initialModelId) &&
          String(item.channel) === String(row.channelId) &&
          (!platformId || String(item.platform) === platformId)
      )
      if (!listing) return
      const priceIn = convertToDisplay(
        listing.retail_input_price_per_million,
        listing.currency
      )
      const priceOut = convertToDisplay(
        listing.retail_output_price_per_million,
        listing.currency
      )
      const priceCacheIn = convertToDisplay(
        listing.retail_cache_input_price_per_million,
        listing.currency
      )
      nextState[row.uniqueId] = {
        ...nextState[row.uniqueId],
        selected: true,
        currency: currencyLabel.value.toUpperCase(),
        priceInRaw:
          priceIn !== null && priceIn !== undefined
            ? formatEditablePrice(priceIn)
            : row.priceInRaw,
        priceOutRaw:
          priceOut !== null && priceOut !== undefined
            ? formatEditablePrice(priceOut)
            : row.priceOutRaw,
        priceCacheInRaw:
          priceCacheIn !== null && priceCacheIn !== undefined
            ? formatEditablePrice(priceCacheIn)
            : row.priceCacheInRaw,
        margin: marginFromListingPrices(row, priceIn, priceOut, priceCacheIn)
      }
    })
  chainState.value = nextState
  syncSelectedChain()
}

function onMarginInput(row, event) {
  const rawValue = event?.target?.value
  if (rawValue === '') {
    return
  }
  const value = Number(rawValue)
  const margin = Number.isFinite(value) ? value : 0
  const patch = pricePatchForMargin(row, margin, {
    clampToReference: false
  })
  updateChainState(row, patch)
}

function onMarginCommit(row, event) {
  const value = Number(event?.target?.value)
  const margin = Number.isFinite(value) ? value : row.margin
  const patch = pricePatchForMargin(row, margin)
  updateChainState(row, patch)
  if (event?.target) event.target.value = patch.margin
  emitChange()
}

function onPriceInput(row, key, event) {
  const rawValue = event?.target?.value ?? ''
  const patch = pricePatchForDimension(key, rawValue)
  if (rawValue === '') {
    updateChainState(row, patch)
    emitChange()
    return
  }
  const rawPrice = Number(rawValue)
  if (!Number.isFinite(rawPrice) || rawPrice < 0) return
  patch.margin = normalizeMargin(marginFromRowPrices(row, patch) ?? row.margin)
  updateChainState(row, patch)
  emitChange()
}

function onPriceCommit(row, key, event) {
  const rawValue = event?.target?.value ?? ''
  if (rawValue === '') return
  const rawPrice = Number(rawValue)
  if (!Number.isFinite(rawPrice) || rawPrice < 0) return
  const price = applyPriceChange(row, key, rawPrice)
  if (
    event?.target &&
    Number.isFinite(price) &&
    Number.isFinite(rawPrice) &&
    price !== rawPrice
  ) {
    event.target.value = price
  }
}

function pricePatchForDimension(key, value) {
  const patch = {}
  if (key === 'input') {
    patch.priceInRaw = value
  } else if (key === 'cache') {
    patch.priceCacheInRaw = value
  } else {
    patch.priceOutRaw = value
  }
  return patch
}

function applyPriceChange(row, key, rawPrice) {
  const dimension = priceDimensions(row).find((item) => item.key === key)
  const cost = dimension?.costRaw ?? 0
  const inputPrice = Number.isFinite(rawPrice) ? rawPrice : 0
  const formattedPrice = formatEditablePrice(inputPrice)
  const margin =
    Number(cost) > 0
      ? ((Number(formattedPrice) - Number(cost)) / Number(cost)) * 100
      : row.margin
  const patch = {}
  if (key === 'input') {
    patch.priceInRaw = formattedPrice
  } else if (key === 'cache') {
    patch.priceCacheInRaw = formattedPrice
  } else {
    patch.priceOutRaw = formattedPrice
  }
  patch.margin = normalizeMargin(
    marginFromRowPrices(row, patch) ?? margin ?? row.margin
  )
  updateChainState(row, patch)
  emitChange()
  return formattedPrice
}

const { marketAvg } = useResaleMarketAverages({
  addMarketSample,
  averageMarketSamples,
  channelPriceValue,
  form,
  modelById,
  priceSpecForItemDimension,
  props,
  selectedMetaModelProcurements
})

function onMarginAxisChange(row, rawMargin) {
  const nextMargin = normalizeMargin(rawMargin)
  updateChainState(row, pricePatchForMargin(row, nextMargin))
  emitChange()
}

function comparablePrice(value, options = {}) {
  if (value === null || value === undefined || value === '') {
    return options.emptyAsZero ? 0 : null
  }
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return options.emptyAsZero ? 0 : null
  const normalized = Math.abs(parsed) < 0.00005 ? 0 : parsed
  return Number(normalized.toFixed(2))
}

function listingForRow(row) {
  const platformId = String(selectedPlatform.value?.id || '')
  return (props.listings || []).find(
    (item) =>
      String(item.model) === String(row.modelId) &&
      String(item.channel) === String(row.channelId) &&
      (!platformId || String(item.platform) === platformId)
  )
}

function baselineForRow(row) {
  const listing = listingForRow(row)
  if (!listing) return null
  return {
    priceIn: comparablePrice(
      convertToDisplay(listing.retail_input_price_per_million, listing.currency)
    ),
    priceOut: comparablePrice(
      convertToDisplay(
        listing.retail_output_price_per_million,
        listing.currency
      )
    ),
    priceCacheIn: comparablePrice(
      convertToDisplay(
        listing.retail_cache_input_price_per_million,
        listing.currency
      ),
      { emptyAsZero: true }
    )
  }
}

function listingRowHasChanges(row) {
  const baseline = baselineForRow(row)
  if (!baseline) return true
  return (
    comparablePrice(row.priceInRaw) !== baseline.priceIn ||
    comparablePrice(row.priceOutRaw) !== baseline.priceOut ||
    comparablePrice(row.priceCacheInRaw, { emptyAsZero: true }) !==
      baseline.priceCacheIn
  )
}

function workspacePayload() {
  return {
    platformId: form.value.platformId,
    metaVendorId: form.value.metaVendorId,
    metaModelId: form.value.modelId,
    modelId: form.value.modelId,
    supplierId: form.value.supplierId,
    hasChanges: workspaceHasChanges.value,
    listings: selectedChainRows.value.map((row) => ({
      channelId: row.channelId,
      metaModelId: row.metaModelId,
      modelId: row.modelId,
      currency: currencyLabel.value.toUpperCase(),
      priceIn: row.priceInRaw,
      priceOut: row.priceOutRaw,
      priceCacheIn: row.priceCacheInRaw,
      margin: row.margin,
      priceBelowReference: rowHasBelowReferencePrice(row),
      hasChanges: listingRowHasChanges(row)
    }))
  }
}

function emitChange() {
  emit('change', workspacePayload())
}

defineExpose({
  reset() {
    form.value = {
      platformId: '',
      metaVendorId: '',
      modelId: '',
      supplierId: ''
    }
    chainState.value = {}
  },
  getPayload() {
    return workspacePayload()
  }
})
</script>
