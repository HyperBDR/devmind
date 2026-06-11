<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition-opacity duration-200"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition-opacity duration-200"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="open"
        class="fixed inset-0 z-50 flex justify-end bg-slate-950/30"
        @click.self="tryClose"
      >
        <Transition
          enter-active-class="transition-transform duration-300 ease-out"
          enter-from-class="translate-x-full"
          enter-to-class="translate-x-0"
          leave-active-class="transition-transform duration-200 ease-in"
          leave-from-class="translate-x-0"
          leave-to-class="translate-x-full"
        >
          <aside
            v-if="open"
            class="listing-drawer-panel flex h-full flex-col bg-white shadow-xl"
          >
            <header class="drawer-header">
              <div class="min-w-0 flex-1">
                <p
                  class="text-xs font-semibold uppercase tracking-[0.18em] text-indigo-600"
                >
                  {{ platformLabel }}
                </p>
                <h2 class="mt-1 truncate text-base font-semibold text-slate-900">
                  {{ headerTitle }}
                </h2>
                <p class="mt-0.5 text-xs text-slate-500">
                  积分换算：{{ rows.pointFormulaLabel.value }}
                </p>
              </div>
              <button
                type="button"
                class="drawer-close"
                :disabled="savingTrendListing"
                @click="tryClose"
              >
                关闭
              </button>
            </header>

            <nav class="drawer-stepper" aria-label="挂售步骤">
              <button
                v-for="step in steps"
                :key="step.id"
                type="button"
                class="stepper-item"
                :class="stepClass(step.id)"
                :disabled="!canAdvanceToStep[step.id] && step.id > currentStep"
                @click="goToStep(step.id)"
              >
                <span class="stepper-dot">{{ step.id }}</span>
                <span class="stepper-title">{{ step.title }}</span>
              </button>
            </nav>

            <div class="drawer-body">
              <!-- Step 1: 选择模型 -->
              <section v-if="currentStep === 1" class="step-section">
                <p class="step-hint">
                  先选择要在 {{ platformLabel }} 上架的模型；只有已配置至少一个采购渠道的模型可以继续。
                </p>
                <CompactSelect
                  v-model="selectedTrendModelId"
                  :options="rows.trendModelOptions.value"
                  class-name="w-full"
                  placeholder="搜索模型"
                  searchable
                  search-placeholder="搜索模型名称 / code / 厂商"
                />
                <div
                  v-if="rows.selectedTrendRow.value"
                  class="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm"
                >
                  <p class="font-medium text-slate-900">
                    {{ rows.modelDisplayName(rows.selectedTrendRow.value.model) }}
                  </p>
                  <p class="mt-1 text-xs text-slate-500">
                    {{ rows.listingModelSubtitle(rows.selectedTrendRow.value) }}
                  </p>
                  <p class="mt-2 text-xs text-slate-500">
                    {{ rows.selectedTrendRow.value.options.length }} 个采购渠道 ·
                    {{ rows.selectedTrendRow.value.active_listings.length }} 个已上架
                  </p>
                </div>
                <div class="mt-6 flex justify-end">
                  <button
                    type="button"
                    class="btn-primary"
                    :disabled="!canContinueFromModelStep"
                    @click="goToStep(2)"
                  >
                    下一步：选择渠道
                  </button>
                </div>
              </section>

              <!-- Step 2: 选择采购渠道 -->
              <section v-else-if="currentStep === 2" class="step-section">
                <p class="step-hint">
                  从可采购该模型的渠道中选一个；选完后会自动按当前利润率折算建议售价。
                </p>
                <div class="space-y-2">
                  <button
                    v-for="row in rows.supplyDecisionRows.value"
                    :key="row.key"
                    type="button"
                    class="channel-row"
                    :class="{ 'channel-row-selected': row.is_selected }"
                    @click="selectChannel(row)"
                  >
                    <div class="flex items-center justify-between gap-3">
                      <div class="min-w-0">
                        <p class="truncate text-sm font-medium text-slate-900">
                          {{ row.channel_name }}
                        </p>
                        <p class="mt-0.5 text-xs text-slate-500">
                          成本 {{ row.cost_summary }} · 建议 {{ row.proposed_summary }}
                        </p>
                      </div>
                      <div class="flex items-center gap-2">
                        <span
                          v-if="row.is_lowest"
                          class="badge-ok"
                        >
                          最低采购
                        </span>
                        <span
                          v-else-if="row.gap_label"
                          class="badge-warn"
                        >
                          {{ row.gap_label }}
                        </span>
                        <span
                          v-if="row.is_listed"
                          class="badge-muted"
                        >
                          当前已上架
                        </span>
                      </div>
                    </div>
                  </button>
                  <p
                    v-if="!rows.supplyDecisionRows.value.length"
                    class="text-sm text-slate-500"
                  >
                    当前模型暂无可用采购渠道。
                  </p>
                </div>

                <details class="mt-4 rounded-lg border border-slate-200 bg-slate-50">
                  <summary class="cursor-pointer px-3 py-2 text-sm font-medium text-slate-700">
                    历史价格趋势
                  </summary>
                  <div class="border-t border-slate-200 bg-white p-3">
                    <p v-if="!rows.selectedTrendRow.value?.model?.id" class="text-xs text-slate-500">
                      请先选择模型后再查看历史。
                    </p>
                    <div v-else-if="historyLoading" class="text-xs text-slate-500">
                      价格历史加载中…
                    </div>
                    <div v-else-if="!priceChartData" class="text-xs text-slate-500">
                      暂无历史数据。
                    </div>
                    <div v-else class="h-64 min-w-0">
                      <Line
                        :data="priceChartData"
                        :options="priceChartOptions"
                      />
                    </div>
                  </div>
                </details>

                <div class="mt-6 flex justify-between">
                  <button
                    type="button"
                    class="btn-secondary"
                    @click="goToStep(1)"
                  >
                    上一步
                  </button>
                  <button
                    type="button"
                    class="btn-primary"
                    :disabled="!rows.selectedTrendOption.value"
                    @click="goToStep(3)"
                  >
                    下一步：设置利润率
                  </button>
                </div>
              </section>

              <!-- Step 3: 设置利润率 -->
              <section v-else-if="currentStep === 3" class="step-section">
                <p class="step-hint">
                  调整利润率后，下方会按选定渠道的成本实时折算拟上架价。
                </p>
                <div class="rounded-lg border border-slate-200 bg-slate-50 p-3">
                  <p class="text-xs text-slate-500">当前渠道</p>
                  <p class="mt-1 text-sm font-medium text-slate-900">
                    {{ rows.selectedTrendOption.value?.channel_name || '-' }}
                  </p>
                  <p class="mt-1 text-xs text-slate-500">
                    {{ rows.metricPriceSummary(rows.selectedTrendOption.value?.metric_values) }}
                  </p>
                </div>
                <label class="field-group mt-4">
                  <span class="field-label">利润率 %</span>
                  <input
                    v-model="trendProfitRate"
                    class="field"
                    type="number"
                    step="1"
                    min="0"
                    placeholder="20"
                  />
                </label>
                <div class="mt-4 rounded-lg border border-emerald-100 bg-emerald-50/60 p-3">
                  <p class="text-xs font-medium text-emerald-700">拟上架价</p>
                  <div class="mt-2 flex flex-wrap gap-2">
                    <span
                      v-for="item in rows.proposedListingPrices.value"
                      :key="item.key"
                      class="proposed-chip"
                    >
                      <strong>
                        {{ item.label }}
                        {{ rows.money(item.value, rows.selectedTrendCurrency.value) }}
                      </strong>
                      <small>{{ points(item.value) }}</small>
                    </span>
                    <span
                      v-if="!rows.proposedListingPrices.value.length"
                      class="text-xs text-slate-500"
                    >
                      请先选择渠道。
                    </span>
                  </div>
                </div>
                <p class="mt-3 text-xs text-slate-500">
                  {{ rows.trendActionHint.value }}
                </p>
                <div class="mt-6 flex justify-between">
                  <button
                    type="button"
                    class="btn-secondary"
                    @click="goToStep(2)"
                  >
                    上一步
                  </button>
                  <button
                    type="button"
                    class="btn-primary"
                    :disabled="!rows.canSaveTrendListing.value"
                    @click="goToStep(4)"
                  >
                    下一步：确认上架
                  </button>
                </div>
              </section>

              <!-- Step 4: 确认上架 -->
              <section v-else-if="currentStep === 4" class="step-section">
                <p class="step-hint">
                  确认以下信息后，保存即把该渠道挂售到 {{ platformLabel }}。
                </p>
                <dl class="confirm-grid">
                  <div>
                    <dt>模型</dt>
                    <dd>
                      {{ rows.modelDisplayName(rows.selectedTrendRow.value?.model) }}
                    </dd>
                  </div>
                  <div>
                    <dt>采购渠道</dt>
                    <dd>
                      {{ rows.selectedTrendOption.value?.channel_name || '-' }}
                    </dd>
                  </div>
                  <div>
                    <dt>利润率</dt>
                    <dd>{{ trendProfitRate }}%</dd>
                  </div>
                  <div>
                    <dt>状态</dt>
                    <dd>{{ rows.selectedDecisionStatusLabel.value }}</dd>
                  </div>
                </dl>
                <div class="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3">
                  <p class="text-xs font-medium text-slate-700">拟上架价</p>
                  <div class="mt-2 flex flex-wrap gap-2">
                    <span
                      v-for="item in rows.proposedListingPrices.value"
                      :key="item.key"
                      class="proposed-chip"
                    >
                      <strong>
                        {{ item.label }}
                        {{ rows.money(item.value, rows.selectedTrendCurrency.value) }}
                      </strong>
                      <small>{{ points(item.value) }}</small>
                    </span>
                  </div>
                </div>
                <p class="mt-3 text-xs text-slate-500">
                  {{ rows.trendActionHint.value }}
                </p>
                <div class="mt-6 flex justify-between">
                  <button
                    type="button"
                    class="btn-secondary"
                    @click="goToStep(3)"
                  >
                    上一步
                  </button>
                </div>
              </section>
            </div>

            <footer
              v-if="currentStep === 4"
              class="drawer-footer"
            >
              <span class="text-xs text-slate-500">
                {{ rows.trendActionHint.value }}
              </span>
              <div class="flex flex-wrap gap-2">
                <button
                  v-if="rows.canSwitchTrendListing.value"
                  type="button"
                  class="btn-secondary"
                  :disabled="savingTrendListing"
                  @click="saveTrendListing(true)"
                >
                  <span
                    class="icon-mark"
                    :class="savingTrendListing ? 'animate-spin' : ''"
                  />
                  切换上架
                </button>
                <button
                  type="button"
                  class="btn-primary"
                  :disabled="!rows.canSaveTrendListing.value || savingTrendListing"
                  @click="saveTrendListing(false)"
                >
                  <span
                    class="icon-mark"
                    :class="savingTrendListing ? 'animate-spin' : ''"
                  />
                  {{ rows.trendPrimaryActionLabel.value }}
                </button>
              </div>
            </footer>
          </aside>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, toRef, watch } from 'vue'
