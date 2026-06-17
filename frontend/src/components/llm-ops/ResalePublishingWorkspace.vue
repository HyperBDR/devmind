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
          <span>发布平台</span>
          <select v-model="form.platformId" class="field-select">
            <option v-for="p in platforms" :key="p.id" :value="p.id">
              {{ p.name }}
            </option>
          </select>
        </label>
        <label class="filter-field">
          <span>元厂商</span>
          <select
            v-model="form.metaVendorId"
            class="field-select"
            @change="onMetaVendorChange"
          >
            <option value="">全部</option>
            <option
              v-for="vendor in metaVendorOptions"
              :key="vendor.id"
              :value="String(vendor.id)"
            >
              {{ vendor.name }}
            </option>
          </select>
        </label>
        <label class="filter-field">
          <span>元模型</span>
          <select
            v-model="form.modelId"
            class="field-select"
            @change="onModelChange"
          >
            <option value="">选择元模型</option>
            <option
              v-for="m in baseModelOptions"
              :key="m.id"
              :value="String(m.id)"
            >
              {{ m.name }}
            </option>
          </select>
        </label>
        <label class="filter-field">
          <span>供货渠道</span>
          <select
            v-model="form.supplierId"
            class="field-select"
            :disabled="!form.modelId"
          >
            <option value="">{{ form.modelId ? '全部支持渠道' : '先选择元模型' }}</option>
            <option
              v-for="s in supplierOptions"
              :key="s.id"
              :value="String(s.id)"
            >
              {{ s.name }}
            </option>
          </select>
        </label>
      </div>
      <div class="pricing-context">
        <div class="pricing-segment">
          <span class="pricing-segment-label">当前平台币种</span>
          <strong class="pricing-segment-value">
            {{ platformCurrencyLabel }}
          </strong>
        </div>
        <div class="pricing-segment">
          <span class="pricing-segment-label">汇率</span>
          <strong class="pricing-segment-value">
            1 USD =
            {{ formatReadonlyNumber(globalPricing.exchangeRate, 4) }}
            CNY
          </strong>
        </div>
        <div class="pricing-segment">
          <span class="pricing-segment-label">{{ pointUnitLabel }}换算</span>
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
          供应链路甄选
        </h3>
        <div class="flex items-center gap-3 text-xs">
          <span
            v-if="!isSupplyChainExpanded"
            class="rounded bg-agione-50 px-2 py-1 font-semibold text-agione-700"
          >
            已选 {{ selectedChainRows.length }} 条链路
          </span>
          <span v-else class="text-slate-500"
            >共 {{ chainRows.length }} 条可用链路</span
          >
          <button
            type="button"
            class="btn-secondary !px-2.5 !py-1.5 !text-xs"
            @click="isSupplyChainExpanded = !isSupplyChainExpanded"
          >
            {{ isSupplyChainExpanded ? '收起' : '展开' }}
          </button>
        </div>
      </header>

      <div v-show="isSupplyChainExpanded">
        <div class="supply-grid supply-grid-header">
          <div>商务及物理链路</div>
          <div>链路成本 (In/Out)</div>
          <div class="text-right">上架售价 (In/Out)</div>
          <div class="text-right">最终 {{ pointUnitLabel }}</div>
        </div>

        <div
          v-if="!chainRows.length"
          class="bg-white p-8 text-center text-sm text-slate-500"
        >
          当前元模型暂无可用供应链路
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
            供货渠道：{{ group.supplierName }}
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
              供应源：{{ srcGroup.source }}
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
                  最低
                </span>
              </label>

              <div class="supply-cost-cell">
                <div>
                  <p class="text-[10px] uppercase tracking-wide text-slate-400">
                    In
                  </p>
                  <p class="font-mono font-bold text-slate-900">
                    {{ row.costIn }}
                  </p>
                </div>
                <div>
                  <p class="text-[10px] uppercase tracking-wide text-slate-400">
                    Out
                  </p>
                  <p class="font-mono font-bold text-slate-900">
                    {{ row.costOut }}
                  </p>
                </div>
              </div>

              <div class="supply-value-cell">
                <span class="text-slate-500 lg:hidden">售价</span>
                <span class="font-mono font-bold text-emerald-600">
                  <span v-if="row.selected"
                    >{{ row.priceIn }} / {{ row.priceOut }}</span
                  >
                  <span v-else class="text-slate-400">-</span>
                </span>
              </div>

              <div class="supply-value-cell">
                <span class="text-slate-500 lg:hidden">Credit</span>
                <span class="font-mono font-bold text-agione-600">
                  <span v-if="row.selected"
                    >{{ formatCredit(row.costInRaw, row.marginIn) }} /
                    {{ formatCredit(row.costOutRaw, row.marginOut) }}</span
                  >
                  <span v-else class="text-slate-400">-</span>
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
      <aside
        class="workspace-section performance-sidebar overflow-hidden p-0"
      >
        <header class="performance-sidebar-header">
          <span class="performance-sidebar-dot" />
          <h3>链路性能全景对标</h3>
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
                :key="`${metric.key}-${item.name}`"
                class="perf-metric-row"
              >
                <div
                  class="perf-metric-name"
                  :title="item.name"
                >
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
              <p
                v-if="!perfCompareRows.length"
                class="perf-empty"
              >
                暂无对比数据
              </p>
            </div>
          </section>
        </div>
        <button
          type="button"
          class="performance-sidebar-resize"
          aria-label="调整链路性能全景对标宽度"
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
              >最低采购链路</span
            >
          </header>
          <div class="space-y-6 p-5">
            <div class="space-y-3 border-b border-dashed border-slate-200 pb-5">
              <div class="pricing-editor-row">
                <div class="pricing-dimension-cell">
                  Input
                </div>
                <div class="cost-formula-cell">
                  <p class="mb-1 text-[11px] text-slate-500">成本价</p>
                  <p class="font-mono text-[13px] font-bold text-slate-900">
                    {{ currencySymbol }}{{ row.costIn }}
                  </p>
                  <p
                    class="cost-formula-text"
                    :title="costFormulaTitle(row, 'In')"
                  >
                    {{ costFormulaText(row, 'In') }}
                  </p>
                </div>
                <div class="profit-input-cell">
                  <p class="mb-1 text-[11px] text-slate-500">利润期望 (%)</p>
                  <div
                    class="flex items-center rounded border border-slate-200 focus-within:border-agione-300 focus-within:ring-2 focus-within:ring-agione-100"
                  >
                    <input
                      :value="row.marginIn"
                      type="number"
                      class="w-full bg-transparent px-2 py-1.5 text-right text-[12px] focus:outline-none"
                      step="0.1"
                      min="0"
                      @input="onMarginInput(row, 'In', $event)"
                    />
                    <span
                      class="border-l border-slate-200 px-2 text-[11px] text-slate-400"
                      >%</span
                    >
                  </div>
                </div>
                <div class="terminal-price-group">
                  <div class="terminal-price-input">
                    <p class="mb-1 text-[11px] font-bold text-emerald-600">
                      终端售卖价
                    </p>
                    <div
                      class="flex items-center rounded border border-slate-200 focus-within:border-emerald-300 focus-within:ring-2 focus-within:ring-emerald-100"
                    >
                      <span
                        class="border-r border-slate-200 px-2 text-[11px] text-slate-400"
                        >{{ currencySymbol }}</span
                      >
                      <input
                        :value="row.priceInRaw"
                        type="number"
                        class="w-full bg-transparent px-2 py-1.5 text-right font-mono text-[12px] focus:outline-none"
                        step="0.0001"
                        min="0"
                        @input="onPriceInput(row, 'In', $event)"
                      />
                    </div>
                  </div>
                  <div class="market-average-group">
                    <p class="mb-1 text-[11px] text-slate-500">市场均价</p>
                    <div class="market-reconcile-card">
                      <strong class="market-average-value">{{
                        marketAverageText(marketAvg.in)
                      }}</strong>
                      <span
                        class="market-diff-pill"
                        :class="priceDiffClass(row.priceInRaw, marketAvg.in)"
                      >
                        {{ priceDiffText(row.priceInRaw, marketAvg.in) }}
                      </span>
                      <span
                        v-if="priceDiffAmountText(row.priceInRaw, marketAvg.in)"
                        class="market-diff-amount"
                        :class="priceDiffClass(row.priceInRaw, marketAvg.in)"
                      >
                        {{ priceDiffAmountText(row.priceInRaw, marketAvg.in) }}
                      </span>
                    </div>
                  </div>
                </div>
                <div class="final-credit-cell">
                  <div class="final-credit-card">
                    <p class="text-[10px] text-agione-600">
                      最终 {{ pointUnitLabel }}
                    </p>
                    <p class="font-mono text-[12px] font-bold text-agione-700">
                      {{ formatCredit(row.costInRaw, row.marginIn) }}
                    </p>
                  </div>
                </div>
              </div>
              <div class="pricing-axis-block">
                <BulletChart
                  :min="bulletRange.in.min"
                  :max="bulletRange.in.max"
                  :value="row.priceInRaw"
                  :refs="bulletRefsIn"
                  :label="`我方售价 ${currencySymbol}${row.priceIn}`"
                  :currency-symbol="currencySymbol"
                  @change="applyPriceChange(row, 'In', $event)"
                />
              </div>
            </div>

            <div v-if="row.hasCacheInput" class="space-y-3 border-b border-dashed border-slate-200 pb-5">
              <div class="pricing-editor-row">
                <div class="pricing-dimension-cell">
                  Cache
                </div>
                <div class="cost-formula-cell">
                  <p class="mb-1 text-[11px] text-slate-500">缓存成本价</p>
                  <p class="font-mono text-[13px] font-bold text-slate-900">
                    {{ currencySymbol }}{{ row.costCacheIn }}
                  </p>
                  <p
                    class="cost-formula-text"
                    :title="costFormulaTitle(row, 'Cache')"
                  >
                    {{ costFormulaText(row, 'Cache') }}
                  </p>
                </div>
                <div class="profit-input-cell">
                  <p class="mb-1 text-[11px] text-slate-500">利润期望 (%)</p>
                  <div
                    class="flex items-center rounded border border-slate-200 focus-within:border-agione-300 focus-within:ring-2 focus-within:ring-agione-100"
                  >
                    <input
                      :value="row.marginCacheIn"
                      type="number"
                      class="w-full bg-transparent px-2 py-1.5 text-right text-[12px] focus:outline-none"
                      step="0.1"
                      min="0"
                      @input="onMarginInput(row, 'Cache', $event)"
                    />
                    <span
                      class="border-l border-slate-200 px-2 text-[11px] text-slate-400"
                      >%</span
                    >
                  </div>
                </div>
                <div class="terminal-price-group">
                  <div class="terminal-price-input">
                    <p class="mb-1 text-[11px] font-bold text-emerald-600">
                      缓存售卖价
                    </p>
                    <div
                      class="flex items-center rounded border border-slate-200 focus-within:border-emerald-300 focus-within:ring-2 focus-within:ring-emerald-100"
                    >
                      <span
                        class="border-r border-slate-200 px-2 text-[11px] text-slate-400"
                        >{{ currencySymbol }}</span
                      >
                      <input
                        :value="row.priceCacheInRaw"
                        type="number"
                        class="w-full bg-transparent px-2 py-1.5 text-right font-mono text-[12px] focus:outline-none"
                        step="0.0001"
                        min="0"
                        @input="onPriceInput(row, 'Cache', $event)"
                      />
                    </div>
                  </div>
                  <div class="market-average-group">
                    <p class="mb-1 text-[11px] text-slate-500">市场均价</p>
                    <div class="market-reconcile-card">
                      <strong class="market-average-value">{{
                        marketAverageText(marketAvg.cacheIn)
                      }}</strong>
                      <span
                        class="market-diff-pill"
                        :class="priceDiffClass(row.priceCacheInRaw, marketAvg.cacheIn)"
                      >
                        {{ priceDiffText(row.priceCacheInRaw, marketAvg.cacheIn) }}
                      </span>
                      <span
                        v-if="priceDiffAmountText(row.priceCacheInRaw, marketAvg.cacheIn)"
                        class="market-diff-amount"
                        :class="priceDiffClass(row.priceCacheInRaw, marketAvg.cacheIn)"
                      >
                        {{ priceDiffAmountText(row.priceCacheInRaw, marketAvg.cacheIn) }}
                      </span>
                    </div>
                  </div>
                </div>
                <div class="final-credit-cell">
                  <div class="final-credit-card">
                    <p class="text-[10px] text-agione-600">
                      最终 {{ pointUnitLabel }}
                    </p>
                    <p class="font-mono text-[12px] font-bold text-agione-700">
                      {{ formatCredit(row.costCacheInRaw, row.marginCacheIn) }}
                    </p>
                  </div>
                </div>
              </div>
            </div>

            <div class="space-y-3">
              <div class="pricing-editor-row">
                <div class="pricing-dimension-cell">
                  Output
                </div>
                <div class="cost-formula-cell">
                  <p class="mb-1 text-[11px] text-slate-500">成本价</p>
                  <p class="font-mono text-[13px] font-bold text-slate-900">
                    {{ currencySymbol }}{{ row.costOut }}
                  </p>
                  <p
                    class="cost-formula-text"
                    :title="costFormulaTitle(row, 'Out')"
                  >
                    {{ costFormulaText(row, 'Out') }}
                  </p>
                </div>
                <div class="profit-input-cell">
                  <p class="mb-1 text-[11px] text-slate-500">利润期望 (%)</p>
                  <div
                    class="flex items-center rounded border border-slate-200 focus-within:border-agione-300 focus-within:ring-2 focus-within:ring-agione-100"
                  >
                    <input
                      :value="row.marginOut"
                      type="number"
                      class="w-full bg-transparent px-2 py-1.5 text-right text-[12px] focus:outline-none"
                      step="0.1"
                      min="0"
                      @input="onMarginInput(row, 'Out', $event)"
                    />
                    <span
                      class="border-l border-slate-200 px-2 text-[11px] text-slate-400"
                      >%</span
                    >
                  </div>
                </div>
                <div class="terminal-price-group">
                  <div class="terminal-price-input">
                    <p class="mb-1 text-[11px] font-bold text-emerald-600">
                      终端售卖价
                    </p>
                    <div
                      class="flex items-center rounded border border-slate-200 focus-within:border-emerald-300 focus-within:ring-2 focus-within:ring-emerald-100"
                    >
                      <span
                        class="border-r border-slate-200 px-2 text-[11px] text-slate-400"
                        >{{ currencySymbol }}</span
                      >
                      <input
                        :value="row.priceOutRaw"
                        type="number"
                        class="w-full bg-transparent px-2 py-1.5 text-right font-mono text-[12px] focus:outline-none"
                        step="0.0001"
                        min="0"
                        @input="onPriceInput(row, 'Out', $event)"
                      />
                    </div>
                  </div>
                  <div class="market-average-group">
                    <p class="mb-1 text-[11px] text-slate-500">市场均价</p>
                    <div class="market-reconcile-card">
                      <strong class="market-average-value">{{
                        marketAverageText(marketAvg.out)
                      }}</strong>
                      <span
                        class="market-diff-pill"
                        :class="priceDiffClass(row.priceOutRaw, marketAvg.out)"
                      >
                        {{ priceDiffText(row.priceOutRaw, marketAvg.out) }}
                      </span>
                      <span
                        v-if="priceDiffAmountText(row.priceOutRaw, marketAvg.out)"
                        class="market-diff-amount"
                        :class="priceDiffClass(row.priceOutRaw, marketAvg.out)"
                      >
                        {{ priceDiffAmountText(row.priceOutRaw, marketAvg.out) }}
                      </span>
                    </div>
                  </div>
                </div>
                <div class="final-credit-cell">
                  <div class="final-credit-card">
                    <p class="text-[10px] text-agione-600">
                      最终 {{ pointUnitLabel }}
                    </p>
                    <p class="font-mono text-[12px] font-bold text-agione-700">
                      {{ formatCredit(row.costOutRaw, row.marginOut) }}
                    </p>
                  </div>
                </div>
              </div>
              <div class="pricing-axis-block">
                <BulletChart
                  :min="bulletRange.out.min"
                  :max="bulletRange.out.max"
                  :value="row.priceOutRaw"
                  :refs="bulletRefsOut"
                  :label="`我方售价 ${currencySymbol}${row.priceOut}`"
                  :currency-symbol="currencySymbol"
                  @change="applyPriceChange(row, 'Out', $event)"
                />
              </div>
            </div>
          </div>
        </article>
      </div>
    </section>

    <div
      v-else-if="form.modelId"
      class="rounded-lg border border-dashed border-slate-200 bg-slate-50 p-8 text-center text-sm text-slate-500"
    >
      请在链路甄选面板中勾选至少一条供应链路，继续定价。
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import BulletChart from '@/components/llm-ops/BulletChart.vue'
import { resolveCanonicalMetaVendor } from '@/utils/llmOpsMeta'

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
  }
})

