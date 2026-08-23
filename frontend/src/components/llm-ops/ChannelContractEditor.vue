<template>
  <section class="panel space-y-4">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h3 class="panel-title">{{ t('llmOps.channelContract.title') }}</h3>
        <p class="mt-1 text-xs leading-5 text-slate-500">
          {{ t('llmOps.channelContract.description') }}
        </p>
      </div>
      <span class="rounded-full bg-indigo-50 px-2.5 py-1 text-xs font-medium text-indigo-700">
        {{ t('llmOps.channelContract.versionLabel', { version: nextVersion }) }}
      </span>
    </div>

    <div class="grid gap-3 md:grid-cols-3">
      <label class="form-field">
        <span class="field-label">{{ t('llmOps.channelContract.channel') }}</span>
        <CompactSelect v-model="form.channel" :options="channelOptions" searchable />
      </label>
      <label class="form-field">
        <span class="field-label">{{ t('llmOps.channelContract.model') }}</span>
        <CompactSelect
          v-model="form.model"
          :options="modelOptions"
          :disabled="!form.channel"
          searchable
          @change="onModelChange"
        />
      </label>
      <label class="form-field">
        <span class="field-label">{{ t('llmOps.channelContract.offering') }}</span>
        <CompactSelect
          v-model="form.offering"
          :options="offeringOptions"
          :disabled="!form.model"
          searchable
        />
      </label>
    </div>

    <div class="grid gap-3 md:grid-cols-4">
      <label class="form-field">
        <span class="field-label">{{ t('llmOps.channelContract.status') }}</span>
        <CompactSelect v-model="form.status" :options="statusOptions" />
      </label>
      <label class="form-field">
        <span class="field-label">{{ t('llmOps.channelContract.effectiveFrom') }}</span>
        <input v-model="form.effective_from" class="field" type="datetime-local" />
      </label>
      <label class="form-field">
        <span class="field-label">{{ t('llmOps.channelContract.effectiveTo') }}</span>
        <input v-model="form.effective_to" class="field" type="datetime-local" />
      </label>
      <label class="form-field">
        <span class="field-label">{{ t('llmOps.channelContract.timezone') }}</span>
        <input v-model="form.timezone" class="field" placeholder="Asia/Shanghai" />
      </label>
    </div>

    <div class="grid gap-3 md:grid-cols-4">
      <label class="form-field">
        <span class="field-label">{{ t('llmOps.channelContract.discountType') }}</span>
        <CompactSelect v-model="form.discount_type" :options="discountOptions" />
      </label>
      <label v-if="form.discount_type !== 'none'" class="form-field">
        <span class="field-label">{{ t('llmOps.channelContract.discountValue') }}</span>
        <input
          v-model="form.discount_value"
          class="field"
          min="0"
          :max="form.discount_type === 'ratio' ? 1 : undefined"
          step="0.000001"
          type="number"
        />
      </label>
      <label class="form-field">
        <span class="field-label">{{ t('llmOps.channelContract.schedule') }}</span>
        <CompactSelect v-model="form.schedule" :options="scheduleOptions" />
      </label>
      <label class="form-field">
        <span class="field-label">{{ t('llmOps.channelContract.scheduleStart') }}</span>
        <input v-model="form.schedule_start" class="field" type="time" />
      </label>
      <label class="form-field">
        <span class="field-label">{{ t('llmOps.channelContract.scheduleEnd') }}</span>
        <input v-model="form.schedule_end" class="field" type="time" />
      </label>
    </div>

    <div class="grid gap-3 md:grid-cols-4">
      <label class="form-field">
        <span class="field-label">{{ t('llmOps.channelContract.contractCurrency') }}</span>
        <CompactSelect v-model="form.contract_currency" :options="currencyOptions" />
      </label>
      <label class="form-field">
        <span class="field-label">{{ t('llmOps.channelContract.contractRate') }}</span>
        <input
          v-model="form.contract_exchange_rate"
          class="field"
          min="0.00000001"
          step="0.00000001"
          type="number"
          :placeholder="t('llmOps.channelContract.ratePlaceholder')"
        />
      </label>
      <label class="form-field md:col-span-2">
        <span class="field-label">{{ t('llmOps.channelContract.capabilities') }}</span>
        <div class="flex flex-wrap gap-4 pt-2 text-sm">
          <label class="inline-flex items-center gap-2">
            <input v-model="form.enable_cache" type="checkbox" :disabled="!capabilities.cache" />
            {{ t('llmOps.channelContract.cache') }}
          </label>
          <label class="inline-flex items-center gap-2">
            <input v-model="form.enable_tier" type="checkbox" :disabled="!capabilities.tier" />
            {{ t('llmOps.channelContract.tier') }}
          </label>
          <span class="text-xs text-slate-500">{{ capabilityHint }}</span>
        </div>
      </label>
    </div>

    <div class="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4">
      <div class="text-xs text-slate-500">
        {{ t('llmOps.channelContract.itemsSummary', { count: contractItems.length }) }}
      </div>
      <div class="flex gap-2">
        <button type="button" class="btn-secondary" :disabled="saving" @click="reset">
          {{ t('common.clear') }}
        </button>
        <button type="button" class="btn-primary" :disabled="!canSave || saving" @click="save">
          {{ saving ? t('common.saving') : t('llmOps.channelContract.save') }}
        </button>
      </div>
    </div>
    <p v-if="error" class="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">
      {{ error }}
    </p>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { llmOpsApi } from '@/api/llmOps'
