<template>
  <div
    v-if="open"
    class="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/30 px-4 py-6"
    @click.self="close"
  >
    <form
      class="max-h-[calc(100vh-3rem)] w-full max-w-3xl overflow-hidden rounded-xl bg-white shadow-2xl"
      @submit.prevent="submit"
    >
      <div class="modal-header">
        <div class="min-w-0">
          <p class="eyebrow">Manual Price Entry</p>
          <h3 class="mt-2 text-lg font-semibold text-slate-900">
            {{ t('llmOps.manualPriceEntry.title') }}
          </h3>
          <p class="mt-1 text-sm text-slate-500">
            {{ t('llmOps.manualPriceEntry.description') }}
          </p>
        </div>
        <button
          type="button"
          class="btn-secondary btn-action-cancel"
          :disabled="saving"
          @click="close"
        >
          {{ t('llmOps.manualPriceEntry.actions.close') }}
        </button>
      </div>

      <div class="modal-body space-y-5">
        <section class="source-context">
          <div class="min-w-0">
            <p class="truncate text-sm font-semibold text-slate-900">
              {{ source?.name || '-' }}
            </p>
            <p class="mt-1 truncate text-xs text-slate-500">
              {{
                t('llmOps.manualPriceEntry.sourceContext', {
                  relation: sourceRelationLabel,
                  currency: form.currency
                })
              }}
            </p>
          </div>
          <span :class="['source-badge', sourceCategoryTone]">
            {{ sourceCategoryLabel }}
          </span>
        </section>

        <section class="form-section">
          <div class="section-heading">
            <h4>{{ t('llmOps.manualPriceEntry.sections.model') }}</h4>
            <p>{{ t('llmOps.manualPriceEntry.sections.modelHint') }}</p>
          </div>

          <div class="mode-tabs">
            <button
              class="mode-tab"
              :class="{ active: modelMode === 'existing' }"
              type="button"
              @click="modelMode = 'existing'"
            >
              {{ t('llmOps.manualPriceEntry.modelMode.existing') }}
            </button>
            <button
              class="mode-tab"
              :class="{ active: modelMode === 'custom' }"
              type="button"
              @click="modelMode = 'custom'"
            >
              {{ t('llmOps.manualPriceEntry.modelMode.custom') }}
            </button>
          </div>

          <div
            v-if="modelMode === 'existing'"
            class="grid gap-4 md:grid-cols-2"
          >
            <label class="field-group md:col-span-2">
              <span class="field-label">
                {{ t('llmOps.manualPriceEntry.fields.model') }}
              </span>
              <CompactSelect
                v-model="form.model_id"
                :options="modelOptions"
                searchable
                :search-placeholder="
                  t('llmOps.manualPriceEntry.placeholders.searchModel')
                "
              />
              <span class="field-help">
                {{ t('llmOps.manualPriceEntry.help.existingModel') }}
              </span>
            </label>
            <div class="readonly-field">
              <span>{{ t('llmOps.manualPriceEntry.fields.provider') }}</span>
              <strong>{{ selectedModelProviderName }}</strong>
            </div>
            <div class="readonly-field">
              <span>{{ t('llmOps.manualPriceEntry.fields.modality') }}</span>
              <strong>{{ modalityLabel(selectedModel?.modality) }}</strong>
            </div>
          </div>

          <div v-else class="grid gap-4 md:grid-cols-2">
            <label class="field-group md:col-span-2">
              <span class="field-label">
                {{ t('llmOps.manualPriceEntry.fields.metaModel') }}
              </span>
              <CompactSelect
                v-model="form.meta_model_id"
                :options="metaModelOptions"
                :placeholder="
                  t('llmOps.manualPriceEntry.placeholders.selectMetaModel')
                "
                searchable
                :search-placeholder="
                  t('llmOps.manualPriceEntry.placeholders.searchMetaModel')
                "
              />
              <span class="field-help">
                {{ t('llmOps.manualPriceEntry.help.metaModel') }}
              </span>
            </label>
            <div class="readonly-field">
              <span>
                {{ t('llmOps.manualPriceEntry.fields.provider') }}
              </span>
              <strong>{{ selectedMetaModelProviderName }}</strong>
            </div>
            <div class="readonly-field">
              <span>
                {{ t('llmOps.manualPriceEntry.fields.modality') }}
              </span>
              <strong>{{ modalityLabel(selectedMetaModel?.modality) }}</strong>
            </div>
          </div>
        </section>

        <section class="form-section">
          <div class="section-heading">
            <h4>{{ t('llmOps.manualPriceEntry.sections.price') }}</h4>
            <p>{{ t('llmOps.manualPriceEntry.sections.priceHint') }}</p>
          </div>

          <div class="grid gap-4 md:grid-cols-2">
            <label class="field-group compact-field">
              <span class="field-label">
                {{ t('llmOps.manualPriceEntry.fields.currency') }}
              </span>
              <CompactSelect
                v-model="form.currency"
                :options="currencyOptions"
              />
            </label>
            <label class="field-group">
              <span class="field-label">
                {{ t('llmOps.manualPriceEntry.fields.sourceUrl') }}
              </span>
              <input
                v-model="form.source_url"
                class="field"
                :placeholder="
                  t('llmOps.manualPriceEntry.placeholders.sourceUrl')
                "
                type="url"
              />
            </label>
          </div>

          <div class="price-grid">
            <label
              v-for="field in activePriceFields"
              :key="field.key"
              class="field-group"
            >
              <span class="field-label">{{ field.label }}</span>
              <input
                v-model="form[field.key]"
                class="field font-mono"
                inputmode="decimal"
                min="0"
                placeholder="-"
                step="0.000001"
                type="number"
              />
              <span class="field-help">{{ field.help }}</span>
            </label>
          </div>
        </section>

        <p v-if="validationMessage" class="error-line">
          {{ validationMessage }}
        </p>
      </div>

      <div class="modal-footer manual-price-modal-footer">
        <div class="modal-footer-actions manual-price-modal-actions">
          <button
            class="btn-secondary btn-action-cancel"
            type="button"
            :disabled="saving"
            @click="close"
          >
            {{ t('llmOps.manualPriceEntry.actions.cancel') }}
          </button>
          <button
            class="btn-primary btn-action-save"
            type="submit"
            :disabled="saving"
          >
            <span class="save-icon" aria-hidden="true" />
            {{
              saving
                ? t('llmOps.manualPriceEntry.actions.saving')
                : t('llmOps.manualPriceEntry.actions.save')
            }}
          </button>
        </div>
      </div>
    </form>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { llmOpsApi } from '@/api/llmOps'