const emit = defineEmits(['change'])

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
    const vendor = resolveCanonicalMetaVendor(item, props.providers)
    return {
      ...item,
      effective_vendor: item.effective_vendor || vendor.id,
      effective_vendor_code: item.effective_vendor_code || vendor.code,
      effective_vendor_name: item.effective_vendor_name || vendor.name
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

const availableMetaModelIds = computed(
  () => new Set(procurementByMetaModel.value.keys())
)

const selectedMetaModel = computed(() => {
  if (!form.value.modelId) return null
  return metaModelById.value.get(String(form.value.modelId)) || null
})

const selectedMetaModelProcurements = computed(() => {
  if (!form.value.modelId) return []
  return procurementByMetaModel.value.get(String(form.value.modelId)) || []
})

const metaVendorOptions = computed(() => {
  const map = new Map()
  metaModelRows.value.forEach((model) => {
    const id = model.effective_vendor
    if (!id) return
    if (!availableMetaModelIds.value.has(String(model.id))) return
    const key = String(id)
    if (map.has(key)) return
    map.set(key, {
      id,
      name: model.effective_vendor_name || model.vendor_name || '未归类',
      code: model.effective_vendor_code || ''
    })
  })
  return Array.from(map.values()).sort((left, right) =>
    String(left.name).localeCompare(String(right.name))
  )
})

const baseModelOptions = computed(() => {
  const metaVendorId = form.value.metaVendorId
  return metaModelRows.value
    .filter((item) => {
      if (!availableMetaModelIds.value.has(String(item.id))) return false
      if (!metaVendorId) return true
      return String(item.effective_vendor) === String(metaVendorId)
    })
    .map((item) => ({
      id: item.id,
      name: item.name || item.code,
      code: item.code,
      family: item.family,
      vendorName: item.effective_vendor_name || item.vendor_name
    }))
    .sort((left, right) => String(left.name).localeCompare(String(right.name)))
})

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

const supportedSupplierIds = computed(
  () => new Set(supplierOptions.value.map((item) => String(item.id)))
)

const pointUnitLabel = computed(
  () => props.pointConversion?.point_name || '积分'
)

const selectedPlatform = computed(() => {
  const id = String(form.value.platformId || '')
  return (
    (props.platforms || []).find((item) => String(item.id) === id) ||
    props.agionePlatform ||
    null
  )
})

const platformCurrencyLabel = computed(() =>
  String(selectedPlatform.value?.currency || props.displayCurrency || 'CNY')
    .toUpperCase()
)

const currencyLabel = computed(() => String(props.displayCurrency || 'CNY'))
const currencySymbol = computed(() =>
  currencyLabel.value === 'USD' ? '$' : '¥'
)

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
  () => supplierOptions.value.map((item) => item.id).join(","),
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
    id: metaModel.effective_vendor,
    code: metaModel.effective_vendor_code,
    name: metaModel.effective_vendor_name || metaModel.vendor_name
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
      const inDisplay = convertToDisplay(
        option.input_price_per_million,
        option.currency
      )
      const outDisplay = convertToDisplay(
        option.output_price_per_million,
        option.currency
      )
      const cacheInDisplay = convertToDisplay(
        option.cache_input_price_per_million,
        option.currency
      )
      const baseInDisplay = convertToDisplay(
        option.base_input_price_per_million ??
          basePriceFromRatio(
            option.input_price_per_million,
            option.input_price_per_million_settlement_ratio ??
              option.settlement_ratio
          ),
        option.currency
      )
      const baseOutDisplay = convertToDisplay(
        option.base_output_price_per_million ??
          basePriceFromRatio(
            option.output_price_per_million,
            option.output_price_per_million_settlement_ratio ??
              option.settlement_ratio
          ),
        option.currency
      )
      const baseCacheInDisplay = convertToDisplay(
        option.base_cache_input_price_per_million ??
          basePriceFromRatio(
            option.cache_input_price_per_million,
            option.cache_input_price_per_million_settlement_ratio ??
              option.settlement_ratio
          ),
        option.currency
      )
      const discountIn = normalizeDiscountRatio(
        option.input_price_per_million_settlement_ratio ??
          option.settlement_ratio
      )
      const discountOut = normalizeDiscountRatio(
        option.output_price_per_million_settlement_ratio ??
          option.settlement_ratio
      )
      const discountCacheIn = normalizeDiscountRatio(
        option.cache_input_price_per_million_settlement_ratio ??
          option.settlement_ratio
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
        provider: metaVendor.name || '未归类',
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
          cacheInDisplay !== null && cacheInDisplay > 0
            ? cacheInDisplay.toFixed(4)
            : '-',
        hasCacheInput: cacheInDisplay !== null && cacheInDisplay > 0,
        selected: Boolean(state.selected),
        marginIn: state.marginIn ?? 20,
        marginOut: state.marginOut ?? 20,
        marginCacheIn: state.marginCacheIn ?? state.marginIn ?? 20,
        priceInRaw: state.priceInRaw ?? null,
        priceOutRaw: state.priceOutRaw ?? null,
        priceCacheInRaw: state.priceCacheInRaw ?? null,
        priceIn:
          state.priceInRaw !== null && state.priceInRaw !== undefined
            ? Number(state.priceInRaw).toFixed(4)
            : '',
        priceOut:
          state.priceOutRaw !== null && state.priceOutRaw !== undefined
            ? Number(state.priceOutRaw).toFixed(4)
            : '',
        priceCacheIn:
          state.priceCacheInRaw !== null &&
          state.priceCacheInRaw !== undefined
            ? Number(state.priceCacheInRaw).toFixed(4)
            : '',
        isLowest: false
      }
    })
    .sort((a, b) => Number(a.costInRaw) - Number(b.costInRaw))
    .map((row, idx) => ({ ...row, isLowest: idx === 0 }))
})

