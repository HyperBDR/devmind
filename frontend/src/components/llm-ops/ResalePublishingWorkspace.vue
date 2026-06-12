<!--
  ResalePublishingWorkspace — immersive resale publishing workspace
  re-implements demo.html "model publishing workspace" using the
  existing llm-ops procurement rows as the chain-of-supply source.
-->
<template>
  <div class="workspace-shell">
    <section
      class="workspace-section flex flex-col gap-3 p-4 lg:flex-row lg:items-center lg:justify-between"
    >
      <div class="flex flex-wrap items-center gap-3">
        <div class="flex items-center gap-2">
          <span
            class="text-[11px] font-bold uppercase tracking-wider text-slate-500 w-[60px]"
            >发布平台</span
          >
          <select v-model="form.platformId" class="field-select w-[160px]">
            <option v-for="p in platforms" :key="p.id" :value="p.id">
              {{ p.name }}
            </option>
          </select>
        </div>
        <span class="hidden h-6 w-px bg-slate-200 lg:block" />
        <div class="flex items-center gap-2">
          <span
            class="text-[11px] font-bold uppercase tracking-wider text-slate-500 w-[60px]"
            >原厂商</span
          >
          <select
            v-model="form.providerId"
            class="field-select w-[150px]"
            @change="onProviderChange"
          >
            <option value="">全部</option>
            <option
              v-for="p in providerOptions"
              :key="p.id"
              :value="String(p.id)"
            >
              {{ p.name }}
            </option>
          </select>
        </div>
        <div class="flex items-center gap-2">
          <span
            class="text-[11px] font-bold uppercase tracking-wider text-slate-500 w-[50px]"
            >元模型</span
          >
          <select
            v-model="form.modelId"
            class="field-select w-[200px]"
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
        </div>
      </div>
      <div
        class="flex flex-wrap items-center gap-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2"
      >
        <div class="flex items-center gap-1.5 text-[11px] text-slate-500">
          <span class="font-semibold">汇率</span>
          <span>1 USD =</span>
          <input
            v-model.number="globalPricing.exchangeRate"
            type="number"
            class="w-16 rounded border border-slate-200 px-1.5 py-1 text-right font-mono text-[12px] focus:border-indigo-300 focus:outline-none focus:ring-2 focus:ring-indigo-100"
            step="0.01"
            min="0"
          />
          <span>CNY</span>
        </div>
        <div class="flex items-center gap-1.5 text-[11px] text-slate-500">
          <span class="font-semibold">{{ pointUnitLabel }}换算</span>
          <span>1 {{ currencyLabel }} =</span>
          <input
            v-model.number="globalPricing.creditRatio"
            type="number"
            class="w-16 rounded border border-slate-200 px-1.5 py-1 text-right font-mono text-[12px] focus:border-indigo-300 focus:outline-none focus:ring-2 focus:ring-indigo-100"
            step="0.01"
            min="0"
          />
          <span>{{ pointUnitLabel }}</span>
        </div>
      </div>
    </section>

    <section v-if="form.modelId" class="workspace-section overflow-hidden p-0">
      <header
        class="flex flex-col gap-2 border-b border-slate-200 px-5 py-4 sm:flex-row sm:items-center sm:justify-between"
      >
        <h3 class="flex items-center gap-2 text-sm font-bold text-slate-900">
          <span class="inline-block h-2 w-2 rounded-full bg-indigo-500" />
          供应链路甄选与账号绑定
        </h3>
        <div class="flex items-center gap-3 text-xs">
          <span
            v-if="!isSupplyChainExpanded"
            class="rounded bg-indigo-50 px-2 py-1 font-semibold text-indigo-700"
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
        <div
          class="hidden border-b border-slate-200 bg-slate-50 px-4 py-2.5 text-[11px] font-bold uppercase tracking-wider text-slate-500 lg:flex"
        >
          <div class="w-[280px] pl-10">商务及物理链路</div>
          <div class="w-[140px]">链路成本 (In/Out)</div>
          <div class="flex-1 min-w-[220px]">绑定转发账号</div>
          <div class="w-[150px] text-right">上架售价 (In/Out)</div>
          <div class="w-[120px] text-right">最终 {{ pointUnitLabel }}</div>
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
          :key="group.provider"
          class="border-b border-slate-200 bg-white last:border-b-0"
        >
          <div
            class="flex items-center gap-2 border-b border-slate-200 bg-slate-50 px-4 py-2 text-[13px] font-bold text-slate-700"
          >
            <span class="inline-block h-1.5 w-1.5 rounded-full bg-indigo-500" />
            供货商：{{ group.provider }}
          </div>
          <div
            v-for="srcGroup in group.sources"
            :key="`${group.provider}-${srcGroup.source}`"
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
              class="flex flex-col gap-3 px-4 py-3 transition hover:bg-indigo-50/40 lg:flex-row lg:items-center lg:gap-0"
              :class="{ 'bg-indigo-50/30': row.selected }"
            >
              <label
                class="flex w-full items-center gap-3 lg:w-[280px] lg:pl-12"
              >
                <input
                  v-model="row.selected"
                  type="checkbox"
                  class="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                  @change="syncSelectedChain"
                />
                <span class="font-mono text-[13px] font-bold text-slate-900">{{
                  row.modelName
                }}</span>
                <span
                  v-if="row.isLowest"
                  class="rounded-full border border-emerald-100 bg-emerald-50 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-700"
                >
                  最低
                </span>
              </label>

              <div class="flex w-full gap-4 text-[12px] lg:w-[140px]">
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

              <div class="flex-1 min-w-[220px] pr-4">
                <select
                  v-if="row.selected"
                  v-model="row.upstreamAccount"
                  class="field-select w-full max-w-[260px]"
                  :class="{
                    '!border-rose-300 focus:!ring-rose-100':
                      !row.upstreamAccount
                  }"
                >
                  <option value="">必填：选择结算密钥账号</option>
                  <option
                    v-for="acc in upstreamAccounts"
                    :key="acc.id"
                    :value="acc.id"
                  >
                    {{ acc.name }}
                  </option>
                </select>
                <span v-else class="text-[11px] italic text-slate-400"
                  >请先勾选左侧以配置账号</span
                >
              </div>

              <div
                class="flex w-full justify-between gap-4 text-[12px] lg:w-[150px] lg:justify-end"
              >
                <span class="text-slate-500 lg:hidden">售价</span>
                <span class="font-mono font-bold text-emerald-600">
                  <span v-if="row.selected"
                    >{{ row.priceIn }} / {{ row.priceOut }}</span
                  >
                  <span v-else class="text-slate-400">-</span>
                </span>
              </div>

              <div
                class="flex w-full justify-between gap-4 text-[12px] lg:w-[120px] lg:justify-end"
              >
                <span class="text-slate-500 lg:hidden">Credit</span>
                <span class="font-mono font-bold text-indigo-600">
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
      class="grid gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]"
    >
      <aside
        class="workspace-section sticky top-0 overflow-hidden self-start p-0"
      >
        <header
          class="flex items-center gap-2 bg-slate-900 px-5 py-3.5 text-white"
        >
          <span class="inline-block h-2 w-2 rounded-full bg-emerald-400" />
          <h3 class="text-sm font-bold">链路性能全景对标</h3>
        </header>
        <div class="max-h-[60vh] space-y-5 overflow-y-auto p-5">
          <div v-for="metric in perfMetrics" :key="metric.key">
            <p
              class="mb-3 flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-slate-500"
            >
              {{ metric.label }}
            </p>
            <div class="space-y-2">
              <div
                v-for="item in perfCompareRows"
                :key="`${metric.key}-${item.name}`"
                class="flex items-center gap-3"
              >
                <div
                  class="w-[140px] truncate text-[11px] text-slate-600"
                  :title="item.name"
                >
                  {{ item.name }}
                </div>
                <div
                  class="h-2 flex-1 overflow-hidden rounded-full bg-slate-100"
                >
                  <div
                    class="h-full rounded-full transition-all"
                    :class="metric.barClass()"
                    :style="{ width: barWidth(item[metric.key], metric.max) }"
                  />
                </div>
                <div
                  class="w-[60px] text-right font-mono text-[11px] font-bold text-slate-700"
                >
                  {{ metric.format(item[metric.key]) }}
                </div>
              </div>
              <p
                v-if="!perfCompareRows.length"
                class="text-[11px] text-slate-400"
              >
                暂无对比数据
              </p>
            </div>
          </div>
        </div>
      </aside>

      <div class="space-y-4">
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
              {{ row.modelName }}
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
              <div class="flex flex-wrap items-end gap-3">
                <div class="w-[60px] text-[13px] font-bold text-slate-500">
                  Input
                </div>
                <div class="w-[100px]">
                  <p class="mb-1 text-[11px] text-slate-500">本链成本</p>
                  <p class="font-mono text-[13px] font-bold text-slate-900">
                    {{ currencySymbol }}{{ row.costIn }}
                  </p>
                </div>
                <div class="w-[120px]">
                  <p class="mb-1 text-[11px] text-slate-500">利润期望 (%)</p>
                  <div
                    class="flex items-center rounded border border-slate-200 focus-within:border-indigo-300 focus-within:ring-2 focus-within:ring-indigo-100"
                  >
                    <input
                      v-model.number="row.marginIn"
                      type="number"
                      class="w-full bg-transparent px-2 py-1.5 text-right text-[12px] focus:outline-none"
                      step="0.1"
                      min="0"
                      @input="onMarginChange(row, 'In')"
                    />
                    <span
                      class="border-l border-slate-200 px-2 text-[11px] text-slate-400"
                      >%</span
                    >
                  </div>
                </div>
                <div class="flex items-end gap-3">
                  <div class="w-[150px]">
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
                        v-model.number="row.priceInRaw"
                        type="number"
                        class="w-full bg-transparent px-2 py-1.5 text-right font-mono text-[12px] focus:outline-none"
                        step="0.0001"
                        min="0"
                        @input="onPriceChange(row, 'In')"
                      />
                    </div>
                  </div>
                  <div
                    v-if="marketAvg.in > 0"
                    class="flex h-[26px] items-center gap-1.5 whitespace-nowrap rounded border border-slate-200 bg-slate-50 px-2 text-[10px]"
                  >
                    <span class="font-mono text-slate-500"
                      >均价 {{ currencySymbol }}{{ marketAvg.in }}</span
                    >
                    <span
                      class="border-l border-slate-200 pl-1.5 font-bold"
                      :class="priceDiffClass(row.priceInRaw, marketAvg.in)"
                    >
                      {{ priceDiffText(row.priceInRaw, marketAvg.in) }}
                    </span>
                  </div>
                </div>
                <div class="flex-1 flex justify-end">
                  <div class="w-[110px] rounded bg-indigo-50 p-2 text-center">
                    <p class="text-[10px] text-indigo-600">
                      最终 {{ pointUnitLabel }}
                    </p>
                    <p class="font-mono text-[12px] font-bold text-indigo-700">
                      {{ formatCredit(row.costInRaw, row.marginIn) }}
                    </p>
                  </div>
                </div>
              </div>
              <BulletChart
                :min="bulletRange.in.min"
                :max="bulletRange.in.max"
                :value="row.priceInRaw"
                :refs="bulletRefsIn"
                :label="`我方售价 ${currencySymbol}${row.priceIn}`"
                :currency-symbol="currencySymbol"
              />
            </div>

            <div class="space-y-3">
              <div class="flex flex-wrap items-end gap-3">
                <div class="w-[60px] text-[13px] font-bold text-slate-500">
                  Output
                </div>
                <div class="w-[100px]">
                  <p class="mb-1 text-[11px] text-slate-500">本链成本</p>
                  <p class="font-mono text-[13px] font-bold text-slate-900">
                    {{ currencySymbol }}{{ row.costOut }}
                  </p>
                </div>
                <div class="w-[120px]">
                  <p class="mb-1 text-[11px] text-slate-500">利润期望 (%)</p>
                  <div
                    class="flex items-center rounded border border-slate-200 focus-within:border-indigo-300 focus-within:ring-2 focus-within:ring-indigo-100"
                  >
                    <input
                      v-model.number="row.marginOut"
                      type="number"
                      class="w-full bg-transparent px-2 py-1.5 text-right text-[12px] focus:outline-none"
                      step="0.1"
                      min="0"
                      @input="onMarginChange(row, 'Out')"
                    />
                    <span
                      class="border-l border-slate-200 px-2 text-[11px] text-slate-400"
                      >%</span
                    >
                  </div>
                </div>
                <div class="flex items-end gap-3">
                  <div class="w-[150px]">
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
                        v-model.number="row.priceOutRaw"
                        type="number"
                        class="w-full bg-transparent px-2 py-1.5 text-right font-mono text-[12px] focus:outline-none"
                        step="0.0001"
                        min="0"
                        @input="onPriceChange(row, 'Out')"
                      />
                    </div>
                  </div>
                  <div
                    v-if="marketAvg.out > 0"
                    class="flex h-[26px] items-center gap-1.5 whitespace-nowrap rounded border border-slate-200 bg-slate-50 px-2 text-[10px]"
                  >
                    <span class="font-mono text-slate-500"
                      >均价 {{ currencySymbol }}{{ marketAvg.out }}</span
                    >
                    <span
                      class="border-l border-slate-200 pl-1.5 font-bold"
                      :class="priceDiffClass(row.priceOutRaw, marketAvg.out)"
                    >
                      {{ priceDiffText(row.priceOutRaw, marketAvg.out) }}
                    </span>
                  </div>
                </div>
                <div class="flex-1 flex justify-end">
                  <div class="w-[110px] rounded bg-indigo-50 p-2 text-center">
                    <p class="text-[10px] text-indigo-600">
                      最终 {{ pointUnitLabel }}
                    </p>
                    <p class="font-mono text-[12px] font-bold text-indigo-700">
                      {{ formatCredit(row.costOutRaw, row.marginOut) }}
                    </p>
                  </div>
                </div>
              </div>
              <BulletChart
                :min="bulletRange.out.min"
                :max="bulletRange.out.max"
                :value="row.priceOutRaw"
                :refs="bulletRefsOut"
                :label="`我方售价 ${currencySymbol}${row.priceOut}`"
                :currency-symbol="currencySymbol"
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
      请在链路甄选面板中勾选至少一条供应链路，继续定价。
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import BulletChart from '@/components/llm-ops/BulletChart.vue'

