<template>
  <section class="space-y-5">
    <div class="panel overflow-hidden p-0">
      <div class="table-toolbar">
        <div>
          <h3 class="panel-title">转发渠道配置</h3>
          <p class="mt-1 text-xs text-slate-500">
            维护渠道基础信息，并进入模型管理配置渠道上游、成本规则和转发能力。
          </p>
        </div>
        <div class="flex flex-col gap-2 sm:flex-row sm:items-center">
          <CompactSelect
            v-model="statusFilter"
            :options="statusFilterOptions"
            class-name="control-select sm:w-36"
          />
          <input
            v-model="searchKeyword"
            class="control-field sm:w-64"
            placeholder="搜索渠道名称、标识或地址"
          />
          <button
            class="btn-primary toolbar-button btn-action-create"
            type="button"
            @click="openChannelModal()"
          >
            <svg
              class="toolbar-button-icon"
              aria-hidden="true"
              fill="none"
              stroke="currentColor"
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              viewBox="0 0 24 24"
            >
              <path d="M12 5v14" />
              <path d="M5 12h14" />
            </svg>
            新建渠道
          </button>
        </div>
      </div>
      <div class="overflow-x-auto">
        <table class="data-table channel-table">
          <colgroup>
            <col class="channel-name-col" />
            <col class="channel-config-col" />
            <col class="channel-model-col" />
            <col class="channel-status-col" />
            <col class="channel-action-col" />
          </colgroup>
          <thead>
            <tr>
              <th class="table-head">渠道</th>
              <th class="table-head">默认配置</th>
              <th class="table-head">模型管理</th>
              <th class="table-head">状态</th>
              <th class="table-head">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="channel in filteredChannelRows" :key="channel.id">
              <td class="table-cell">
                <div class="channel-name-cell min-w-44">
                  <p class="font-medium text-slate-900">
                    {{ channel.name }}
                  </p>
                  <p class="mt-1 font-mono text-xs text-slate-400">
                    {{ channel.code }}
                  </p>
                </div>
              </td>
              <td class="table-cell max-w-sm">
                <div class="channel-config-cell">
                  <a
                    v-if="channel.api_endpoint"
                    class="link-url"
                    :href="channel.api_endpoint"
                    rel="noopener noreferrer"
                    target="_blank"
                    :title="channel.api_endpoint"
                  >
                    已配置 API
                  </a>
                  <span v-else class="config-status-muted"> API 未配置 </span>
                  <div class="channel-config-chips">
                    <span class="config-chip">
                      币种 {{ channel.currency || 'USD' }}
                    </span>
                    <span class="config-chip">
                      折扣 {{ ratioLabel(channel.settlement_ratio) }}
                    </span>
                  </div>
                </div>
              </td>
              <td class="table-cell">
                <div class="channel-model-metrics">
                  <span class="model-metric-pill">
                    <strong>{{ channel.model_count }}</strong>
                    <span>启用</span>
                  </span>
                  <span class="model-metric-pill">
                    <strong>{{ channel.configured_model_count }}</strong>
                    <span>配置</span>
                  </span>
                </div>
              </td>
              <td class="table-cell">
                <span :class="channel.is_active ? 'badge-ok' : 'badge-muted'">
                  {{ channel.is_active ? '启用' : '停用' }}
                </span>
              </td>
              <td class="table-cell">
                <div class="inline-flex items-center justify-center gap-2">
                  <OperationIconButton
                    icon="config"
                    label="管理模型"
                    tone="primary"
                    @click="selectedChannelForModels = channel"
                  />
                  <OperationIconButton
                    icon="edit"
                    label="编辑"
                    @click="openChannelModal(channel)"
                  />
                  <OperationIconButton
                    :disabled="deletingChannelId === channel.id"
                    icon="delete"
                    label="删除"
                    tone="danger"
                    @click="openDeleteConfirm(channel)"
                  />
                </div>
              </td>
            </tr>
            <tr v-if="!filteredChannelRows.length">
              <td class="table-cell text-slate-500" colspan="5">
                暂无符合条件的渠道配置。
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <ChannelModal
      :open="showChannelModal"
      :channel="editingChannel"
      @close="closeChannelModal"
      @saved="handleChannelSaved"
    />
    <ChannelModelDrawer
      :channel="selectedChannelForModels"
      :providers="providers"
      :models="models"
      :channel-prices="channelPrices"
      :channel-price-items="channelPriceItems"
      :price-items="priceItems"
      :display-currency="displayCurrency"
      :exchange-rate="exchangeRate"
      @close="selectedChannelForModels = null"
      @refresh="emit('refresh')"
      @saved="handleChannelModelsSaved"
    />
    <div
      v-if="deleteTarget"
      class="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 px-4"
      @click.self="closeDeleteConfirm"
    >
      <div class="w-full max-w-md rounded-lg bg-white shadow-xl">
        <div class="border-b border-slate-200 px-5 py-4">
          <h3 class="text-base font-semibold text-slate-900">删除转发渠道</h3>
          <p class="mt-1 text-sm text-slate-500">
            删除后，该渠道下的模型配置、采购价格项和对账记录会一并删除；
            已上架记录会保留，但不再关联该渠道。
          </p>
        </div>
        <div class="space-y-3 px-5 py-4">
          <div class="rounded-lg border border-rose-100 bg-rose-50 px-3 py-2">
            <p class="text-sm font-medium text-rose-900">
              {{ deleteTarget.name }}
            </p>
            <p class="mt-1 font-mono text-xs text-rose-700">
              {{ deleteTarget.code }}
            </p>
          </div>
          <p class="text-sm text-slate-500">
            请确认不再需要这个渠道及其模型关系后再删除。
          </p>
        </div>
        <div
          class="flex items-center justify-end gap-2 border-t border-slate-200 px-5 py-4"
        >
          <button
            class="btn-secondary btn-action-cancel"
            type="button"
            :disabled="Boolean(deletingChannelId)"
            @click="closeDeleteConfirm"
          >
            取消
          </button>
          <button
            class="btn-danger btn-action-danger"
            type="button"
            :disabled="Boolean(deletingChannelId)"
            @click="deleteChannel"
          >
            {{ deletingChannelId ? '删除中' : '确认删除' }}
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { llmOpsApi } from '@/api/llmOps'
import { useToast } from '@/composables/useToast'
import ChannelModelDrawer from '@/components/llm-ops/ChannelModelDrawer.vue'
import ChannelModal from '@/components/llm-ops/ChannelModal.vue'
import CompactSelect from '@/components/llm-ops/CompactSelect.vue'
import OperationIconButton from '@/components/llm-ops/OperationIconButton.vue'

