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
                      v-if="item.options.length"
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
                      <span>上游 {{ upstreamPriceSummary(item.model) }}</span>
                      <strong>
                        成本
                        {{ pendingDraftPriceSummary(newDraft, item.model) }}
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
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { llmOpsApi } from '@/api/llmOps'
import CompactSelect from './CompactSelect.vue'
import OperationIconButton from './OperationIconButton.vue'

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
const performanceFields = [
  {
    key: 'tpm_limit',
    label: 'TPM',
    shortLabel: 'TPM',
    placeholder: '每分钟 Token',
    shortPlaceholder: 'Token/min',
    title: '每分钟 Token 上限'
  },
  {
    key: 'rpm_limit',
    label: 'RPM',
    shortLabel: 'RPM',
    placeholder: '每分钟请求',
    shortPlaceholder: 'Req/min',
    title: '每分钟请求上限'
  },
  {
    key: 'latency_ms',
    label: '延迟(ms)',
    shortLabel: '延迟',
    placeholder: '毫秒',
    shortPlaceholder: 'ms',
    title: '渠道平均延迟，单位毫秒'
  }
]
const performanceFieldKeys = performanceFields.map((field) => field.key)

const priceModeOptions = [
  { label: '默认折扣', value: 'channel_default' },
  { label: '折扣比例', value: 'discount' },
  { label: '固定成本价', value: 'fixed' }
]

const channelCurrency = computed(() =>
  String(props.channel?.currency || 'USD').toUpperCase()
)

const currencyOptions = computed(() => [
  {
    label: '使用渠道默认币种',
    value: '',
    description: `保存为 ${channelCurrency.value}`
  },
  { label: 'CNY', value: 'CNY', description: '固定保存为人民币' },
  { label: 'USD', value: 'USD', description: '固定保存为美元' }
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

const vendorOptions = computed(() => {
  const vendors = new Map()
  baseAvailableModels.value.forEach((model) => {
    const key = modelVendorKey(model)
    const vendor = vendors.get(key) || {
      label: modelVendorName(model),
      value: key,
      count: 0
    }
    vendor.count += 1
    vendors.set(key, vendor)
  })
  return Array.from(vendors.values())
    .map((vendor) => ({
      label: vendor.label,
      value: vendor.value,
      description: `${vendor.count} 个可添加元模型`
    }))
    .sort((left, right) => left.label.localeCompare(right.label))
})

const availableModelGroups = computed(() => {
  const groups = new Map()
  baseAvailableModels.value
    .filter(
      (model) =>
        !selectedVendorKey.value ||
        modelVendorKey(model) === selectedVendorKey.value
    )
    .forEach((model) => {
      const key = modelMetaIdentityKey(model)
      const group = groups.get(key) || {
        key,
        name: modelDisplayName(model),
        code: model.meta_model_code || model.code,
        modality: model.modality,
        modalities: new Set(),
        models: []
      }
      group.models.push(model)
      if (model.modality) {
        group.modalities.add(model.modality)
      }
      group.providerCount = uniqueProviderModelsForGroup(group).length
      groups.set(key, group)
    })
  return Array.from(groups.values())
    .map((group) => ({
      ...group,
      modalitySummary: Array.from(group.modalities)
        .map((modality) => modalityLabel(modality))
        .join(' / ')
    }))
    .sort((left, right) => left.name.localeCompare(right.name))
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

const selectedModelOptions = computed(() =>
  availableModelGroups.value.filter((option) =>
    selectedModelKeys.value.has(option.key)
  )
)

const selectedModelCount = computed(() => selectedModelOptions.value.length)

const selectedResolvedModels = computed(() =>
  selectedModelOptions.value.map((group) => {
    const selectedProviderId = selectedProviderByModelKey.value[group.key] || ''
    const model = group.models.find(
      (item) => String(item.id) === String(selectedProviderId)
    )
    return {
      group,
      model: model || null,
      options: providerOptionsForModelGroup(group)
    }
  })
)

const selectedResolvedCount = computed(
  () => selectedResolvedModels.value.filter((item) => item.model).length
)

const selectedCostModel = computed(() => {
  const selected = selectedResolvedModels.value.find((item) => item.model)
  return selected?.model || selectedModelOptions.value[0]?.models?.[0] || null
})

const canAddSelectedModels = computed(
  () =>
    selectedModelCount.value > 0 &&
    selectedResolvedCount.value === selectedModelCount.value
)

const newDraftRuleSummary = computed(() => {
  if (newDraft.value.price_mode === 'discount') {
    return `折扣 ${ratioPercent(newDraft.value.settlement_ratio)}`
  }
  if (newDraft.value.price_mode === 'fixed') return '固定成本价'
  return `默认折扣 ${ratioPercent(props.channel?.settlement_ratio, 1)}`
})

const newDraftPerformanceSummary = computed(() => {
  const parts = performanceFields.map((field) => {
    const value = newDraft.value[field.key] || '-'
    return `${field.shortLabel} ${value}`
  })
  return parts.join(' · ')
})

const newDraftSettlementPercent = computed({
  get() {
    return ratioToPercentInput(newDraft.value.settlement_ratio)
  },
  set(value) {
    newDraft.value.settlement_ratio = percentInputToRatio(value)
  }
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
      priceItems: channelPriceItemsForModel(model, drafts.value[model.id])
    }))
})

const filteredRows = computed(() => {
  if (!props.channel) return []
  const keyword = search.value.trim().toLowerCase()
  return managedRows.value.filter((row) => {
    const currentModel = row.model
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
    return true
  })
})

const displayedRows = computed(() => {
  if (configuredRowsExpanded.value) return filteredRows.value
  return filteredRows.value.slice(0, 20)
})

const hiddenConfiguredRowCount = computed(() =>
  Math.max(filteredRows.value.length - displayedRows.value.length, 0)
)

function channelPriceItemsForModel(model, draft) {
  if (!props.channel || !draft?.id) return []
  return sortPriceItems(
    props.channelPriceItems.filter(
      (item) =>
        String(item.channel) === String(props.channel.id) &&
        String(item.model) === String(model.id) &&
        item.is_current !== false
    )
  )
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
  selectedVendorKey.value = ''
  modelSearch.value = ''
  clearSelectedModels()
  modelDropdownOpen.value = false
  configuredRowsExpanded.value = false
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
      normalized.custom_video_output_price_per_second || '',
    tpm_limit: normalized.tpm_limit || '',
    rpm_limit: normalized.rpm_limit || '',
    latency_ms: normalized.latency_ms || ''
  }
}

