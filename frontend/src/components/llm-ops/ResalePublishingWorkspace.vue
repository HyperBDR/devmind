<!--
  ResalePublishingWorkspace — immersive resale publishing workspace
  re-implements demo.html "model publishing workspace" using the
  existing llm-ops procurement rows as the chain-of-supply source.
-->
<template>
  <div class="workspace-shell">
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
          <div>{{ t('llmOps.publishingWorkspace.pricing.cost') }}</div>
          <div>{{ t('llmOps.publishingWorkspace.pricing.price') }}</div>
          <div>
            {{
              t('llmOps.publishingWorkspace.pricing.finalPoint', {
                point: pointUnitLabel
              })
            }}
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

              <div class="supply-metric-column">
                <div
                  v-for="dim in priceDimensions(row)"
                  :key="`cost-${row.uniqueId}-${dim.key}`"
                  class="supply-metric-row"
                >
                  <span class="supply-metric-label">
                    {{ dim.shortLabel }}
                  </span>
                  <span class="supply-metric-value text-slate-900">
                    {{ dim.costText }}
                  </span>
                </div>
              </div>

              <div class="supply-metric-column">
                <span class="text-slate-500 lg:hidden">
                  {{ t('llmOps.publishingWorkspace.pricing.price') }}
                </span>
                <template v-if="row.selected">
                  <div
                    v-for="dim in priceDimensions(row)"
                    :key="`price-${row.uniqueId}-${dim.key}`"
                    class="supply-metric-row"
                  >
                    <span class="supply-metric-label">
                      {{ dim.shortLabel }}
                    </span>
                    <span class="supply-metric-value text-emerald-600">
                      {{ dim.priceText || '-' }}
                    </span>
                  </div>
                </template>
                <span v-else class="supply-metric-empty">-</span>
              </div>

              <div class="supply-metric-column">
                <span class="text-slate-500 lg:hidden">
                  {{ pointUnitLabel }}
                </span>
                <template v-if="row.selected">
                  <div
                    v-for="dim in priceDimensions(row)"
                    :key="`credit-${row.uniqueId}-${dim.key}`"
                    class="supply-metric-row"
                  >
                    <span class="supply-metric-label">
                      {{ dim.shortLabel }}
                    </span>
                    <span class="supply-metric-value text-agione-600">
                      {{ formatCredit(dim.priceRaw) }}
                    </span>
                  </div>
                </template>
                <span v-else class="supply-metric-empty">-</span>
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
                    <div class="terminal-price-control">
                      <span>{{ currencySymbol }}</span>
                      <input
                        :value="dimension.priceText"
                        type="number"
                        step="0.01"
                        min="0"
                        @input="onPriceInput(row, dimension.key, $event)"
                      />
                    </div>
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
                :lower-tooltip="marginPolicyTooltip('min')"
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
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import BulletChart from '@/components/llm-ops/BulletChart.vue'
import CompactSelect from '@/components/llm-ops/CompactSelect.vue'
import {
  averageMarginRate,
  isMarginAutoApprovable,
  referenceRetailPrice,
  RESALE_PRICE_DIMENSION_SPECS
} from '@/utils/resalePricing'
import { resolveCanonicalMetaOwner } from '@/utils/llmOpsMeta'

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

const form = ref({
  platformId: '',
  metaVendorId: '',
  modelId: '',
  supplierId: ''
})

const globalPricing = ref({
  exchangeRate: 7.23,
  creditRatio: 10
})

const isSupplyChainExpanded = ref(true)
const chainState = ref({})
const sidebarWidth = ref(380)
const isResizingSidebar = ref(false)
const resizeStartX = ref(0)
const resizeStartWidth = ref(0)

const MIN_SIDEBAR_WIDTH = 340
const MAX_SIDEBAR_WIDTH = 560

const workbenchGridStyle = computed(() => ({
  '--performance-sidebar-width': `${sidebarWidth.value}px`
}))

function clampSidebarWidth(width) {
  return Math.min(
    MAX_SIDEBAR_WIDTH,
    Math.max(MIN_SIDEBAR_WIDTH, Math.round(width))
  )
}

function stopSidebarResize() {
  if (!isResizingSidebar.value) return
  isResizingSidebar.value = false
  document.removeEventListener('pointermove', handleSidebarResize)
  document.removeEventListener('pointerup', stopSidebarResize)
}

function handleSidebarResize(event) {
  if (!isResizingSidebar.value) return
  const delta = event.clientX - resizeStartX.value
  sidebarWidth.value = clampSidebarWidth(resizeStartWidth.value + delta)
}

function startSidebarResize(event) {
  if (!event?.isPrimary) return
  event.preventDefault()
  isResizingSidebar.value = true
  resizeStartX.value = event.clientX
  resizeStartWidth.value = sidebarWidth.value
  document.addEventListener('pointermove', handleSidebarResize)
  document.addEventListener('pointerup', stopSidebarResize)
}

onBeforeUnmount(() => {
  stopSidebarResize()
})

const metaModelRows = computed(() =>
  (props.metaModels || []).map((item) => {
    const vendor = resolveCanonicalMetaOwner(item, props.providers)
    return {
      ...item,
      owner_key: item.owner_code || vendor.code,
      owner_code: item.owner_code || vendor.code,
      owner_name: item.owner_name || vendor.name
    }
  })
)

const metaModelById = computed(() => {
  const map = new Map()
  metaModelRows.value.forEach((item) => {
    map.set(String(item.id), item)
  })
  return map
})

const modelById = computed(() => {
  const map = new Map()
  ;(props.models || []).forEach((model) => {
    map.set(String(model.id), model)
  })
  return map
})

const channelPriceItemsByKey = computed(() => {
  const map = new Map()
  ;(props.channelPriceItems || []).forEach((item) => {
    if (!item?.channel || !item?.model || !item?.dimension) return
    const key = channelPriceItemKey(item.channel, item.model, item.dimension)
    map.set(key, item)
  })
  return map
})

const procurementByMetaModel = computed(() => {
  const map = new Map()
  ;(props.procurementRows || []).forEach((row) => {
    const model = modelById.value.get(String(row.model_id))
    const metaModelId = model?.meta_model
    if (!metaModelId) return
    const key = String(metaModelId)
    if (!map.has(key)) {
      map.set(key, [])
    }
    map.get(key).push(row)
  })
  return map
})

const selectedMetaModel = computed(() => {
  if (!form.value.modelId) return null
  return metaModelById.value.get(String(form.value.modelId)) || null
})

const selectedMetaModelProcurements = computed(() => {
  if (!form.value.modelId) return []
  return procurementByMetaModel.value.get(String(form.value.modelId)) || []
})

const platformSelectOptions = computed(() =>
  (props.platforms || []).map((item) => ({
    value: String(item.id),
    label:
      item.name ||
      item.code ||
      t('llmOps.publishingWorkspace.fallback.platform', { id: item.id })
  }))
)

const metaVendorOptions = computed(() => {
  const map = new Map()
  metaModelRows.value.forEach((model) => {
    const id = model.owner_key
    if (!id) return
    const key = String(id)
    if (map.has(key)) return
    map.set(key, {
      id,
      name:
        model.owner_name ||
        t('llmOps.publishingWorkspace.fallback.uncategorized'),
      code: model.owner_code || ''
    })
  })
  return Array.from(map.values()).sort((left, right) =>
    String(left.name).localeCompare(String(right.name))
  )
})

const metaVendorSelectOptions = computed(() => [
  { value: '', label: t('llmOps.publishingWorkspace.filters.all') },
  ...metaVendorOptions.value.map((item) => ({
    value: String(item.id),
    label: item.name,
    description: item.code || ''
  }))
])