const selectedChainRows = computed(() =>
  chainRows.value.filter((r) => r.selected)
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
    if (state.priceInRaw === null || state.priceInRaw === undefined) {
      state.priceInRaw = Number(
        (row.costInRaw * (1 + (Number(row.marginIn) || 0) / 100)).toFixed(4)
      )
    }
    if (state.priceOutRaw === null || state.priceOutRaw === undefined) {
      state.priceOutRaw = Number(
        (row.costOutRaw * (1 + (Number(row.marginOut) || 0) / 100)).toFixed(4)
      )
    }
    if (
      row.hasCacheInput &&
      (state.priceCacheInRaw === null ||
        state.priceCacheInRaw === undefined)
    ) {
      const margin = Number(row.marginCacheIn ?? row.marginIn) || 0
      state.marginCacheIn = margin
      state.priceCacheInRaw = Number(
        (row.costCacheInRaw * (1 + margin / 100)).toFixed(4)
      )
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
  form.value.metaVendorId = metaModel?.effective_vendor
    ? String(metaModel.effective_vendor)
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
        priceInRaw: priceIn ?? row.priceInRaw,
        priceOutRaw: priceOut ?? row.priceOutRaw,
        priceCacheInRaw: priceCacheIn ?? row.priceCacheInRaw,
        marginIn: marginFromPrice(priceIn, row.costInRaw),
        marginOut: marginFromPrice(priceOut, row.costOutRaw),
        marginCacheIn: marginFromPrice(priceCacheIn, row.costCacheInRaw)
      }
    })
  chainState.value = nextState
  syncSelectedChain()
}

