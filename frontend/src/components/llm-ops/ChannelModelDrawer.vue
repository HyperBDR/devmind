<template>
  <div
    v-if="channel"
    class="channel-model-drawer fixed inset-0 z-50 flex justify-end bg-slate-950/30"
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
            <button
              type="button"
              class="btn-secondary btn-action-cancel"
              @click="close"
            >
              关闭
            </button>
            <button
              type="button"
              class="btn-primary btn-action-save"
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
              <h4 class="text-sm font-semibold text-slate-900">添加渠道模型</h4>
              <p class="mt-1 text-xs leading-5 text-slate-500">
                先选择元模型，再指定该渠道实际使用的上游供货源。
                添加后默认启用，可在下方设置成本规则和固定成本价。
              </p>
            </div>
            <div class="flex flex-wrap gap-2 text-xs text-slate-500">
              <span class="summary-pill">
                已配置 {{ managedRows.length }}
              </span>
              <span class="summary-pill"> 已启用 {{ listedCount }} </span>
              <span class="summary-pill">
                可添加 {{ availableModelCount }}
              </span>
            </div>
          </div>

          <div class="add-model-layout">
            <div class="add-model-main">
              <div class="add-grid">
                <div class="form-field">
                  <label class="field-label">元模型厂商</label>
                  <CompactSelect
                    v-model="selectedVendorKey"
                    :options="vendorOptions"
                    placeholder="先选择元模型厂商"
                    searchable
                    search-placeholder="搜索厂商"
                    @change="handleVendorChange"
                  />
                </div>

                <div class="form-field model-select-field">
                  <label class="field-label">选择元模型</label>
                  <div ref="modelDropdownRef" class="searchable-select">
                    <button
                      class="searchable-trigger"
                      :disabled="!selectedVendorKey"
                      type="button"
                      @click="toggleModelDropdown"
                    >
                      <span class="min-w-0 flex-1">
                        <span
                          v-if="selectedModelCount"
                          class="block truncate font-medium text-slate-800"
                        >
                          已选 {{ selectedModelCount }} 个元模型
                        </span>
                        <span
                          v-else-if="!selectedVendorKey"
                          class="block truncate text-slate-400"
                        >
                          先选择元模型厂商
                        </span>
                        <span v-else class="block truncate text-slate-400">
                          搜索并选择元模型
                        </span>
                      </span>
                      <span class="dropdown-caret">⌄</span>
                    </button>

                    <div v-if="modelDropdownOpen" class="searchable-menu">
                      <input
                        ref="modelSearchInput"
                        v-model="modelSearch"
                        class="searchable-input"
                        placeholder="名称 / code / 模态"
                        @keydown.escape="closeModelDropdown"
                      />
                      <div class="searchable-meta">
                        <span>
                          {{ availableModelGroups.length }} 个可添加元模型
                          <template v-if="selectedModelCount">
                            · 已选 {{ selectedModelCount }}
                          </template>
                        </span>
                        <span class="searchable-meta-actions">
                          <button
                            type="button"
                            @click.stop="selectVisibleModels"
                          >
                            全选当前结果
                          </button>
                          <button
                            type="button"
                            @click.stop="clearSelectedModels"
                          >
                            清空
                          </button>
                        </span>
                      </div>
                      <div class="searchable-list">
                        <button
                          v-for="model in availableModelOptions"
                          :key="model.key"
                          class="searchable-option"
                          :class="
                            isModelSelected(model.key)
                              ? 'searchable-option-active'
                              : ''
                          "
                          :aria-checked="isModelSelected(model.key)"
                          role="checkbox"
                          type="button"
                          @click="toggleModelSelection(model)"
                        >
                          <span
                            class="searchable-checkbox"
                            :class="
                              isModelSelected(model.key)
                                ? 'searchable-checkbox-checked'
                                : ''
                            "
                          >
                            <span v-if="isModelSelected(model.key)">✓</span>
                          </span>
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
                            {{
                              model.modalitySummary ||
                              modalityLabel(model.modality)
                            }}
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

                <div class="inline-cost-grid">
                  <div class="form-field">
                    <label class="field-label">成本规则</label>
                    <CompactSelect
                      v-model="newDraft.price_mode"
                      :options="priceModeOptions"
                      @change="applyPriceMode(newDraft)"
                    />
                  </div>

                  <div class="form-field">
                    <label class="field-label">配置值</label>
                    <div
                      v-if="newDraft.price_mode === 'channel_default'"
                      class="readonly-field cost-value-readonly"
                    >
                      <span class="truncate">渠道默认折扣</span>
                      <strong>
                        {{ ratioPercent(props.channel?.settlement_ratio, 1) }}
                      </strong>
                    </div>
                    <div
                      v-else-if="newDraft.price_mode === 'discount'"
                      class="percent-input-wrap"
                    >
                      <input
                        v-model="newDraftSettlementPercent"
                        class="field compact-field pr-8 text-right"
                        min="0"
                        step="0.01"
                        type="number"
                        placeholder="85"
                      />
                      <span>%</span>
                    </div>
                    <div
                      v-else-if="newDraft.price_mode === 'fixed'"
                      class="fixed-cost-value-grid"
                    >
                      <label
                        v-for="field in customPriceFields(selectedCostModel)"
                        :key="field.key"
                        class="form-field fixed-add-field"
                      >
                        <span class="field-label">{{ field.label }}</span>
                        <input
                          v-model="newDraft[field.key]"
                          class="field compact-field text-right"
                          step="0.000001"
                          type="number"
                          placeholder="可选"
                        />
                      </label>
                      <div
                        v-if="
                          selectedCostModel &&
                          !customPriceFields(selectedCostModel).length
                        "
                        class="fixed-price-note"
                      >
                        当前模型的图片等特殊计价维度暂不支持在渠道配置中手动覆盖，
                        会使用上游价格或折扣后的渠道成本价。
                      </div>
                      <div
                        v-else-if="!selectedCostModel"
                        class="fixed-price-note"
                      >
                        先选择元模型，再配置固定成本价。
                      </div>
                    </div>
                    <div v-else class="readonly-field">
                      <span class="truncate">跟随成本规则</span>
                    </div>
                  </div>
                </div>
              </div>

              <div
                v-if="selectedModelOptions.length"
                class="batch-selection-panel"
              >
                <div class="batch-selection-head">
                  <div>
                    <p>已选模型</p>
                    <span>为每个元模型指定实际使用的渠道上游。</span>
                  </div>
                  <button type="button" @click="clearSelectedModels">
                    清空选择
                  </button>
                </div>
                <div class="batch-selection-list">
                  <div
                    v-for="item in selectedResolvedModels"
                    :key="item.group.key"
                    class="batch-selection-row"
                  >
                    <div class="batch-model-main">
                      <p>{{ item.group.name }}</p>
                      <span>{{ modelOptionMeta(item.group) }}</span>
                    </div>
                    <CompactSelect
                      v-if="item.options?.length"
                      :model-value="
                        selectedProviderByModelKey[item.group.key] || ''
                      "
                      :options="item.options"
                      placeholder="选择渠道上游"
                      searchable
                      search-placeholder="搜索上游 / 币种 / 类型"
                      @change="
                        (value) =>
                          selectBatchPriceSourceModel(item.group.key, value)
                      "
                    />
                    <div v-else class="readonly-field">
                      <span class="truncate">无可用上游</span>
                    </div>
                    <div v-if="item.model" class="batch-price-preview">
                      <span>
                        上游 {{ batchUpstreamPriceSummary(item.model) }}
                      </span>
                      <strong>
                        成本
                        {{
                          batchPendingDraftPriceSummary(newDraft, item.model)
                        }}
                      </strong>
                    </div>
                    <div v-else class="batch-price-preview muted">
                      <span>待选择渠道上游</span>
                      <strong>选择后显示价格</strong>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div class="channel-performance-panel">
              <p class="channel-performance-title">模型转发能力</p>
              <div class="channel-performance-grid">
                <label
                  v-for="field in performanceFields"
                  :key="field.key"
                  class="form-field"
                >
                  <span class="field-label">{{ field.label }}</span>
                  <input
                    v-model="newDraft[field.key]"
                    class="field compact-field text-right"
                    min="0"
                    step="1"
                    type="number"
                    :placeholder="field.placeholder"
                  />
                </label>
              </div>
            </div>
          </div>

          <div v-if="selectedModelOptions.length" class="pending-association">
            <div class="pending-main">
              <p class="truncate text-sm font-semibold text-slate-900">
                已选 {{ selectedModelCount }} 个元模型
              </p>
              <p class="mt-1 truncate text-xs text-slate-500">
                {{ selectedResolvedCount }} 个已指定上游
              </p>
            </div>
            <div class="pending-price-compact">
              <span>成本规则</span>
              <strong>{{ newDraftRuleSummary }}</strong>
            </div>
            <div class="pending-price-compact">
              <span>转发能力</span>
              <strong>{{ newDraftPerformanceSummary }}</strong>
            </div>
            <button
              type="button"
              class="btn-primary btn-compact btn-action-create"
              :disabled="!canAddSelectedModels"
              @click="addSelectedModels"
            >
              批量添加 {{ selectedModelCount }} 个模型
            </button>
          </div>
        </div>

        <div class="grid gap-3">
          <input
            v-model="search"
            class="field compact-field"
            placeholder="搜索已配置元模型、code 或上游来源"
          />
        </div>

        <div class="panel channel-model-list-panel p-0">
          <div class="table-toolbar">
            <div class="min-w-0">
              <h3 class="panel-title">
                已配置元模型（{{ filteredRows.length }}）
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
                v-if="hiddenConfiguredRowCount"
                type="button"
                class="btn-toolbar btn-action-view"
                @click="configuredRowsExpanded = !configuredRowsExpanded"
              >
                {{
                  configuredRowsExpanded
                    ? '收起'
                    : `显示全部 ${filteredRows.length}`
                }}
              </button>
            </div>
          </div>
          <div class="grid channel-model-cards lg:hidden">
            <article
              v-for="row in displayedRows"
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
                <OperationIconButton
                  icon="remove"
                  label="移除"
                  tone="danger"
                  @click="removeRow(row)"
                />
              </div>

              <div class="mt-3 flex flex-wrap items-center gap-1.5">
                <span
                  v-if="hasKnownSourceCategory(modelSourceCategory(row.model))"
                  :class="[
                    'source-badge',
                    sourceTone(modelSourceCategory(row.model))
                  ]"
                >
                  {{ sourceCategoryLabel(modelSourceCategory(row.model)) }}
                </span>
                <span class="source-badge unknown">
                  {{ channelRowSourceLabel(row) }}
                </span>
                <span class="source-badge unknown">
                  {{ modalityLabel(row.model.modality) }}
                </span>
              </div>

              <div class="channel-model-summary-list">
                <div class="channel-model-price-summary">
                  <span>价格</span>
                  <strong>
                    <em>规则</em>
                    {{ priceRuleSummary(row) }}
                  </strong>
                  <strong>
                    <em>成本</em>
                    {{ compactCostSummary(row) }}
                  </strong>
                  <strong>
                    <em>上游</em>
                    {{ upstreamPriceSummary(row.model) }}
                  </strong>
                </div>
                <div class="channel-model-ability-summary">
                  <span>能力</span>
                  <strong
                    v-for="item in performanceSummaryItems(row)"
                    :key="item.label"
                  >
                    <em>{{ item.label }}</em>
                    {{ item.value }}
                  </strong>
                </div>
              </div>

              <details class="channel-model-detail">
                <summary>配置详情</summary>

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
                      v-if="row.priceItems?.length"
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
                  <div
                    v-if="row.draft.price_mode === 'discount'"
                    class="percent-input-wrap"
                  >
                    <input
                      :value="ratioToPercentInput(row.draft.settlement_ratio)"
                      class="field compact-field pr-8 text-right"
                      min="0"
                      step="0.01"
                      type="number"
                      placeholder="85"
                      @input="
                        updateSettlementPercent(row.draft, $event.target.value)
                      "
                    />
                    <span>%</span>
                  </div>
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

                <div class="mt-3 grid gap-2 sm:grid-cols-3">
                  <label
                    v-for="field in performanceFields"
                    :key="field.key"
                    class="form-field"
                  >
                    <span class="field-label">{{ field.label }}</span>
                    <input
                      v-model="row.draft[field.key]"
                      class="field compact-field text-right"
                      min="0"
                      step="1"
                      type="number"
                      :placeholder="field.placeholder"
                    />
                  </label>
                </div>
              </details>
            </article>
            <div v-if="!filteredRows.length" class="empty-card">
              还没有配置模型，请先从上方添加。
            </div>
            <button
              v-if="hiddenConfiguredRowCount"
              type="button"
              class="show-more-card"
              @click="configuredRowsExpanded = true"
            >
              还有 {{ hiddenConfiguredRowCount }} 个模型，点击显示全部
            </button>
          </div>

          <div class="hidden lg:block">
            <table class="data-table channel-model-table">
              <colgroup>
                <col class="model-col" />
                <col class="source-col" />
                <col class="price-col" />
                <col class="ability-col" />
                <col class="action-col" />
              </colgroup>
              <thead>
                <tr>
                  <th class="table-head">模型</th>
                  <th class="table-head">上游</th>
                  <th class="table-head">价格</th>
                  <th class="table-head">能力</th>
                  <th class="table-head action-col text-center">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="row in displayedRows"
                  :key="row.model.id"
                  :class="
                    String(recentlyAddedModelId) === String(row.model.id)
                      ? 'recently-added-row'
                      : ''
                  "
                >
                  <td class="table-cell model-cell">
                    <p class="model-name font-medium text-slate-900">
                      {{ modelDisplayName(row.model) }}
                    </p>
                    <p class="model-code mt-1 font-mono text-xs text-slate-500">
                      {{ channelModelSubtitle(row) }}
                    </p>
                  </td>
                  <td class="table-cell">
                    <div class="source-cell">
                      <p>{{ channelRowSourceLabel(row) }}</p>
                      <div>
                        <span
                          v-if="
                            hasKnownSourceCategory(
                              modelSourceCategory(row.model)
                            )
                          "
                          :class="[
                            'source-badge',
                            sourceTone(modelSourceCategory(row.model))
                          ]"
                        >
                          {{
                            sourceCategoryLabel(modelSourceCategory(row.model))
                          }}
                        </span>
                        <span class="source-badge unknown">
                          {{ modalityLabel(row.model.modality) }}
                        </span>
                      </div>
                    </div>
                  </td>
                  <td class="table-cell">
                    <div class="price-cell">
                      <p>
                        <em>规则</em>
                        <strong>{{ priceRuleSummary(row) }}</strong>
                      </p>
                      <span>
                        <em>成本</em>
                        <strong>{{ compactCostSummary(row) }}</strong>
                      </span>
                      <span>
                        <em>上游</em>
                        <strong>{{ upstreamPriceSummary(row.model) }}</strong>
                      </span>
                    </div>
                  </td>
                  <td class="table-cell">
                    <div class="ability-edit-cell">
                      <label
                        v-for="field in performanceFields"
                        :key="field.key"
                        :title="field.title"
                      >
                        <span>{{ field.shortLabel }}</span>
                        <input
                          v-model="row.draft[field.key]"
                          class="field-sm table-performance-input text-right"
                          min="0"
                          step="1"
                          type="number"
                          :placeholder="field.shortPlaceholder"
                        />
                      </label>
                    </div>
                  </td>
                  <td class="table-cell action-col text-center">
                    <div class="flex items-center justify-center">
                      <OperationIconButton
                        icon="remove"
                        label="移除"
                        tone="danger"
                        @click="removeRow(row)"
                      />
                    </div>
                  </td>
                </tr>
                <tr v-if="hiddenConfiguredRowCount">
                  <td class="table-cell text-center text-slate-500" colspan="5">
                    <button
                      type="button"
                      class="link-btn"
                      @click="configuredRowsExpanded = true"
                    >
                      还有 {{ hiddenConfiguredRowCount }} 个模型，点击显示全部
                    </button>
                  </td>
                </tr>
                <tr v-if="!filteredRows.length">
                  <td class="table-cell text-slate-500" colspan="5">
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
import '@/components/llm-ops/channelModelDrawer.css'