import { useToast } from '@/composables/useToast'
import CompactSelect from '@/components/llm-ops/CompactSelect.vue'
import { resolveCanonicalMetaOwner } from '@/utils/llmOpsMeta'

const props = defineProps({
  open: {
    type: Boolean,
    default: false
  },
  source: {
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
  }
})

const emit = defineEmits(['close', 'saved'])
const { showSuccess, showError } = useToast()
const { t } = useI18n()

const saving = ref(false)
const modelMode = ref('existing')
const form = ref(defaults())

const priceFields = computed(() => [
  {
    key: 'input_price_per_million',
    label: t('llmOps.manualPriceEntry.priceFields.textInput.label'),
    help: t('llmOps.manualPriceEntry.priceFields.textInput.help'),
    modalities: ['text', 'multimodal']
  },
  {
    key: 'output_price_per_million',
    label: t('llmOps.manualPriceEntry.priceFields.textOutput.label'),
    help: t('llmOps.manualPriceEntry.priceFields.textOutput.help'),
    modalities: ['text', 'multimodal']
  },
  {
    key: 'cache_input_price_per_million',
    label: t('llmOps.manualPriceEntry.priceFields.cacheInput.label'),
    help: t('llmOps.manualPriceEntry.priceFields.cacheInput.help'),
    modalities: ['text', 'multimodal']
  },
  {
    key: 'image_output_price_per_image',
    label: t('llmOps.manualPriceEntry.priceFields.imageOutput.label'),
    help: t('llmOps.manualPriceEntry.priceFields.imageOutput.help'),
    modalities: ['multimodal']
  },
  {
    key: 'audio_input_price_per_second',
    label: t('llmOps.manualPriceEntry.priceFields.audioInput.label'),
    help: t('llmOps.manualPriceEntry.priceFields.audioInput.help'),
    modalities: ['audio']
  },
  {
    key: 'audio_output_price_per_second',
    label: t('llmOps.manualPriceEntry.priceFields.audioOutput.label'),
    help: t('llmOps.manualPriceEntry.priceFields.audioOutput.help'),
    modalities: ['audio']
  },
  {
    key: 'video_input_price_per_second',
    label: t('llmOps.manualPriceEntry.priceFields.videoInput.label'),
    help: t('llmOps.manualPriceEntry.priceFields.videoInput.help'),
    modalities: ['video']
  },
  {
    key: 'video_output_price_per_second',
    label: t('llmOps.manualPriceEntry.priceFields.videoOutput.label'),
    help: t('llmOps.manualPriceEntry.priceFields.videoOutput.help'),
    modalities: ['video']
  }
])