function isSerializedConfigured(draft) {
  return Boolean(
    draft?.id || draft?.is_configured || shouldPersist(draft || {})
  )
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
      price?.price_source_category || modelSourceCategory(model) || '',
    price_source_endpoint_url:
      price?.price_source_endpoint_url || model.source_endpoint_url || '',
    is_configured: Boolean(price?.id),
    is_listed: price?.is_listed || false,
    price_mode: priceModeFromDraft(price || {}),
    currency: price?.currency || '',
    settlement_ratio: price?.settlement_ratio || '',
    custom_input_price_per_million: price?.custom_input_price_per_million || '',
    custom_output_price_per_million:
      price?.custom_output_price_per_million || '',
    custom_audio_input_price_per_second:
      price?.custom_audio_input_price_per_second || '',
    custom_audio_output_price_per_second:
      price?.custom_audio_output_price_per_second || '',
    custom_video_input_price_per_second:
      price?.custom_video_input_price_per_second || '',
    custom_video_output_price_per_second:
      price?.custom_video_output_price_per_second || '',
    tpm_limit: price?.tpm_limit || '',
    rpm_limit: price?.rpm_limit || '',
    latency_ms: price?.latency_ms || ''
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
    custom_video_output_price_per_second: '',
    tpm_limit: '',
    rpm_limit: '',
    latency_ms: ''
  }
}