import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { llmOpsApi } from '@/api/llmOps'
import {
  normalizeSearch,
  useChannelModelDisplay
} from '@/composables/useChannelModelDisplay'
import { useChannelModelDrafts } from '@/composables/useChannelModelDrafts'
import { useChannelModelNewDraft } from '@/composables/useChannelModelNewDraft'
import { useChannelModelPricing } from '@/composables/useChannelModelPricing'
import { useChannelModelRows } from '@/composables/useChannelModelRows'
import { useChannelModelSelection } from '@/composables/useChannelModelSelection'
import CompactSelect from './CompactSelect.vue'
import OperationIconButton from './OperationIconButton.vue'

const props = defineProps({
  channel: {
    type: Object,
    default: null
  },
  providers: {
    type: Array,
    default: () => []
  },
  metaModels: {
    type: Array,
    default: () => []
  },
  models: {
    type: Array,
    default: () => []
  },
  channelPrices: {
    type: Array,
    default: () => []
  },
  channelPriceItems: {
    type: Array,
    default: () => []
  },
  priceItems: {
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
const selectedVendorKey = ref('')
const modelSearch = ref('')
const selectedModelKeys = ref(new Set())
const selectedProviderByModelKey = ref({})
const modelDropdownOpen = ref(false)
const modelDropdownRef = ref(null)
const modelSearchInput = ref(null)
const configuredRowsExpanded = ref(false)
const drafts = ref({})
const baselineDrafts = ref({})
const saving = ref(false)
const pendingRefresh = ref(false)
const recentlyAddedModelId = ref(null)

const priceModeOptions = [
  { label: '默认折扣', value: 'channel_default' },
  { label: '折扣比例', value: 'discount' },
  { label: '固定成本价', value: 'fixed' }
]

const channelCurrency = computed(() =>
  String(props.channel?.currency || 'USD').toUpperCase()
)

const {
  applyPriceMode,
  costCurrencyTitle,
  customPriceFields,
  draftDefaults,
  emptyNewDraft,
  payloadForDraft,
  percentInputToRatio,
  performanceFields,
  priceRuleSummary,
  ratioPercent,
  ratioToPercentInput,
  serializeDraft,
  shouldPersist,
  summarizeDraftChanges,
  updateSettlementPercent
} = useChannelModelDrafts({
  baselineDrafts,
  channelCurrency,
  drafts,
  getChannel: () => props.channel,
  getModelSourceCategory: (model) => modelSourceCategory(model)
})

const {
  batchPendingDraftPriceSummary,
  batchUpstreamPriceSummary,
  channelRowSourceLabel,
  compactCostSummary,
  comparisonTitle,
  comparisonTone,
  dimensionLabel,
  hasKnownSourceCategory,
  modalityLabel,
  moneyOrStatus,
  modelSourceCategory,
  performanceSummaryItems,
  priceText,
  providerPriceSummary,
  purchaseSourceLabel,
  sortPriceItems,
  sourceCategoryBadge,
  sourceCategoryLabel,
  sourceTone,
  upstreamPriceSummary
} = useChannelModelPricing({
  customPriceFields,
  normalizeSearch,
  props
})

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
    return !configuredIdentityKeys.value.has(modelMetaIdentityKey(model))
  })
)