const currencyOptions = computed(() => [
  { label: t('llmOps.manualPriceEntry.currencies.cny'), value: 'CNY' },
  { label: t('llmOps.manualPriceEntry.currencies.usd'), value: 'USD' }
])

const modelOptions = computed(() => buildModelOptions())
const metaModelOptions = computed(() => buildMetaModelOptions())

const selectedModel = computed(() =>
  props.models.find((model) => String(model.id) === String(form.value.model_id))
)

const selectedModelProviderName = computed(() => {
  if (!selectedModel.value) return '-'
  return (
    selectedModel.value.provider_name ||
    selectedModel.value.provider_code ||
    '-'
  )
})

const selectedMetaModel = computed(() =>
  props.metaModels.find(
    (model) => String(model.id) === String(form.value.meta_model_id)
  )
)

const selectedMetaModelOwner = computed(() => {
  if (!selectedMetaModel.value) {
    return { providerId: '', code: '', name: '' }
  }
  const owner = resolveCanonicalMetaOwner(
    selectedMetaModel.value,
    props.providers
  )
  const provider = props.providers.find(
    (item) =>
      String(item.code || '').toLowerCase() ===
      String(owner.code || '').toLowerCase()
  )
  return {
    providerId: provider?.id || '',
    code: owner.code || selectedMetaModel.value.owner_code || '',
    name: owner.name || selectedMetaModel.value.owner_name || ''
  }
})

const selectedMetaModelProviderName = computed(() => {
  return (
    selectedMetaModelOwner.value.name ||
    selectedMetaModelOwner.value.code ||
    '-'
  )
})

const currentPriceModality = computed(() => {
  if (modelMode.value === 'existing') {
    return selectedModel.value?.modality || 'text'
  }
  return selectedMetaModel.value?.modality || 'text'
})

const activePriceFields = computed(() =>
  priceFields.value.filter((field) =>
    field.modalities.includes(currentPriceModality.value)
  )
)

const sourceCategoryLabel = computed(() => {
  const labels = {
    official_provider: t('llmOps.manualPriceEntry.categories.officialProvider'),
    supplier: t('llmOps.manualPriceEntry.categories.supplier'),
    manual: t('llmOps.manualPriceEntry.categories.manual'),
    unknown: t('llmOps.manualPriceEntry.categories.unknown')
  }
  const category =
    props.source?.business_source_category ||
    props.source?.source_category ||
    'unknown'
  return labels[category] || labels.unknown
})