import { Line } from 'vue-chartjs'
import {
  CategoryScale,
  Chart as ChartJS,
  Filler,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip
} from 'chart.js'
import { llmOpsApi } from '@/api/llmOps'
import CompactSelect from '@/components/llm-ops/CompactSelect.vue'
import { useToast } from '@/composables/useToast'
import { useAgioneListingRows } from '@/composables/useAgioneListingRows'

ChartJS.register(
  CategoryScale,
  Filler,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip
)

const props = defineProps({
  open: {
    type: Boolean,
    default: false
  },
  modelId: {
    type: [String, Number, null],
    default: null
  },
  agionePlatform: {
    type: Object,
    default: null
  },
  providers: {
    type: Array,
    required: true
  },
  models: {
    type: Array,
    required: true
  },
  priceItems: {
    type: Array,
    default: () => []
  },
  listings: {
    type: Array,
    required: true
  },
  listingExclusions: {
    type: Array,
    default: () => []
  },
  summary: {
    type: Object,
    required: true
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

const emit = defineEmits(['update:open', 'saved'])
const { showSuccess, showError } = useToast()

const FULL_LIST_PARAMS = { page_size: 10000 }
const currentStep = ref(1)
const selectedTrendModelId = ref('')
const selectedTrendChannelId = ref('')
const trendProfitRate = ref('20')
const trendProfitRateInitial = ref('20')
const savingTrendListing = ref(false)
const priceHistory = ref([])
const channelPriceHistory = ref([])
const listingPriceHistory = ref([])
const historyLoading = ref(false)

const steps = [
  { id: 1, title: '选择模型' },
  { id: 2, title: '选择渠道' },
  { id: 3, title: '设置利润率' },
  { id: 4, title: '确认上架' }
]

const platformLabel = computed(
  () => props.agionePlatform?.name || '挂售平台'
)

const headerTitle = computed(() => {
  const model = rows.selectedTrendModel.value
  if (model) {
    return `挂售价格决策 · ${rows.modelDisplayName(model)}`
  }
  return '挂售价格决策'
})

const rows = useAgioneListingRows({
  agionePlatformRef: toRef(props, 'agionePlatform'),
  providersRef: toRef(props, 'providers'),
  modelsRef: toRef(props, 'models'),
  priceItemsRef: toRef(props, 'priceItems'),
  listingsRef: toRef(props, 'listings'),
  listingExclusionsRef: toRef(props, 'listingExclusions'),
  summaryRef: toRef(props, 'summary'),
  displayCurrencyRef: toRef(props, 'displayCurrency'),
  exchangeRateRef: toRef(props, 'exchangeRate'),
  selectedTrendModelIdRef: selectedTrendModelId,
  selectedTrendChannelIdRef: selectedTrendChannelId,
  trendProfitRateRef: trendProfitRate,
  pointConversionRef: toRef(props, 'pointConversion')
})

const canAdvanceToStep = computed(() => ({
  1: true,
  2: canContinueFromModelStep.value,
  3: !!rows.selectedTrendOption.value,
  4: rows.canSaveTrendListing.value
}))

const canContinueFromModelStep = computed(
  () =>
    !!rows.selectedTrendRow.value &&
    rows.selectedTrendRow.value.options.length > 0
)

function stepClass(stepId) {
  if (stepId < currentStep.value) return 'stepper-item-done'
  if (stepId === currentStep.value) return 'stepper-item-active'
  return 'stepper-item-idle'
}

function goToStep(target) {
  if (target === 1) {
    currentStep.value = 1
    return
  }
  if (canAdvanceToStep.value[target]) {
    currentStep.value = target
  }
}

function selectChannel(row) {
  selectedTrendChannelId.value = row.channel_id
}

function hasUnsavedChanges() {
  return trendProfitRate.value !== trendProfitRateInitial.value
}

function tryClose() {
  if (hasUnsavedChanges()) {
    if (!confirm('有未保存的修改，确定关闭抽屉？')) return
  }
  emit('update:open', false)
}

function handleKeydown(event) {
  if (event.key === 'Escape' && props.open) {
    tryClose()
  }
}

onMounted(() => {
  document.addEventListener('keydown', handleKeydown)
})
onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown)
})