const baseModelOptions = computed(() => {
  const metaVendorId = form.value.metaVendorId
  return metaModelRows.value
    .filter((item) => {
      if (!metaVendorId) return true
      return String(item.owner_key) === String(metaVendorId)
    })
    .map((item) => ({
      id: item.id,
      name: item.name || item.code,
      code: item.code,
      family: item.family,
      vendorName: item.owner_name
    }))
    .sort((left, right) => String(left.name).localeCompare(String(right.name)))
})

const baseModelSelectOptions = computed(() => [
  {
    value: '',
    label: t('llmOps.publishingWorkspace.filters.selectMetaModel')
  },
  ...baseModelOptions.value.map((item) => ({
    value: String(item.id),
    label: item.name,
    description: [item.vendorName, item.family, item.code]
      .filter(Boolean)
      .join(' · '),
    searchText: [item.name, item.vendorName, item.family, item.code]
      .filter(Boolean)
      .join(' ')
  }))
])

const supplierOptions = computed(() => {
  if (!form.value.modelId) return []
  const seen = new Map()
  selectedMetaModelProcurements.value.forEach((row) => {
    ;(row.options || []).forEach((opt) => {
      if (!opt?.channel_id || !opt?.channel_name) return
      const id = String(opt.channel_id)
      if (seen.has(id)) return
      seen.set(id, { id, name: opt.channel_name })
    })
  })
  return Array.from(seen.values()).sort((a, b) =>
    String(a.name).localeCompare(String(b.name))
  )
})

const supplierSelectOptions = computed(() => {
  if (!form.value.modelId) {
    return [
      {
        value: '',
        label: t('llmOps.publishingWorkspace.filters.selectMetaModelFirst'),
        disabled: true
      }
    ]
  }
  return [
    {
      value: '',
      label: t('llmOps.publishingWorkspace.filters.allSupportedChannels')
    },
    ...supplierOptions.value.map((item) => ({
      value: String(item.id),
      label: item.name
    }))
  ]
})

const supportedSupplierIds = computed(
  () => new Set(supplierOptions.value.map((item) => String(item.id)))
)

const pointUnitLabel = computed(
  () =>
    props.pointConversion?.point_name ||
    t('llmOps.publishingWorkspace.fallback.points')
)

const selectedPlatform = computed(() => {
  const id = String(form.value.platformId || '')
  return (
    (props.platforms || []).find((item) => String(item.id) === id) ||
    props.agionePlatform ||
    null
  )
})

const selectedPlatformLabel = computed(
  () =>
    selectedPlatform.value?.name ||
    t('llmOps.publishingWorkspace.fallback.currentPlatform')
)

const platformCurrencyLabel = computed(() =>
  String(
    selectedPlatform.value?.currency || props.displayCurrency || 'CNY'
  ).toUpperCase()
)

const currencyLabel = computed(() => String(props.displayCurrency || 'CNY'))
const currencySymbol = computed(() =>
  currencyLabel.value === 'USD' ? '$' : '¥'
)

const selectedPlatformFeeRate = computed(() => {
  const value = Number(selectedPlatform.value?.fee_rate)
  return Number.isFinite(value) ? value : 0
})

const selectedPlatformServiceFeeRate = computed(() => {
  const value = Number(selectedPlatform.value?.service_fee_rate)
  return Number.isFinite(value) ? value : 0
})

const selectedPlatformAutoApproveLimit = computed(() => {
  if (!workflowAutoApproveEnabled.value) return null
  const runtimeValue = Number(
    props.workflowConfig?.runtime?.auto_approve_max_margin_rate
  )
  if (Number.isFinite(runtimeValue)) return runtimeValue
  const value = Number(selectedPlatform.value?.auto_approve_max_margin_rate)
  return Number.isFinite(value) ? value : null
})

const workflowAutoApproveEnabled = computed(() => {
  const value = props.workflowConfig?.policies?.auto_approve_enabled
  return value !== false
})

watch(
  () => props.agionePlatform,
  (next) => {
    if (next?.id) {
      form.value.platformId = String(next.id)
    }
  },
  { immediate: true }
)

watch(
  () => props.platforms,
  (list) => {
    if (!form.value.platformId && list?.length) {
      form.value.platformId = String(list[0].id)
    }
  },
  { immediate: true }
)

watch(
  () => props.pointConversion,
  (next) => {
    if (next?.points_per_currency_unit) {
      globalPricing.value.creditRatio = Number(next.points_per_currency_unit)
    }
  },
  { immediate: true }
)