const sourceCategoryTone = computed(() => {
  const tones = {
    official_provider: 'official',
    supplier: 'supplier',
    manual: 'manual'
  }
  const category =
    props.source?.business_source_category ||
    props.source?.source_category ||
    'unknown'
  return tones[category] || 'unknown'
})

const sourceRelationLabel = computed(() => {
  if (props.source?.provider_name) {
    return t('llmOps.manualPriceEntry.relation.provider', {
      name: props.source.provider_name
    })
  }
  if (props.source?.channel_name) {
    return t('llmOps.manualPriceEntry.relation.channel', {
      name: props.source.channel_name
    })
  }
  return t('llmOps.manualPriceEntry.relation.unbound')
})

const isManualSource = computed(() => {
  const category =
    props.source?.business_source_category ||
    props.source?.source_category ||
    'unknown'
  return category === 'manual'
})

const validationMessage = computed(() => {
  if (!props.source?.id) return t('llmOps.manualPriceEntry.validation.noSource')
  if (modelMode.value === 'existing' && !selectedModel.value) {
    return t('llmOps.manualPriceEntry.validation.selectExistingModel')
  }
  if (
    modelMode.value === 'existing' &&
    !resolveModelProviderId(selectedModel.value)
  ) {
    return t('llmOps.manualPriceEntry.validation.customModelProvider')
  }
  if (modelMode.value === 'custom') {
    if (!selectedMetaModel.value) {
      return t('llmOps.manualPriceEntry.validation.selectMetaModel')
    }
    if (
      !selectedMetaModelOwner.value.providerId &&
      !selectedMetaModelOwner.value.code &&
      !selectedMetaModelOwner.value.name
    ) {
      return t('llmOps.manualPriceEntry.validation.customModelProvider')
    }
  }
  if (!hasAnyPrice()) return t('llmOps.manualPriceEntry.validation.price')
  return ''
})

watch(
  () => props.open,
  (open) => {
    if (open) {
      modelMode.value = isManualSource.value ? 'custom' : 'existing'
      form.value = defaults()
    }
  }
)

watch(currentPriceModality, () => {
  clearInactivePrices()
})

function defaults() {
  return {
    model_id: '',
    meta_model_id: '',
    currency: props.source?.currency || 'CNY',
    source_url: props.source?.endpoint_url || '',
    input_price_per_million: '',
    output_price_per_million: '',
    cache_input_price_per_million: '',
    image_output_price_per_image: '',
    audio_input_price_per_second: '',
    audio_output_price_per_second: '',
    video_input_price_per_second: '',
    video_output_price_per_second: ''
  }
}

function close() {
  if (saving.value) return
  emit('close')
}

async function submit() {
  if (validationMessage.value) {
    showError(validationMessage.value)
    return
  }

  saving.value = true
  try {
    const { providerId, row } = resolveImportSelection()
    const payload = {
      source: props.source.id,
      source_name: props.source.name,
      source_slug: props.source.slug,
      source_url: form.value.source_url || props.source.endpoint_url || '',
      currency: form.value.currency,
      updates_model_prices: false,
      rows: [row]
    }
    if (providerId) {
      payload.provider = providerId
    }
    await llmOpsApi.importManualPrices(payload)
    showSuccess(t('llmOps.manualPriceEntry.messages.saved'))
    emit('saved')
  } catch (error) {
    showError(errorMessage(error, t('llmOps.manualPriceEntry.errors.save')))
  } finally {
    saving.value = false
  }
}