// Open lifecycle: reset state when the drawer opens with a fresh modelId.
watch(
  [() => props.open, () => props.modelId],
  ([nextOpen, nextModelId], [prevOpen, prevModelId]) => {
    if (nextOpen && (!prevOpen || String(prevModelId) !== String(nextModelId))) {
      currentStep.value = 1
      selectedTrendModelId.value = resolveTrendModelKey(nextModelId)
      selectedTrendChannelId.value = ''
      const initial = '20'
      trendProfitRate.value = initial
      trendProfitRateInitial.value = initial
    }
  },
  { immediate: true }
)

watch(
  () => rows.trendRows.value.map((row) => `${row.key}:${row.model.id}`).join(','),
  () => {
    if (!props.open || !props.modelId) return
    const next = resolveTrendModelKey(props.modelId)
    if (next && String(selectedTrendModelId.value) !== String(next)) {
      selectedTrendModelId.value = next
    }
  },
  { immediate: true }
)

// When the model list arrives/changes, default the selection if needed.
watch(
  () => rows.actionableTrendRows.value.map((row) => row.key).join(','),
  () => {
    if (!selectedTrendModelId.value && rows.actionableTrendRows.value.length) {
      selectedTrendModelId.value = rows.defaultTrendRow()?.key || ''
    }
  },
  { immediate: true }
)