function marginFromPrice(price, cost) {
  const priceValue = Number(price)
  const costValue = Number(cost)
  if (
    !Number.isFinite(priceValue) ||
    !Number.isFinite(costValue) ||
    costValue <= 0
  ) {
    return 20
  }
  return Number((((priceValue - costValue) / costValue) * 100).toFixed(2))
}

function onMarginInput(row, dir, event) {
  const value = Number(event?.target?.value)
  const margin = Number.isFinite(value) ? value : 0
  const cost =
    dir === 'In'
      ? row.costInRaw
      : dir === 'Cache'
        ? row.costCacheInRaw
        : row.costOutRaw
  const price = Number(cost) * (1 + (Number(margin) || 0) / 100)
  if (dir === 'In') {
    updateChainState(row, {
      marginIn: margin,
      priceInRaw: Number(price.toFixed(4))
    })
  } else if (dir === 'Cache') {
    updateChainState(row, {
      marginCacheIn: margin,
      priceCacheInRaw: Number(price.toFixed(4))
    })
  } else {
    updateChainState(row, {
      marginOut: margin,
      priceOutRaw: Number(price.toFixed(4))
    })
  }
  emitChange()
}

function onPriceInput(row, dir, event) {
  const rawPrice = Number(event?.target?.value)
  applyPriceChange(row, dir, rawPrice)
}