function resolveImportSelection() {
  if (modelMode.value === 'existing') {
    return {
      providerId: resolveModelProviderId(selectedModel.value),
      row: buildImportRow(selectedModel.value)
    }
  }
  const owner = selectedMetaModelOwner.value
  const model = {
    code: selectedMetaModel.value.code,
    name: selectedMetaModel.value.name || selectedMetaModel.value.code,
    modality: selectedMetaModel.value.modality || 'text',
    provider_code: owner.code,
    provider_name: owner.name
  }
  return {
    providerId: owner.providerId,
    row: buildImportRow(model)
  }
}

function buildImportRow(model) {
  const row = {
    model_code: model.code,
    model_name: model.name || model.code,
    modality: model.modality || form.value.modality,
    currency: form.value.currency,
    source_url: form.value.source_url || props.source.endpoint_url || ''
  }
  if (model.provider_code) {
    row.provider_code = model.provider_code
  }
  if (model.provider_name) {
    row.provider_name = model.provider_name
  }
  activePriceFields.value.forEach((field) => {
    const value = normalizePrice(form.value[field.key])
    if (value !== null) row[field.key] = value
  })
  return row
}

function hasAnyPrice() {
  return activePriceFields.value.some(
    (field) => normalizePrice(form.value[field.key]) !== null
  )
}

function clearInactivePrices() {
  const activeKeys = new Set(activePriceFields.value.map((field) => field.key))
  priceFields.value.forEach((field) => {
    if (!activeKeys.has(field.key)) {
      form.value[field.key] = ''
    }
  })
}

function buildModelOptions() {
  const sortedModels = props.models.slice().sort((left, right) => {
    const providerCompare = String(left.provider_name || '').localeCompare(
      String(right.provider_name || '')
    )
    if (providerCompare !== 0) return providerCompare
    return String(left.name || '').localeCompare(String(right.name || ''))
  })
  return sortedModels.map(modelOption)
}

function resolveModelProviderId(model) {
  if (!model) return ''
  return model.provider || ''
}

function buildMetaModelOptions() {
  return props.metaModels
    .map((model) => {
      const owner = resolveCanonicalMetaOwner(model, props.providers)
      return {
        ...model,
        resolved_owner: owner.id,
        resolved_owner_name: owner.name
      }
    })
    .sort((left, right) => {
      const ownerCompare = String(left.resolved_owner_name || '').localeCompare(
        String(right.resolved_owner_name || '')
      )
      if (ownerCompare !== 0) return ownerCompare
      return String(left.name || left.code || '').localeCompare(
        String(right.name || right.code || '')
      )
    })
    .map(metaModelOption)
}

function modelOption(model) {
  return {
    label: model.name || model.code,
    value: model.id,
    description: `${
      model.provider_name ||
      t('llmOps.manualPriceEntry.fallback.unknownProvider')
    } · ${model.code}`,
    badge: modalityLabel(model.modality),
    searchText: [model.name, model.code, model.provider_name].join(' ')
  }
}

function metaModelOption(model) {
  const providerName =
    model.resolved_owner_name ||
    model.owner_name ||
    t('llmOps.manualPriceEntry.fallback.unknownProvider')
  return {
    label: model.name || model.code,
    value: model.id,
    description: `${providerName} · ${model.code}`,
    badge: modalityLabel(model.modality),
    searchText: [
      model.name,
      model.code,
      model.family,
      providerName,
      ...(Array.isArray(model.aliases) ? model.aliases : [])
    ].join(' ')
  }
}

function normalizePrice(value) {
  if (value === '' || value === null || value === undefined) return null
  const number = Number(value)
  if (!Number.isFinite(number) || number < 0) return null
  return String(number)
}

function modalityLabel(value) {
  const labels = {
    text: t('llmOps.manualPriceEntry.modalities.text'),
    multimodal: t('llmOps.manualPriceEntry.modalities.multimodal'),
    audio: t('llmOps.manualPriceEntry.modalities.audio'),
    video: t('llmOps.manualPriceEntry.modalities.video')
  }
  return labels[value] || value || labels.text
}