// After the channel options change, ensure a sane default channel.
watch(
  () => rows.trendChannelOptions.value.map((option) => option.channel_id).join(','),
  () => {
    const next = rows.ensureSelectedTrendChannel()
    if (next !== undefined) {
      selectedTrendChannelId.value = next
    }
  },
  { immediate: true }
)

// Fetch price history whenever the model changes.
watch(
  () => rows.selectedTrendRow.value?.model?.id,
  (modelId) => {
    if (!modelId) {
      priceHistory.value = []
      channelPriceHistory.value = []
      listingPriceHistory.value = []
      return
    }
    if (!props.open) return
    fetchPriceHistory()
  }
)

async function fetchPriceHistory() {
  if (!rows.selectedTrendRow.value?.model?.id) return
  historyLoading.value = true
  try {
    const [collectedRes, channelRes, listingRes] = await Promise.all([
      llmOpsApi.listCollectedPriceHistory({
        ...FULL_LIST_PARAMS,
        model: rows.selectedTrendRow.value.model.id
      }),
      llmOpsApi.listChannelModelPriceHistory({
        ...FULL_LIST_PARAMS,
        model: rows.selectedTrendRow.value.model.id
      }),
      llmOpsApi.listResaleListingPriceHistory({
        ...FULL_LIST_PARAMS,
        model: rows.selectedTrendRow.value.model.id,
        platform: props.agionePlatform?.id || ''
      })
    ])
    priceHistory.value = extract(collectedRes)
    channelPriceHistory.value = extract(channelRes)
    listingPriceHistory.value = extract(listingRes)
  } catch (error) {
    // silent: chart is auxiliary
  } finally {
    historyLoading.value = false
  }
}