import CompactSelect from '@/components/llm-ops/CompactSelect.vue'
import { userFacingApiError } from '@/utils/llmOpsErrors'

const props = defineProps({
  channels: { type: Array, default: () => [] },
  models: { type: Array, default: () => [] },
  channelPrices: { type: Array, default: () => [] },
  channelOfferings: { type: Array, default: () => [] },
  channelPriceVersions: { type: Array, default: () => [] },
  priceItems: { type: Array, default: () => [] }
})

const emit = defineEmits(['refresh'])
const { t } = useI18n()
const saving = ref(false)
const error = ref('')
const form = ref(defaults())

const channelOptions = computed(() =>
  props.channels.map((item) => ({ value: String(item.id), label: item.name }))
)
const modelOptions = computed(() => {
  const channelId = String(form.value.channel || '')
  const ids = new Set(
    props.channelPrices
      .filter((item) => String(item.channel) === channelId)
      .map((item) => String(item.model))
  )
  return props.models
    .filter((item) => ids.has(String(item.id)))
    .map((item) => ({
      value: String(item.id),
      label: item.name,
      description: [item.provider_name, item.code].filter(Boolean).join(' · ')
    }))
})
const selectedModel = computed(() =>
  props.models.find((item) => String(item.id) === String(form.value.model))
)
const selectedOffering = computed(() =>
  props.channelOfferings.find(
    (item) => String(item.id) === String(form.value.offering)
  )
)
const offeringOptions = computed(() => {
  const model = selectedModel.value
  if (!model) return []
  return props.channelOfferings
    .filter(
      (item) =>
        String(item.channel) === String(form.value.channel) &&
        String(item.meta_model) === String(model.meta_model)
    )
    .map((item) => ({
      value: String(item.id),
      label: item.display_name,
      description: [item.offering_key, item.source_offering_name]
        .filter(Boolean)
        .join(' · ')
    }))
})
const currentVersions = computed(() =>
  props.channelPriceVersions.filter(
    (item) =>
      String(item.offering) === String(form.value.offering) &&
      String(item.model) === String(form.value.model)
  )
)
const nextVersion = computed(() =>
  Math.max(0, ...currentVersions.value.map((item) => Number(item.version) || 0)) + 1
)
const sourceItems = computed(() => {
  const model = selectedModel.value
  if (!model) return []
  const sourceOfferingId = selectedOffering.value?.source_offering
  const candidates = props.priceItems
    .filter(
      (item) =>
        item.is_current !== false &&
        (String(item.model) === String(model.id) ||
          String(item.meta_model) === String(model.meta_model))
    )
  const offeringItems = sourceOfferingId
    ? candidates.filter(
        (item) => String(item.offering) === String(sourceOfferingId)
      )
    : []
  const rows = offeringItems.length ? offeringItems : candidates
  const groups = new Map()
  rows.forEach((item) => {
    const key = sourcePriceGroupKey(item)
    const group = groups.get(key) || []
    group.push(item)
    groups.set(key, group)
  })
  const bestGroup = Array.from(groups.values()).sort(
    (left, right) => sourcePriceGroupScore(right, model) - sourcePriceGroupScore(left, model)
  )[0]
  return (bestGroup || []).sort(
    (left, right) => {
      const dimension = String(left.dimension).localeCompare(String(right.dimension))
      return (
        dimension ||
        Number(left.tier_start || 0) - Number(right.tier_start || 0)
      )
    }
  )
})