function applyPriceChange(row, dir, rawPrice) {
  const cost =
    dir === 'In'
      ? row.costInRaw
      : dir === 'Cache'
        ? row.costCacheInRaw
        : row.costOutRaw
  const price = Number.isFinite(rawPrice) ? rawPrice : 0
  const margin =
    Number(cost) > 0
      ? ((Number(price) - Number(cost)) / Number(cost)) * 100
      : dir === 'In'
        ? row.marginIn
        : dir === 'Cache'
          ? row.marginCacheIn
          : row.marginOut
  if (dir === 'In') {
    updateChainState(row, {
      priceInRaw: price,
      marginIn: Number(margin.toFixed(2))
    })
  } else if (dir === 'Cache') {
    updateChainState(row, {
      priceCacheInRaw: price,
      marginCacheIn: Number(margin.toFixed(2))
    })
  } else {
    updateChainState(row, {
      priceOutRaw: price,
      marginOut: Number(margin.toFixed(2))
    })
  }
  emitChange()
}

function formatCredit(cost, margin) {
  const c = Number(cost) || 0
  const m = Number(margin) || 0
  const rate = Number(globalPricing.value.creditRatio) || 0
  const price = c * (1 + m / 100)
  return (price * rate).toFixed(2)
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

function formatDiscount(value) {
  const ratio = normalizeDiscountRatio(value)
  return `${(ratio * 100).toFixed(1).replace(/\.0$/, '')}%`
}

function costFormulaParts(row, dir) {
  if (dir === 'Cache') {
    return {
      baseCost: row.baseCostCacheInRaw,
      discount: row.discountCacheIn,
      cost: row.costCacheInRaw
    }
  }
  const isInput = dir === 'In'
  return {
    baseCost: isInput ? row.baseCostInRaw : row.baseCostOutRaw,
    discount: isInput ? row.discountIn : row.discountOut,
    cost: isInput ? row.costInRaw : row.costOutRaw
  }
}

function costFormulaText(row, dir) {
  const parts = costFormulaParts(row, dir)
  return `${formatMoneyAmount(parts.baseCost)} × ${formatDiscount(
    parts.discount
  )} = ${formatMoneyAmount(parts.cost)}`
}

function costFormulaTitle(row, dir) {
  return `成本价 = 供应商成本价 × 折扣；${costFormulaText(row, dir)}`
}

function marketAverageText(avg) {
  const value = Number(avg)
  if (!Number.isFinite(value) || value <= 0) return '-'
  return `${currencySymbol.value}${value.toFixed(4)}`
}

function priceDiffText(price, avg) {
  const p = Number(price)
  const a = Number(avg)
  if (!Number.isFinite(p) || !Number.isFinite(a) || a <= 0) return '暂无对账'
  const diff = p - a
  const pct = Math.abs((diff / a) * 100).toFixed(1)
  if (diff < -0.00001) return `↓ 低 ${pct}%`
  if (diff > 0.00001) return `↑ 高 ${pct}%`
  return '- 持平'
}

function priceDiffAmountText(price, avg) {
  const p = Number(price)
  const a = Number(avg)
  if (!Number.isFinite(p) || !Number.isFinite(a) || a <= 0) return ''
  const diff = p - a
  const prefix = diff > 0 ? '+' : diff < 0 ? '-' : ''
  return `${prefix}${currencySymbol.value}${Math.abs(diff).toFixed(4)}`
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

const selectedSkuModelIds = computed(() => {
  const metaModelId = form.value.modelId
  if (!metaModelId) return new Set()
  return new Set(
    (props.models || [])
      .filter((model) => String(model.meta_model) === String(metaModelId))
      .map((model) => String(model.id))
  )
})

const marketAvg = computed(() => {
  const refs = (props.priceItems || []).filter(
    (it) => selectedSkuModelIds.value.has(String(it.model))
  )
  if (!refs.length) return { in: 0, out: 0, cacheIn: 0 }
  let inSum = 0
  let outSum = 0
  let cacheInSum = 0
  let inCount = 0
  let outCount = 0
  let cacheInCount = 0
  refs.forEach((it) => {
    const inV = convertToDisplay(it.input_price_per_million, it.currency)
    const outV = convertToDisplay(it.output_price_per_million, it.currency)
    const cacheInV = convertToDisplay(
      it.cache_input_price_per_million,
      it.currency
    )
    if (inV !== null) {
      inSum += inV
      inCount += 1
    }
    if (outV !== null) {
      outSum += outV
      outCount += 1
    }
    if (cacheInV !== null) {
      cacheInSum += cacheInV
      cacheInCount += 1
    }
  })
  return {
    in: inCount > 0 ? Number((inSum / inCount).toFixed(4)) : 0,
    out: outCount > 0 ? Number((outSum / outCount).toFixed(4)) : 0,
    cacheIn:
      cacheInCount > 0 ? Number((cacheInSum / cacheInCount).toFixed(4)) : 0
  }
})

const bulletRefsIn = computed(() => {
  return (props.priceItems || [])
    .filter((it) => selectedSkuModelIds.value.has(String(it.model)))
    .map((it) => ({
      source: it.source_name || it.vendor_name || '市场参考',
      price: convertToDisplay(it.input_price_per_million, it.currency) || 0
    }))
    .filter((r) => r.price > 0)
})

const bulletRefsOut = computed(() => {
  return (props.priceItems || [])
    .filter((it) => selectedSkuModelIds.value.has(String(it.model)))
    .map((it) => ({
      source: it.source_name || it.vendor_name || '市场参考',
      price: convertToDisplay(it.output_price_per_million, it.currency) || 0
    }))
    .filter((r) => r.price > 0)
})

const bulletRange = computed(() => {
  const inMarketPrices = bulletRefsIn.value.map((r) => r.price)
  const outMarketPrices = bulletRefsOut.value.map((r) => r.price)
  const inMin = Math.min(...inMarketPrices)
  const inMax = Math.max(...inMarketPrices)
  const outMin = Math.min(...outMarketPrices)
  const outMax = Math.max(...outMarketPrices)
  return {
    in: {
      min: Number.isFinite(inMin) && inMin > 0 ? inMin : 0,
      max: Number.isFinite(inMax) && inMax > 0 ? inMax : 0
    },
    out: {
      min: Number.isFinite(outMin) && outMin > 0 ? outMin : 0,
      max: Number.isFinite(outMax) && outMax > 0 ? outMax : 0
    }
  }
})

// Performance: derive stable mock metrics from cost to keep bars visually
// comparable across chains. The dataset is intentionally lightweight
// until a real channel-perf API exists.
const perfCompareRows = computed(() =>
  selectedChainRows.value.map((row) => {
    const seed = Number(row.costInRaw) || 0
    return {
      name: `${row.provider} · ${row.source}`,
      rpm: Math.max(0, 30000 - Math.round(seed * 60000)),
      tpm: Math.max(0, 4000000 - Math.round(seed * 4000000)),
      context: row.context || 128,
      latency: Math.max(40, Math.round(80 + seed * 200))
    }
  })
)

const perfMetrics = computed(() => {
  const rpmMax = Math.max(1, ...perfCompareRows.value.map((r) => r.rpm))
  const tpmMax = Math.max(1, ...perfCompareRows.value.map((r) => r.tpm))
  const ctxMax = Math.max(1, ...perfCompareRows.value.map((r) => r.context))
  const latMax = Math.max(1, ...perfCompareRows.value.map((r) => r.latency))
  return [
    {
      key: 'rpm',
      label: '并发请求速率 (RPM)',
      max: rpmMax,
      format: (v) => `${(v / 1000).toFixed(1)}K`,
      barClass: () => 'bg-violet-500'
    },
    {
      key: 'tpm',
      label: 'Token 吞吐量 (TPM)',
      max: tpmMax,
      format: (v) => `${(v / 1000000).toFixed(1)}M`,
      barClass: () => 'bg-emerald-500'
    },
    {
      key: 'context',
      label: '上下文长度 (Context)',
      max: ctxMax,
      format: (v) => `${v}K`,
      barClass: () => 'bg-sky-500'
    },
    {
      key: 'latency',
      label: '首字延迟 (Latency · 越低越好)',
      max: latMax,
      format: (v) => `${v}ms`,
      barClass: () => 'bg-amber-500'
    }
  ]
})

function barWidth(value, max) {
  if (!Number.isFinite(value) || !Number.isFinite(max) || max <= 0) return '0%'
  return `${Math.max(2, (value / max) * 100)}%`
}

function emitChange() {
  emit('change', {
    platformId: form.value.platformId,
    metaVendorId: form.value.metaVendorId,
    metaModelId: form.value.modelId,
    modelId: form.value.modelId,
    supplierId: form.value.supplierId,
    listings: selectedChainRows.value.map((row) => ({
      channelId: row.channelId,
      metaModelId: row.metaModelId,
      modelId: row.modelId,
      priceIn: row.priceInRaw,
      priceOut: row.priceOutRaw,
      priceCacheIn: row.hasCacheInput ? row.priceCacheInRaw : null,
      marginIn: row.marginIn,
      marginOut: row.marginOut
    }))
  })
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
    return {
      platformId: form.value.platformId,
      metaVendorId: form.value.metaVendorId,
      metaModelId: form.value.modelId,
      modelId: form.value.modelId,
      supplierId: form.value.supplierId,
      listings: selectedChainRows.value.map((row) => ({
        channelId: row.channelId,
        metaModelId: row.metaModelId,
        modelId: row.modelId,
        priceIn: row.priceInRaw,
        priceOut: row.priceOutRaw,
        priceCacheIn: row.hasCacheInput ? row.priceCacheInRaw : null,
        marginIn: row.marginIn,
        marginOut: row.marginOut
      }))
    }
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
  gap: 0.75rem;
  padding: 1rem;
}

@media (min-width: 1280px) {
  .workspace-toolbar {
    grid-template-columns: minmax(0, 1fr);
  }
}

.workspace-filter-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 0.75rem;
  min-width: 0;
}

@media (min-width: 768px) {
  .workspace-filter-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

.filter-field {
  display: grid;
  grid-template-columns: 58px minmax(0, 1fr);
  align-items: center;
  gap: 0.5rem;
  min-width: 0;
}

.filter-field > span {
  color: #64748b;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0;
  line-height: 1;
  white-space: nowrap;
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
  justify-self: stretch;
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
  gap: 0.5rem;
  min-height: 38px;
  border-right: 1px solid #e2e8f0;
  padding: 0 0.75rem;
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
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas,
    "Liberation Mono", "Courier New", monospace;
  font-size: 12px;
  font-weight: 700;
}

@media (max-width: 820px) {
  .pricing-context {
    grid-template-columns: 1fr;
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
  grid-template-columns: minmax(300px, 1fr) 170px 170px 140px;
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

.pricing-editor-row {
  display: grid;
  grid-template-columns:
    52px minmax(156px, 178px) minmax(96px, 108px)
    minmax(238px, 1fr) minmax(92px, 104px);
  gap: 0.625rem;
  align-items: end;
}

.pricing-dimension-cell {
  align-self: center;
  color: #64748b;
  font-size: 13px;
  font-weight: 700;
}

.pricing-axis-block {
  padding: 2rem 0 4.25rem;
}

.pricing-axis-block :deep(.range-bar-wrapper) {
  margin: 0;
}

.profit-input-cell,
.terminal-price-input {
  min-width: 0;
}

.final-credit-cell {
  display: flex;
  min-width: 0;
  justify-content: flex-end;
}

.final-credit-card {
  width: 100%;
  min-width: 92px;
  border-radius: 6px;
  background-color: #ece9f9;
  padding: 0.5rem;
  text-align: center;
}

.terminal-price-group {
  display: grid;
  grid-template-columns: minmax(112px, 132px) minmax(150px, 1fr);
  align-items: flex-end;
  gap: 0.375rem;
  min-width: 0;
}

.cost-formula-cell {
  min-width: 0;
}

.cost-formula-text {
  margin-top: 0.125rem;
  max-width: 100%;
  overflow: hidden;
  color: #64748b;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas,
    "Liberation Mono", "Courier New", monospace;
  font-size: 10px;
  font-weight: 600;
  line-height: 1.2;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.market-reconcile-card {
  display: flex;
  min-height: 34px;
  min-width: 0;
  max-width: 100%;
  align-items: center;
  gap: 0.25rem;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background-color: #f8fafc;
  padding: 0.25rem 0.5rem;
  font-size: 10px;
  line-height: 1.2;
  white-space: nowrap;
}

.market-average-group {
  min-width: 0;
}

.market-average-value,
.market-diff-amount,
.market-diff-pill {
  overflow: hidden;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas,
    "Liberation Mono", "Courier New", monospace;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.market-average-value {
  color: #334155;
}

.market-diff-pill {
  border-left: 1px solid #e2e8f0;
  padding-left: 0.25rem;
}

.market-diff-amount {
  color: #64748b;
}

@media (max-width: 720px) {
  .pricing-editor-row {
    grid-template-columns: 1fr;
  }

  .cost-formula-cell {
    width: 100%;
  }

  .terminal-price-group {
    grid-template-columns: 1fr;
  }

  .market-reconcile-card {
    width: 100%;
    max-width: none;
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
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas,
    "Liberation Mono", "Courier New", monospace;
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
    grid-template-columns:
      var(--performance-sidebar-width, 380px) minmax(0, 1fr);
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
    content: "";
    opacity: 0;
    transform: translateY(-50%);
    transition: opacity 150ms ease, background-color 150ms ease;
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

.supply-cost-cell {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
  color: #334155;
  font-size: 12px;
}

.supply-value-cell {
  display: flex;
  width: 100%;
  justify-content: space-between;
  gap: 1rem;
  font-size: 12px;
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

  .supply-value-cell {
    justify-content: flex-end;
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