function extract(response) {
  const data = response?.data?.data || response?.data || []
  return Array.isArray(data.results) ? data.results : data
}

function resolveTrendModelKey(value) {
  if (!value) return ''
  const direct = rows.trendRows.value.find(
    (row) => String(row.key) === String(value)
  )
  if (direct) return direct.key
  const byModelId = rows.trendRows.value.find((row) =>
    row.rows.some((item) => String(item.model.id) === String(value))
  )
  return byModelId?.key || ''
}

// Chart derivations (lightweight, just three series).
const chartLabels = computed(() => {
  const labels = new Map()
  const add = (value) => {
    if (!value) return
    const ts = new Date(value).getTime()
    if (!Number.isFinite(ts)) return
    const label = formatDateLabel(value)
    labels.set(label, Math.min(labels.get(label) || ts, ts))
  }
  priceHistory.value.forEach((row) => add(row.effective_from || row.collected_at))
  channelPriceHistory.value.forEach((row) => add(row.effective_from || row.created_at))
  listingPriceHistory.value.forEach((row) => add(row.effective_from || row.created_at))
  const values = labels.size
    ? Array.from(labels.entries())
        .sort((left, right) => left[1] - right[1])
        .map(([label]) => label)
    : ['当前']
  return values.length > 1 ? values : [...values, '决策价']
})