const props = defineProps({
  channels: {
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

const emit = defineEmits(['refresh'])
const { showSuccess, showError } = useToast()

const showChannelModal = ref(false)
const editingChannel = ref(null)
const selectedChannelForModels = ref(null)
const deleteTarget = ref(null)
const searchKeyword = ref('')
const statusFilter = ref('all')
const deletingChannelId = ref(null)

const statusFilterOptions = [
  { label: '全部状态', value: 'all' },
  { label: '仅启用', value: 'active' },
  { label: '仅停用', value: 'inactive' }
]

const channelRows = computed(() =>
  props.channels.map((channel) => ({
    ...channel,
    model_count: channel.listed_model_count || 0,
    configured_model_count: channel.configured_model_count || 0
  }))
)

const filteredChannelRows = computed(() => {
  const keyword = searchKeyword.value.trim().toLowerCase()
  return channelRows.value.filter((channel) => {
    const matchStatus =
      statusFilter.value === 'all' ||
      (statusFilter.value === 'active' && channel.is_active) ||
      (statusFilter.value === 'inactive' && !channel.is_active)
    const haystack = [channel.name, channel.code, channel.api_endpoint]
      .filter(Boolean)
      .join(' ')
      .toLowerCase()
    return matchStatus && (!keyword || haystack.includes(keyword))
  })
})

function openChannelModal(channel = null) {
  editingChannel.value = channel
  showChannelModal.value = true
}

function closeChannelModal() {
  showChannelModal.value = false
  editingChannel.value = null
}

function handleChannelSaved() {
  closeChannelModal()
  emit('refresh')
}

function handleChannelModelsSaved() {
  selectedChannelForModels.value = null
  emit('refresh')
}

function openDeleteConfirm(channel) {
  deleteTarget.value = channel
}

function closeDeleteConfirm() {
  if (deletingChannelId.value) return
  deleteTarget.value = null
}

async function deleteChannel() {
  if (!deleteTarget.value) return
  deletingChannelId.value = deleteTarget.value.id
  try {
    await llmOpsApi.deleteChannel(deleteTarget.value.id)
    showSuccess(`${deleteTarget.value.name} 已删除`)
    if (selectedChannelForModels.value?.id === deleteTarget.value.id) {
      selectedChannelForModels.value = null
    }
    deleteTarget.value = null
    emit('refresh')
  } catch (error) {
    showError(errorMessage(error, '删除渠道失败'))
  } finally {
    deletingChannelId.value = null
  }
}

function ratioLabel(value) {
  if (value === null || value === undefined || value === '') return '-'
  return `${(Number(value) * 100).toFixed(1)}%`
}

function errorMessage(error, fallback) {
  return (
    error?.response?.data?.detail ||
    error?.response?.data?.message ||
    error?.message ||
    fallback
  )
}
</script>

<style scoped>
.panel {
  @apply rounded-lg border border-slate-200 bg-white p-4 shadow-sm;
}

.table-toolbar {
  @apply flex flex-col gap-4 border-b border-slate-200 bg-white px-4 py-4 xl:flex-row xl:items-end xl:justify-between;
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

.table-head {
  @apply whitespace-nowrap bg-slate-50 px-4 py-3 text-center text-xs font-semibold uppercase tracking-wide text-slate-500;
}

.table-cell {
  @apply min-w-0 px-4 py-3 text-sm text-slate-600;
}

.channel-table .table-head,
.channel-table .table-cell {
  @apply text-center align-middle;
}

.channel-name-cell {
  @apply mx-auto;
}

.channel-table .link-url {
  @apply mx-auto text-center;
}

.channel-config-cell {
  @apply mx-auto flex max-w-[16rem] flex-col items-center gap-2;
}

.channel-config-chips,
.channel-model-metrics {
  @apply flex flex-wrap items-center justify-center gap-1.5;
}

.config-status-muted {
  @apply text-xs font-medium text-slate-400;
}

.model-metric-pill {
  @apply inline-flex min-w-[3.75rem] items-center justify-center gap-1 rounded-full border border-slate-200 bg-white px-2 py-1 text-xs text-slate-500;
}

.model-metric-pill strong {
  @apply font-mono text-sm font-semibold text-slate-900;
}

.channel-name-col {
  width: 22%;
}

.channel-config-col {
  width: 34%;
}

.channel-model-col {
  width: 18%;
}

.channel-status-col {
  width: 10%;
}

.channel-action-col {
  width: 16%;
}

.control-field {
  @apply h-9 rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-700 outline-none transition placeholder:text-slate-400 focus:border-indigo-300 focus:ring-4 focus:ring-indigo-50;
}

.control-select :deep(.compact-select-trigger) {
  @apply h-9 rounded-lg border-slate-200 px-3 text-sm text-slate-700;
}

.toolbar-button {
  @apply h-9 justify-center rounded-md border border-indigo-500 bg-indigo-600 px-3.5 font-semibold shadow-sm shadow-indigo-100 hover:-translate-y-px hover:border-indigo-600 hover:bg-indigo-700 hover:shadow-md hover:shadow-indigo-100;
}

.toolbar-button-icon {
  @apply h-4 w-4 shrink-0;
}

.btn-primary {
  @apply inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60;
}

.btn-secondary {
  @apply inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60;
}

.btn-compact {
  @apply px-2.5 py-1.5;
}

.link-btn {
  @apply text-sm font-medium text-indigo-600 hover:text-indigo-700;
}

.danger-link-btn {
  @apply text-sm font-medium text-rose-600 hover:text-rose-700 disabled:cursor-not-allowed disabled:text-slate-400;
}

.link-url {
  @apply block truncate text-sm font-medium text-indigo-600 hover:text-indigo-700 hover:underline;
}

.btn-danger {
  @apply inline-flex items-center gap-2 rounded-lg bg-rose-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-rose-700 disabled:cursor-not-allowed disabled:opacity-60;
}

.badge-ok {
  @apply rounded-full border border-emerald-100 bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700;
}

.badge-muted {
  @apply rounded-full border border-slate-200 bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600;
}

.config-chip {
  @apply inline-flex rounded-full border border-indigo-100 bg-indigo-50 px-2 py-1 text-xs font-medium text-indigo-700;
}
</style>