function sourcePriceGroupKey(item) {
  const spec = JSON.stringify(item.spec || {})
  if (item.offering) return `offering:${item.offering}:${spec}`
  if (item.sku) return `sku:${item.source || ''}:${item.sku}:${spec}`
  if (item.model) return `model:${item.source || ''}:${item.model}:${spec}`
  return `source:${item.source || ''}:${spec}`
}

function sourcePriceGroupScore(rows, model) {
  if (!rows.length) return 0
  const first = rows[0]
  const category = String(
    first.business_source_category || first.source_category || ''
  )
  const categoryScore =
    category === 'official_provider' ? 300 : category === 'supplier' ? 200 : 0
  const latest = Math.max(
    ...rows
      .map((item) => new Date(item.effective_from || item.updated_at || 0).getTime())
      .filter(Number.isFinite),
    0
  )
  const alignment = rows.reduce((score, item) => {
    const fieldMap = {
      text_input: 'input_price_per_million',
      text_output: 'output_price_per_million',
      cache_input: 'cache_input_price_per_million',
      image_output: 'image_output_price_per_image',
      audio_input: 'audio_input_price_per_second',
      audio_output: 'audio_output_price_per_second',
      video_input: 'video_input_price_per_second',
      video_output: 'video_output_price_per_second'
    }
    const modelValue = Number(model?.[fieldMap[item.dimension]])
    const itemValue = Number(item.unit_price)
    return Number.isFinite(modelValue) && Number.isFinite(itemValue) && modelValue === itemValue
      ? score + 1
      : score
  }, 0)
  return categoryScore + rows.length * 10 + alignment * 1000 + latest / 100000000000
}
const capabilities = computed(() => ({
  cache: sourceItems.value.some((item) => item.dimension === 'cache_input'),
  tier: sourceItems.value.some((item) => item.tier_type === 'usage_range')
}))
const capabilityHint = computed(() => {
  const labels = []
  if (capabilities.value.cache) labels.push(t('llmOps.channelContract.cacheAvailable'))
  if (capabilities.value.tier) labels.push(t('llmOps.channelContract.tierAvailable'))
  return labels.join(' · ') || t('llmOps.channelContract.noCapability')
})
const contractItems = computed(() => {
  const rows = sourceItems.value.filter((item) => {
    if (!form.value.enable_cache && item.dimension === 'cache_input') return false
    return true
  })
  const seenDimensions = new Set()
  return rows.filter((item) => {
    if (form.value.enable_tier) return true
    if (seenDimensions.has(item.dimension)) return false
    seenDimensions.add(item.dimension)
    return true
  })
})
const canSave = computed(
  () =>
    Boolean(form.value.channel && form.value.model && form.value.offering) &&
    contractItems.value.length > 0 &&
    (form.value.status === 'draft' || form.value.effective_from)
)

