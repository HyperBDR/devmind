<template>
  <div
    v-if="open"
    class="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/30 px-4 py-6"
    @click.self="close"
  >
    <form
      autocomplete="off"
      class="max-h-[calc(100vh-3rem)] w-full max-w-3xl overflow-hidden rounded-xl bg-white shadow-2xl"
      @submit.prevent="save"
    >
      <div class="border-b border-slate-200 px-5 py-4">
        <div class="flex items-start justify-between gap-4">
          <div>
            <p
              class="text-xs font-semibold uppercase tracking-[0.18em] text-indigo-600"
            >
              Resale Platform
            </p>
            <h3 class="mt-2 text-lg font-semibold text-slate-900">
              {{
                form.id
                  ? t('llmOps.resalePlatformModal.editTitle')
                  : t('llmOps.resalePlatformModal.createTitle')
              }}
            </h3>
            <p class="mt-1 text-sm text-slate-500">
              {{ t('llmOps.resalePlatformModal.description') }}
            </p>
          </div>
          <button
            type="button"
            class="btn-secondary btn-action-cancel"
            :disabled="saving"
            @click="close"
          >
            {{ t('common.close') }}
          </button>
        </div>
      </div>

      <div
        class="max-h-[calc(100vh-15rem)] space-y-5 overflow-y-auto px-5 py-5"
      >
        <section class="form-section">
          <div class="section-heading">
            <h4>{{ t('llmOps.resalePlatformModal.platformInfo') }}</h4>
            <p>{{ t('llmOps.resalePlatformModal.platformInfoHint') }}</p>
          </div>
          <div class="grid gap-4 md:grid-cols-2">
            <label class="field-group">
              <span class="field-label">
                {{ t('llmOps.resalePlatformModal.fields.name') }}
              </span>
              <input
                v-model="form.name"
                class="field"
                :placeholder="t('llmOps.resalePlatformModal.placeholders.name')"
                required
              />
            </label>
            <label class="field-group">
              <span class="field-label">
                {{ t('llmOps.resalePlatformModal.fields.code') }}
              </span>
              <input
                v-model="form.code"
                class="field"
                :placeholder="t('llmOps.resalePlatformModal.placeholders.code')"
                required
              />
            </label>
            <label class="field-group">
              <span class="field-label">
                {{ t('llmOps.resalePlatformModal.fields.platformType') }}
              </span>
              <CompactSelect
                v-model="form.platform_type"
                :options="platformTypeOptions"
              />
            </label>
            <label class="field-group">
              <span class="field-label">
                {{ t('llmOps.resalePlatformModal.fields.environment') }}
              </span>
              <CompactSelect
                v-model="form.environment"
                :options="environmentOptions"
              />
            </label>
            <label class="field-group">
              <span class="field-label">
                {{ t('llmOps.resalePlatformModal.fields.region') }}
              </span>
              <CompactSelect
                v-model="form.region_code"
                :options="regionOptions"
                searchable
              />
            </label>
            <label class="field-group">
              <span class="field-label">
                {{ t('llmOps.resalePlatformModal.fields.regionName') }}
              </span>
              <input
                v-model="form.region_name"
                class="field"
                :placeholder="
                  t('llmOps.resalePlatformModal.placeholders.regionName')
                "
              />
            </label>
            <label class="field-group">
              <span class="field-label">
                {{ t('llmOps.resalePlatformModal.fields.website') }}
              </span>
              <input
                v-model="form.website"
                class="field"
                placeholder="https://www.agione.com"
                type="url"
              />
            </label>
            <label class="field-group">
              <span class="field-label">
                {{ t('llmOps.resalePlatformModal.fields.apiEndpoint') }}
              </span>
              <input
                v-model="form.api_endpoint"
                autocomplete="off"
                autocapitalize="off"
                autocorrect="off"
                class="field"
                data-1p-ignore="true"
                data-bwignore="true"
                data-form-type="other"
                data-lpignore="true"
                inputmode="url"
                placeholder="https://api.example.com"
                spellcheck="false"
                type="url"
              />
            </label>
            <label class="field-group md:col-span-2">
              <span class="field-label">
                {{ t('llmOps.resalePlatformModal.fields.apiKey') }}
              </span>
              <input
                v-model="form.api_key"
                autocomplete="off"
                autocapitalize="off"
                autocorrect="off"
                class="field secret-field font-mono"
                data-1p-ignore="true"
                data-bwignore="true"
                data-form-type="other"
                data-lpignore="true"
                :placeholder="
                  t('llmOps.resalePlatformModal.placeholders.apiKey')
                "
                spellcheck="false"
                type="text"
              />
              <span class="field-help">
                {{ t('llmOps.resalePlatformModal.apiKeyHint') }}
              </span>
            </label>
          </div>
        </section>

        <section class="form-section">
          <div class="section-heading">
            <h4>{{ t('llmOps.resalePlatformModal.settlementTitle') }}</h4>
            <p>{{ t('llmOps.resalePlatformModal.settlementHint') }}</p>
          </div>
          <div class="grid gap-4 md:grid-cols-2">
            <label class="field-group">
              <span class="field-label">
                {{ t('llmOps.resalePlatformModal.fields.currency') }}
              </span>
              <CompactSelect
                v-model="form.currency"
                :options="currencyOptions"
              />
            </label>
            <label class="field-group">
              <span class="field-label">
                {{ t('llmOps.resalePlatformModal.fields.feeRate') }}
              </span>
              <input
                v-model="form.fee_rate"
                class="field"
                min="0"
                max="99.99"
                step="0.01"
                type="number"
                :placeholder="
                  t('llmOps.resalePlatformModal.placeholders.feeRate')
                "
              />
            </label>
            <label class="field-group">
              <span class="field-label">
                {{ t('llmOps.resalePlatformModal.fields.serviceFeeRate') }}
              </span>
              <input
                v-model="form.service_fee_rate"
                class="field"
                min="0"
                max="99.99"
                step="0.01"
                type="number"
                :placeholder="
                  t('llmOps.resalePlatformModal.placeholders.serviceFeeRate')
                "
              />
            </label>
            <label class="field-group">
              <span class="field-label">
                {{ t('llmOps.resalePlatformModal.fields.taxRate') }}
              </span>
              <input
                v-model="form.tax_rate"
                class="field"
                min="0"
                max="99.99"
                step="0.01"
                type="number"
                :placeholder="
                  t('llmOps.resalePlatformModal.placeholders.optionalRate')
                "
              />
            </label>
            <label class="field-group">
              <span class="field-label">
                {{ t('llmOps.resalePlatformModal.fields.settlementRate') }}
              </span>
              <input
                v-model="form.settlement_rate"
                class="field"
                min="0"
                step="0.01"
                type="number"
                :placeholder="
                  t('llmOps.resalePlatformModal.placeholders.settlementRate')
                "
              />
            </label>
            <label class="field-group">
              <span class="field-label">
                {{ t('llmOps.resalePlatformModal.fields.yieldWarning') }}
              </span>
              <input
                v-model="form.yield_warning"
                class="field"
                min="0"
                step="0.01"
                type="number"
                :placeholder="
                  t('llmOps.resalePlatformModal.placeholders.yieldWarning')
                "
              />
            </label>
            <label class="field-group">
              <span class="field-label">
                {{ t('llmOps.resalePlatformModal.fields.yieldTarget') }}
              </span>
              <input
                v-model="form.yield_target"
                class="field"
                min="0"
                step="0.01"
                type="number"
                :placeholder="
                  t('llmOps.resalePlatformModal.placeholders.yieldTarget')
                "
              />
            </label>
            <label class="field-group">
              <span class="field-label">
                {{
                  t('llmOps.resalePlatformModal.fields.autoApproveMaxMargin')
                }}
              </span>
              <input
                v-model="form.auto_approve_max_margin_rate"
                class="field"
                min="0"
                step="0.01"
                type="number"
                :placeholder="
                  t(
                    'llmOps.resalePlatformModal.placeholders.autoApproveMaxMargin'
                  )
                "
              />
            </label>
            <label class="field-group">
              <span class="field-label">
                {{ t('llmOps.resalePlatformModal.fields.pointName') }}
              </span>
              <input
                v-model="form.point_name"
                class="field"
                :placeholder="
                  t('llmOps.resalePlatformModal.placeholders.pointName')
                "
              />
            </label>
            <label class="field-group">
              <span class="field-label">
                {{
                  t('llmOps.resalePlatformModal.fields.pointsPerCurrencyUnit')
                }}
              </span>
              <input
                v-model="form.points_per_currency_unit"
                class="field"
                min="0.01"
                step="0.01"
                type="number"
                :placeholder="
                  t(
                    'llmOps.resalePlatformModal.placeholders.pointsPerCurrencyUnit'
                  )
                "
              />
            </label>
            <label class="field-group">
              <span class="field-label">
                {{ t('llmOps.resalePlatformModal.fields.roundingMode') }}
              </span>
              <CompactSelect
                v-model="form.point_rounding_mode"
                :options="roundingModeOptions"
              />
            </label>
            <label class="field-group">
              <span class="field-label">
                {{ t('llmOps.resalePlatformModal.fields.decimalPlaces') }}
              </span>
              <CompactSelect
                v-model="form.point_decimal_places"
                :options="decimalPlaceOptions"
              />
            </label>
          </div>
        </section>

        <section class="form-section">
          <div class="section-heading">
            <h4>{{ t('llmOps.resalePlatformModal.metadataTitle') }}</h4>
            <p>{{ t('llmOps.resalePlatformModal.metadataHint') }}</p>
          </div>
          <textarea
            v-model="form.metadata_text"
            class="field min-h-28 resize-none font-mono text-xs leading-5"
            :placeholder="t('llmOps.resalePlatformModal.placeholders.metadata')"
            :aria-invalid="Boolean(metadataError)"
          />
          <p v-if="metadataError" class="field-error">
            {{ metadataError }}
          </p>
        </section>

        <section class="form-section">
          <div class="section-heading">
            <h4>{{ t('llmOps.resalePlatformModal.notesTitle') }}</h4>
            <p>{{ t('llmOps.resalePlatformModal.notesHint') }}</p>
          </div>
          <textarea
            v-model="form.notes"
            class="field min-h-20 resize-none"
            :placeholder="t('llmOps.resalePlatformModal.placeholders.notes')"
          />
        </section>
      </div>

      <div class="modal-footer">
        <label class="status-inline" :class="{ active: form.is_active }">
          <input v-model="form.is_active" type="checkbox" class="sr-only" />
          <span class="status-switch" aria-hidden="true">
            <span class="status-switch-dot" />
          </span>
          <span class="text-sm text-slate-700">
            {{
              form.is_active
                ? t('llmOps.resalePlatformModal.enabled')
                : t('llmOps.resalePlatformModal.disabled')
            }}
          </span>
        </label>
        <div class="modal-footer-actions">
          <button
            class="btn-secondary btn-action-cancel"
            type="button"
            :disabled="saving"
            @click="close"
          >
            {{ t('common.cancel') }}
          </button>
          <button
            class="btn-primary btn-action-save"
            type="submit"
            :disabled="saving"
          >
            <span class="icon-mark" :class="saving ? 'animate-spin' : ''" />
            {{
              saving
                ? t('common.saving')
                : form.id
                  ? t('llmOps.resalePlatformModal.saveChanges')
                  : t('llmOps.resalePlatformModal.createPlatform')
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
import CompactSelect from '@/components/llm-ops/CompactSelect.vue'

const props = defineProps({
  open: {
    type: Boolean,
    default: false
  },
  platform: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['close', 'saved'])
const { t } = useI18n()

const form = ref(defaults())
const saving = ref(false)
const currencyOptions = [
  { label: 'CNY', value: 'CNY' },
  { label: 'USD', value: 'USD' }
]
const platformTypeOptions = [{ label: 'Agione', value: 'agione' }]
const environmentOptions = computed(() => [
  {
    label: t('llmOps.resalePlatform.environments.production'),
    value: 'production'
  },
  { label: t('llmOps.resalePlatform.environments.staging'), value: 'staging' },
  { label: t('llmOps.resalePlatform.environments.sandbox'), value: 'sandbox' },
  { label: t('llmOps.resalePlatform.environments.test'), value: 'test' }
])
const regionOptions = computed(() => [
  { label: t('llmOps.resalePlatformModal.regions.global'), value: '' },
  { label: t('llmOps.resalePlatformModal.regions.cn'), value: 'cn' },
  {
    label: t('llmOps.resalePlatformModal.regions.cnNorth'),
    value: 'cn-north'
  },
  {
    label: t('llmOps.resalePlatformModal.regions.cnEast'),
    value: 'cn-east'
  },
  {
    label: t('llmOps.resalePlatformModal.regions.cnSouth'),
    value: 'cn-south'
  },
  {
    label: t('llmOps.resalePlatformModal.regions.cnHongkong'),
    value: 'cn-hongkong'
  },
  {
    label: t('llmOps.resalePlatformModal.regions.apSoutheast1'),
    value: 'ap-southeast-1'
  },
  {
    label: t('llmOps.resalePlatformModal.regions.apNortheast1'),
    value: 'ap-northeast-1'
  },
  {
    label: t('llmOps.resalePlatformModal.regions.usEast1'),
    value: 'us-east-1'
  },
  {
    label: t('llmOps.resalePlatformModal.regions.euWest1'),
    value: 'eu-west-1'
  }
])
const roundingModeOptions = computed(() => [
  { label: t('llmOps.resalePlatformModal.rounding.halfUp'), value: 'half_up' },
  { label: t('llmOps.resalePlatformModal.rounding.up'), value: 'up' },
  { label: t('llmOps.resalePlatformModal.rounding.down'), value: 'down' }
])
const decimalPlaceOptions = computed(() =>
  Array.from({ length: 7 }, (_, value) => ({
    label: t('llmOps.resalePlatformModal.decimalPlaces', { count: value }),
    value
  }))
)
const metadataError = ref('')

watch(
  () => [props.open, props.platform],
  () => {
    metadataError.value = ''
    form.value = props.platform ? platformToForm(props.platform) : defaults()
  },
  { immediate: true }
)

function defaults() {
  return {
    id: null,
    name: '',
    code: '',
    platform_type: 'agione',
    region_code: '',
    region_name: '',
    environment: 'production',
    website: '',
    api_endpoint: '',
    api_key: '',
    currency: 'CNY',
    fee_rate: '3',
    service_fee_rate: '0',
    tax_rate: '',
    settlement_rate: '',
    yield_warning: '',
    yield_target: '',
    auto_approve_max_margin_rate: '100',
    point_name: t('llmOps.resalePlatformModal.defaultPointName'),
    points_per_currency_unit: '100.00',
    point_rounding_mode: 'half_up',
    point_decimal_places: 0,
    metadata: {},
    metadata_text: '',
    notes: '',
    is_active: true
  }
}

function platformToForm(platform) {
  return {
    ...platform,
    platform_type: 'agione',
    region_code: platform.region_code || '',
    region_name: platform.region_name || '',
    environment: platform.environment || 'production',
    fee_rate: percentFromRatio(platform.fee_rate),
    service_fee_rate: percentFromRatio(platform.service_fee_rate),
    tax_rate: optionalPercentFromRatio(platform.tax_rate),
    settlement_rate: optionalPercentFromRatio(platform.settlement_rate),
    yield_warning: optionalPercentFromRatio(platform.yield_warning),
    yield_target: optionalPercentFromRatio(platform.yield_target),
    points_per_currency_unit: formatDecimal(
      platform.points_per_currency_unit,
      2
    ),
    point_decimal_places: platform.point_decimal_places ?? 0,
    metadata: platform.metadata || {},
    metadata_text: formatMetadata(platform.metadata)
  }
}

function formatMetadata(value) {
  if (!value || Array.isArray(value) || typeof value !== 'object') return ''
  if (Object.keys(value).length === 0) return ''
  return JSON.stringify(value, null, 2)
}

function percentFromRatio(value) {
  const numberValue = Number(value)
  if (!Number.isFinite(numberValue)) return ''
  return (numberValue * 100).toFixed(2).replace(/\.?0+$/, '')
}

function ratioFromPercent(value) {
  const numberValue = Number(value)
  if (!Number.isFinite(numberValue)) return 0
  return Number((numberValue / 100).toFixed(6))
}

function optionalPercentFromRatio(value) {
  if (value === null || value === undefined || value === '') return ''
  return percentFromRatio(value)
}

function optionalRatioFromPercent(value) {
  if (value === null || value === undefined || value === '') return null
  const numberValue = Number(value)
  if (!Number.isFinite(numberValue)) return null
  return Number((numberValue / 100).toFixed(6))
}

function normalizePayload(payload) {
  const clean = { ...payload }
  clean.platform_type = 'agione'
  clean.code = String(clean.code || '')
    .trim()
    .toLowerCase()
  clean.region_code = String(clean.region_code || '').trim()
  clean.region_name = String(clean.region_name || '').trim()
  clean.currency = String(clean.currency || 'CNY')
    .trim()
    .toUpperCase()
  clean.points_per_currency_unit = normalizePointRatio(
    clean.points_per_currency_unit
  )
  clean.fee_rate = ratioFromPercent(clean.fee_rate)
  clean.service_fee_rate = ratioFromPercent(clean.service_fee_rate)
  clean.tax_rate = optionalRatioFromPercent(clean.tax_rate)
  clean.settlement_rate = optionalRatioFromPercent(clean.settlement_rate)
  clean.yield_warning = optionalRatioFromPercent(clean.yield_warning)
  clean.yield_target = optionalRatioFromPercent(clean.yield_target)
  clean.point_decimal_places = normalizePointDecimalPlaces(
    clean.point_decimal_places
  )
  clean.metadata = parseMetadata(clean.metadata_text)
  delete clean.id
  delete clean.listing_count
  delete clean.metadata_text
  return clean
}

function formatDecimal(value, digits) {
  const numberValue = Number(value)
  if (!Number.isFinite(numberValue)) return ''
  return numberValue.toFixed(digits)
}

function normalizePointRatio(value) {
  const numberValue = Number(value)
  if (!Number.isFinite(numberValue)) return '0.00'
  return Math.max(0, numberValue).toFixed(2)
}

function normalizePointDecimalPlaces(value) {
  const numberValue = Number(value)
  if (!Number.isFinite(numberValue)) return 0
  return Math.min(6, Math.max(0, Math.trunc(numberValue)))
}

function parseMetadata(value) {
  const text = String(value || '').trim()
  if (!text) return {}
  let parsed
  try {
    parsed = JSON.parse(text)
  } catch {
    throw new Error(t('llmOps.resalePlatformModal.errors.invalidMetadataJson'))
  }
  if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') {
    throw new Error(t('llmOps.resalePlatformModal.errors.metadataObject'))
  }
  return parsed
}

function close() {
  form.value = defaults()
  metadataError.value = ''
  emit('close')
}

async function save() {
  if (saving.value) return
  saving.value = true
  metadataError.value = ''
  try {
    const payload = normalizePayload(form.value)
    if (form.value.id) {
      await llmOpsApi.updateResalePlatform(form.value.id, payload)
    } else {
      await llmOpsApi.createResalePlatform(payload)
    }
    form.value = defaults()
    emit('saved')
  } catch (error) {
    if (error instanceof SyntaxError) {
      metadataError.value = t(
        'llmOps.resalePlatformModal.errors.invalidMetadataJson'
      )
      return
    }
    if (
      error?.message ===
      t('llmOps.resalePlatformModal.errors.invalidMetadataJson')
    ) {
      metadataError.value = error.message
      return
    }
    if (
      error?.message === t('llmOps.resalePlatformModal.errors.metadataObject')
    ) {
      metadataError.value = error.message
      return
    }
    throw error
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.field {
  @apply w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 outline-none transition focus:border-indigo-300 focus:ring-4 focus:ring-indigo-50;
}

.secret-field {
  -webkit-text-security: disc;
}

.field-group {
  @apply block space-y-1.5;
}

.field-label {
  @apply block text-sm font-medium text-slate-800;
}

.field-help {
  @apply block text-xs leading-5 text-slate-500;
}

.field-error {
  @apply mt-1 text-xs leading-5 text-rose-600;
}

.form-section {
  @apply space-y-3;
}

.section-heading h4 {
  @apply text-sm font-semibold text-slate-900;
}

.section-heading p {
  @apply mt-0.5 text-xs leading-5 text-slate-500;
}

.icon-mark {
  @apply inline-block h-3.5 w-3.5 shrink-0 rounded-sm bg-current;
}

.btn-primary {
  @apply inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60;
}

.btn-secondary {
  @apply inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60;
}

.status-inline {
  @apply inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2;
}

.status-inline.active {
  @apply border-emerald-100 bg-emerald-50;
}

.status-switch {
  @apply inline-flex h-5 w-9 items-center rounded-full bg-slate-300 p-0.5 transition;
}

.status-inline.active .status-switch {
  @apply bg-emerald-500;
}

.status-switch-dot {
  @apply h-4 w-4 rounded-full bg-white shadow transition;
}

.status-inline.active .status-switch-dot {
  transform: translateX(1rem);
}
</style>