const configuredIdentityKeys = computed(() => {
  const keys = new Set()
  props.models.forEach((model) => {
    const draft = drafts.value[model.id]
    if (draft?.is_configured || shouldPersist(draft || {})) {
      keys.add(modelMetaIdentityKey(model))
    }
  })
  return keys
})

const metaModelById = computed(() => {
  const items = new Map()
  props.metaModels.forEach((model) => {
    if (model?.id !== undefined && model?.id !== null) {
      items.set(String(model.id), model)
    }
  })
  return items
})

const metaModelByCode = computed(() => {
  const items = new Map()
  props.metaModels.forEach((model) => {
    const code = normalizeSearch(model?.code || '')
    if (code) {
      items.set(code, model)
    }
  })
  return items
})

const {
  channelModelSubtitle,
  fuzzyScore,
  metaModelDisplayName,
  metaModelForSourceModel,
  metaModelIdentityKey,
  metaModelVendorKey,
  metaModelVendorName,
  modelDisplayName,
  modelMetaIdentityKey,
  modelOptionMeta,
  modelOptionSearchText,
  providerModelDescription
} = useChannelModelDisplay({
  hasKnownSourceCategory,
  metaModelByCode,
  metaModelById,
  modalityLabel,
  modelSourceCategory,
  sourceCategoryLabel
})