const priceChartData = computed(() => {
  if (!rows.selectedTrendRow.value) return null
  const labels = chartLabels.value
  const collected = labels.map((label) =>
    latestValueAtLabel(
      priceHistory.value,
      label,
      (row) => extractCollectedMetric(row),
      (row) => row.effective_from || row.collected_at
    )
  )
  const channel = labels.map((label) =>
    lowestValueAtLabel(
      channelPriceHistory.value,
      label,
      (row) => {
        const value = row.input_price_per_million
        return rows.convertCurrencyAmount(value, row.currency)
      },
      (row) => row.effective_from || row.created_at
    )
  )
  const listing = labels.map((label) =>
    lowestValueAtLabel(
      listingPriceHistory.value,
      label,
      (row) => {
        const value = row.retail_input_price_per_million
        return rows.convertCurrencyAmount(value, row.currency)
      },
      (row) => row.effective_from || row.created_at
    )
  )
  return {
    labels,
    datasets: [
      {
        label: '采集历史价',
        data: collected,
        borderColor: '#4f46e5',
        backgroundColor: 'rgba(79,70,229,0.08)',
        borderWidth: 2,
        fill: false,
        pointRadius: 3,
        tension: 0.3
      },
      {
        label: '渠道历史最低价',
        data: channel,
        borderColor: '#0891b2',
        backgroundColor: 'rgba(8,145,178,0.08)',
        borderWidth: 2,
        fill: false,
        pointRadius: 3,
        tension: 0.25
      },
      {
        label: `${platformLabel.value} 挂售历史`,
        data: listing,
        borderColor: '#dc2626',
        backgroundColor: 'rgba(220,38,38,0.08)',
        borderWidth: 2,
        fill: false,
        pointRadius: 3,
        tension: 0.25
      }
    ]
  }
})

const priceChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { position: 'bottom' } },
  scales: {
    y: { beginAtZero: true }
  }
}

function extractCollectedMetric(row) {
  const priceRows = row?.normalized_price_rows || []
  for (const priceRow of priceRows) {
    const values = priceRow.values || {}
    for (const key of ['input_price', 'image_input_price']) {
      const value = numeric(values[key])
      if (value !== null) return historyUnitPrice(value, row)
    }
  }
  return null
}

function historyUnitPrice(value, row) {
  const unit = numeric(row?.raw_price_info?.unit) || 1000000
  const normalized = (value * 1000000) / unit
  return rows.convertCurrencyAmount(
    normalized,
    row.currency || row.raw_price_info?.currency
  )
}

