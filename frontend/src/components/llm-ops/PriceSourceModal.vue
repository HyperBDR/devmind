<template>
  <div
    v-if="open"
    class="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/30 px-4 py-6"
    @click.self="close"
  >
    <form
      class="max-h-[calc(100vh-3rem)] w-full max-w-2xl overflow-hidden rounded-xl bg-white shadow-2xl"
      @submit.prevent="save"
    >
      <div class="border-b border-slate-200 px-5 py-4">
        <div class="flex items-start justify-between gap-4">
          <div>
            <p
              class="text-xs font-semibold uppercase tracking-[0.18em] text-indigo-600"
            >
              Price Source
            </p>
            <h3 class="mt-2 text-lg font-semibold text-slate-900">
              {{
                isEditing
                  ? t('llmOps.priceSourceModal.title.edit')
                  : t('llmOps.priceSourceModal.title.create')
              }}
            </h3>
            <p class="mt-1 text-sm text-slate-500">
              {{
                isEditing
                  ? t('llmOps.priceSourceModal.description.edit')
                  : t('llmOps.priceSourceModal.description.create')
              }}
            </p>
          </div>
          <button
            type="button"
            class="btn-secondary btn-action-cancel"
            :disabled="saving"
            @click="close"
          >
            {{ t('llmOps.priceSourceModal.actions.close') }}
          </button>
        </div>
      </div>

      <div
        class="max-h-[calc(100vh-15rem)] space-y-5 overflow-y-auto px-5 py-5"
      >
        <section class="form-section">
          <div class="section-heading">
            <h4>{{ t('llmOps.priceSourceModal.sections.basic') }}</h4>
            <p>{{ t('llmOps.priceSourceModal.sections.basicHint') }}</p>
          </div>
          <div class="grid gap-4 md:grid-cols-2">
            <label class="field-group">
              <span class="field-label">
                {{ t('llmOps.priceSourceModal.fields.name') }}
              </span>
              <input
                v-model="form.name"
                class="field"
                :placeholder="t('llmOps.priceSourceModal.placeholders.name')"
                required
              />
            </label>
            <label class="field-group">
              <span class="field-label">
                {{ t('llmOps.priceSourceModal.fields.slug') }}
              </span>
              <input
                v-model="form.slug"
                class="field font-mono"
                :disabled="!canEditSlug"
                maxlength="100"
                :placeholder="sourceSlugLabel"
                @blur="normalizeSlugField"
              />
              <span class="field-help">
                {{ slugHelpText }}
              </span>
            </label>
            <label class="field-group">
              <span class="field-label">
                {{ t('llmOps.priceSourceModal.fields.sourceOwnerType') }}
              </span>
              <CompactSelect
                v-model="sourceOwnerTypeSelection"
                :options="sourceOwnerTypeOptions"
              />
            </label>
            <label class="field-group">
              <span class="field-label">
                {{ t('llmOps.priceSourceModal.fields.collectionMethod') }}
              </span>
              <CompactSelect
                v-model="form.collection_method"
                :options="collectionMethodOptions"
              />
            </label>
            <label
              class="field-group"
            >
              <span class="field-label">
                {{ t('llmOps.priceSourceModal.fields.officialProvider') }}
              </span>
              <CompactSelect
                v-model="selectedOfficialProviderCode"
                :disabled="
                  !shouldUseOfficialPreset ||
                  loadingOfficialProviderOptions ||
                  saving
                "
                :options="officialProviderSelectOptions"
                class-name="w-full"
                :menu-min-width="360"
                :placeholder="
                  t('llmOps.priceSourceModal.officialPreset.selectProvider')
                "
              />
              <span class="field-help">
                {{ officialProviderHelpText }}
              </span>
            </label>
            <label class="field-group">
              <span class="field-label">
                {{ t('llmOps.priceSourceModal.fields.currency') }}
              </span>
              <CompactSelect
                v-model="form.currency"
                :options="currencyOptions"
              />
            </label>
            <label class="field-group md:col-span-2">
              <span class="field-label">
                {{ t('llmOps.priceSourceModal.fields.endpointUrl') }}
              </span>
              <input
                v-model="form.endpoint_url"
                class="field"
                placeholder="https://example.com/pricing"
                type="url"
              />
              <span class="field-help">
                {{ t('llmOps.priceSourceModal.help.endpointUrl') }}
              </span>
            </label>
          </div>
        </section>

        <section class="form-section">
          <div class="section-heading">
            <h4>{{ t('llmOps.priceSourceModal.sections.notes') }}</h4>
            <p>{{ t('llmOps.priceSourceModal.sections.notesHint') }}</p>
          </div>
          <textarea
            v-model="form.notes"
            class="field min-h-20 resize-none"
            :placeholder="t('llmOps.priceSourceModal.placeholders.notes')"
          />
        </section>
      </div>

      <div class="modal-footer">
        <label
          class="modal-footer-status status-inline"
          :class="{ active: form.is_enabled }"
        >
          <input v-model="form.is_enabled" type="checkbox" class="sr-only" />
          <span class="status-switch" aria-hidden="true">
            <span class="status-switch-dot" />
          </span>
          <span class="text-sm text-slate-700">
            {{
              form.is_enabled
                ? t('llmOps.priceSourceModal.status.enabled')
                : t('llmOps.priceSourceModal.status.disabled')
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
            {{ t('llmOps.priceSourceModal.actions.cancel') }}
          </button>
          <button
            class="btn-primary btn-action-save"
            type="submit"
            :disabled="saving || saveDisabled"
          >
            <span class="icon-mark" />
            {{
              saving
                ? t('llmOps.priceSourceModal.actions.saving')
                : isEditing
                  ? t('llmOps.priceSourceModal.actions.saveChanges')
                  : t('llmOps.priceSourceModal.actions.create')
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

const props = defineProps({
  open: {
    type: Boolean,
    default: false
  },
  source: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['close', 'saved'])
const { showSuccess, showError } = useToast()
const { t } = useI18n()

const saving = ref(false)
const form = ref(defaults())
const officialProviderOptions = ref([])
const selectedOfficialProviderCode = ref('')
const loadingOfficialProviderOptions = ref(false)
const officialSourceOwnerTypes = [
  'model_provider_official',
  'cloud_provider_official'
]
const visibleSourceOwnerTypes = ['supplier', 'internal']
const sourceOwnerOfficialOption = 'official'
const isEditing = computed(() => Boolean(props.source?.id))
const shouldUseOfficialPreset = computed(
  () =>
    !isEditing.value &&
    officialSourceOwnerTypes.includes(form.value.source_owner_type)
)
const canEditSlug = computed(
  () => !shouldUseOfficialPreset.value && !isStableOfficialSource.value
)
const isStableOfficialSource = computed(() => {
  if (!isEditing.value) return false
  const source = props.source || {}
  const providerCode = String(source.provider_code || '').trim()
  if (!providerCode) return false
  return (
    source.source_category === 'official_provider' &&
    String(source.slug || '') === `${providerCode}-official`
  )
})
const slugHelpText = computed(() => {
  if (shouldUseOfficialPreset.value && !selectedOfficialProviderOption.value) {
    return t('llmOps.priceSourceModal.help.officialSlugPreset')
  }
  if (isStableOfficialSource.value) {
    return t('llmOps.priceSourceModal.help.officialSlugLocked')
  }
  if (shouldUseOfficialPreset.value) {
    return t('llmOps.priceSourceModal.help.officialSlugLocked')
  }
  if (isEditing.value) {
    return t('llmOps.priceSourceModal.help.slug')
  }
  return t('llmOps.priceSourceModal.help.autoSlug', {
    slug: sourceSlugLabel.value
  })
})
const sourceSlugLabel = computed(() => {
  if (shouldUseOfficialPreset.value && selectedOfficialProviderOption.value) {
    return selectedOfficialProviderOption.value.source_slug || '-'
  }
  return autoSlug(form.value.name || '')
})
const sourceOwnerTypeOptions = computed(() => [
  {
    label: t('llmOps.priceSourceModal.sourceOwnerTypes.official'),
    value: sourceOwnerOfficialOption
  },
  {
    label: t('llmOps.priceSourceModal.sourceOwnerTypes.supplier'),
    value: 'supplier'
  },
  {
    label: t('llmOps.priceSourceModal.sourceOwnerTypes.internal'),
    value: 'internal'
  }
])

const sourceOwnerTypeSelection = computed({
  get() {
    if (officialSourceOwnerTypes.includes(form.value.source_owner_type)) {
      return sourceOwnerOfficialOption
    }
    if (visibleSourceOwnerTypes.includes(form.value.source_owner_type)) {
      return form.value.source_owner_type
    }
    return 'internal'
  },
  set(value) {
    if (value === sourceOwnerOfficialOption) {
      selectedOfficialProviderCode.value = ''
      form.value.source_owner_type = sourceOwnerTypeForOfficialProvider(
        { provider_code: selectedOfficialProviderCode.value }
      )
      form.value.collection_method = 'auto_collect'
      return
    }
    selectedOfficialProviderCode.value = ''
    form.value.source_owner_type = value
    if (['supplier', 'internal'].includes(value)) {
      form.value.collection_method = 'manual_entry'
    }
  }
})

const collectionMethodOptions = computed(() => [
  {
    label: t('llmOps.priceSourceModal.collectionMethods.autoCollect'),
    value: 'auto_collect'
  },
  {
    label: t('llmOps.priceSourceModal.collectionMethods.manualEntry'),
    value: 'manual_entry'
  },
  {
    label: t('llmOps.priceSourceModal.collectionMethods.manualImport'),
    value: 'manual_import'
  },
  {
    label: t('llmOps.priceSourceModal.collectionMethods.apiSync'),
    value: 'api_sync'
  },
  {
    label: t('llmOps.priceSourceModal.collectionMethods.unknown'),
    value: 'unknown'
  }
])

const currencyOptions = computed(() => [
  { label: t('llmOps.priceSourceModal.currencies.cny'), value: 'CNY' },
  { label: t('llmOps.priceSourceModal.currencies.usd'), value: 'USD' }
])

const officialProviderSelectOptions = computed(() =>
  officialProviderOptions.value.map((option) => ({
    value: option.provider_code,
    label: option.provider_name,
    description: option.source_name,
    badge: option.source_exists
      ? t('llmOps.priceSourceModal.officialPreset.existsBadge')
      : option.currency
  }))
)

const selectedOfficialProviderOption = computed(() =>
  officialProviderOptions.value.find(
    (option) =>
      String(option.provider_code) ===
      String(selectedOfficialProviderCode.value)
  )
)

const officialProviderStatus = computed(() => {
  if (loadingOfficialProviderOptions.value) {
    return t('llmOps.priceSourceModal.officialPreset.loading')
  }
  const option = selectedOfficialProviderOption.value
  if (!option && officialProviderOptions.value.length) {
    return t('llmOps.priceSourceModal.officialPreset.selectProvider')
  }
  if (!option) return t('llmOps.priceSourceModal.officialPreset.empty')
  if (option.source_exists) {
    return t('llmOps.priceSourceModal.officialPreset.exists')
  }
  return t('llmOps.priceSourceModal.officialPreset.ready')
})

const officialProviderHelpText = computed(() => {
  if (!shouldUseOfficialPreset.value) {
    return t('llmOps.priceSourceModal.officialPreset.onlyOfficial')
  }
  return officialProviderStatus.value
})

const saveDisabled = computed(
  () =>
    shouldUseOfficialPreset.value &&
    (!selectedOfficialProviderOption.value ||
      selectedOfficialProviderOption.value.source_exists)
)

watch(
  () => props.source,
  (source) => {
    form.value = source ? normalizeSource(source) : defaults()
  },
  { immediate: true }
)

watch(
  () => [props.open, form.value.source_owner_type, isEditing.value],
  ([open]) => {
    if (open && shouldUseOfficialPreset.value) {
      loadOfficialProviderOptions()
    }
  }
)

watch(selectedOfficialProviderOption, (option) => {
  if (!shouldUseOfficialPreset.value || !option) return
  applyOfficialProviderOption(option)
})

function defaults() {
  return {
    name: '',
    slug: '',
    source_owner_type: 'model_provider_official',
    collection_method: 'auto_collect',
    endpoint_url: '',
    currency: 'CNY',
    is_enabled: true,
    updates_model_prices: false,
    notes: ''
  }
}

function normalizeSource(source) {
  return {
    name: source.name || '',
    slug: source.slug || '',
    source_owner_type:
      source.source_owner_type ||
      sourceOwnerTypeFromLegacyCategory(source.source_category),
    collection_method: source.collection_method || 'unknown',
    endpoint_url: source.endpoint_url || '',
    currency: source.currency || 'CNY',
    is_enabled: source.is_enabled !== false,
    updates_model_prices: Boolean(source.updates_model_prices),
    notes: source.notes || ''
  }
}

function close() {
  if (saving.value) return
  emit('close')
}

async function save() {
  saving.value = true
  try {
    if (shouldUseOfficialPreset.value) {
      await saveOfficialProviderSource()
      return
    }
    const submittedSlug = canEditSlug.value
      ? normalizeSlug(form.value.slug) || autoSlug(form.value.name)
      : props.source?.slug || form.value.slug || autoSlug(form.value.name)
    const payload = {
      ...form.value,
      slug: submittedSlug,
      source_type: props.source?.source_type || 'custom'
    }
    payload.source_category = legacyCategoryForSourceOwnerType(
      payload.source_owner_type
    )
    if (isEditing.value) {
      await llmOpsApi.updateCollectionSource(props.source.id, payload)
      showSuccess(t('llmOps.priceSourceModal.messages.updated'))
    } else {
      await llmOpsApi.createCollectionSource(payload)
      showSuccess(t('llmOps.priceSourceModal.messages.created'))
    }
    emit('saved')
  } catch (error) {
    showError(errorMessage(error, t('llmOps.priceSourceModal.errors.save')))
  } finally {
    saving.value = false
  }
}

async function saveOfficialProviderSource() {
  const option = selectedOfficialProviderOption.value
  if (!option || option.source_exists) return

  const response = await llmOpsApi.ensureOfficialProviderSource(
    option.provider_code
  )
  const payload = response?.data?.data || response?.data || {}
  const sourceName = payload.source?.name || option.source_name
  showSuccess(
    t('llmOps.priceSourceModal.messages.officialCreated', {
      name: sourceName
    })
  )
  emit('saved')
}

async function loadOfficialProviderOptions() {
  if (loadingOfficialProviderOptions.value) return
  loadingOfficialProviderOptions.value = true
  try {
    const response = await llmOpsApi.listOfficialProviderSourceOptions()
    const payload = response?.data?.data || response?.data || {}
    const options = Array.isArray(payload.results) ? payload.results : []
    officialProviderOptions.value = options
    const current = options.find(
      (option) =>
        String(option.provider_code) ===
        String(selectedOfficialProviderCode.value)
    )
    selectedOfficialProviderCode.value = current?.provider_code || ''
    if (current) applyOfficialProviderOption(current)
  } catch (error) {
    showError(
      errorMessage(
        error,
        t('llmOps.priceSourceModal.errors.loadOfficialSources')
      )
    )
  } finally {
    loadingOfficialProviderOptions.value = false
  }
}

function applyOfficialProviderOption(option) {
  form.value = {
    ...form.value,
    source_owner_type: sourceOwnerTypeForOfficialProvider(option),
    collection_method: 'auto_collect',
    name: option.source_name || option.provider_name || form.value.name,
    slug: option.source_slug || form.value.slug,
    currency: option.currency || form.value.currency,
    endpoint_url: option.source_url || form.value.endpoint_url,
    updates_model_prices: true
  }
}

function legacyCategoryForSourceOwnerType(value) {
  if (officialSourceOwnerTypes.includes(value)) {
    return 'official_provider'
  }
  if (value === 'supplier') return 'supplier'
  if (value === 'internal') return 'manual'
  return 'unknown'
}

function sourceOwnerTypeFromLegacyCategory(value) {
  if (value === 'official_provider') return 'model_provider_official'
  if (value === 'supplier') return 'supplier'
  if (value === 'manual') return 'internal'
  return 'unknown'
}

function sourceOwnerTypeForOfficialProvider(option) {
  const code = String(option?.provider_code || '').toLowerCase()
  if (['aliyun', 'aliyun-wanx', 'baidu', 'volcengine'].includes(code)) {
    return 'cloud_provider_official'
  }
  return 'model_provider_official'
}

function errorMessage(error, fallback) {
  return (
    error?.response?.data?.detail ||
    error?.response?.data?.message ||
    error?.message ||
    fallback
  )
}

function normalizeSlugField() {
  if (!canEditSlug.value) return
  form.value.slug = normalizeSlug(form.value.slug)
}

function autoSlug(value) {
  return normalizeSlug(value) || 'price-source'
}

function normalizeSlug(value) {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}
</script>

<style scoped>
.form-section {
  @apply rounded-lg border border-slate-200 bg-slate-50 p-4;
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

.field-group {
  @apply flex min-w-0 flex-col gap-1.5;
}

.field-label {
  @apply text-xs font-medium text-slate-500;
}

.field-help {
  @apply text-xs leading-5 text-slate-400;
}

.field {
  @apply h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-indigo-300 focus:ring-2 focus:ring-indigo-100 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-500;
}

.status-inline {
  @apply inline-flex items-center gap-2;
}

.status-switch {
  @apply flex h-5 w-9 items-center rounded-full bg-slate-300 p-0.5 transition;
}

.status-inline.active .status-switch {
  @apply bg-emerald-500;
}

.status-switch-dot {
  @apply h-4 w-4 rounded-full bg-white shadow transition;
}

.status-inline.active .status-switch-dot {
  @apply translate-x-4;
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
</style>