const {
  availableModelCount,
  availableModelGroups,
  availableModelOptions,
  canAddSelectedModels,
  clearSelectedModels,
  isModelSelected,
  selectBatchPriceSourceModel,
  selectVisibleModels,
  selectedCostModel,
  selectedModelCount,
  selectedResolvedModels,
  toggleModelSelection,
  vendorOptions
} = useChannelModelSelection({
  baseAvailableModels,
  fuzzyScore,
  metaModelDisplayName,
  metaModelForSourceModel,
  metaModelIdentityKey,
  metaModelVendorKey,
  metaModelVendorName,
  modalityLabel,
  modelOptionSearchText,
  modelSearch,
  modelSourceCategory,
  normalizeSearch,
  providerModelDescription,
  providerPriceSummary,
  purchaseSourceLabel,
  selectedModelKeys,
  selectedProviderByModelKey,
  selectedVendorKey,
  sourceCategoryBadge
})

const {
  currencyOptions,
  newDraft,
  newDraftPerformanceSummary,
  newDraftRuleSummary,
  newDraftSettlementPercent,
  addSelectedModels,
  resetNewDraft
} = useChannelModelNewDraft({
  applyPriceMode,
  canAddSelectedModels,
  channelCurrency,
  clearSelectedModels,
  draftDefaults,
  drafts,
  emptyNewDraft,
  modelDropdownOpen,
  modelSearch,
  modelSourceCategory,
  percentInputToRatio,
  performanceFields,
  props,
  ratioPercent,
  ratioToPercentInput,
  recentlyAddedModelId,
  selectedResolvedModels
})