function numeric(value) {
  if (value === null || value === undefined || value === '') return null
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

function formatDateLabel(value) {
  if (!value) return '-'
  return new Date(value).toLocaleDateString()
}

function latestValueAtLabel(rows, label, getter, dateGetter) {
  const matches = rows.filter((row) => formatDateLabel(dateGetter(row)) === label)
  if (!matches.length) return null
  return getter(matches[matches.length - 1])
}

function lowestValueAtLabel(rows, label, getter, dateGetter) {
  const values = rows
    .filter((row) => formatDateLabel(dateGetter(row)) === label)
    .map(getter)
    .filter((value) => value !== null)
  if (!values.length) return null
  return Math.min(...values)
}

function points(value) {
  if (value === null || value === undefined || value === '') return '-'
  const rate = Number(props.pointConversion?.points_per_currency_unit || 0)
  if (!Number.isFinite(rate) || rate <= 0) return '-'
  const platformAmount = displayAmountToPlatformCurrency(value)
  if (platformAmount === null) return '-'
  const rawPoints = platformAmount * rate
  const mode = props.pointConversion?.rounding_mode || 'half_up'
  let pointValue = Math.round(rawPoints)
  if (mode === 'up') pointValue = Math.ceil(rawPoints)
  if (mode === 'down') pointValue = Math.floor(rawPoints)
  return `${pointValue} ${props.pointConversion?.point_name || '积分'}`
}

function displayAmountToPlatformCurrency(value) {
  const amount = Number(value)
  if (!Number.isFinite(amount)) return null
  const source = String(props.displayCurrency || 'CNY').toUpperCase()
  const target = String(props.pointConversion?.currency || source).toUpperCase()
  if (source === target) return amount
  if (source === 'USD' && target === 'CNY') {
    return amount * Number(props.exchangeRate || 7.15)
  }
  if (source === 'CNY' && target === 'USD') {
    return amount / Number(props.exchangeRate || 7.15)
  }
  return null
}

async function saveTrendListing(replaceExisting) {
  if (!rows.canSaveTrendListing.value || savingTrendListing.value) return
  savingTrendListing.value = true
  try {
    const payload = rows.buildTrendListingPayload()
    if (replaceExisting) {
      await llmOpsApi.bulkReplaceResaleListings([payload])
      showSuccess('已切换上架渠道')
    } else if (rows.selectedOptionIsListed.value) {
      await llmOpsApi.bulkUpsertResaleListings([payload])
      showSuccess('挂售价格已更新')
    } else {
      await llmOpsApi.bulkUpsertResaleListings([payload])
      showSuccess('已追加上架')
    }
    trendProfitRateInitial.value = trendProfitRate.value
    emit('saved')
  } catch (error) {
    const message =
      error?.response?.data?.detail ||
      error?.response?.data?.message ||
      error?.message ||
      ''
    showError(message || '保存失败')
  } finally {
    savingTrendListing.value = false
  }
}
</script>

<style scoped>
.listing-drawer-panel {
  width: min(100vw, 560px);
}

@media (min-width: 1024px) {
  .listing-drawer-panel {
    width: min(60vw, 720px);
  }
}

.drawer-header {
  @apply sticky top-0 z-10 flex items-start gap-3 border-b border-slate-200 bg-white px-5 py-4;
}

.drawer-close {
  @apply inline-flex items-center rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60;
}

.drawer-stepper {
  @apply flex flex-col gap-1 border-b border-slate-100 bg-slate-50 px-5 py-3;
}

.stepper-item {
  @apply flex items-center gap-3 rounded-md px-2 py-1.5 text-left text-sm transition disabled:cursor-not-allowed;
}

.stepper-item-idle {
  @apply text-slate-400 disabled:opacity-100;
}

.stepper-item-done {
  @apply text-slate-700 hover:bg-white;
}

.stepper-item-active {
  @apply bg-white text-slate-900 shadow-sm;
}

.stepper-dot {
  @apply inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold;
}

.stepper-item-idle .stepper-dot {
  @apply bg-slate-200 text-slate-500;
}

.stepper-item-done .stepper-dot {
  @apply bg-emerald-500 text-white;
}

.stepper-item-active .stepper-dot {
  @apply border-2 border-indigo-500 bg-white text-indigo-600;
}

.stepper-title {
  @apply truncate text-sm font-medium;
}

.drawer-body {
  @apply flex-1 overflow-y-auto px-5 py-5;
}

.step-section {
  @apply space-y-4;
}

.step-hint {
  @apply text-sm text-slate-500;
}

.field-group {
  @apply block space-y-1.5;
}

.field-label {
  @apply block text-sm font-medium text-slate-800;
}

.field {
  @apply w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 outline-none transition focus:border-indigo-300 focus:ring-4 focus:ring-indigo-50;
}

.btn-primary {
  @apply inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60;
}

.btn-secondary {
  @apply inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60;
}

.icon-mark {
  @apply inline-block h-3.5 w-3.5 shrink-0 rounded-sm bg-current;
}

.channel-row {
  @apply block w-full rounded-lg border border-slate-200 bg-white px-3 py-3 text-left transition hover:border-indigo-200 hover:bg-indigo-50/30;
}

.channel-row-selected {
  @apply border-indigo-400 bg-indigo-50/60;
}

.badge-ok {
  @apply inline-flex items-center rounded-full border border-emerald-100 bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700;
}

.badge-warn {
  @apply inline-flex items-center rounded-full border border-amber-100 bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700;
}

.badge-muted {
  @apply inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs font-medium text-slate-500;
}

.proposed-chip {
  @apply inline-flex flex-col items-start rounded-md border border-emerald-100 bg-white px-2.5 py-1.5 text-xs;
}

.proposed-chip strong {
  @apply text-sm font-semibold text-emerald-700;
}

.proposed-chip small {
  @apply text-xs text-slate-500;
}

.confirm-grid {
  @apply grid grid-cols-2 gap-3 rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm;
}

.confirm-grid dt {
  @apply text-xs text-slate-500;
}

.confirm-grid dd {
  @apply mt-0.5 text-sm font-medium text-slate-900;
}

.drawer-footer {
  @apply sticky bottom-0 z-10 flex flex-col gap-3 border-t border-slate-200 bg-white px-5 py-3 sm:flex-row sm:items-center sm:justify-between;
}
</style>