const statusOptions = computed(() => [
  { value: 'draft', label: t('llmOps.channelContract.statusDraft') },
  { value: 'scheduled', label: t('llmOps.channelContract.statusScheduled') },
  { value: 'active', label: t('llmOps.channelContract.statusActive') }
])
const discountOptions = computed(() => [
  { value: 'none', label: t('llmOps.channelContract.discountNone') },
  { value: 'ratio', label: t('llmOps.channelContract.discountRatio') },
  { value: 'fixed', label: t('llmOps.channelContract.discountFixed') }
])
const scheduleOptions = computed(() => [
  { value: 'all', label: t('llmOps.channelContract.scheduleAll') },
  { value: 'business', label: t('llmOps.channelContract.scheduleBusiness') },
  { value: 'offpeak', label: t('llmOps.channelContract.scheduleOffpeak') }
])
const currencyOptions = [
  { value: '', label: t('llmOps.channelContract.currencyDefault') },
  { value: 'CNY', label: 'CNY' },
  { value: 'USD', label: 'USD' }
]

watch(
  () => [form.value.channel, form.value.model, props.channelOfferings],
  () => {
    if (!form.value.model || !modelOptions.value.some((item) => item.value === String(form.value.model))) {
      form.value.model = ''
    }
    if (!form.value.offering || !offeringOptions.value.some((item) => item.value === String(form.value.offering))) {
      form.value.offering = offeringOptions.value[0]?.value || ''
    }
    if (!capabilities.value.cache) form.value.enable_cache = false
    if (!capabilities.value.tier) form.value.enable_tier = false
  },
  { deep: true }
)

function defaults() {
  return {
    channel: '',
    model: '',
    offering: '',
    status: 'draft',
    effective_from: '',
    effective_to: '',
    timezone: 'Asia/Shanghai',
    discount_type: 'none',
    discount_value: '',
    schedule: 'all',
    schedule_start: '09:00',
    schedule_end: '18:00',
    contract_currency: '',
    contract_exchange_rate: '',
    enable_cache: true,
    enable_tier: true
  }
}

function onModelChange() {
  form.value.offering = offeringOptions.value[0]?.value || ''
}

function reset() {
  form.value = defaults()
  error.value = ''
}

function toIso(value) {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date.toISOString()
}

function scheduleSpec() {
  if (form.value.schedule === 'all') return {}
  const weekdays = form.value.schedule === 'business' ? [1, 2, 3, 4, 5] : [0, 6]
  return {
    time_windows: [
      {
        end: form.value.schedule_end,
        start: form.value.schedule_start,
        weekdays
      }
    ]
  }
}

async function save() {
  if (!canSave.value || saving.value) return
  saving.value = true
  error.value = ''
  try {
    await llmOpsApi.createChannelPriceVersion({
      discount_dimensions: [],
      discount_type: form.value.discount_type,
      discount_value:
        form.value.discount_type === 'none' ? null : form.value.discount_value,
      effective_from: toIso(form.value.effective_from),
      effective_to: toIso(form.value.effective_to),
      contract_currency: form.value.contract_currency,
      contract_exchange_rate: form.value.contract_exchange_rate || null,
      exchange_rate_effective_from: toIso(form.value.effective_from),
      exchange_rate_effective_to: toIso(form.value.effective_to),
      model: Number(form.value.model),
      offering: Number(form.value.offering),
      price_items: contractItems.value.map((item) => ({
        billing_unit: item.billing_unit,
        currency: item.currency,
        dimension: item.dimension,
        spec: {
          ...(item.spec || {}),
          ...scheduleSpec()
        },
        tier_end: form.value.enable_tier ? item.tier_end : null,
        tier_start: form.value.enable_tier ? item.tier_start : null,
        tier_type: form.value.enable_tier ? item.tier_type : 'flat',
        unit_price: item.unit_price
      })),
      status: form.value.status,
      timezone: form.value.timezone,
      version: nextVersion.value
    })
    emit('refresh')
    reset()
  } catch (saveError) {
    error.value = userFacingApiError(
      saveError,
      t('llmOps.channelContract.saveFailed')
    )
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.field {
  @apply w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 outline-none transition focus:border-indigo-300 focus:ring-4 focus:ring-indigo-50;
}

.form-field {
  @apply block space-y-1.5;
}

.field-label {
  @apply block text-xs font-medium text-slate-700;
}
</style>