const {
  displayedRows,
  filteredRows,
  hiddenConfiguredRowCount,
  listedCount,
  managedRows
} = useChannelModelRows({
  configuredRowsExpanded,
  drafts,
  props,
  search,
  shouldPersist,
  sortPriceItems
})

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
  selectedVendorKey.value = ''
  modelSearch.value = ''
  clearSelectedModels()
  modelDropdownOpen.value = false
  configuredRowsExpanded.value = false
  resetNewDraft()
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

function toggleModelDropdown() {
  if (!selectedVendorKey.value) return
  if (modelDropdownOpen.value) {
    closeModelDropdown()
    return
  }
  openModelDropdown()
}

function openModelDropdown() {
  if (!selectedVendorKey.value) return
  modelDropdownOpen.value = true
  nextTick(() => {
    modelSearchInput.value?.focus()
  })
}

function closeModelDropdown() {
  modelDropdownOpen.value = false
}

function handleVendorChange() {
  clearSelectedModels()
  modelSearch.value = ''
  modelDropdownOpen.value = false
}

function handleModelDropdownOutside(event) {
  if (!modelDropdownOpen.value || !modelDropdownRef.value) return
  if (!modelDropdownRef.value.contains(event.target)) {
    closeModelDropdown()
  }
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
</script>