watch(
  () => props.exchangeRate,
  (next) => {
    if (Number.isFinite(next)) {
      globalPricing.value.exchangeRate = next
    }
  },
  { immediate: true }
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

function onMetaVendorChange() {
  // Cascading reset: changing meta vendor invalidates the meta
  // model and the supplier selection.
  form.value.modelId = ''
  form.value.supplierId = ''
  isSupplyChainExpanded.value = true
}

function onModelChange() {
  // Reset supplier selection when the meta model changes.
  form.value.supplierId = ''
  isSupplyChainExpanded.value = true
}

function convertToDisplay(amount, currency) {
  if (amount === null || amount === undefined) return null
  const source = String(currency || 'USD').toUpperCase()
  const target = currencyLabel.value.toUpperCase()
  const num = Number(amount)
  if (!Number.isFinite(num)) return null
  if (source === target) return num
  const rate = Number(globalPricing.value.exchangeRate || 7.23)
  if (source === 'USD' && target === 'CNY') return num * rate
  if (source === 'CNY' && target === 'USD') return num / rate
  return null
}

function channelPriceItemKey(channelId, modelId, dimension) {
  return [channelId, modelId, dimension].map(String).join(':')
}

function channelPriceValue(option, modelId, dimension, fallbackValue) {
  const item = channelPriceItemsByKey.value.get(
    channelPriceItemKey(option.channel_id, modelId, dimension)
  )
  if (item && item.unit_price !== null && item.unit_price !== undefined) {
    return {
      value: item.unit_price,
      currency: item.currency || option.currency,
      ratio: item.settlement_ratio ?? option.settlement_ratio
    }
  }
  return {
    value: fallbackValue,
    currency: option.currency,
    ratio: option.settlement_ratio
  }
}

function normalizeDiscountRatio(value) {
  const ratio = Number(value)
  if (!Number.isFinite(ratio) || ratio <= 0) return 1
  return ratio
}

function basePriceFromRatio(price, ratio) {
  const priceValue = Number(price)
  const ratioValue = normalizeDiscountRatio(ratio)
  if (!Number.isFinite(priceValue)) return null
  return priceValue / ratioValue
}

const chainRows = computed(() => {
  if (!form.value.modelId) return []
  const metaModel = selectedMetaModel.value
  if (!metaModel) return []
  const supplierFilter = form.value.supplierId
  const metaVendor = {
    id: metaModel.owner_key,
    code: metaModel.owner_code,
    name: metaModel.owner_name
  }
  return selectedMetaModelProcurements.value
    .flatMap((procurement) => {
      const skuModel = modelById.value.get(String(procurement.model_id))
      return (procurement.options || [])
        .filter((option) => {
          if (!supportedSupplierIds.value.has(String(option.channel_id))) {
            return false
          }
          if (!supplierFilter) return true
          return String(option.channel_id) === String(supplierFilter)
        })
        .map((option) => ({ procurement, skuModel, option }))
    })
    .map(({ procurement, skuModel, option }) => {
      const inputCost = channelPriceValue(
        option,
        procurement.model_id,
        'text_input',
        option.input_price_per_million
      )
      const outputCost = channelPriceValue(
        option,
        procurement.model_id,
        'text_output',
        option.output_price_per_million
      )
      const cacheInputCost = channelPriceValue(
        option,
        procurement.model_id,
        'cache_input',
        option.cache_input_price_per_million
      )
      const inDisplay = convertToDisplay(inputCost.value, inputCost.currency)
      const outDisplay = convertToDisplay(outputCost.value, outputCost.currency)
      const cacheInDisplay = convertToDisplay(
        cacheInputCost.value,
        cacheInputCost.currency
      )
      const baseInDisplay = convertToDisplay(
        option.base_input_price_per_million ??
          basePriceFromRatio(
            inputCost.value,
            option.input_price_per_million_settlement_ratio ?? inputCost.ratio
          ),
        inputCost.currency
      )
      const baseOutDisplay = convertToDisplay(
        option.base_output_price_per_million ??
          basePriceFromRatio(
            outputCost.value,
            option.output_price_per_million_settlement_ratio ?? outputCost.ratio
          ),
        outputCost.currency
      )
      const baseCacheInDisplay = convertToDisplay(
        option.base_cache_input_price_per_million ??
          basePriceFromRatio(
            cacheInputCost.value,
            option.cache_input_price_per_million_settlement_ratio ??
              cacheInputCost.ratio
          ),
        cacheInputCost.currency
      )
      const discountIn = normalizeDiscountRatio(
        option.input_price_per_million_settlement_ratio ?? inputCost.ratio
      )
      const discountOut = normalizeDiscountRatio(
        option.output_price_per_million_settlement_ratio ?? outputCost.ratio
      )
      const discountCacheIn = normalizeDiscountRatio(
        option.cache_input_price_per_million_settlement_ratio ??
          cacheInputCost.ratio
      )
      const uniqueId = `${option.channel_id}-${procurement.model_id}`
      const state = getChainState(uniqueId)
      return {
        uniqueId,
        channelId: option.channel_id,
        channelName: option.channel_name,
        // Supplier = the channel that publishes the price row.
        supplierName: option.channel_name,
        source: option.channel_name,
        // Meta vendor = the company that develops the model.
        metaVendorId: metaVendor.id,
        metaVendorName: metaVendor.name || metaVendor.code,
        metaVendorCode: metaVendor.code,
        provider:
          metaVendor.name ||
          t('llmOps.publishingWorkspace.fallback.uncategorized'),
        modelId: procurement.model_id,
        skuModelName:
          skuModel?.name || procurement.model_name || procurement.model_code,
        modelName: metaModel.name || metaModel.code,
        metaModelId: metaModel.id,
        metaModelCode: metaModel.code,
        metaModelFamily: metaModel.family,
        costInRaw: inDisplay ?? 0,
        costOutRaw: outDisplay ?? 0,
        costCacheInRaw: cacheInDisplay ?? 0,
        baseCostInRaw: baseInDisplay ?? inDisplay ?? 0,
        baseCostOutRaw: baseOutDisplay ?? outDisplay ?? 0,
        baseCostCacheInRaw: baseCacheInDisplay ?? cacheInDisplay ?? 0,
        discountIn,
        discountOut,
        discountCacheIn,
        costIn: inDisplay !== null ? inDisplay.toFixed(4) : '-',
        costOut: outDisplay !== null ? outDisplay.toFixed(4) : '-',
        costCacheIn:
          cacheInDisplay !== null ? cacheInDisplay.toFixed(4) : '0.0000',
        hasCacheInput: cacheInDisplay !== null && cacheInDisplay > 0,
        tpmLimit: numberOrNull(option.tpm_limit),
        rpmLimit: numberOrNull(option.rpm_limit),
        latencyMs: numberOrNull(option.latency_ms),
        selected: Boolean(state.selected),
        margin: normalizeMargin(
          state.margin ??
            state.marginIn ??
            state.marginOut ??
            state.marginCacheIn ??
            20
        ),
        priceInRaw: state.priceInRaw ?? null,
        priceOutRaw: state.priceOutRaw ?? null,
        priceCacheInRaw: state.priceCacheInRaw ?? 0,
        priceIn:
          state.priceInRaw !== null && state.priceInRaw !== undefined
            ? Number(state.priceInRaw).toFixed(2)
            : '',
        priceOut:
          state.priceOutRaw !== null && state.priceOutRaw !== undefined
            ? Number(state.priceOutRaw).toFixed(2)
            : '',
        priceCacheIn: Number(state.priceCacheInRaw ?? 0).toFixed(2),
        isLowest: false
      }
    })
    .filter((row) => Number(row.costInRaw) > 0 && Number(row.costOutRaw) > 0)
    .sort((a, b) => Number(a.costInRaw) - Number(b.costInRaw))
    .map((row, idx) => ({ ...row, isLowest: idx === 0 }))
})

const selectedChainRows = computed(() =>
  chainRows.value.filter((r) => r.selected)
)

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

const groupedChainRows = computed(() => {
  const map = new Map()
  chainRows.value.forEach((row) => {
    // The top-level grouping reflects the actual supplier
    // (price-source / reseller channel), not the meta vendor.
    const supplierKey = row.supplierName || row.source
    if (!map.has(supplierKey)) {
      map.set(supplierKey, {
        supplierName: supplierKey,
        metaVendorName: row.metaVendorName,
        sources: new Map()
      })
    }
    const entry = map.get(supplierKey)
    if (!entry.sources.has(row.source)) {
      entry.sources.set(row.source, { source: row.source, models: [] })
    }
    entry.sources.get(row.source).models.push(row)
  })
  return Array.from(map.values()).map((g) => ({
    supplierName: g.supplierName,
    metaVendorName: g.metaVendorName,
    sources: Array.from(g.sources.values())
  }))
})

function syncSelectedChain() {
  const nextState = { ...chainState.value }
  selectedChainRows.value.forEach((row) => {
    const state = { ...(nextState[row.uniqueId] || {}) }
    const margin = normalizeMargin(state.margin ?? row.margin)
    state.margin = margin
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
      ...patch
    }
  }
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

function marginFromListingPrices(row, priceIn, priceOut, priceCacheIn) {
  const margin = averageMarginRate(
    [
      { price: priceIn, cost: row.costInRaw },
      { price: priceOut, cost: row.costOutRaw },
      { price: priceCacheIn, cost: row.costCacheInRaw }
    ].filter(Boolean)
  )
  return normalizeMargin(margin ?? 20)
}

function marginFromRowPrices(row, patch = {}) {
  return marginFromListingPrices(
    row,
    patch.priceInRaw ?? row.priceInRaw,
    patch.priceOutRaw ?? row.priceOutRaw,
    patch.priceCacheInRaw ?? row.priceCacheInRaw
  )
}

function normalizeMargin(value) {
  const margin = Number(value)
  if (!Number.isFinite(margin)) return 0
  return Number(margin.toFixed(1))
}

function referenceMarginFloor() {
  const feeRate = Number(selectedPlatformFeeRate.value)
  const serviceFeeRate = Number(selectedPlatformServiceFeeRate.value)
  const fee = Number.isFinite(feeRate) && feeRate > 0 ? feeRate : 0
  const service =
    Number.isFinite(serviceFeeRate) && serviceFeeRate > 0 ? serviceFeeRate : 0
  return normalizeMargin((fee + service) * 100)
}

function clampMarginToReference(value) {
  return Math.max(normalizeMargin(value), referenceMarginFloor())
}

function priceFromMargin(cost, margin) {
  const costValue = Number(cost) || 0
  const marginValue = Number(margin) || 0
  return formatEditablePrice(costValue * (1 + marginValue / 100))
}

function pricePatchForMargin(row, margin, options = {}) {
  const shouldClamp = options.clampToReference !== false
  const nextMargin = shouldClamp
    ? clampMarginToReference(margin)
    : normalizeMargin(margin)
  const patch = {
    margin: nextMargin,
    priceInRaw: priceFromMargin(row.costInRaw, nextMargin),
    priceOutRaw: priceFromMargin(row.costOutRaw, nextMargin)
  }
  patch.priceCacheInRaw = priceFromMargin(row.costCacheInRaw, nextMargin)
  return patch
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
  const rawPrice = Number(event?.target?.value)
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

function applyPriceChange(row, key, rawPrice) {
  const dimension = priceDimensions(row).find((item) => item.key === key)
  const cost = dimension?.costRaw ?? 0
  const referencePrice = Number(dimension?.referencePriceRaw)
  const inputPrice = Number.isFinite(rawPrice) ? rawPrice : 0
  const price =
    Number.isFinite(referencePrice) && referencePrice > 0
      ? Math.max(inputPrice, referencePrice)
      : inputPrice
  const formattedPrice = formatEditablePrice(price)
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

function formatCredit(price) {
  const amount = Number(price) || 0
  const rate = Number(globalPricing.value.creditRatio) || 0
  return formatRoundedPoints(amount * rate)
}

function formatRoundedPoints(value) {
  const points = Number(value)
  if (!Number.isFinite(points)) return '0'
  const mode = props.pointConversion?.rounding_mode || 'half_up'
  if (mode === 'up') return String(Math.ceil(points))
  if (mode === 'down') return String(Math.floor(points))
  return String(Math.round(points))
}

function formatReadonlyNumber(value, digits) {
  const num = Number(value)
  if (!Number.isFinite(num)) return '-'
  return num.toFixed(digits).replace(/\.?0+$/, '')
}

function formatMoneyAmount(value) {
  const num = Number(value)
  if (!Number.isFinite(num)) return '-'
  return `${currencySymbol.value}${num.toFixed(4)}`
}

function formatEditablePrice(value) {
  const amount = Number(value)
  if (!Number.isFinite(amount)) return 0
  return Number(amount.toFixed(2))
}

function formatMinimumPrice(value) {
  const amount = Number(value)
  if (!Number.isFinite(amount)) return 0
  return Number((Math.ceil(amount * 100) / 100).toFixed(2))
}

function formatDiscount(value) {
  const ratio = normalizeDiscountRatio(value)
  return `${(ratio * 100).toFixed(1).replace(/\.0$/, '')}%`
}

function formatPercent(value) {
  const num = Number(value)
  if (!Number.isFinite(num)) return '-'
  return `${num.toFixed(1).replace(/\.0$/, '')}%`
}

function formatRatioPercent(value) {
  const num = Number(value)
  if (!Number.isFinite(num)) return '-'
  return `${(num * 100).toFixed(2).replace(/\.?0+$/, '')}%`
}

function referencePriceForCost(cost) {
  return referenceRetailPrice(cost, {
    feeRate: selectedPlatformFeeRate.value,
    serviceFeeRate: selectedPlatformServiceFeeRate.value
  })
}

function referencePriceText(value) {
  const amount = Number(value)
  if (!Number.isFinite(amount)) return '-'
  return amount.toFixed(2)
}

function referencePriceTitle(dimension) {
  return t('llmOps.publishingWorkspace.pricing.referenceTitle', {
    serviceFee: formatRatioPercent(selectedPlatformServiceFeeRate.value),
    commission: formatRatioPercent(selectedPlatformFeeRate.value),
    reference:
      currencySymbol.value + referencePriceText(dimension.referencePriceRaw)
  })
}

function isBelowReferencePrice(price, referencePrice) {
  const priceValue = Number(price)
  const referenceValue = Number(referencePrice)
  if (!Number.isFinite(priceValue) || !Number.isFinite(referenceValue)) {
    return false
  }
  return priceValue + 0.000001 < referenceValue
}

function autoApproveStatus(margin) {
  if (!workflowAutoApproveEnabled.value) {
    return {
      ok: true,
      label: '免审路径已关闭'
    }
  }
  if (selectedPlatformAutoApproveLimit.value === null) {
    return {
      ok: true,
      label: t('llmOps.publishingWorkspace.margin.noAutoApprove')
    }
  }
  const isAllowed = isMarginAutoApprovable(
    margin,
    selectedPlatformAutoApproveLimit.value
  )
  if (isAllowed === null) {
    return {
      ok: true,
      label: t('llmOps.publishingWorkspace.margin.autoApproveInactive')
    }
  }
  if (isAllowed) {
    return {
      ok: true,
      label: t('llmOps.publishingWorkspace.margin.withinAutoApprove', {
        value: formatPercent(selectedPlatformAutoApproveLimit.value)
      })
    }
  }
  return {
    ok: false,
    label: t('llmOps.publishingWorkspace.margin.aboveAutoApprove', {
      value: formatPercent(selectedPlatformAutoApproveLimit.value)
    })
  }
}

function costFormulaParts(row, key) {
  if (key === 'cache') {
    return {
      baseCost: row.baseCostCacheInRaw,
      discount: row.discountCacheIn,
      cost: row.costCacheInRaw
    }
  }
  const isInput = key === 'input'
  return {
    baseCost: isInput ? row.baseCostInRaw : row.baseCostOutRaw,
    discount: isInput ? row.discountIn : row.discountOut,
    cost: isInput ? row.costInRaw : row.costOutRaw
  }
}

function costFormulaText(row, key) {
  const parts = costFormulaParts(row, key)
  return `${formatMoneyAmount(parts.baseCost)} × ${formatDiscount(
    parts.discount
  )} = ${formatMoneyAmount(parts.cost)}`
}

function costFormulaTitle(row, key) {
  return t('llmOps.publishingWorkspace.pricing.costFormulaTitle', {
    formula: costFormulaText(row, key)
  })
}

function marketAverageText(avg) {
  const value = Number(avg)
  if (!Number.isFinite(value) || value <= 0) return '-'
  return `${currencySymbol.value}${value.toFixed(2)}`
}

function priceDiffText(price, avg) {
  const p = Number(price)
  const a = Number(avg)
  if (!Number.isFinite(p) || !Number.isFinite(a) || a <= 0) {
    return t('llmOps.publishingWorkspace.pricing.noBenchmark')
  }
  const diff = p - a
  const pct = Math.abs((diff / a) * 100).toFixed(1)
  if (diff < -0.00001) {
    return t('llmOps.publishingWorkspace.pricing.lowerThanAverage', {
      pct
    })
  }
  if (diff > 0.00001) {
    return t('llmOps.publishingWorkspace.pricing.higherThanAverage', {
      pct
    })
  }
  return t('llmOps.publishingWorkspace.pricing.sameAsAverage')
}

function priceDiffAmountText(price, avg) {
  const p = Number(price)
  const a = Number(avg)
  if (!Number.isFinite(p) || !Number.isFinite(a) || a <= 0) return ''
  const diff = p - a
  const prefix = diff > 0 ? '+' : diff < 0 ? '-' : ''
  return `${prefix}${currencySymbol.value}${Math.abs(diff).toFixed(2)}`
}

function priceDiffClass(price, avg) {
  const p = Number(price)
  const a = Number(avg)
  if (!Number.isFinite(p) || !Number.isFinite(a) || a === 0)
    return 'text-slate-400'
  if (p < a) return 'text-emerald-600'
  if (p > a) return 'text-amber-600'
  return 'text-slate-500'
}

const selectedMetaModelPriceItems = computed(() => {
  const metaModelId = form.value.modelId
  if (!metaModelId) return []
  return (props.priceItems || []).filter((item) => {
    if (item.source_is_enabled === false) return false
    if (String(item.meta_model || '') === String(metaModelId)) return true
    const model = modelById.value.get(String(item.model || ''))
    return String(model?.meta_model || '') === String(metaModelId)
  })
})

const marketAvg = computed(() => {
  const samples = {
    in: [],
    out: [],
    cacheIn: []
  }
  selectedMetaModelPriceItems.value.forEach((item) => {
    const spec = priceSpecForItemDimension(item.dimension)
    if (!spec || item.is_current === false) return
    addMarketSample(samples[spec.marketKey], item.unit_price, item.currency)
  })
  RESALE_PRICE_DIMENSION_SPECS.forEach((spec) => {
    if (samples[spec.marketKey].length) return
    selectedMetaModelProcurements.value.forEach((procurement) => {
      ;(procurement.options || []).forEach((option) => {
        const price = channelPriceValue(
          option,
          procurement.model_id,
          spec.itemDimension,
          option[spec.costField]
        )
        addMarketSample(
          samples[spec.marketKey],
          price.value,
          price.currency || option.currency
        )
      })
    })
  })
  return {
    in: averageMarketSamples(samples.in),
    out: averageMarketSamples(samples.out),
    cacheIn: averageMarketSamples(samples.cacheIn)
  }
})

function priceSpecForItemDimension(dimension) {
  return RESALE_PRICE_DIMENSION_SPECS.find(
    (spec) => spec.itemDimension === dimension
  )
}

function addMarketSample(samples, value, currency) {
  const converted = convertToDisplay(value, currency)
  if (converted === null || converted <= 0) return
  samples.push(converted)
}

function averageMarketSamples(samples) {
  if (!samples.length) return 0
  const sum = samples.reduce((total, value) => total + value, 0)
  return Number((sum / samples.length).toFixed(4))
}

const priceMetricConfigs = Object.fromEntries(
  RESALE_PRICE_DIMENSION_SPECS.map((item) => [
    item.key,
    {
      label: item.label,
      shortLabel: item.shortLabel,
      priceField: item.workspacePriceField,
      priceTextField: item.workspacePriceTextField,
      costRawField: item.workspaceCostField,
      costTextField: item.workspaceCostTextField,
      marketKey: item.marketKey,
      itemDimension: item.itemDimension
    }
  ])
)

function priceDimensions(row) {
  return ['input', 'output', 'cache'].map((key) => {
    const config = priceMetricConfigs[key]
    const referencePrice = formatMinimumPrice(
      referencePriceForCost(row[config.costRawField])
    )
    return {
      key,
      label: config.label,
      shortLabel: config.shortLabel,
      priceRaw: row[config.priceField],
      priceText: row[config.priceTextField],
      costRaw: row[config.costRawField],
      costText: row[config.costTextField],
      marketAverage: marketAvg.value[config.marketKey] || 0,
      referencePriceRaw: referencePrice,
      referencePriceText: referencePriceText(referencePrice)
    }
  })
}

function marketMarginRefsFor(row) {
  const margins = priceDimensions(row)
    .map((dimension) => {
      const marketPrice = Number(dimension.marketAverage)
      const cost = Number(dimension.costRaw)
      if (
        !Number.isFinite(marketPrice) ||
        !Number.isFinite(cost) ||
        marketPrice <= 0 ||
        cost <= 0
      ) {
        return null
      }
      return ((marketPrice - cost) / cost) * 100
    })
    .filter((value) => value !== null)
  if (!margins.length) return []
  const average =
    margins.reduce((total, value) => total + value, 0) / margins.length
  return [
    {
      source: t('llmOps.publishingWorkspace.pricing.marketAverage'),
      price: Number(average.toFixed(2))
    }
  ]
}

function marginAxisRangeFor(row) {
  const current = Number(row.margin)
  const floor = referenceMarginFloor()
  const approveLimit = Number(selectedPlatformAutoApproveLimit.value)
  const limit =
    Number.isFinite(approveLimit) && approveLimit > floor
      ? approveLimit
      : Math.max(floor + 20, Number.isFinite(current) ? current : floor)
  return {
    min: floor,
    max: limit
  }
}

function onMarginAxisChange(row, rawMargin) {
  const nextMargin = normalizeMargin(rawMargin)
  updateChainState(row, pricePatchForMargin(row, nextMargin))
  emitChange()
}

function marginPolicyTooltip(type) {
  const isMin = type === 'min'
  const floor = referenceMarginFloor()
  const approveLimit = Number(selectedPlatformAutoApproveLimit.value)
  return {
    title: isMin
      ? t('llmOps.publishingWorkspace.margin.minTitle')
      : t('llmOps.publishingWorkspace.margin.autoApproveTitle'),
    source: isMin
      ? t('llmOps.publishingWorkspace.margin.minSource')
      : t('llmOps.publishingWorkspace.margin.autoApproveSource'),
    rows: isMin
      ? [
          {
            label: t('llmOps.publishingWorkspace.margin.platformFloor'),
            value: formatPercent(floor),
            source: t('llmOps.publishingWorkspace.margin.feeBreakdown', {
              serviceFee: formatRatioPercent(
                selectedPlatformServiceFeeRate.value
              ),
              commission: formatRatioPercent(selectedPlatformFeeRate.value)
            })
          }
        ]
      : [
          {
            label: t('llmOps.publishingWorkspace.margin.autoApproveLimit'),
            value: Number.isFinite(approveLimit)
              ? formatPercent(approveLimit)
              : t('llmOps.publishingWorkspace.fallback.notConfigured'),
            source: selectedPlatformLabel.value
          }
        ]
  }
}

const perfCompareRows = computed(() =>
  selectedChainRows.value.map((row) => ({
    id: row.uniqueId,
    name: performanceRowName(row),
    rpm: row.rpmLimit,
    tpm: row.tpmLimit,
    latency: row.latencyMs
  }))
)

function performanceRowName(row) {
  const channelName = row.channelName || row.supplierName || row.source
  const modelName = row.skuModelName || row.modelName
  if (!channelName) {
    return modelName || t('llmOps.publishingWorkspace.supply.chainFallback')
  }
  if (!modelName || modelName === row.modelName) return channelName
  return `${channelName} · ${modelName}`
}

const perfMetrics = computed(() => {
  const rpmMax = Math.max(1, ...perfCompareRows.value.map((r) => r.rpm))
  const tpmMax = Math.max(1, ...perfCompareRows.value.map((r) => r.tpm))
  const latMax = Math.max(1, ...perfCompareRows.value.map((r) => r.latency))
  return [
    {
      key: 'rpm',
      label: t('llmOps.publishingWorkspace.performance.rpm'),
      max: rpmMax,
      format: (v) => formatPerformanceValue(v, 'K', 1000),
      barClass: () => 'bg-violet-500'
    },
    {
      key: 'tpm',
      label: t('llmOps.publishingWorkspace.performance.tpm'),
      max: tpmMax,
      format: (v) => formatPerformanceValue(v, 'M', 1000000),
      barClass: () => 'bg-emerald-500'
    },
    {
      key: 'latency',
      label: t('llmOps.publishingWorkspace.performance.latency'),
      max: latMax,
      format: (v) => (Number.isFinite(v) ? `${v}ms` : '-'),
      barClass: () => 'bg-amber-500'
    }
  ]
})

function numberOrNull(value) {
  if (value === null || value === undefined || value === '') return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
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
      priceIn: row.priceInRaw,
      priceOut: row.priceOutRaw,
      priceCacheIn: row.priceCacheInRaw,
      margin: row.margin,
      hasChanges: listingRowHasChanges(row)
    }))
  }
}