const props = defineProps({
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
  providerId: '',
  modelId: ''
})

const globalPricing = ref({
  exchangeRate: 7.23,
  creditRatio: 10
})

const isSupplyChainExpanded = ref(true)

const providerOptions = computed(() => props.providers || [])

const procurementByModel = computed(() => {
  const map = new Map()
  ;(props.procurementRows || []).forEach((row) => {
    map.set(String(row.model_id), row)
  })
  return map
})

const baseModelOptions = computed(() => {
  const providerId = form.value.providerId
  return (props.procurementRows || [])
    .filter((row) => {
      if (!providerId) return true
      const model = (props.models || []).find(
        (m) => String(m.id) === String(row.model_id)
      )
      if (!model) return true
      return (
        String(model.provider) === String(providerId) ||
        String(model.provider_id) === String(providerId)
      )
    })
    .map((row) => ({
      id: row.model_id,
      name:
        (props.models || []).find((m) => String(m.id) === String(row.model_id))
          ?.meta_model_name ||
        row.model_name ||
        row.model_code
    }))
})

const pointUnitLabel = computed(
  () => props.pointConversion?.point_name || '积分'
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

function onProviderChange() {
  form.value.modelId = ''
  isSupplyChainExpanded.value = true
}

function onModelChange() {
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

const chainRows = computed(() => {
  if (!form.value.modelId) return []
  const procurement = procurementByModel.value.get(String(form.value.modelId))
  if (!procurement) return []
  const options = procurement.options || []
  return options
    .map((option) => {
      const inDisplay = convertToDisplay(
        option.input_price_per_million,
        option.currency
      )
      const outDisplay = convertToDisplay(
        option.output_price_per_million,
        option.currency
      )
      return {
        uniqueId: `${option.channel_id}-${procurement.model_id}`,
        channelId: option.channel_id,
        channelName: option.channel_name,
        provider: procurement.provider_name || procurement.model_name,
        source: option.channel_name,
        modelId: procurement.model_id,
        modelName: procurement.model_name || procurement.model_code,
        costInRaw: inDisplay ?? 0,
        costOutRaw: outDisplay ?? 0,
        costIn: inDisplay !== null ? inDisplay.toFixed(4) : '-',
        costOut: outDisplay !== null ? outDisplay.toFixed(4) : '-',
        selected: false,
        upstreamAccount: '',
        marginIn: 20,
        marginOut: 20,
        priceInRaw: null,
        priceOutRaw: null,
        isLowest: false
      }
    })
    .sort((a, b) => Number(a.costInRaw) - Number(b.costInRaw))
    .map((row, idx) => ({ ...row, isLowest: idx === 0 }))
})

const selectedChainRows = computed(() =>
  chainRows.value.filter((r) => r.selected)
)

const groupedChainRows = computed(() => {
  const map = new Map()
  selectedChainRows.value.forEach((row) => {
    if (!map.has(row.provider)) {
      map.set(row.provider, { provider: row.provider, sources: new Map() })
    }
    const sMap = map.get(row.provider).sources
    if (!sMap.has(row.source)) {
      sMap.set(row.source, { source: row.source, models: [] })
    }
    sMap.get(row.source).models.push(row)
  })
  return Array.from(map.values()).map((g) => ({
    provider: g.provider,
    sources: Array.from(g.sources.values())
  }))
})

const upstreamAccounts = computed(() =>
  (props.channels || []).map((c) => ({ id: String(c.id), name: c.name }))
)

function syncSelectedChain() {
  selectedChainRows.value.forEach((r) => {
    if (r.priceInRaw === null) {
      r.priceInRaw = Number(
        (r.costInRaw * (1 + (Number(r.marginIn) || 0) / 100)).toFixed(4)
      )
    }
    if (r.priceOutRaw === null) {
      r.priceOutRaw = Number(
        (r.costOutRaw * (1 + (Number(r.marginOut) || 0) / 100)).toFixed(4)
      )
    }
  })
  emitChange()
}

function onMarginChange(row, dir) {
  const cost = dir === 'In' ? row.costInRaw : row.costOutRaw
  const margin = dir === 'In' ? row.marginIn : row.marginOut
  const price = Number(cost) * (1 + (Number(margin) || 0) / 100)
  if (dir === 'In') {
    row.priceInRaw = Number(price.toFixed(4))
  } else {
    row.priceOutRaw = Number(price.toFixed(4))
  }
  emitChange()
}

function onPriceChange(row, dir) {
  const cost = dir === 'In' ? row.costInRaw : row.costOutRaw
  const price = dir === 'In' ? row.priceInRaw : row.priceOutRaw
  if (Number(cost) <= 0) return
  const margin = ((Number(price) - Number(cost)) / Number(cost)) * 100
  if (dir === 'In') row.marginIn = Number(margin.toFixed(2))
  else row.marginOut = Number(margin.toFixed(2))
  emitChange()
}

function formatCredit(cost, margin) {
  const c = Number(cost) || 0
  const m = Number(margin) || 0
  const rate = Number(globalPricing.value.creditRatio) || 0
  const price = c * (1 + m / 100)
  return (price * rate).toFixed(2)
}

function priceDiffText(price, avg) {
  const p = Number(price)
  const a = Number(avg)
  if (!Number.isFinite(p) || !Number.isFinite(a) || a === 0) return '-'
  const diff = p - a
  const pct = Math.abs((diff / a) * 100).toFixed(1)
  if (diff < -0.00001) return `↓ 低 ${pct}%`
  if (diff > 0.00001) return `↑ 高 ${pct}%`
  return '- 持平'
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

const marketAvg = computed(() => {
  const refs = (props.priceItems || []).filter(
    (it) => String(it.model) === String(form.value.modelId)
  )
  if (!refs.length) return { in: 0, out: 0 }
  let inSum = 0
  let outSum = 0
  let inCount = 0
  let outCount = 0
  refs.forEach((it) => {
    const inV = convertToDisplay(it.input_price_per_million, it.currency)
    const outV = convertToDisplay(it.output_price_per_million, it.currency)
    if (inV !== null) {
      inSum += inV
      inCount += 1
    }
    if (outV !== null) {
      outSum += outV
      outCount += 1
    }
  })
  return {
    in: inCount > 0 ? Number((inSum / inCount).toFixed(4)) : 0,
    out: outCount > 0 ? Number((outSum / outCount).toFixed(4)) : 0
  }
})

const bulletRefsIn = computed(() => {
  return (props.priceItems || [])
    .filter((it) => String(it.model) === String(form.value.modelId))
    .map((it) => ({
      source: it.source_name || it.vendor_name || '市场参考',
      price: convertToDisplay(it.input_price_per_million, it.currency) || 0
    }))
    .filter((r) => r.price > 0)
})

const bulletRefsOut = computed(() => {
  return (props.priceItems || [])
    .filter((it) => String(it.model) === String(form.value.modelId))
    .map((it) => ({
      source: it.source_name || it.vendor_name || '市场参考',
      price: convertToDisplay(it.output_price_per_million, it.currency) || 0
    }))
    .filter((r) => r.price > 0)
})

const bulletRange = computed(() => {
  const inMinCandidates = [
    ...selectedChainRows.value.map((r) => Number(r.costInRaw) || 0),
    ...bulletRefsIn.value.map((r) => r.price),
    marketAvg.value.in
  ]
  const inMaxCandidates = [
    ...selectedChainRows.value.map((r) => Number(r.priceInRaw) || 0),
    ...bulletRefsIn.value.map((r) => r.price)
  ]
  const outMinCandidates = [
    ...selectedChainRows.value.map((r) => Number(r.costOutRaw) || 0),
    ...bulletRefsOut.value.map((r) => r.price),
    marketAvg.value.out
  ]
  const outMaxCandidates = [
    ...selectedChainRows.value.map((r) => Number(r.priceOutRaw) || 0),
    ...bulletRefsOut.value.map((r) => r.price)
  ]
  const inMin = Math.min(...inMinCandidates)
  const inMax = Math.max(...inMaxCandidates)
  const outMin = Math.min(...outMinCandidates)
  const outMax = Math.max(...outMaxCandidates)
  return {
    in: {
      min: Number.isFinite(inMin) && inMin > 0 ? inMin : 0.0001,
      max: Number.isFinite(inMax) && inMax > 0 ? inMax * 1.5 : 0.01
    },
    out: {
      min: Number.isFinite(outMin) && outMin > 0 ? outMin : 0.0001,
      max: Number.isFinite(outMax) && outMax > 0 ? outMax * 1.5 : 0.01
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
    providerId: form.value.providerId,
    modelId: form.value.modelId,
    listings: selectedChainRows.value.map((row) => ({
      channelId: row.channelId,
      modelId: row.modelId,
      upstreamAccount: row.upstreamAccount,
      priceIn: row.priceInRaw,
      priceOut: row.priceOutRaw,
      marginIn: row.marginIn,
      marginOut: row.marginOut
    }))
  })
}

defineExpose({
  reset() {
    form.value = { platformId: '', providerId: '', modelId: '' }
  },
  getPayload() {
    return {
      platformId: form.value.platformId,
      providerId: form.value.providerId,
      modelId: form.value.modelId,
      listings: selectedChainRows.value.map((row) => ({
        channelId: row.channelId,
        modelId: row.modelId,
        upstreamAccount: row.upstreamAccount,
        priceIn: row.priceInRaw,
        priceOut: row.priceOutRaw,
        marginIn: row.marginIn,
        marginOut: row.marginOut
      }))
    }
  }
})
</script>

<style scoped>
.workspace-shell {
  @apply flex flex-col gap-4;
}

.workspace-section {
  @apply rounded-xl border border-slate-200 bg-white shadow-sm;
}

.field-select {
  @apply rounded-md border border-slate-200 bg-white px-2 py-1.5 text-[12px] font-medium text-slate-700 transition focus:border-indigo-300 focus:outline-none focus:ring-2 focus:ring-indigo-100 disabled:cursor-not-allowed disabled:opacity-60;
}

.btn-secondary {
  @apply inline-flex items-center rounded-md border border-slate-200 bg-white px-3 py-1.5 text-[12px] font-medium text-slate-700 transition hover:border-slate-300 hover:bg-slate-50;
}
</style>