function addSelectedModels() {
  if (!canAddSelectedModels.value) return
  const modelsToAdd = selectedResolvedModels.value
    .map((item) => item.model)
    .filter(Boolean)
  modelsToAdd.forEach((model) => {
    drafts.value[model.id] = buildDraftForModel(model)
    applyPriceMode(drafts.value[model.id])
  })
  recentlyAddedModelId.value = modelsToAdd.at(-1)?.id || null
  newDraft.value = emptyNewDraft()
  modelSearch.value = ''
  clearSelectedModels()
  modelDropdownOpen.value = false
  nextTick(() => {
    const row = document.querySelector(
      '.recently-added-row, .recently-added-card'
    )
    row?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  })
}

function buildDraftForModel(model) {
  return {
    ...draftDefaults(model, null),
    is_configured: true,
    is_listed: true,
    price_mode: newDraft.value.price_mode,
    price_source: model.source || '',
    price_source_name: model.source_name || '',
    price_source_category: modelSourceCategory(model) || '',
    price_source_endpoint_url: model.source_endpoint_url || '',
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
        : '',
    tpm_limit: newDraft.value.tpm_limit,
    rpm_limit: newDraft.value.rpm_limit,
    latency_ms: newDraft.value.latency_ms
  }
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

function providerOptionsForModelGroup(group) {
  if (!group) return []
  return uniqueProviderModelsForGroup(group)
    .slice()
    .sort((left, right) =>
      purchaseSourceLabel(left).localeCompare(purchaseSourceLabel(right))
    )
    .map((model) => ({
      label: purchaseSourceLabel(model),
      value: model.id,
      description: providerModelDescription(model),
      badge: sourceCategoryBadge(modelSourceCategory(model)),
      searchText: [
        model.provider_name,
        model.provider_code,
        model.source_name,
        modelSourceCategory(model),
        model.currency
      ].join(' ')
    }))
}

function uniqueProviderModelsForGroup(group) {
  if (!group?.models?.length) return []
  const modelsByUpstream = new Map()
  group.models.forEach((model) => {
    const key = providerOptionIdentityKey(model)
    const current = modelsByUpstream.get(key)
    if (!current || providerOptionScore(model) > providerOptionScore(current)) {
      modelsByUpstream.set(key, model)
    }
  })
  return Array.from(modelsByUpstream.values())
}

function providerOptionIdentityKey(model) {
  const sourceId = String(model?.source || '').trim()
  if (sourceId) return `source:${sourceId}`
  return `model:${model?.id || model?.code || model?.name || ''}`
}

function providerOptionScore(model) {
  return providerPriceSummary(model).length
}

function isModelSelected(key) {
  return selectedModelKeys.value.has(key)
}

function toggleModelSelection(modelOption) {
  const next = new Set(selectedModelKeys.value)
  if (next.has(modelOption.key)) {
    next.delete(modelOption.key)
    removeSelectedProvider(modelOption.key)
  } else {
    next.add(modelOption.key)
    ensureDefaultProvider(modelOption)
  }
  selectedModelKeys.value = next
}

function selectVisibleModels() {
  const next = new Set(selectedModelKeys.value)
  availableModelOptions.value.forEach((modelOption) => {
    next.add(modelOption.key)
    ensureDefaultProvider(modelOption)
  })
  selectedModelKeys.value = next
}

function clearSelectedModels() {
  selectedModelKeys.value = new Set()
  selectedProviderByModelKey.value = {}
}

function ensureDefaultProvider(group) {
  if (selectedProviderByModelKey.value[group.key]) return
  const options = uniqueProviderModelsForGroup(group)
  if (options.length !== 1) return
  selectBatchPriceSourceModel(group.key, options[0].id)
}

function removeSelectedProvider(key) {
  const next = { ...selectedProviderByModelKey.value }
  delete next[key]
  selectedProviderByModelKey.value = next
}

function selectBatchPriceSourceModel(key, value) {
  selectedProviderByModelKey.value = {
    ...selectedProviderByModelKey.value,
    [key]: value
  }
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

function modelVendorKey(model) {
  return normalizeSearch(
    model.meta_model_owner_code ||
      model.meta_model_owner_name ||
      model.provider_code ||
      model.provider_name ||
      'unknown'
  )
}

function modelVendorName(model) {
  return (
    model.meta_model_owner_name ||
    model.meta_model_owner_code ||
    model.provider_name ||
    model.provider_code ||
    '未归属厂商'
  )
}

function modelMetaIdentityKey(model) {
  return normalizeSearch(
    model.meta_model || model.meta_model_code || model.code || model.name
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
      option.modalitySummary,
      option.models.map((model) => model.modality).join(' '),
      option.models.map((model) => model.provider_name).join(' '),
      option.models.map((model) => model.provider_code).join(' '),
      option.models.map((model) => model.source_name).join(' '),
      option.models.map((model) => modelSourceCategory(model)).join(' '),
      modalityLabel(option.modality)
    ]
      .filter(Boolean)
      .join(' ')
  )
}

function providerModelDescription(model) {
  return [
    hasKnownSourceCategory(modelSourceCategory(model))
      ? sourceCategoryLabel(modelSourceCategory(model))
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

function ratioPercent(value, fallback = null) {
  const rawValue =
    value === '' || value === null || value === undefined ? fallback : value
  const ratio = Number(rawValue)
  if (!Number.isFinite(ratio)) return '-'
  return `${(ratio * 100).toFixed(1)}%`
}

function ratioToPercentInput(value) {
  if (value === '' || value === null || value === undefined) return ''
  const ratio = Number(value)
  if (!Number.isFinite(ratio)) return ''
  return Number((ratio * 100).toFixed(4)).toString()
}

function percentInputToRatio(value) {
  if (value === '' || value === null || value === undefined) return ''
  const percent = Number(value)
  if (!Number.isFinite(percent)) return ''
  return String(percent / 100)
}

function updateSettlementPercent(draft, value) {
  draft.settlement_ratio = percentInputToRatio(value)
}

function priceRuleSummary(row) {
  const draft = row?.draft || {}
  if (draft.price_mode === 'fixed') return '固定成本价'
  if (draft.price_mode === 'discount') {
    return `折扣 ${ratioPercent(draft.settlement_ratio)}`
  }
  return `默认折扣 ${ratioPercent(props.channel?.settlement_ratio, 1)}`
}

function costCurrencyTitle(currency) {
  const value = String(currency || '')
    .trim()
    .toUpperCase()
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
  clean.currency = String(clean.currency || '')
    .trim()
    .toUpperCase()
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
      'custom_video_output_price_per_second',
      ...performanceFieldKeys
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
      draft.custom_video_output_price_per_second ||
      performanceFieldKeys.some((key) => draft[key])
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

function compactCostSummary(row) {
  if (row?.priceItems?.length) {
    return sortPriceItems(row.priceItems)
      .map(
        (item) =>
          `${priceItemDisplayLabel(item.dimension)} ${moneyOrStatus(
            item.unit_price,
            item.currency
          )}`
      )
      .join(' · ')
  }
  const previewItems = draftPricePreview(row?.draft, row?.model)
  if (!previewItems.length) return '成本待生成'
  return previewItems
    .map(
      (item) =>
        `${previewPriceLabel(item.label)} ${priceText(item, row?.model)}`
    )
    .join(' · ')
}

function upstreamPriceSummary(model) {
  const rows = providerPriceSummary(model)
  if (!rows.length) return '-'
  return rows
    .map((item) => `${item.label} ${priceText(item, model)}`)
    .join(' · ')
}

function pendingDraftPriceSummary(draft, model) {
  const rows = draftPricePreview(draft, model)
  if (!rows.length) return '-'
  return rows
    .map((item) => `${previewPriceLabel(item.label)} ${priceText(item, model)}`)
    .join(' · ')
}

function performanceSummaryItems(row) {
  const draft = row?.draft || {}
  return [
    {
      label: 'TPM',
      value: draft.tpm_limit || '-'
    },
    {
      label: 'RPM',
      value: draft.rpm_limit || '-'
    },
    {
      label: '延迟',
      value: draft.latency_ms ? `${draft.latency_ms}ms` : '-'
    }
  ]
}

function priceText(item, model) {
  if (!item) return '-'
  if (item.missingReason) return item.missingReason
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
  const itemRows = providerPriceItemsForModel(model)
  if (itemRows.length) {
    return compactPriceRows(
      itemRows.map((item) => [
        providerPriceItemLabel(item.dimension),
        item.unit_price,
        item.currency
      ])
    )
  }

  if (model.modality === 'video') {
    return compactPriceRowsWithMissingReason(model, [
      ['Video In', model.video_input_price_per_second, model.currency],
      ['Video Out', model.video_output_price_per_second, model.currency]
    ])
  }
  if (model.modality === 'audio') {
    return compactPriceRowsWithMissingReason(model, [
      ['Audio In', model.audio_input_price_per_second, model.currency],
      ['Audio Out', model.audio_output_price_per_second, model.currency]
    ])
  }
  if (model.image_output_price_per_image) {
    return compactPriceRowsWithMissingReason(model, [
      ['Input', model.input_price_per_million, model.currency],
      ['Output', model.output_price_per_million, model.currency],
      ['Image Out', model.image_output_price_per_image, model.currency]
    ])
  }
  return compactPriceRowsWithMissingReason(model, [
    ['Input', model.input_price_per_million, model.currency],
    ['Output', model.output_price_per_million, model.currency]
  ])
}

function providerPriceItemsForModel(model) {
  if (!model) return []
  const exactRows = sortPriceItems(
    props.priceItems.filter(
      (item) =>
        String(item.model) === String(model.id) && item.is_current !== false
    )
  )
  if (exactRows.length) return exactRows
  return fallbackPriceItemsForMetaModel(model)
}

function fallbackPriceItemsForMetaModel(model) {
  const metaModelId = String(model?.meta_model || '')
  const metaModelCode = normalizeSearch(model?.meta_model_code || '')
  if (!metaModelId && !metaModelCode) return []

  const rows = props.priceItems.filter((item) => {
    if (item.is_current === false || !hasPositiveUnitPrice(item)) {
      return false
    }
    const itemMetaId = String(item.meta_model || '')
    const itemMetaCode = normalizeSearch(item.meta_model_code || '')
    return (
      (metaModelId && itemMetaId === metaModelId) ||
      (metaModelCode && itemMetaCode === metaModelCode)
    )
  })
  if (!rows.length) return []

  const groups = new Map()
  rows.forEach((item) => {
    const key = String(item.source || item.model || '')
    const group = groups.get(key) || []
    group.push(item)
    groups.set(key, group)
  })

  const bestGroup = Array.from(groups.values()).sort(
    (left, right) => priceItemGroupScore(right) - priceItemGroupScore(left)
  )[0]
  return sortPriceItems(bestGroup || [])
}

function hasPositiveUnitPrice(item) {
  const value = Number(item?.unit_price)
  return Number.isFinite(value) && value > 0
}

function priceItemGroupScore(rows) {
  if (!rows?.length) return 0
  const first = rows[0] || {}
  const category = String(
    first.business_source_category || first.source_category || ''
  )
  const categoryScore =
    category === 'official_provider' ? 300 : category === 'supplier' ? 200 : 0
  const latestTime = Math.max(
    ...rows
      .map((item) => new Date(item.effective_from || item.updated_at || 0))
      .map((date) => date.getTime())
      .filter(Number.isFinite),
    0
  )
  return categoryScore + rows.length * 10 + latestTime / 100000000000
}

function sortPriceItems(items) {
  return items.slice().sort((left, right) => {
    const leftKey = priceDimensionSortKey(left)
    const rightKey = priceDimensionSortKey(right)
    return leftKey.localeCompare(rightKey)
  })
}

function priceDimensionSortKey(item) {
  const order = {
    text_input: 10,
    text_output: 20,
    cache_input: 30,
    image_input: 40,
    image_output: 50,
    audio_input: 60,
    audio_output: 70,
    video_input: 80,
    video_output: 90
  }
  const dimension = String(item?.dimension || '')
  const score = order[dimension] ?? 999
  return `${String(score).padStart(3, '0')}-${item?.tier_start || ''}-${dimension}`
}

function providerPriceItemLabel(dimension) {
  const labels = {
    text_input: 'Input',
    text_output: 'Output',
    cache_input: 'Cache',
    image_input: 'Image In',
    image_output: 'Image Out',
    audio_input: 'Audio In',
    audio_output: 'Audio Out',
    video_input: 'Video In',
    video_output: 'Video Out'
  }
  return labels[dimension] || dimensionLabel(dimension)
}

function priceItemDisplayLabel(dimension) {
  return providerPriceItemLabel(dimension)
}

function previewPriceLabel(label) {
  const normalized = String(label || '').replace('预估', '')
  const labels = {
    文入: 'Input',
    文出: 'Output',
    缓存: 'Cache',
    音入: 'Audio In',
    音出: 'Audio Out',
    视入: 'Video In',
    视出: 'Video Out',
    图入: 'Image In',
    图出: 'Image Out',
    文本入: 'Input',
    文本出: 'Output',
    图片出: 'Image Out',
    音频入: 'Audio In',
    音频出: 'Audio Out',
    视频入: 'Video In',
    视频出: 'Video Out'
  }
  return labels[normalized] || normalized || '-'
}

function compactPriceRowsWithMissingReason(model, rows) {
  const missingReason = missingPriceReason(model)
  return rows
    .filter(
      ([, value]) => value !== null && value !== undefined && value !== ''
    )
    .map(([label, value, currency]) => ({
      label,
      value,
      currency,
      missingReason: Number(value) === 0 && missingReason ? missingReason : ''
    }))
}

function missingPriceReason(model) {
  if (!model) return ''
  if (providerPriceItemsForModel(model).length) return ''
  if (model.last_price_updated_at) return ''
  if (model.source_name || model.source_endpoint_url) return '源未入库'
  return ''
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
        currency,
        missingReason: item.missingReason || ''
      }
    })
    .filter((item) => item.value !== null)
}

function compactPriceRows(rows) {
  return rows
    .filter(
      ([, value]) => value !== null && value !== undefined && value !== ''
    )
    .map(([label, value, currency]) => ({ label, value, currency }))
}

function dimensionLabel(dimension) {
  const labels = {
    text_input: 'Input',
    text_output: 'Output',
    cache_input: 'Cache',
    image_input: 'Image In',
    image_output: 'Image Out',
    audio_input: 'Audio In',
    audio_output: 'Audio Out',
    video_input: 'Video In',
    video_output: 'Video Out'
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

function modelSourceCategory(model) {
  return model?.business_source_category || model?.source_category || 'unknown'
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
      '已按全局显示货币换算展示；缺少同维度上游基准价时，' + '暂无法判断高低。'
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

.add-model-layout {
  @apply grid gap-3 xl:grid-cols-[minmax(0,1fr)_minmax(18rem,0.42fr)] xl:items-start;
}

.add-model-main {
  @apply grid min-w-0 gap-3;
}

.add-grid {
  @apply grid gap-3 md:grid-cols-2 xl:grid-cols-1;
}

.inline-cost-grid {
  @apply grid gap-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-3 md:col-span-2 md:grid-cols-[minmax(0,0.45fr)_minmax(0,0.55fr)] xl:col-span-1;
}

.cost-value-readonly {
  @apply justify-between gap-3 border-indigo-100 bg-indigo-50 text-indigo-700;
}

.cost-value-readonly strong {
  @apply shrink-0 font-mono text-sm font-semibold;
}

.fixed-cost-value-grid {
  @apply grid gap-2;
}

.channel-performance-panel {
  @apply h-full rounded-lg border border-slate-200 bg-white px-3 py-3;
}

.channel-performance-title {
  @apply mb-2 text-xs font-semibold text-slate-600;
}

.channel-performance-grid {
  @apply grid gap-3;
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

.batch-selection-panel {
  @apply rounded-lg border border-slate-200 bg-white;
}

.batch-selection-head {
  @apply flex items-center justify-between gap-3 border-b border-slate-100 px-3 py-2;
}

.batch-selection-head p {
  @apply text-xs font-semibold text-slate-700;
}

.batch-selection-head span {
  @apply mt-0.5 block text-[11px] text-slate-400;
}

.batch-selection-head button {
  @apply shrink-0 rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-500 transition hover:border-slate-300 hover:text-slate-700;
}

.batch-selection-list {
  @apply grid max-h-80 gap-0 overflow-y-auto divide-y divide-slate-100;
}

.batch-selection-row {
  @apply grid gap-2 px-3 py-2.5 xl:grid-cols-[minmax(9rem,0.8fr)_minmax(11rem,0.9fr)_minmax(0,1.35fr)] xl:items-center;
}

.batch-model-main {
  @apply min-w-0;
}

.batch-model-main p {
  @apply truncate text-sm font-semibold text-slate-900;
}

.batch-model-main span {
  @apply mt-0.5 block truncate font-mono text-[11px] text-slate-400;
}

.batch-price-preview {
  @apply grid min-w-0 gap-0.5 rounded-lg bg-slate-50 px-2.5 py-1.5 text-xs;
}

.batch-price-preview span,
.batch-price-preview strong {
  @apply truncate font-mono text-xs leading-5;
}

.batch-price-preview span {
  @apply text-slate-500;
}

.batch-price-preview strong {
  @apply font-semibold text-slate-800;
}

.batch-price-preview.muted span,
.batch-price-preview.muted strong {
  @apply font-sans text-slate-400;
}

.pending-association {
  @apply mt-3 grid gap-3 rounded-lg border border-indigo-100 bg-indigo-50/60 px-3 py-2.5 xl:items-center;
  grid-template-columns:
    minmax(9rem, 0.8fr) minmax(0, 1.35fr) minmax(0, 1.35fr)
    minmax(4.25rem, auto);
}

.pending-main {
  @apply min-w-0;
}

.pending-price-compact {
  @apply grid min-w-0 gap-1 rounded-lg border border-white bg-white/80 px-2.5 py-1.5 text-xs text-slate-500;
}

.pending-price-compact span {
  @apply font-medium text-slate-500;
}

.pending-price-compact strong {
  @apply whitespace-normal break-words font-mono text-xs font-semibold leading-5 text-slate-900;
}

@media (max-width: 1279px) {
  .pending-association {
    grid-template-columns: 1fr;
  }
}

.searchable-select {
  @apply relative min-w-0;
}

.searchable-trigger {
  @apply flex min-h-9 w-full items-center gap-2 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-left text-sm text-slate-800 outline-none transition hover:border-slate-300 focus:border-indigo-300 focus:ring-4 focus:ring-indigo-50;
}

.searchable-trigger:disabled {
  @apply cursor-not-allowed bg-slate-50 text-slate-400 hover:border-slate-200;
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

.searchable-meta-actions {
  @apply inline-flex shrink-0 items-center gap-2;
}

.searchable-meta-actions button {
  @apply text-[11px] font-semibold text-indigo-600 transition hover:text-indigo-700;
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

.searchable-checkbox {
  @apply flex h-4 w-4 shrink-0 items-center justify-center rounded border border-slate-300 bg-white text-[10px] font-bold text-white;
}

.searchable-checkbox-checked {
  @apply border-indigo-500 bg-indigo-600;
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

.percent-input-wrap {
  @apply relative min-w-0;
}

.percent-input-wrap span {
  @apply pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-xs font-semibold text-slate-400;
}

.icon-mark {
  @apply inline-block h-3.5 w-3.5 shrink-0 rounded-sm bg-current;
}

.data-table {
  @apply min-w-full divide-y divide-slate-200;
  table-layout: fixed;
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

.channel-model-list-panel {
  overflow: visible;
}

.channel-model-summary-list {
  @apply mt-3 grid gap-1.5 text-xs sm:grid-cols-[minmax(0,1fr)_max-content_max-content];
}

.channel-model-summary-list div {
  @apply min-w-0 rounded-md border border-slate-100 bg-slate-50 px-2 py-1;
}

.channel-model-summary-list span {
  @apply mr-1 text-slate-400;
}

.channel-model-summary-list strong {
  @apply font-medium text-slate-700;
}

.channel-model-ability-summary strong {
  @apply grid grid-cols-[2.25rem_minmax(0,1fr)] gap-1 font-mono text-[11px] leading-5;
}

.channel-model-ability-summary em {
  @apply not-italic text-slate-400;
}

.channel-model-price-summary strong {
  @apply grid grid-cols-[2.25rem_minmax(0,1fr)] gap-1 font-mono text-[11px] leading-5;
}

.channel-model-price-summary em {
  @apply not-italic text-slate-400;
}

.channel-model-detail {
  @apply mt-3 rounded-lg border border-dashed border-slate-200 bg-slate-50/40 px-3 py-2;
}

.channel-model-detail summary {
  @apply cursor-pointer select-none text-xs font-semibold text-indigo-600;
}

.show-more-card {
  @apply rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-3 text-center text-sm font-medium text-indigo-600 transition hover:border-indigo-200 hover:bg-indigo-50;
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
  @apply whitespace-nowrap bg-slate-50 px-4 py-3 text-center text-xs font-semibold uppercase tracking-wide text-slate-500;
}

.table-cell {
  @apply whitespace-nowrap px-4 py-3 text-sm text-slate-600;
}

.channel-model-table .table-head {
  @apply px-3 py-2 text-center text-[11px];
}

.channel-model-table .table-cell {
  @apply whitespace-normal px-3 py-2 align-middle;
}

.channel-model-table .model-col {
  width: 16%;
}

.channel-model-table .source-col {
  width: 18%;
}

.channel-model-table .price-col {
  width: 38%;
}

.channel-model-table .ability-col {
  width: 20%;
}

.channel-model-table .action-col {
  width: 6%;
}

.channel-model-table .model-cell {
  @apply min-w-0;
}

.channel-model-table .model-name {
  display: -webkit-box;
  max-width: 10.5rem;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow-wrap: anywhere;
}

.channel-model-table .model-code {
  max-width: 10.5rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-cell {
  @apply min-w-0 space-y-1.5;
}

.source-cell p {
  @apply truncate text-sm font-medium text-slate-800;
}

.source-cell div {
  @apply flex flex-wrap items-center gap-1.5;
}

.price-cell {
  @apply min-w-0 space-y-1;
}

.price-cell p,
.price-cell span {
  @apply grid min-w-0 grid-cols-[2.25rem_minmax(0,1fr)] items-center gap-2 text-xs;
}

.price-cell em {
  @apply not-italic text-slate-400;
}

.price-cell strong {
  @apply min-w-0 truncate font-semibold text-slate-800;
}

.price-cell span strong {
  @apply font-medium text-slate-600;
}

.ability-cell {
  @apply grid gap-1 text-xs;
}

.ability-cell span {
  @apply grid grid-cols-[2.25rem_minmax(0,1fr)] items-center gap-2;
}

.ability-cell em {
  @apply not-italic text-slate-400;
}

.ability-cell strong {
  @apply truncate text-right font-mono font-semibold text-slate-700;
}

.ability-edit-cell {
  @apply grid gap-1.5;
}

.ability-edit-cell label {
  @apply grid grid-cols-[2.5rem_minmax(0,1fr)] items-center gap-1.5 text-xs font-medium text-slate-500;
}

.table-performance-input {
  @apply min-w-0;
  padding: 0.25rem 0.35rem;
  font-size: 0.75rem;
  line-height: 1rem;
}

.channel-model-input {
  width: 5rem;
  padding: 0.25rem 0.4rem;
  font-size: 0.75rem;
  line-height: 1rem;
}

.performance-input-grid {
  @apply grid min-w-44 grid-cols-1 gap-1.5;
}

.performance-input-field {
  @apply grid grid-cols-[2.5rem_minmax(5.5rem,1fr)] items-center gap-1 text-xs text-slate-500;
}

.performance-input {
  min-width: 5.5rem;
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
  width: 4.5rem;
  min-width: 4.5rem;
}
</style>