function formatPerformanceValue(value, suffix, divisor) {
  if (!Number.isFinite(value)) return '-'
  if (!value) return '0'
  return `${(value / divisor).toFixed(1)}${suffix}`
}

function barWidth(value, max) {
  if (!Number.isFinite(value) || !Number.isFinite(max) || max <= 0) return '0%'
  return `${Math.max(2, (value / max) * 100)}%`
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

<style scoped>
/* === Base utility classes (hardcoded, Tailwind fallback) === */
.bg-white {
  background-color: #ffffff;
}
.bg-slate-50 {
  background-color: #f8fafc;
}
.bg-slate-100 {
  background-color: #f1f5f9;
}
.bg-slate-200 {
  background-color: #e2e8f0;
}
.bg-slate-950 {
  background-color: #020617;
}
.bg-transparent {
  background-color: transparent;
}
.bg-emerald-50 {
  background-color: #ecfdf5;
}
.bg-emerald-500 {
  background-color: #10b981;
}
.bg-amber-50 {
  background-color: #fffbeb;
}
.bg-amber-500 {
  background-color: #f59e0b;
}
.bg-rose-50 {
  background-color: #fff1f2;
}
.bg-rose-500 {
  background-color: #f43f5e;
}
.bg-violet-500 {
  background-color: #8b5cf6;
}
.bg-sky-500 {
  background-color: #0ea5e9;
}
.bg-indigo-50 {
  background-color: #eef2ff;
}
.bg-indigo-100 {
  background-color: #e0e7ff;
}
.bg-agione-50 {
  background-color: #ece9f9;
}
.bg-agione-100 {
  background-color: #d8d2f0;
}
.bg-agione-200 {
  background-color: #b3a8e2;
}
.bg-agione-300 {
  background-color: #8b7dd1;
}
.bg-agione-400 {
  background-color: #7a6ac4;
}
.bg-agione-500 {
  background-color: #6a5ac7;
}
.bg-agione-600 {
  background-color: #5f4ecf;
}
.bg-agione-700 {
  background-color: #4a3eb0;
}
.bg-agione-800 {
  background-color: #3d3399;
}
.bg-agione-900 {
  background-color: #312870;
}
.text-white {
  color: #ffffff;
}
.text-slate-500 {
  color: #64748b;
}
.text-slate-600 {
  color: #475569;
}
.text-slate-700 {
  color: #334155;
}
.text-slate-900 {
  color: #0f172a;
}
.text-emerald-600 {
  color: #059669;
}
.text-emerald-700 {
  color: #047857;
}
.text-amber-600 {
  color: #d97706;
}
.text-amber-700 {
  color: #b45309;
}
.text-rose-500 {
  color: #f43f5e;
}
.text-rose-600 {
  color: #e11d48;
}
.text-rose-700 {
  color: #be123c;
}
.text-agione-50 {
  color: #ece9f9;
}
.text-agione-100 {
  color: #d8d2f0;
}
.text-agione-300 {
  color: #8b7dd1;
}
.text-agione-500 {
  color: #6a5ac7;
}
.text-agione-600 {
  color: #5f4ecf;
}
.text-agione-700 {
  color: #4a3eb0;
}
.text-agione-800 {
  color: #3d3399;
}
.border-slate-200 {
  border-color: #e2e8f0;
}
.border-slate-300 {
  border-color: #cbd5e1;
}
.border-emerald-100 {
  border-color: #d1fae5;
}
.border-emerald-200 {
  border-color: #a7f3d0;
}
.border-amber-100 {
  border-color: #fef3c7;
}
.border-amber-200 {
  border-color: #fde68a;
}
.border-rose-100 {
  border-color: #ffe4e6;
}
.border-rose-200 {
  border-color: #fecdd3;
}
.border-agione-100 {
  border-color: #d8d2f0;
}
.border-agione-200 {
  border-color: #b3a8e2;
}
.border-agione-300 {
  border-color: #8b7dd1;
}
.border-agione-400 {
  border-color: #7a6ac4;
}
.border-agione-500 {
  border-color: #6a5ac7;
}
.focus\:border-agione-300:focus {
  border-color: #8b7dd1;
}
.focus\:border-agione-400:focus {
  border-color: #7a6ac4;
}
.focus\:ring-2:focus {
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.3);
}
.focus\:ring-4:focus {
  box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.3);
}
.focus\:ring-agione-100:focus {
  box-shadow: 0 0 0 2px #d8d2f0;
}
.focus\:ring-agione-200:focus {
  box-shadow: 0 0 0 2px #b3a8e2;
}
.hover\:bg-slate-50:hover {
  background-color: #f8fafc;
}
.hover\:bg-agione-600:hover {
  background-color: #5f4ecf;
}
.hover\:bg-agione-700:hover {
  background-color: #4a3eb0;
}
.hover\:border-slate-300:hover {
  border-color: #cbd5e1;
}
.hover\:text-agione-700:hover {
  color: #4a3eb0;
}
.hover\:text-slate-500:hover {
  color: #64748b;
}
.disabled\:cursor-not-allowed:disabled {
  cursor: not-allowed;
}
.disabled\:opacity-50:disabled {
  opacity: 0.5;
}
.disabled\:opacity-60:disabled {
  opacity: 0.6;
}
.text-xs {
  font-size: 0.75rem;
  line-height: 1rem;
}
.text-sm {
  font-size: 0.875rem;
  line-height: 1.25rem;
}
.text-base {
  font-size: 1rem;
  line-height: 1.5rem;
}
.text-lg {
  font-size: 1.125rem;
  line-height: 1.75rem;
}
.text-xl {
  font-size: 1.25rem;
  line-height: 1.75rem;
}
.text-2xl {
  font-size: 1.5rem;
  line-height: 2rem;
}
.text-3xl {
  font-size: 1.875rem;
  line-height: 2.25rem;
}
.text-4xl {
  font-size: 2.25rem;
  line-height: 2.5rem;
}
.text-\[10px\] {
  font-size: 10px;
}
.text-\[11px\] {
  font-size: 11px;
}
.text-\[12px\] {
  font-size: 12px;
}
.text-\[13px\] {
  font-size: 13px;
}
.text-\[14px\] {
  font-size: 14px;
}
.text-\[15px\] {
  font-size: 15px;
}
.text-\[18px\] {
  font-size: 18px;
}
.text-\[24px\] {
  font-size: 24px;
}
.top-0 {
  top: 0;
}
.z-10 {
  z-index: 10;
}
.z-20 {
  z-index: 20;
}
.z-50 {
  z-index: 50;
}
.max-w-\[20rem\] {
  max-width: 20rem;
}
.w-60 {
  width: 15rem;
}
.w-72 {
  width: 18rem;
}
.w-80 {
  width: 20rem;
}
.w-36 {
  width: 9rem;
}
.w-32 {
  width: 8rem;
}
.h-9 {
  height: 2.25rem;
}
.h-7 {
  height: 1.75rem;
}
.h-8 {
  height: 2rem;
}
.text-left {
  text-align: left;
}
.text-right {
  text-align: right;
}
.text-center {
  text-align: center;
}
.border {
  border-width: 1px;
}
.bg-indigo-50 {
  background-color: #eef2ff;
}
.bg-indigo-100 {
  background-color: #e0e7ff;
}
.bg-indigo-500 {
  background-color: #6366f1;
}
.bg-indigo-600 {
  background-color: #4f46e5;
}
.bg-indigo-700 {
  background-color: #4338ca;
}
.text-indigo-300 {
  color: #a5b4fc;
}
.text-indigo-500 {
  color: #6366f1;
}
.text-indigo-600 {
  color: #4f46e5;
}
.text-indigo-700 {
  color: #4338ca;
}
.border-indigo-200 {
  border-color: #c7d2fe;
}
.border-indigo-300 {
  border-color: #a5b4fc;
}
.border-indigo-400 {
  border-color: #818cf8;
}
.focus\:border-indigo-300:focus {
  border-color: #a5b4fc;
}
.focus\:ring-indigo-100:focus {
  box-shadow: 0 0 0 2px #e0e7ff;
}

