<template>
  <div
    v-if="channel"
    class="fixed inset-0 z-50 flex justify-end bg-slate-950/30"
    @click.self="close"
  >
    <aside class="drawer-panel">
      <div
        class="sticky top-0 z-10 border-b border-slate-200 bg-white px-5 py-4"
      >
        <div
          class="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between"
        >
          <div>
            <p
              class="text-xs font-semibold uppercase tracking-[0.18em] text-indigo-600"
            >
              Channel Models
            </p>
            <h3 class="mt-2 text-xl font-semibold text-slate-900">
              {{ channel.name }}
            </h3>
            <p class="mt-1 font-mono text-xs text-slate-500">
              {{ channel.code }}
            </p>
          </div>
          <div class="flex flex-wrap items-center justify-end gap-2">
            <span v-if="hasUnsavedChanges" class="dirty-badge">
              未保存变更
            </span>
            <button type="button" class="btn-secondary" @click="close">
              关闭
            </button>
            <button
              type="button"
              class="btn-primary"
              :disabled="saving || !hasUnsavedChanges"
              @click="save"
            >
              <span class="icon-mark" :class="saving ? 'animate-spin' : ''" />
              {{ saving ? '保存中' : saveButtonLabel }}
            </button>
          </div>
        </div>
      </div>

      <div class="space-y-4 px-4 py-4 lg:px-5">
        <div class="panel space-y-4">
          <div class="flex flex-col gap-3 xl:flex-row xl:items-start">
            <div class="min-w-0 flex-1">
              <h4 class="text-sm font-semibold text-slate-900">
                添加渠道模型
              </h4>
              <p class="mt-1 text-xs leading-5 text-slate-500">
                先选择模型，再指定该渠道实际使用的上游供货源。
                添加后可在下方设置渠道状态、成本规则和固定成本价。
              </p>
            </div>
            <div class="flex flex-wrap gap-2 text-xs text-slate-500">
              <span class="summary-pill">
                已配置 {{ managedRows.length }}
              </span>
              <span class="summary-pill">
                已启用 {{ listedCount }}
              </span>
              <span class="summary-pill">
                可添加 {{ availableModelCount }}
              </span>
            </div>
          </div>

          <div class="add-grid">
            <div class="form-field model-select-field">
              <label class="field-label">选择模型</label>
              <div ref="modelDropdownRef" class="searchable-select">
                <button
                  class="searchable-trigger"
                  type="button"
                  @click="toggleModelDropdown"
                >
                  <span class="min-w-0 flex-1">
                    <span
                      v-if="selectedModelOption"
                      class="block truncate font-medium text-slate-800"
                    >
                      {{ selectedModelOption.name }}
                    </span>
                    <span v-else class="block truncate text-slate-400">
                      搜索并选择模型
                    </span>
                  </span>
                  <span class="dropdown-caret">⌄</span>
                </button>

                <div v-if="modelDropdownOpen" class="searchable-menu">
                  <input
                    ref="modelSearchInput"
                    v-model="modelSearch"
                    class="searchable-input"
                    placeholder="名称 / code / 上游供货源"
                    @keydown.escape="closeModelDropdown"
                  />
                  <div class="searchable-meta">
                    <span>{{ availableModelGroups.length }} 个可添加模型</span>
                    <span v-if="!modelSearch">默认展示前 24 个</span>
                    <span v-else>已按关键词筛选</span>
                  </div>
                  <div class="searchable-list">
                    <button
                      v-for="model in availableModelOptions"
                      :key="model.key"
                      class="searchable-option"
                      :class="
                        selectedModelKey === model.key
                          ? 'searchable-option-active'
                          : ''
                      "
                      type="button"
                      @click="selectModel(model)"
                    >
                      <span class="min-w-0 flex-1">
                        <span class="block truncate text-sm font-medium">
                          {{ model.name }}
                        </span>
                        <span
                          class="mt-0.5 block truncate font-mono text-[11px] text-slate-400"
                        >
                          {{ modelOptionMeta(model) }}
                        </span>
                      </span>
                      <span class="option-provider">
                        {{ modalityLabel(model.modality) }}
                      </span>
                    </button>
                    <div
                      v-if="!availableModelOptions.length"
                      class="searchable-empty"
                    >
                      没有匹配的可添加模型
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div class="form-field">
              <label class="field-label">渠道上游</label>
              <CompactSelect
                v-if="selectedModelKey"
                v-model="newDraft.model"
                :options="providerModelOptions"
                placeholder="选择渠道上游"
                searchable
                search-placeholder="搜索上游供货源 / 币种 / 类型"
                @change="selectPriceSourceModel"
              />
              <div v-else class="readonly-field">
                <span class="truncate">
                  先选择模型
                </span>
              </div>
              <p v-if="!selectedModelKey" class="field-helper">
                选择模型后会显示该模型可用的原厂、供货商或人工价格源。
              </p>
            </div>

          </div>

          <div class="advanced-cost-panel">
            <button
              type="button"
              class="advanced-cost-toggle"
              @click="showAdvancedCost = !showAdvancedCost"
            >
              <span>高级成本设置</span>
              <span>{{ showAdvancedCost ? '收起' : '展开' }}</span>
            </button>
            <div v-if="showAdvancedCost" class="advanced-cost-grid">
              <div class="form-field">
                <label class="field-label">成本规则</label>
                <CompactSelect
                  v-model="newDraft.price_mode"
                  :options="priceModeOptions"
                  @change="applyPriceMode(newDraft)"
                />
              </div>

              <div class="form-field">
                <label class="field-label">成本保存币种</label>
                <CompactSelect
                  v-model="newDraft.currency"
                  :options="currencyOptions"
                  title="留空时跟随渠道结算币种保存；页面价格仍按全局显示货币换算。"
                />
                <p class="field-helper">
                  留空表示跟随渠道结算币种；展示价格会按当前全局货币换算。
                </p>
              </div>

              <div
                v-if="newDraft.price_mode === 'discount'"
                class="form-field"
              >
                <label class="field-label">折扣比例</label>
                <input
                  v-model="newDraft.settlement_ratio"
                  class="field compact-field text-right"
                  step="0.0001"
                  type="number"
                  placeholder="0.85"
                />
              </div>

              <template v-if="newDraft.price_mode === 'fixed'">
                <div
                  v-for="field in customPriceFields(selectedModel)"
                  :key="field.key"
                  class="form-field fixed-add-field"
                >
                  <label class="field-label">{{ field.label }}</label>
                  <input
                    v-model="newDraft[field.key]"
                    class="field compact-field text-right"
                    step="0.000001"
                    type="number"
                    placeholder="可选"
                  />
                </div>
                <div
                  v-if="!customPriceFields(selectedModel).length"
                  class="fixed-price-note xl:col-span-2"
                >
                  当前模型的图片等特殊计价维度暂不支持在渠道配置中手动覆盖，
                  会使用上游价格或折扣后的渠道成本价。
                </div>
              </template>
            </div>
          </div>

          <div
            v-if="selectedModelOption"
            class="pending-association"
          >
            <div class="pending-main">
              <p class="text-xs font-medium text-slate-500">
                待添加关联
              </p>
              <p class="mt-1 truncate text-sm font-semibold text-slate-900">
                {{ selectedModelOption.name }}
              </p>
              <p class="mt-1 truncate text-xs text-slate-500">
                {{
                  selectedModel
                    ? `${purchaseSourceLabel(selectedModel)} / ${modalityLabel(selectedModel.modality)}`
                    : '请选择渠道上游'
                }}
              </p>
              <a
                v-if="selectedModel?.source_endpoint_url"
                class="mt-1 block truncate text-xs text-indigo-600 hover:text-indigo-700 hover:underline"
                :href="selectedModel.source_endpoint_url"
                rel="noopener noreferrer"
                target="_blank"
                :title="selectedModel.source_endpoint_url"
              >
                {{ selectedModel.source_endpoint_url }}
              </a>
            </div>
            <div
              v-if="selectedModel"
              class="pending-price-summary"
            >
              <p class="pending-price-title">上游价格</p>
              <span
                v-for="item in providerPriceSummary(selectedModel)"
                :key="item.label"
              >
                <span>{{ item.label }}</span>
                <strong>{{ priceText(item, selectedModel) }}</strong>
              </span>
            </div>
            <div
              v-if="
              selectedModel &&
              draftPricePreview(newDraft, selectedModel).length
            "
              class="pending-price-summary"
            >
              <p class="pending-price-title">渠道成本预估</p>
              <span
                v-for="item in draftPricePreview(newDraft, selectedModel)"
                :key="item.label"
              >
                <span>{{ item.label }}</span>
                <strong>{{ priceText(item, selectedModel) }}</strong>
              </span>
            </div>
            <div class="association-meta">
              <span v-if="hasKnownSourceCategory(selectedModel?.source_category)">
                {{ sourceCategoryLabel(selectedModel?.source_category) }}
              </span>
              <span>{{ priceModeLabel(newDraft.price_mode) }}</span>
              <span>{{ costCurrencyLabel(newDraft.currency) }}</span>
              <span>添加后默认不参与转发</span>
            </div>
            <button
              type="button"
              class="btn-primary justify-center"
              :disabled="!selectedModel"
              @click="addSelectedModel"
            >
              添加
            </button>
          </div>
        </div>

        <div class="grid gap-3 md:grid-cols-[minmax(0,1fr)_10rem]">
          <input
            v-model="search"
            class="field compact-field"
            placeholder="搜索已配置模型名称、code 或厂商"
          />
          <CompactSelect
            v-model="statusFilter"
            :options="statusFilterOptions"
          />
        </div>

        <div class="panel overflow-hidden p-0">
          <div class="table-toolbar">
            <div class="min-w-0">
              <h3 class="panel-title">
                已配置模型（{{ filteredRows.length }}）
              </h3>
              <div
                v-if="changeSummaryLabels.length"
                class="mt-2 flex flex-wrap gap-1.5"
              >
                <span
                  v-for="label in changeSummaryLabels"
                  :key="label"
                  class="change-chip"
                >
                  {{ label }}
                </span>
              </div>
            </div>
            <div class="flex flex-wrap gap-2">
              <button
                type="button"
                class="btn-toolbar"
                :disabled="!filteredRows.length || saving"
                @click="setFilteredRowsListed(true)"
              >
                批量设为渠道可用
              </button>
              <button
                type="button"
                class="btn-toolbar"
                :disabled="!filteredRows.length || saving"
                @click="setFilteredRowsListed(false)"
              >
                批量设为不可用
              </button>
            </div>
          </div>
          <div class="grid channel-model-cards lg:hidden">
            <article
              v-for="row in filteredRows"
              :key="row.model.id"
              class="channel-model-card"
              :class="
                String(recentlyAddedModelId) === String(row.model.id)
                  ? 'recently-added-card'
                  : ''
              "
            >
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <p class="model-name font-medium text-slate-900">
                    {{ modelDisplayName(row.model) }}
                  </p>
                  <p class="model-code mt-1 font-mono text-xs text-slate-500">
                    {{ channelModelSubtitle(row) }}
                  </p>
                </div>
                <button
                  class="link-btn"
                  type="button"
                  @click="removeRow(row)"
                >
                  移除
                </button>
              </div>

              <div class="mt-3 flex flex-wrap items-center gap-1.5">
                <span
                  v-if="hasKnownSourceCategory(row.model.source_category)"
                  :class="['source-badge', sourceTone(row.model.source_category)]"
                >
                  {{ sourceCategoryLabel(row.model.source_category) }}
                </span>
                <span class="source-badge unknown">
                  {{ channelRowSourceLabel(row) }}
                </span>
                <span class="source-badge unknown">
                  {{ modalityLabel(row.model.modality) }}
                </span>
              </div>

              <div class="mt-3 grid gap-2 sm:grid-cols-2">
                <div class="card-field">
                  <span>上游价格</span>
                  <div class="mt-1 space-y-1 font-mono">
                    <p
                      v-for="item in providerPriceSummary(row.model)"
                      :key="item.label"
                    >
                      <span class="text-slate-400">{{ item.label }}</span>
                      {{ priceText(item, row.model) }}
                    </p>
                  </div>
                </div>
                <div class="card-field">
                  <span>渠道成本价</span>
                  <div
                    v-if="row.priceItems.length"
                    class="mt-1 flex flex-wrap gap-1"
                  >
                    <span
                      v-for="item in row.priceItems"
                      :key="item.id"
                      class="price-chip"
                      :class="comparisonTone(item.comparison_status)"
                      :title="comparisonTitle(item)"
                    >
                      {{ dimensionLabel(item.dimension) }}
                      {{ moneyOrStatus(item.unit_price, item.currency) }}
                    </span>
                  </div>
                  <span v-else class="mt-1 block text-xs text-slate-400">
                    保存后自动生成
                  </span>
                </div>
              </div>

              <div class="mt-3 grid gap-2 sm:grid-cols-2">
                <label
                  class="publish-status justify-center"
                  :class="
                    row.draft.is_listed
                      ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                      : 'border-slate-200 bg-slate-50 text-slate-500'
                  "
                >
                  <input
                    v-model="row.draft.is_listed"
                    type="checkbox"
                    class="h-3.5 w-3.5 rounded border-slate-300 text-indigo-600"
                  />
                  {{ row.draft.is_listed ? '渠道可用' : '不可用' }}
                </label>
                <CompactSelect
                  v-model="row.draft.price_mode"
                  :options="priceModeOptions"
                  size="sm"
                  @change="applyPriceMode(row.draft)"
                />
                <CompactSelect
                  v-model="row.draft.currency"
                  :options="currencyOptions"
                  size="sm"
                  :title="costCurrencyTitle(row.draft.currency)"
                />
                <input
                  v-if="row.draft.price_mode === 'discount'"
                  v-model="row.draft.settlement_ratio"
                  class="field compact-field text-right"
                  step="0.0001"
                  type="number"
                  placeholder="折扣比例，如 0.85"
                />
              </div>

              <div
                v-if="row.draft.price_mode === 'fixed'"
                class="mt-3 grid gap-2 sm:grid-cols-2"
              >
                <label
                  v-for="field in customPriceFields(row.model)"
                  :key="field.key"
                  class="form-field"
                >
                  <span class="field-label">{{ field.label }}</span>
                  <input
                    v-model="row.draft[field.key]"
                    class="field compact-field text-right"
                    step="0.000001"
                    type="number"
                    placeholder="可选"
                  />
                </label>
                <span
                  v-if="!customPriceFields(row.model).length"
                  class="text-xs text-slate-400"
                >
                  当前模型暂不支持手动覆盖固定成本价。
                </span>
              </div>
            </article>
            <div v-if="!filteredRows.length" class="empty-card">
              还没有配置模型，请先从上方添加。
            </div>
          </div>

          <div class="hidden overflow-x-auto lg:block">
            <table class="data-table channel-model-table">
              <thead>
                <tr>
                  <th class="table-head">模型</th>
                  <th class="table-head">渠道上游 / 渠道状态</th>
                  <th class="table-head text-right">上游价格</th>
                  <th class="table-head">渠道成本价 / 上游对比</th>
                  <th class="table-head">成本规则</th>
                  <th class="table-head">固定成本价</th>
                  <th class="table-head action-col text-right">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="row in filteredRows"
                  :key="row.model.id"
                  :class="
                    String(recentlyAddedModelId) === String(row.model.id)
                      ? 'recently-added-row'
                      : ''
                  "
                >
                  <td class="table-cell max-w-[260px]">
                    <p class="model-name font-medium text-slate-900">
                      {{ modelDisplayName(row.model) }}
                    </p>
                    <p class="model-code mt-1 font-mono text-xs text-slate-500">
                      {{ channelModelSubtitle(row) }}
                    </p>
                  </td>
                  <td class="table-cell">
                    <div class="space-y-2">
                      <p class="text-sm font-medium text-slate-800">
                        {{ channelRowSourceLabel(row) }}
                        <span class="text-xs font-normal text-slate-400">
                          / {{ modalityLabel(row.model.modality) }}
                        </span>
                      </p>
                      <div class="flex flex-wrap items-center gap-1.5">
                        <span
                          v-if="hasKnownSourceCategory(row.model.source_category)"
                          :class="['source-badge', sourceTone(row.model.source_category)]"
                        >
                          {{ sourceCategoryLabel(row.model.source_category) }}
                        </span>
                        <a
                          v-if="row.model.source_endpoint_url"
                          class="source-mini-link"
                          :href="row.model.source_endpoint_url"
                          rel="noopener noreferrer"
                          target="_blank"
                          :title="row.model.source_endpoint_url"
                        >
                          上游价格地址
                        </a>
                      </div>
                      <label
                        class="publish-status"
                        :class="
                          row.draft.is_listed
                            ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                            : 'border-slate-200 bg-slate-50 text-slate-500'
                        "
                      >
                        <input
                          v-model="row.draft.is_listed"
                          type="checkbox"
                          class="h-3.5 w-3.5 rounded border-slate-300 text-indigo-600"
                        />
                        {{ row.draft.is_listed ? '渠道可用' : '不可用' }}
                      </label>
                    </div>
                  </td>
                  <td class="table-cell text-right font-mono">
                    <div class="space-y-1">
                      <p
                        v-for="item in providerPriceSummary(row.model)"
                        :key="item.label"
                        class="whitespace-nowrap text-xs"
                      >
                        <span class="text-slate-400">{{ item.label }}</span>
                        {{ priceText(item, row.model) }}
                      </p>
                    </div>
                  </td>
                  <td class="table-cell min-w-56">
                    <div
                      v-if="row.priceItems.length"
                      class="flex flex-wrap gap-1.5"
                    >
                      <span
                        v-for="item in row.priceItems"
                        :key="item.id"
                        class="price-chip"
                        :class="comparisonTone(item.comparison_status)"
                        :title="comparisonTitle(item)"
                      >
                        {{ dimensionLabel(item.dimension) }}
                        {{ moneyOrStatus(item.unit_price, item.currency) }}
                      </span>
                    </div>
                    <span v-else class="text-xs text-slate-400">
                      保存后自动生成
                    </span>
                  </td>
                  <td class="table-cell">
                    <div class="flex max-w-56 flex-wrap gap-1.5">
                      <CompactSelect
                        v-model="row.draft.price_mode"
                        :options="priceModeOptions"
                        class-name="price-mode-select"
                        size="sm"
                        @change="applyPriceMode(row.draft)"
                      />
                      <CompactSelect
                        v-model="row.draft.currency"
                        :options="currencyOptions"
                        class-name="currency-select"
                        size="sm"
                        :title="costCurrencyTitle(row.draft.currency)"
                      />
                      <input
                        v-if="row.draft.price_mode === 'discount'"
                        v-model="row.draft.settlement_ratio"
                        class="field-sm channel-model-input text-right"
                        step="0.0001"
                        type="number"
                        placeholder="0.85"
                      />
                    </div>
                  </td>
                  <td class="table-cell">
                    <div
                      v-if="row.draft.price_mode === 'fixed'"
                      class="fixed-price-grid"
                    >
                      <label
                        v-for="field in customPriceFields(row.model)"
                        :key="field.key"
                        class="fixed-price-field"
                        :title="field.label"
                      >
                        <span>{{ field.shortLabel }}</span>
                        <input
                          v-model="row.draft[field.key]"
                          class="field-sm channel-model-input text-right"
                          step="0.000001"
                          type="number"
                          placeholder="可选"
                        />
                      </label>
                      <span
                        v-if="!customPriceFields(row.model).length"
                        class="text-xs text-slate-400"
                      >
                        暂不支持手动覆盖
                      </span>
                    </div>
                    <span v-else class="text-xs text-slate-400">
                      {{ priceModeHint(row.draft.price_mode) }}
                    </span>
                  </td>
                  <td class="table-cell action-col text-right">
                    <button
                      class="link-btn"
                      type="button"
                      @click="removeRow(row)"
                    >
                      移除
                    </button>
                  </td>
                </tr>
                <tr v-if="!filteredRows.length">
                  <td class="table-cell text-slate-500" colspan="7">
                    还没有配置模型，请先从上方添加。
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </aside>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { llmOpsApi } from '@/api/llmOps'
import CompactSelect from './CompactSelect.vue'