function errorMessage(error, fallback) {
  const data = error?.response?.data
  const fieldMessage = firstErrorMessage(data)
  if (data?.detail) return data.detail
  if (data?.message) return data.message
  if (fieldMessage) return fieldMessage
  return error?.message || fallback
}

function firstErrorMessage(value, field = '') {
  if (!value || typeof value === 'string') return value || ''
  if (Array.isArray(value)) {
    return firstErrorMessage(value[0], field)
  }
  if (typeof value !== 'object') return String(value)

  const [key, nested] = Object.entries(value)[0] || []
  if (!key) return ''
  const label = field && key !== 'non_field_errors' ? `${field}.${key}` : key
  const message = firstErrorMessage(nested, label)
  if (!message) return ''
  if (key === 'non_field_errors') return message
  return `${label}: ${message}`
}
</script>

<style scoped>
.modal-header {
  @apply flex flex-col gap-3 border-b border-slate-200 px-5 py-4 sm:flex-row sm:items-start sm:justify-between;
}

.modal-body {
  @apply max-h-[calc(100vh-13rem)] overflow-y-auto px-5 py-5;
}

.eyebrow {
  @apply text-xs font-semibold uppercase tracking-[0.18em] text-indigo-600;
}

.source-context {
  @apply flex items-center justify-between gap-3 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3;
}

.form-section {
  @apply rounded-lg border border-slate-200 bg-white p-4;
}

.section-heading {
  @apply mb-4;
}

.section-heading h4 {
  @apply text-sm font-semibold text-slate-900;
}

.section-heading p {
  @apply mt-1 text-xs leading-5 text-slate-500;
}

.mode-tabs {
  @apply mb-4 inline-flex rounded-lg border border-slate-200 bg-slate-50 p-1;
}

.mode-tab {
  @apply rounded-md px-3 py-1.5 text-sm font-medium text-slate-500 transition hover:text-slate-800;
}

.mode-tab.active {
  @apply bg-white text-indigo-700 shadow-sm;
}

.field-group {
  @apply flex min-w-0 flex-col gap-1.5;
}

.compact-field {
  @apply md:max-w-44;
}

.field-label {
  @apply text-xs font-medium text-slate-500;
}

.field-help {
  @apply text-xs leading-5 text-slate-400;
}

.field {
  @apply h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-indigo-300 focus:ring-2 focus:ring-indigo-100;
}

.readonly-field {
  @apply rounded-lg border border-slate-200 bg-slate-50 px-3 py-2;
}

.readonly-field span {
  @apply block text-xs font-medium text-slate-500;
}

.readonly-field strong {
  @apply mt-1 block truncate text-sm font-semibold text-slate-900;
}

.price-grid {
  @apply mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4;
}

.error-line {
  @apply rounded-lg border border-amber-100 bg-amber-50 px-3 py-2 text-sm text-amber-700;
}

.btn-primary {
  @apply inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60;
}

.btn-secondary {
  @apply inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60;
}

.source-badge {
  @apply shrink-0 rounded-full border px-2 py-1 text-xs font-medium;
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

:global(body.llm-ops-theme) .manual-price-modal-footer.modal-footer {
  gap: 0.75rem !important;
  padding: 0.75rem 1.25rem !important;
}

:global(body.llm-ops-theme) .manual-price-modal-actions.modal-footer-actions {
  gap: 0.5rem !important;
}

.save-icon {
  align-items: center;
  background: rgba(255, 255, 255, 0.18);
  border: 1px solid rgba(255, 255, 255, 0.32);
  border-radius: 999px;
  display: inline-flex;
  height: 1rem;
  justify-content: center;
  position: relative;
  width: 1rem;
}

.save-icon::after {
  border-bottom: 2px solid currentColor;
  border-right: 2px solid currentColor;
  content: '';
  height: 0.45rem;
  margin-top: -0.1rem;
  transform: rotate(45deg);
  width: 0.25rem;
}
</style>