.workspace-shell {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.workspace-section {
  border-radius: 12px;
  border-width: 1px;
  border-color: #e2e8f0;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
}

.workspace-toolbar {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
}

@media (min-width: 1280px) {
  .workspace-toolbar {
    grid-template-columns: minmax(720px, 1fr) max-content;
  }
}

.workspace-filter-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  align-items: end;
  gap: 0.625rem;
  min-width: 0;
}

@media (min-width: 768px) {
  .workspace-filter-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (min-width: 1280px) {
  .workspace-filter-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}

.filter-field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  min-width: 0;
}

.filter-field > span {
  color: #64748b;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0;
  line-height: 1.2;
  white-space: nowrap;
}

.workspace-select :deep(.compact-select-trigger) {
  min-height: 34px;
  border-radius: 8px;
  border-color: #dbe4f0;
  background-color: #ffffff;
  padding: 0.375rem 0.625rem;
  color: #334155;
  font-size: 13px;
  font-weight: 700;
  line-height: 1rem;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.8);
}

.workspace-select :deep(.compact-select-trigger:hover:not(:disabled)) {
  border-color: #cbd5e1;
  background-color: #f8fafc;
}

.workspace-select :deep(.compact-select-trigger:focus-visible) {
  border-color: #8b7dd1;
  box-shadow: 0 0 0 3px rgba(139, 125, 209, 0.16);
}