const props = defineProps({
  channel: {
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
  channelPrices: {
    type: Array,
    required: true
  },
  channelPriceItems: {
    type: Array,
    default: () => []
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

const emit = defineEmits(['close', 'refresh', 'saved'])

const search = ref('')
const statusFilter = ref('all')
const modelSearch = ref('')
const selectedModelKey = ref('')
const modelDropdownOpen = ref(false)
const modelDropdownRef = ref(null)
const modelSearchInput = ref(null)
const showAdvancedCost = ref(false)
const drafts = ref({})
const baselineDrafts = ref({})
const saving = ref(false)
const newDraft = ref(emptyNewDraft())
const pendingRefresh = ref(false)
const recentlyAddedModelId = ref(null)
const customPriceKeys = [
  'custom_input_price_per_million',
  'custom_output_price_per_million',
  'custom_audio_input_price_per_second',
  'custom_audio_output_price_per_second',
  'custom_video_input_price_per_second',
  'custom_video_output_price_per_second'
]

const selectedModel = computed(() =>
  props.models.find(
    (model) => String(model.id) === String(newDraft.value.model)
  )
)

const selectedModelOption = computed(() =>
  availableModelGroups.value.find(
    (option) => option.key === selectedModelKey.value
  )
)

const priceModeOptions = [
  { label: '默认折扣', value: 'channel_default' },
  { label: '折扣比例', value: 'discount' },
  { label: '固定成本价', value: 'fixed' }
]

const channelCurrency = computed(() =>
  String(props.channel?.currency || 'USD').toUpperCase()
)

const statusFilterOptions = [
  { label: '全部配置', value: 'all' },
  { label: '渠道可用', value: 'listed' },
  { label: '不可用', value: 'unlisted' }
]

const currencyOptions = computed(() => [
  {
    label: '使用渠道默认币种',
    value: '',
    description: `保存为 ${channelCurrency.value}`
  },
  { label: '人民币 CNY', value: 'CNY', description: '固定保存为人民币' },
  { label: '美元 USD', value: 'USD', description: '固定保存为美元' }
])

const listedCount = computed(
  () => managedRows.value.filter((row) => row.draft.is_listed).length
)

const changeSummary = computed(() => summarizeDraftChanges())

const hasUnsavedChanges = computed(() =>
  Object.values(changeSummary.value).some((count) => count > 0)
)

const changeSummaryLabels = computed(() => {
  const summary = changeSummary.value
  return [
    summary.added ? `新增 ${summary.added}` : '',
    summary.modified ? `改成本 ${summary.modified}` : '',
    summary.enabled ? `启用 ${summary.enabled}` : '',
    summary.disabled ? `停用 ${summary.disabled}` : '',
    summary.removed ? `移除 ${summary.removed}` : ''
  ].filter(Boolean)
})

const saveButtonLabel = computed(() =>
  hasUnsavedChanges.value ? '保存变更' : '暂无变更'
)

const baseAvailableModels = computed(() =>
  props.models.filter((model) => {
    const draft = drafts.value[model.id]
    return !configuredIdentityKeys.value.has(modelIdentityKey(model))
  })
)

const configuredIdentityKeys = computed(() => {
  const keys = new Set()
  props.models.forEach((model) => {
    const draft = drafts.value[model.id]
    if (draft?.is_configured || shouldPersist(draft || {})) {
      keys.add(modelIdentityKey(model))
    }
  })
  return keys
})

const availableModelGroups = computed(() => {
  const groups = new Map()
  baseAvailableModels.value.forEach((model) => {
    const key = modelIdentityKey(model)
    const group = groups.get(key) || {
      key,
      name: modelDisplayName(model),
      code: model.meta_model_code || model.code,
      modality: model.modality,
      models: []
    }
    group.models.push(model)
    group.providerCount = group.models.length
    groups.set(key, group)
  })
  return Array.from(groups.values()).sort((left, right) =>
    left.name.localeCompare(right.name)
  )
})

const availableModelCount = computed(() => availableModelGroups.value.length)

const availableModelOptions = computed(() => {
  const keyword = normalizeSearch(modelSearch.value)
  const limit = keyword ? 80 : 24
  return availableModelGroups.value
    .map((option) => {
      const haystack = modelOptionSearchText(option)
      return {
        option,
        score: keyword ? fuzzyScore(haystack, keyword) : 1
      }
    })
    .filter((item) => item.score > 0)
    .sort((left, right) => right.score - left.score)
    .map((item) => item.option)
    .slice(0, limit)
})

const providerModelOptions = computed(() => {
  if (!selectedModelKey.value) return []
  const group = availableModelGroups.value.find(
    (item) => item.key === selectedModelKey.value
  )
  if (!group) return []
  return group.models
    .slice()
    .sort((left, right) =>
      purchaseSourceLabel(left).localeCompare(purchaseSourceLabel(right))
    )
    .map((model) => ({
      label: purchaseSourceLabel(model),
      value: model.id,
      description: providerModelDescription(model),
      badge: sourceCategoryBadge(model.source_category),
      searchText: [
        model.provider_name,
        model.provider_code,
        model.source_name,
        model.source_category,
        model.currency
      ].join(' ')
    }))
})

const managedRows = computed(() => {
  if (!props.channel) return []
  return props.models
    .filter((model) => {
      const draft = drafts.value[model.id]
      return draft?.is_configured || shouldPersist(draft || {})
    })
    .map((model) => ({
      model,
      draft: drafts.value[model.id],
      priceItems: channelPriceItemsForModel(model)
    }))
})

const filteredRows = computed(() => {
  if (!props.channel) return []
  const keyword = search.value.trim().toLowerCase()
  return managedRows.value
    .filter((row) => {
      const currentModel = row.model
      const draft = row.draft
      const haystack = [
        currentModel.name,
        currentModel.code,
        currentModel.meta_model_name,
        currentModel.meta_model_code,
        currentModel.provider_name,
        currentModel.provider_code
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()
      if (keyword && !haystack.includes(keyword)) {
        return false
      }
      if (statusFilter.value === 'listed' && !draft?.is_listed) {
        return false
      }
      if (statusFilter.value === 'unlisted' && draft?.is_listed) {
        return false
      }
      return true
    })
})

function channelPriceItemsForModel(model) {
  if (!props.channel) return []
  return props.channelPriceItems
    .filter(
      (item) =>
        String(item.channel) === String(props.channel.id) &&
        String(item.model) === String(model.id) &&
        item.is_current !== false
    )
    .sort((left, right) => {
      const leftKey = `${left.dimension}-${left.tier_start || ''}`
      const rightKey = `${right.dimension}-${right.tier_start || ''}`
      return leftKey.localeCompare(rightKey)
    })
}

watch(
  () => [props.channel, props.models, props.channelPrices],
  () => {
    if (!props.channel) {
      reset()
      return
    }
    const pricesByModel = new Map(
      props.channelPrices
        .filter((price) => String(price.channel) === String(props.channel.id))
        .map((price) => [String(price.model), price])
    )
    drafts.value = Object.fromEntries(
      props.models.map((model) => [
        model.id,
        draftDefaults(model, pricesByModel.get(String(model.id)))
      ])
    )
    baselineDrafts.value = snapshotDrafts(drafts.value)
    recentlyAddedModelId.value = null
  },
  { immediate: true }
)

onMounted(() => {
  document.addEventListener('click', handleModelDropdownOutside)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleModelDropdownOutside)
})

function reset() {
  search.value = ''
  statusFilter.value = 'all'
  modelSearch.value = ''
  selectedModelKey.value = ''
  modelDropdownOpen.value = false
  newDraft.value = emptyNewDraft()
  drafts.value = {}
  baselineDrafts.value = {}
  pendingRefresh.value = false
  recentlyAddedModelId.value = null
}

function close() {
  if (
    hasUnsavedChanges.value &&
    !window.confirm('当前有未保存的模型配置变更，确定关闭抽屉吗？')
  ) {
    return
  }
  const shouldRefresh = pendingRefresh.value
  reset()
  emit('close')
  if (shouldRefresh) {
    emit('refresh')
  }
}

function snapshotDrafts(source) {
  return Object.fromEntries(
    Object.entries(source || {}).map(([modelId, draft]) => [
      modelId,
      serializeDraft(draft)
    ])
  )
}

function serializeDraft(draft) {
  const normalized = normalizeDraftForMode(draft || {})
  return {
    id: normalized.id || null,
    model: String(normalized.model || ''),
    price_source: String(normalized.price_source || ''),
    price_source_name: normalized.price_source_name || '',
    price_source_category: normalized.price_source_category || '',
    price_source_endpoint_url: normalized.price_source_endpoint_url || '',
    is_configured: Boolean(normalized.is_configured),
    is_listed: Boolean(normalized.is_listed),
    price_mode: normalized.price_mode || 'channel_default',
    currency: String(normalized.currency || '').toUpperCase(),
    settlement_ratio: normalized.settlement_ratio || '',
    custom_input_price_per_million:
      normalized.custom_input_price_per_million || '',
    custom_output_price_per_million:
      normalized.custom_output_price_per_million || '',
    custom_audio_input_price_per_second:
      normalized.custom_audio_input_price_per_second || '',
    custom_audio_output_price_per_second:
      normalized.custom_audio_output_price_per_second || '',
    custom_video_input_price_per_second:
      normalized.custom_video_input_price_per_second || '',
    custom_video_output_price_per_second:
      normalized.custom_video_output_price_per_second || ''
  }
}

function isSerializedConfigured(draft) {
  return Boolean(draft?.id || draft?.is_configured || shouldPersist(draft || {}))
}

function serializedDraftChanged(left, right) {
  return JSON.stringify(left || {}) !== JSON.stringify(right || {})
}

function summarizeDraftChanges() {
  const summary = {
    added: 0,
    modified: 0,
    enabled: 0,
    disabled: 0,
    removed: 0
  }
  const modelIds = new Set([
    ...Object.keys(baselineDrafts.value || {}),
    ...Object.keys(drafts.value || {})
  ])
  modelIds.forEach((modelId) => {
    const baseline = baselineDrafts.value[modelId] || {}
    const current = serializeDraft(drafts.value[modelId] || {})
    const wasConfigured = isSerializedConfigured(baseline)
    const isConfigured = isSerializedConfigured(current)

    if (!wasConfigured && isConfigured) {
      summary.added += 1
      return
    }
    if (wasConfigured && !isConfigured) {
      summary.removed += 1
      return
    }
    if (!wasConfigured || !isConfigured) return

    if (Boolean(baseline.is_listed) !== Boolean(current.is_listed)) {
      if (current.is_listed) {
        summary.enabled += 1
      } else {
        summary.disabled += 1
      }
    }

    const baselineWithoutStatus = {
      ...baseline,
      is_listed: Boolean(current.is_listed)
    }
    if (serializedDraftChanged(baselineWithoutStatus, current)) {
      summary.modified += 1
    }
  })
  return summary
}

function draftDefaults(model, price) {
  return {
    id: price?.id || null,
    channel: props.channel?.id || '',
    model: model.id,
    price_source: price?.price_source || model.source || '',
    price_source_name: price?.price_source_name || model.source_name || '',
    price_source_category:
      price?.price_source_category || model.source_category || '',
    price_source_endpoint_url:
      price?.price_source_endpoint_url || model.source_endpoint_url || '',
    is_configured: Boolean(price?.id),
    is_listed: price?.is_listed || false,
    price_mode: priceModeFromDraft(price || {}),
    currency: price?.currency || '',
    settlement_ratio: price?.settlement_ratio || '',
    custom_input_price_per_million:
      price?.custom_input_price_per_million || '',
    custom_output_price_per_million:
      price?.custom_output_price_per_million || '',
    custom_audio_input_price_per_second:
      price?.custom_audio_input_price_per_second || '',
    custom_audio_output_price_per_second:
      price?.custom_audio_output_price_per_second || '',
    custom_video_input_price_per_second:
      price?.custom_video_input_price_per_second || '',
    custom_video_output_price_per_second:
      price?.custom_video_output_price_per_second || ''
  }
}

function emptyNewDraft() {
  return {
    model: '',
    price_source: '',
    price_source_name: '',
    price_source_category: '',
    price_source_endpoint_url: '',
    is_listed: false,
    price_mode: 'channel_default',
    currency: '',
    settlement_ratio: '',
    custom_input_price_per_million: '',
    custom_output_price_per_million: '',
    custom_audio_input_price_per_second: '',
    custom_audio_output_price_per_second: '',
    custom_video_input_price_per_second: '',
    custom_video_output_price_per_second: ''
  }
}

function addSelectedModel() {
  const model = selectedModel.value
  if (!model) return
  drafts.value[model.id] = {
    ...draftDefaults(model, null),
    is_configured: true,
    is_listed: false,
    price_source: newDraft.value.price_source || model.source || '',
    currency: newDraft.value.currency,
    settlement_ratio:
      newDraft.value.price_mode === 'discount'
        ? newDraft.value.settlement_ratio
        : '',
    custom_input_price_per_million:
      newDraft.value.price_mode === 'fixed'
        ? newDraft.value.custom_input_price_per_million
        : '',
    custom_output_price_per_million:
      newDraft.value.price_mode === 'fixed'
        ? newDraft.value.custom_output_price_per_million
        : '',
    custom_audio_input_price_per_second:
      newDraft.value.price_mode === 'fixed'
        ? newDraft.value.custom_audio_input_price_per_second
        : '',
    custom_audio_output_price_per_second:
      newDraft.value.price_mode === 'fixed'
        ? newDraft.value.custom_audio_output_price_per_second
        : '',
    custom_video_input_price_per_second:
      newDraft.value.price_mode === 'fixed'
        ? newDraft.value.custom_video_input_price_per_second
        : '',
    custom_video_output_price_per_second:
      newDraft.value.price_mode === 'fixed'
        ? newDraft.value.custom_video_output_price_per_second
        : ''
  }
  applyPriceMode(drafts.value[model.id])
  recentlyAddedModelId.value = model.id
  newDraft.value = emptyNewDraft()
  modelSearch.value = ''
  selectedModelKey.value = ''
  modelDropdownOpen.value = false
  nextTick(() => {
    const row = document.querySelector(
      '.recently-added-row, .recently-added-card'
    )
    row?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  })
}

function toggleModelDropdown() {
  if (modelDropdownOpen.value) {
    closeModelDropdown()
    return
  }
  openModelDropdown()
}

function openModelDropdown() {
  modelDropdownOpen.value = true
  nextTick(() => {
    modelSearchInput.value?.focus()
  })
}

function closeModelDropdown() {
  modelDropdownOpen.value = false
}

function selectModel(modelOption) {
  selectedModelKey.value = modelOption.key
  const providers = providerModelOptions.value.filter((option) => option.value)
  newDraft.value.model = providers.length === 1 ? providers[0].value : ''
  selectPriceSourceModel(newDraft.value.model)
  modelSearch.value = ''
  closeModelDropdown()
}

function selectPriceSourceModel(value) {
  const model = props.models.find(
    (item) => String(item.id) === String(value)
  )
  newDraft.value.price_source = model?.source || ''
  newDraft.value.price_source_name = model?.source_name || ''
  newDraft.value.price_source_category = model?.source_category || ''
  newDraft.value.price_source_endpoint_url = model?.source_endpoint_url || ''
}

function handleModelDropdownOutside(event) {
  if (!modelDropdownOpen.value || !modelDropdownRef.value) return
  if (!modelDropdownRef.value.contains(event.target)) {
    closeModelDropdown()
  }
}

function normalizeSearch(value) {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '')
}

function modelIdentityKey(model) {
  return normalizeSearch(
    [
      model.meta_model || model.meta_model_code || model.code || model.name,
      model.modality || 'text'
    ]
      .filter(Boolean)
      .join('|')
  )
}

function modelDisplayName(model) {
  return model?.meta_model_name || model?.name || model?.code || ''
}

function modelOptionSearchText(option) {
  return normalizeSearch(
    [
      option.name,
      option.code,
      option.modality,
      option.models.map((model) => model.provider_name).join(' '),
      option.models.map((model) => model.provider_code).join(' '),
      option.models.map((model) => model.source_name).join(' '),
      option.models.map((model) => model.source_category).join(' '),
      modalityLabel(option.modality)
    ]
      .filter(Boolean)
      .join(' ')
  )
}

function providerModelDescription(model) {
  return [
    hasKnownSourceCategory(model.source_category)
      ? sourceCategoryLabel(model.source_category)
      : null,
    model.currency || '默认币种'
  ]
    .filter(Boolean)
    .join(' · ')
}

function modelOptionMeta(option) {
  const parts = []
  if (normalizeSearch(option.code) !== normalizeSearch(option.name)) {
    parts.push(option.code)
  }
  parts.push(`${option.providerCount} 个可选上游`)
  return parts.filter(Boolean).join(' · ')
}

function channelModelSubtitle(row) {
  const model = row?.model || {}
  const name = String(modelDisplayName(model) || '').trim()
  const code = String(model.meta_model_code || model.code || '').trim()
  if (code && code !== name) return code
  return [
    model.source_name || model.provider_name,
    model.code && model.code !== code ? model.code : ''
  ]
    .filter(Boolean)
    .join(' · ')
}

function priceModeLabel(mode) {
  return (
    priceModeOptions.find((option) => option.value === mode)?.label ||
    '默认折扣'
  )
}

function costCurrencyLabel(currency) {
  const value = String(currency || '').trim().toUpperCase()
  return value || `跟随渠道 ${channelCurrency.value}`
}

function costCurrencyTitle(currency) {
  const value = String(currency || '').trim().toUpperCase()
  if (value) {
    return `成本价保存为 ${value}；页面价格按全局显示货币换算。`
  }
  return `成本价跟随渠道结算币种 ${channelCurrency.value} 保存；页面价格按全局显示货币换算。`
}

function fuzzyScore(haystack, keyword) {
  if (!keyword) return 1
  if (haystack.includes(keyword)) {
    return 1000 - haystack.indexOf(keyword)
  }
  let haystackIndex = 0
  let score = 0
  for (const char of keyword) {
    const foundIndex = haystack.indexOf(char, haystackIndex)
    if (foundIndex === -1) return 0
    score += Math.max(1, 80 - (foundIndex - haystackIndex))
    haystackIndex = foundIndex + 1
  }
  return score
}

function normalizePayload(payload, nullableFields = []) {
  const clean = { ...payload }
  const nullable = new Set(nullableFields)
  Object.keys(clean).forEach((key) => {
    if (clean[key] === '' && nullable.has(key)) {
      clean[key] = null
    }
  })
  clean.currency = String(clean.currency || '').trim().toUpperCase()
  delete clean.id
  delete clean.is_configured
  delete clean.price_mode
  delete clean.price_source_name
  delete clean.price_source_category
  delete clean.price_source_endpoint_url
  return clean
}

function payloadForDraft(draft) {
  const payload = normalizeDraftForMode(draft)
  return normalizePayload(
    {
      ...payload,
      channel: props.channel.id
    },
    [
      'settlement_ratio',
      'custom_input_price_per_million',
      'custom_output_price_per_million',
      'custom_audio_input_price_per_second',
      'custom_audio_output_price_per_second',
      'custom_video_input_price_per_second',
      'custom_video_output_price_per_second'
    ]
  )
}

function shouldPersist(draft) {
  return Boolean(
    draft.id ||
      draft.is_configured ||
      draft.is_listed ||
      draft.settlement_ratio ||
      draft.currency ||
      draft.custom_input_price_per_million ||
      draft.custom_output_price_per_million ||
      draft.custom_audio_input_price_per_second ||
      draft.custom_audio_output_price_per_second ||
      draft.custom_video_input_price_per_second ||
      draft.custom_video_output_price_per_second
  )
}

function customPriceFields(model) {
  if (!model) return []
  if (model.modality === 'audio') {
    return [
      {
        key: 'custom_audio_input_price_per_second',
        label: '音频输入 / 秒',
        shortLabel: '音入'
      },
      {
        key: 'custom_audio_output_price_per_second',
        label: '音频输出 / 秒',
        shortLabel: '音出'
      }
    ]
  }
  if (model.modality === 'video') {
    return [
      {
        key: 'custom_video_input_price_per_second',
        label: '视频输入 / 秒',
        shortLabel: '视入'
      },
      {
        key: 'custom_video_output_price_per_second',
        label: '视频输出 / 秒',
        shortLabel: '视出'
      }
    ]
  }
  if (model.image_output_price_per_image && !hasTokenPricing(model)) {
    return []
  }
  return [
    {
      key: 'custom_input_price_per_million',
      label: '文本输入 / 百万 tokens',
      shortLabel: '文入'
    },
    {
      key: 'custom_output_price_per_million',
      label: '文本输出 / 百万 tokens',
      shortLabel: '文出'
    }
  ]
}

function hasTokenPricing(model) {
  return (
    Number(model.input_price_per_million || 0) > 0 ||
    Number(model.output_price_per_million || 0) > 0
  )
}

function priceModeFromDraft(draft) {
  if (hasCustomPrices(draft)) return 'fixed'
  if (draft.settlement_ratio) return 'discount'
  return 'channel_default'
}

function hasCustomPrices(draft) {
  return customPriceKeys.some((key) => Boolean(draft[key]))
}

function applyPriceMode(draft) {
  const normalized = normalizeDraftForMode(draft)
  Object.assign(draft, normalized)
}

function normalizeDraftForMode(draft) {
  const next = { ...draft }
  if (next.price_mode === 'channel_default') {
    next.settlement_ratio = ''
    customPriceKeys.forEach((key) => {
      next[key] = ''
    })
  }
  if (next.price_mode === 'discount') {
    customPriceKeys.forEach((key) => {
      next[key] = ''
    })
  }
  if (next.price_mode === 'fixed') {
    next.settlement_ratio = ''
  }
  return next
}

async function removeRow(row) {
  const draft = row.draft
  if (draft.id) {
    saving.value = true
    try {
      await llmOpsApi.deleteChannelModelPrice(draft.id)
      drafts.value[row.model.id] = draftDefaults(row.model, null)
      baselineDrafts.value[row.model.id] = serializeDraft(
        drafts.value[row.model.id]
      )
      pendingRefresh.value = true
    } finally {
      saving.value = false
    }
    return
  }
  drafts.value[row.model.id] = draftDefaults(row.model, null)
}

function setFilteredRowsListed(value) {
  filteredRows.value.forEach((row) => {
    row.draft.is_listed = value
  })
}

async function save() {
  if (!props.channel || !hasUnsavedChanges.value) return
  saving.value = true
  try {
    const rows = Object.values(drafts.value).filter(shouldPersist)
    await llmOpsApi.bulkUpsertChannelModelPrices(
      rows.map((draft) => payloadForDraft(draft))
    )
    reset()
    emit('saved')
  } finally {
    saving.value = false
  }
}

function convertCurrencyAmount(value, sourceCurrency = 'USD') {
  if (value === null || value === undefined || value === '') return null
  const source = String(sourceCurrency || '').toUpperCase()
  const target = String(props.displayCurrency || 'CNY').toUpperCase()
  const amount = Number(value)
  if (!Number.isFinite(amount)) return null
  if (source === target) return amount
  if (source === 'USD' && target === 'CNY') {
    return amount * Number(props.exchangeRate || 7.15)
  }
  if (source === 'CNY' && target === 'USD') {
    return amount / Number(props.exchangeRate || 7.15)
  }
  return null
}

function convertAmountBetween(value, sourceCurrency, targetCurrency) {
  if (value === null || value === undefined || value === '') return null
  const source = String(sourceCurrency || '').toUpperCase()
  const target = String(targetCurrency || '').toUpperCase()
  const amount = Number(value)
  if (!Number.isFinite(amount) || !source || !target) return null
  if (source === target) return amount
  if (source === 'USD' && target === 'CNY') {
    return amount * Number(props.exchangeRate || 7.15)
  }
  if (source === 'CNY' && target === 'USD') {
    return amount / Number(props.exchangeRate || 7.15)
  }
  return null
}

function money(value, currency = 'USD') {
  if (value === null || value === undefined || value === '') return '-'
  const displayValue = convertCurrencyAmount(value, currency)
  if (displayValue === null) {
    return `${currency || 'USD'} ${Number(value).toFixed(4)}`
  }
  return `${props.displayCurrency || 'CNY'} ${displayValue.toFixed(4)}`
}

function moneyOrStatus(value, currency = 'USD') {
  if (value === null || value === undefined || value === '') return '-'
  if (Number(value) === 0) return '缺价格'
  return money(value, currency)
}

function priceText(item, model) {
  if (!item) return '-'
  if (item.value === null || item.value === undefined || item.value === '') {
    return '-'
  }
  if (Number(item.value) !== 0) {
    return money(item.value, item.currency)
  }
  if (isNotApplicablePrice(item, model)) {
    return '不适用'
  }
  return '缺价格'
}

function isNotApplicablePrice(item, model) {
  const code = String(model?.code || '').toLowerCase()
  const label = String(item?.label || '')
  if (code.includes('embedding') && label.includes('出')) {
    return true
  }
  if (
    Number(model?.image_output_price_per_image || 0) > 0 &&
    (label.includes('文本入') || label.includes('文本出'))
  ) {
    return true
  }
  return false
}

function providerPriceSummary(model) {
  if (model.modality === 'video') {
    return compactPriceRows([
      ['视频入', model.video_input_price_per_second, model.currency],
      ['视频出', model.video_output_price_per_second, model.currency]
    ])
  }
  if (model.modality === 'audio') {
    return compactPriceRows([
      ['音频入', model.audio_input_price_per_second, model.currency],
      ['音频出', model.audio_output_price_per_second, model.currency]
    ])
  }
  if (model.image_output_price_per_image) {
    return compactPriceRows([
      ['文本入', model.input_price_per_million, model.currency],
      ['文本出', model.output_price_per_million, model.currency],
      ['图片出', model.image_output_price_per_image, model.currency]
    ])
  }
  return compactPriceRows([
    ['入', model.input_price_per_million, model.currency],
    ['出', model.output_price_per_million, model.currency]
  ])
}

function draftPricePreview(draft, model) {
  if (!model) return []
  const targetCurrency =
    draft.currency || props.channel?.currency || model.currency
  if (draft.price_mode === 'fixed') {
    return fixedPricePreview(draft, model, targetCurrency)
  }
  if (draft.price_mode === 'discount') {
    return discountPricePreview(
      model,
      targetCurrency,
      Number(draft.settlement_ratio || 0)
    )
  }
  return discountPricePreview(
    model,
    targetCurrency,
    Number(props.channel?.settlement_ratio || 1)
  )
}

function fixedPricePreview(draft, model, currency) {
  return customPriceFields(model)
    .map((field) => ({
      label: `${field.shortLabel}预估`,
      value: draft[field.key],
      currency
    }))
    .filter((item) => item.value !== '')
}

function discountPricePreview(model, currency, ratio) {
  if (!Number.isFinite(ratio) || ratio <= 0) return []
  return providerPriceSummary(model)
    .map((item) => {
      const sourceCurrency = item.currency || model.currency || currency
      const baseAmount = convertAmountBetween(
        item.value,
        sourceCurrency,
        currency
      )
      return {
        label: `${item.label}预估`,
        value: baseAmount === null ? null : baseAmount * ratio,
        currency
      }
    })
    .filter((item) => item.value !== null)
}

function compactPriceRows(rows) {
  return rows
    .filter(([, value]) => value !== null && value !== undefined && value !== '')
    .map(([label, value, currency]) => ({ label, value, currency }))
}

function dimensionLabel(dimension) {
  const labels = {
    text_input: '文入',
    text_output: '文出',
    cache_input: '缓存',
    image_input: '图入',
    image_output: '图出',
    audio_input: '音入',
    audio_output: '音出',
    video_input: '视入',
    video_output: '视出'
  }
  return labels[dimension] || dimension || '-'
}

function upstreamSourceLabel(model) {
  if (!model) return '未绑定上游'
  return model.source_name || model.provider_name || '未绑定上游'
}

function purchaseSourceLabel(model) {
  if (!model) return '未选择渠道上游'
  return upstreamSourceLabel(model)
}

function channelRowSourceLabel(row) {
  return (
    row.draft.price_source_name ||
    row.model.price_source_name ||
    purchaseSourceLabel(row.model)
  )
}

function sourceCategoryLabel(category) {
  const labels = {
    official_provider: '原厂',
    supplier: '供货商',
    manual: '人工',
    unknown: '未标记类型'
  }
  return labels[category] || '未标记类型'
}

function sourceCategoryBadge(category) {
  if (!hasKnownSourceCategory(category)) return ''
  return sourceCategoryLabel(category)
}

function hasKnownSourceCategory(category) {
  return ['official_provider', 'supplier', 'manual'].includes(category)
}

function sourceTone(category) {
  const tones = {
    official_provider: 'official',
    supplier: 'supplier',
    manual: 'manual',
    unknown: 'unknown'
  }
  return tones[category] || 'unknown'
}

function comparisonTone(status) {
  return {
    below_official: 'price-chip-good',
    same_as_official: 'price-chip-neutral',
    above_official: 'price-chip-warn',
    unknown: 'price-chip-muted'
  }[status || 'unknown']
}

function comparisonTitle(item) {
  if (item.comparison_status === 'unknown') {
    return (
      '已按全局显示货币换算展示；缺少同维度上游基准价时，' +
      '暂无法判断高低。'
    )
  }
  const delta = item.delta_amount || 0
  const percent = item.delta_percent || 0
  return `较上游价格 ${item.currency} ${Number(delta).toFixed(4)} / ${Number(percent).toFixed(2)}%`
}

function modalityLabel(modality) {
  const labels = {
    text: '文本',
    audio: '音频',
    video: '视频',
    multimodal: '多模态'
  }
  return labels[modality] || modality || '-'
}

function priceModeHint(mode) {
  if (mode === 'discount') return '按模型折扣生成'
  if (mode === 'fixed') return '使用固定成本价'
  return '使用渠道默认折扣'
}
</script>

<style scoped>
.panel {
  @apply rounded-lg border border-slate-200 bg-white p-4 shadow-sm;
}

.drawer-panel {
  width: min(100vw, 1100px);
  @apply h-full overflow-y-auto bg-white shadow-xl;
}

@media (min-width: 1280px) {
  .drawer-panel {
    width: min(88vw, 1180px);
  }
}

.panel-title {
  @apply text-sm font-semibold text-slate-900;
}

.summary-pill {
  @apply inline-flex rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 font-medium text-slate-600;
}

.dirty-badge {
  @apply inline-flex items-center rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700;
}

.change-chip {
  @apply inline-flex items-center rounded-full border border-indigo-100 bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700;
}

.add-grid {
  @apply grid gap-3 md:grid-cols-2;
}

.advanced-cost-panel {
  @apply rounded-lg border border-slate-200 bg-slate-50;
}

.advanced-cost-toggle {
  @apply flex w-full items-center justify-between gap-3 px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-100;
}

.advanced-cost-grid {
  @apply grid gap-3 border-t border-slate-200 px-3 py-3 md:grid-cols-2 xl:grid-cols-4;
}

.form-field {
  @apply flex min-w-0 flex-col gap-1.5;
}

.model-select-field {
  @apply md:col-span-2 xl:col-span-1;
}

.fixed-add-field {
  @apply max-w-full;
}

.pending-association {
  @apply mt-3 grid gap-3 rounded-lg border border-indigo-100 bg-indigo-50/60 px-3 py-3 xl:grid-cols-[minmax(0,1.3fr)_minmax(12rem,0.7fr)_minmax(12rem,0.7fr)_minmax(10rem,auto)_auto] xl:items-center;
}

.pending-main {
  @apply min-w-0 border-b border-indigo-100 pb-2 xl:border-b-0 xl:border-r xl:pb-0 xl:pr-3;
}

.pending-price-summary {
  @apply grid grid-cols-2 gap-1.5 text-xs text-slate-500;
}

.pending-price-title {
  @apply col-span-2 text-[11px] font-semibold text-slate-500;
}

.pending-price-summary span {
  @apply min-w-0 rounded-lg border border-white bg-white/80 px-2 py-1;
}

.pending-price-summary strong {
  @apply mt-0.5 block truncate font-mono text-slate-900;
}

.association-meta {
  @apply flex flex-wrap gap-1.5 text-xs font-medium text-slate-600;
}

.association-meta span {
  @apply rounded-full border border-white bg-white/80 px-2 py-1;
}

.searchable-select {
  @apply relative min-w-0;
}

.searchable-trigger {
  @apply flex min-h-9 w-full items-center gap-2 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-left text-sm text-slate-800 outline-none transition hover:border-slate-300 focus:border-indigo-300 focus:ring-4 focus:ring-indigo-50;
}

.dropdown-caret {
  @apply shrink-0 text-sm leading-none text-slate-400;
}

.searchable-menu {
  @apply absolute left-0 right-0 top-[calc(100%+0.35rem)] z-30 overflow-hidden rounded-lg border border-slate-200 bg-white shadow-lg;
}

.searchable-input {
  @apply m-2 w-[calc(100%-1rem)] rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-indigo-300 focus:bg-white focus:ring-4 focus:ring-indigo-50;
}

.searchable-meta {
  @apply flex items-center justify-between gap-3 border-t border-slate-100 px-3 py-1.5 text-[11px] font-medium text-slate-400;
}

.searchable-list {
  @apply max-h-72 overflow-y-auto border-t border-slate-100 p-1;
}

.searchable-option {
  @apply flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-slate-700 transition hover:bg-indigo-50 hover:text-indigo-700;
}

.searchable-option-active {
  @apply bg-indigo-50 text-indigo-700;
}

.option-provider {
  @apply max-w-28 shrink-0 truncate rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-500;
}

.searchable-empty {
  @apply px-3 py-6 text-center text-xs text-slate-400;
}

.field-label {
  @apply block text-xs font-medium text-slate-500;
}

.field-helper {
  @apply text-xs leading-5 text-slate-400;
}

.readonly-field {
  @apply flex min-h-9 w-full items-center rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-sm font-medium text-slate-700;
}

.publish-toggle {
  @apply flex min-h-9 items-center justify-center gap-2 whitespace-nowrap rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-sm font-medium text-slate-700;
}

.publish-status {
  @apply inline-flex min-w-20 cursor-pointer items-center justify-center gap-2 whitespace-nowrap rounded-full border px-2.5 py-1 text-xs font-medium transition;
}

.fixed-price-note {
  @apply flex min-h-10 items-center rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-500;
}

.table-toolbar {
  @apply flex flex-col gap-3 border-b border-slate-200 bg-white px-4 py-3 sm:flex-row sm:items-center sm:justify-between;
}

.field {
  @apply w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 outline-none transition focus:border-indigo-300 focus:ring-4 focus:ring-indigo-50;
}

.compact-field {
  @apply min-h-9 px-2.5 py-1.5 text-sm;
}

.field-sm {
  @apply rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none focus:border-indigo-300 focus:ring-4 focus:ring-indigo-50;
}

.icon-mark {
  @apply inline-block h-3.5 w-3.5 shrink-0 rounded-sm bg-current;
}

.data-table {
  @apply min-w-full divide-y divide-slate-200;
}

.data-table tbody {
  @apply divide-y divide-slate-100 bg-white;
}

.data-table tr {
  @apply hover:bg-slate-50;
}

.data-table .recently-added-row {
  @apply bg-indigo-50/50 ring-1 ring-inset ring-indigo-100;
}

.channel-model-cards {
  @apply gap-3 p-3;
}

.channel-model-card {
  @apply rounded-lg border border-slate-200 bg-white p-3 shadow-sm;
}

.recently-added-card {
  @apply border-indigo-200 bg-indigo-50/40 ring-1 ring-inset ring-indigo-100;
}

.card-field {
  @apply rounded-lg border border-slate-100 bg-slate-50 px-2.5 py-2 text-xs text-slate-500;
}

.empty-card {
  @apply rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500;
}

.table-head {
  @apply whitespace-nowrap bg-slate-50 px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500;
}

.table-cell {
  @apply whitespace-nowrap px-4 py-3 text-sm text-slate-600;
}

.channel-model-table .table-head {
  @apply px-3 py-2 text-[11px];
}

.channel-model-table .table-cell {
  @apply whitespace-normal px-3 py-2 align-middle;
}

.channel-model-table .model-name {
  display: -webkit-box;
  max-width: 260px;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow-wrap: anywhere;
}

.channel-model-table .model-code {
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.channel-model-input {
  width: 5rem;
  padding: 0.25rem 0.4rem;
  font-size: 0.75rem;
  line-height: 1rem;
}

.currency-select {
  width: 6.75rem;
  padding: 0.25rem 0.4rem;
  font-size: 0.75rem;
  line-height: 1rem;
}

.price-mode-select {
  width: 7.5rem;
  padding: 0.25rem 0.4rem;
  font-size: 0.75rem;
  line-height: 1rem;
}

.fixed-price-grid {
  @apply grid min-w-36 max-w-xs grid-cols-1 gap-1.5;
}

.fixed-price-field {
  @apply flex items-center gap-1 text-xs text-slate-500;
}

.price-chip {
  @apply inline-flex max-w-full items-center gap-1 rounded-full px-2 py-1 text-xs font-medium;
}

.price-chip-good {
  @apply bg-emerald-50 text-emerald-700;
}

.price-chip-neutral {
  @apply bg-slate-100 text-slate-600;
}

.price-chip-warn {
  @apply bg-amber-50 text-amber-700;
}

.price-chip-muted {
  @apply bg-slate-50 text-slate-400;
}

.source-badge {
  @apply inline-flex rounded-full border px-2 py-0.5 text-[11px] font-medium;
}

.source-badge.official {
  @apply border-emerald-100 bg-emerald-50 text-emerald-700;
}

.source-badge.supplier {
  @apply border-indigo-100 bg-indigo-50 text-indigo-700;
}

.source-badge.manual {
  @apply border-amber-100 bg-amber-50 text-amber-700;
}

.source-badge.unknown {
  @apply border-slate-200 bg-slate-100 text-slate-600;
}

.source-mini-link {
  @apply inline-flex rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] font-medium text-indigo-600 hover:border-indigo-200 hover:bg-indigo-50 hover:text-indigo-700;
}

.btn-primary {
  @apply inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60;
}

.btn-secondary {
  @apply inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60;
}

.btn-toolbar {
  @apply inline-flex min-h-8 items-center rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-600 transition hover:border-indigo-200 hover:bg-indigo-50 hover:text-indigo-700 disabled:cursor-not-allowed disabled:opacity-50;
}

.link-btn {
  @apply whitespace-nowrap text-sm font-medium text-indigo-600 hover:text-indigo-700 disabled:cursor-not-allowed disabled:opacity-50;
}

.action-col {
  width: 3.75rem;
  min-width: 3.75rem;
}
</style>