.workspace-select :deep(.compact-select-disabled) {
  border-color: #e2e8f0;
  background-color: #f8fafc;
  color: #94a3b8;
}

.workspace-select :deep(.compact-select-caret) {
  color: #64748b;
  font-size: 11px;
}

.workspace-select :deep(.compact-select-menu) {
  border-radius: 10px;
  padding: 0.375rem;
}

.workspace-select :deep(.compact-select-search) {
  min-height: 34px;
  border-radius: 8px;
  font-size: 13px;
}

.workspace-select :deep(.compact-select-option) {
  border-radius: 8px;
  padding: 0.5rem 0.625rem;
  font-size: 13px;
}

.field-select {
  width: 100%;
  min-width: 0;
  height: 34px;
  border-radius: 6px;
  border-width: 1px;
  border-color: #e2e8f0;
  background-color: #ffffff;
  padding-left: 0.5rem;
  padding-right: 0.5rem;
  font-size: 12px;
  font-weight: 500;
  line-height: 1.25rem;
  color: #334155;
  transition-property: color, background-color, border-color, box-shadow;
  transition-duration: 150ms;
}

.field-select:focus {
  border-color: #8b7dd1;
  outline: none;
  box-shadow: 0 0 0 2px #d8d2f055;
}

.field-select:disabled {
  cursor: not-allowed;
  background-color: #f8fafc;
  color: #94a3b8;
}

.pricing-context {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, max-content));
  gap: 0;
  align-self: end;
  justify-self: stretch;
  height: 34px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background-color: #ffffff;
  overflow: hidden;
}

@media (min-width: 1280px) {
  .pricing-context {
    justify-self: end;
  }
}

.pricing-segment {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  min-height: 32px;
  border-right: 1px solid #e2e8f0;
  padding: 0 0.625rem;
  white-space: nowrap;
}

.pricing-segment:last-child {
  border-right: 0;
}

.pricing-segment-label {
  color: #64748b;
  font-size: 11px;
  font-weight: 700;
}

.pricing-segment-value {
  color: #334155;
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono',
    'Courier New', monospace;
  font-size: 12px;
  font-weight: 700;
}

@media (max-width: 820px) {
  .pricing-context {
    grid-template-columns: 1fr;
    justify-self: stretch;
  }

  .pricing-segment {
    justify-content: space-between;
    border-right: 0;
    border-bottom: 1px solid #e2e8f0;
  }

  .pricing-segment:last-child {
    border-bottom: 0;
  }
}

.supply-grid {
  display: grid;
  grid-template-columns: minmax(260px, 1.1fr) repeat(3, minmax(150px, 0.75fr));
  column-gap: 0.75rem;
  align-items: center;
}

.supply-grid-header {
  display: none;
  border-bottom: 1px solid #e2e8f0;
  background-color: #f8fafc;
  padding: 0.625rem 1rem;
  color: #64748b;
  font-size: 11px;
  font-weight: 700;
  line-height: 1.2;
}

.supply-grid-row {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  transition-property: color, background-color, border-color, box-shadow;
  transition-duration: 150ms;
}

.supply-grid-row > * {
  min-width: 0;
  width: 100%;
}

.supply-grid-row:hover {
  background-color: #ece9f966;
}

.publishing-workbench-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 1rem;
  align-items: start;
}

.pricing-workbench-main {
  min-width: 0;
}

.pricing-matrix {
  display: grid;
  grid-template-columns:
    68px minmax(170px, 0.78fr) minmax(300px, 1.45fr)
    minmax(118px, 0.48fr);
  gap: 0.625rem;
  align-items: center;
}

.pricing-matrix-head {
  color: #64748b;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0;
  line-height: 1;
  text-align: left;
}

.pricing-matrix-label {
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
  line-height: 1.15;
}

.pricing-axis-block {
  padding: 2rem 0 4.25rem;
}

.compact-pricing-axis {
  position: relative;
  padding: 1.5rem 0 2.75rem;
}

.pricing-axis-block :deep(.range-bar-wrapper) {
  margin: 0;
}

.pricing-matrix-card {
  min-width: 0;
  min-height: 68px;
  border-radius: 6px;
  background-color: #f8fafc;
  padding: 0.5rem;
}

.unified-margin-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  border-bottom: 1px dashed #e2e8f0;
  padding-bottom: 1rem;
}

.unified-margin-input {
  display: flex;
  min-width: 9rem;
  align-items: center;
  overflow: hidden;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background-color: #ffffff;
}

.unified-margin-input:focus-within {
  border-color: #8b7dd1;
  box-shadow: 0 0 0 2px #d8d2f0;
}

.unified-margin-input input {
  width: 100%;
  border: 0;
  background: transparent;
  padding: 0.5rem;
  text-align: right;
  font-size: 13px;
  outline: none;
}

.unified-margin-input span {
  border-left: 1px solid #e2e8f0;
  padding: 0 0.625rem;
  color: #64748b;
  font-size: 12px;
}

.unified-margin-status {
  border-left: 1px solid #e2e8f0;
  padding-left: 0.5rem;
  font-size: 10px;
  font-weight: 700;
  line-height: 1.2;
}

.pricing-card-caption {
  margin-bottom: 0.25rem;
  color: #64748b;
  font-size: 10px;
  font-weight: 700;
  line-height: 1.1;
}

.final-credit-card {
  display: flex;
  flex-direction: column;
  justify-content: center;
  background-color: #ece9f9;
  text-align: center;
}

.terminal-price-card {
  display: grid;
  grid-template-columns: minmax(130px, 0.78fr) minmax(170px, 1.22fr);
  gap: 0.5rem;
}

.terminal-price-control {
  display: flex;
  align-items: center;
  overflow: hidden;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background-color: #ffffff;
}

.terminal-price-control:focus-within {
  border-color: #86efac;
  box-shadow: 0 0 0 2px #dcfce7;
}

.terminal-price-control span {
  border-right: 1px solid #e2e8f0;
  padding: 0 0.5rem;
  color: #94a3b8;
  font-size: 11px;
}

.terminal-price-control input {
  width: 100%;
  border: 0;
  background: transparent;
  padding: 0.375rem 0.5rem;
  text-align: right;
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono',
    'Courier New', monospace;
  font-size: 12px;
  outline: none;
}

.cost-formula-text {
  margin-top: 0.125rem;
  max-width: 100%;
  overflow: hidden;
  color: #64748b;
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono',
    'Courier New', monospace;
  font-size: 10px;
  font-weight: 600;
  line-height: 1.2;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.terminal-price-meta {
  display: grid;
  align-content: center;
  gap: 0.125rem;
  min-width: 0;
  color: #64748b;
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono',
    'Courier New', monospace;
  font-size: 10px;
  font-weight: 700;
  line-height: 1.2;
}

.terminal-price-meta p {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.terminal-price-meta strong {
  color: #334155;
}

@media (max-width: 720px) {
  .pricing-matrix {
    grid-template-columns: 1fr;
  }

  .pricing-matrix-head {
    display: none;
  }

  .terminal-price-card {
    grid-template-columns: 1fr;
  }
}

.performance-sidebar {
  display: flex;
  flex-direction: column;
  min-width: 0;
  position: relative;
}

.performance-sidebar-header {
  display: flex;
  min-height: 52px;
  align-items: center;
  gap: 0.5rem;
  background-color: #0f172a;
  padding: 0 1rem;
  color: #ffffff;
}

.performance-sidebar-header h3 {
  font-size: 13px;
  font-weight: 700;
  line-height: 1.2;
}

.performance-sidebar-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  flex: 0 0 auto;
  border-radius: 9999px;
  background-color: #34d399;
}

.performance-sidebar-body {
  display: flex;
  flex: 1;
  min-height: 0;
  flex-direction: column;
  gap: 0.75rem;
  overflow-y: auto;
  padding: 0.875rem;
}

.perf-metric-section {
  display: flex;
  flex: 1 1 0;
  min-height: 0;
  flex-direction: column;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background-color: #ffffff;
}

.perf-metric-title {
  border-bottom: 1px solid #e2e8f0;
  background-color: #f8fafc;
  padding: 0.5rem 0.625rem;
  color: #475569;
  font-size: 11px;
  font-weight: 700;
  line-height: 1.2;
}

.perf-metric-rows {
  display: flex;
  flex: 1;
  min-height: 0;
  flex-direction: column;
}

.perf-metric-row {
  display: grid;
  grid-template-columns: minmax(0, 96px) minmax(56px, 1fr) 52px;
  align-items: center;
  gap: 0.5rem;
  min-height: 34px;
  padding: 0.375rem 0.625rem;
  border-bottom: 1px solid #f1f5f9;
}

.perf-metric-row:last-child {
  border-bottom: 0;
}

.perf-metric-name {
  min-width: 0;
  overflow: hidden;
  color: #475569;
  font-size: 11px;
  font-weight: 500;
  line-height: 1.2;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.perf-metric-track {
  height: 7px;
  overflow: hidden;
  border-radius: 9999px;
  background-color: #f1f5f9;
}

.perf-metric-bar {
  height: 100%;
  border-radius: 9999px;
  transition: width 150ms ease;
}

.perf-metric-value {
  color: #334155;
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono',
    'Courier New', monospace;
  font-size: 11px;
  font-weight: 700;
  line-height: 1;
  text-align: right;
  white-space: nowrap;
}

.perf-empty {
  padding: 0.625rem;
  color: #94a3b8;
  font-size: 11px;
}

.performance-sidebar-resize {
  display: none;
}

@media (min-width: 1024px) {
  .publishing-workbench-grid {
    grid-template-columns: var(--performance-sidebar-width, 380px) minmax(
        0,
        1fr
      );
    align-items: stretch;
    min-height: 0;
  }

  .publishing-workbench-grid.is-resizing-sidebar {
    cursor: col-resize;
    user-select: none;
  }

  .performance-sidebar {
    max-height: clamp(520px, calc(100vh - 250px), 760px);
    order: 1;
  }

  .performance-sidebar-resize {
    position: absolute;
    top: 0;
    right: 0;
    display: block;
    width: 10px;
    height: 100%;
    cursor: col-resize;
    border: 0;
    background: transparent;
    padding: 0;
  }

  .performance-sidebar-resize::after {
    position: absolute;
    top: 50%;
    right: 3px;
    width: 3px;
    height: 44px;
    border-radius: 9999px;
    background-color: #cbd5e1;
    content: '';
    opacity: 0;
    transform: translateY(-50%);
    transition:
      opacity 150ms ease,
      background-color 150ms ease;
  }

  .performance-sidebar-resize:hover::after,
  .performance-sidebar-resize:focus-visible::after,
  .publishing-workbench-grid.is-resizing-sidebar
    .performance-sidebar-resize::after {
    background-color: #8b7dd1;
    opacity: 1;
  }

  .pricing-workbench-main {
    min-height: 0;
    max-height: clamp(520px, calc(100vh - 250px), 760px);
    overflow-y: auto;
    padding-right: 0.25rem;
    order: 2;
  }
}

.supply-model-cell {
  box-sizing: border-box;
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 0.75rem;
}

.supply-model-cell > span:first-of-type {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.supply-metric-column {
  display: grid;
  gap: 0.375rem;
  color: #334155;
  font-size: 12px;
}

.supply-metric-row {
  display: grid;
  grid-template-columns: 4.25rem minmax(0, 1fr);
  align-items: baseline;
  column-gap: 0.5rem;
  min-height: 1.25rem;
}

.supply-metric-label {
  color: #94a3b8;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}

.supply-metric-value {
  min-width: 0;
  overflow: hidden;
  text-align: right;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono',
    'Courier New', monospace;
  font-weight: 700;
}

.supply-metric-empty {
  display: block;
  color: #94a3b8;
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono',
    'Courier New', monospace;
  font-weight: 700;
  text-align: right;
}

@media (min-width: 1024px) {
  .supply-grid-header {
    display: grid;
  }

  .supply-grid-row {
    display: grid;
    min-height: 58px;
  }

  .supply-model-cell {
    padding-left: 1.5rem;
  }

  .supply-metric-column {
    text-align: right;
  }
}

.btn-secondary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  border-width: 1px;
  border-color: #e2e8f0;
  padding-left: 0.75rem;
  padding-right: 0.75rem;
  padding-top: 0.375rem;
  padding-bottom: 0.375rem;
  font-size: 12px;
  font-weight: 500;
  color: #334155;
  transition-property: color, background-color, border-color, box-shadow;
  transition-duration: 150ms;
  border-color: #cbd5e1;
  background-color: #f8fafc;
}
</style>
