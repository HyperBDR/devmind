<template>
  <div
    v-if="open"
    class="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 px-4 py-6"
    @click.self="close"
  >
    <div class="modal-panel">
      <div class="modal-header">
        <div>
          <p class="eyebrow">Manual Price Source</p>
          <h3 class="mt-1 text-lg font-semibold text-slate-900">
            {{ t('llmOps.manualPriceImport.title') }}
          </h3>
          <p class="mt-1 text-xs leading-5 text-slate-500">
            {{ t('llmOps.manualPriceImport.description') }}
          </p>
        </div>
        <button
          class="btn-secondary btn-action-cancel"
          type="button"
          @click="close"
        >
          {{ t('llmOps.manualPriceImport.actions.close') }}
        </button>
      </div>

      <div class="modal-body space-y-4">
        <div class="grid gap-3 md:grid-cols-2">
          <label class="form-field">
            <span class="field-label">
              {{ t('llmOps.manualPriceImport.fields.provider') }}
            </span>
            <CompactSelect v-model="form.provider" :options="providerOptions" />
          </label>
          <label class="form-field">
            <span class="field-label">
              {{ t('llmOps.manualPriceImport.fields.currency') }}
            </span>
            <CompactSelect v-model="form.currency" :options="currencyOptions" />
          </label>
          <label class="form-field">
            <span class="field-label">
              {{ t('llmOps.manualPriceImport.fields.sourceName') }}
            </span>
            <input
              v-model="form.source_name"
              class="field"
              :placeholder="
                t('llmOps.manualPriceImport.placeholders.sourceName')
              "
            />
          </label>
          <label class="form-field">
            <span class="field-label">
              {{ t('llmOps.manualPriceImport.fields.sourceUrl') }}
            </span>
            <input
              v-model="form.source_url"
              class="field"
              :placeholder="
                t('llmOps.manualPriceImport.placeholders.sourceUrl')
              "
            />
          </label>
        </div>

        <label class="inline-flex items-start gap-2 text-xs text-slate-600">
          <input
            v-model="form.updates_model_prices"
            class="mt-0.5 h-4 w-4 rounded border-slate-300 text-indigo-600"
            type="checkbox"
          />
          <span>
            {{ t('llmOps.manualPriceImport.updateModelPrices') }}
          </span>
        </label>

        <div class="rounded-lg border border-slate-200 bg-slate-50 p-3">
          <div class="flex flex-col gap-3 xl:flex-row xl:items-start">
            <div class="min-w-0 flex-1">
              <label class="field-label">
                {{ t('llmOps.manualPriceImport.fields.tableContent') }}
              </label>
              <textarea
                v-model="rawTable"
                class="table-input"
                spellcheck="false"
                placeholder="model_code	model_name	modality	currency	input_price_per_million	output_price_per_million"
              />
            </div>
            <div class="example-box">
              <p class="text-xs font-semibold text-slate-700">
                {{ t('llmOps.manualPriceImport.supportedFieldsTitle') }}
              </p>
              <p class="mt-2 text-xs leading-5 text-slate-500">
                model_code、model_name、modality、currency、source_url、
                input_price_per_million、output_price_per_million、
                cache_input_price_per_million、image_output_price_per_image、
                audio_input_price_per_second、audio_output_price_per_second、
                video_input_price_per_second、video_output_price_per_second
              </p>
            </div>
          </div>
        </div>

        <div class="preview-panel">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <div>
              <p class="text-sm font-semibold text-slate-900">
                {{ t('llmOps.manualPriceImport.preview.title') }}
              </p>
              <p class="mt-1 text-xs text-slate-500">
                {{
                  t('llmOps.manualPriceImport.preview.summary', {
                    valid: parsedRows.length,
                    errors: parseErrors.length
                  })
                }}
              </p>
            </div>
            <span :class="parseErrors.length ? 'badge-warn' : 'badge-ok'">
              {{
                parseErrors.length
                  ? t('llmOps.manualPriceImport.preview.needsFix')
                  : t('llmOps.manualPriceImport.preview.ready')
              }}
            </span>
          </div>

          <div v-if="parseErrors.length" class="mt-3 space-y-1">
            <p
              v-for="error in parseErrors.slice(0, 5)"
              :key="error"
              class="text-xs text-amber-700"
            >
              {{ error }}
            </p>
          </div>

          <div class="mt-3 max-h-52 overflow-auto">
            <table class="preview-table">
              <thead>
                <tr>
                  <th>{{ t('llmOps.manualPriceImport.table.model') }}</th>
                  <th>{{ t('llmOps.manualPriceImport.table.type') }}</th>
                  <th>{{ t('llmOps.manualPriceImport.table.currency') }}</th>
                  <th class="text-right">
                    {{ t('llmOps.manualPriceImport.table.input') }}
                  </th>
                  <th class="text-right">
                    {{ t('llmOps.manualPriceImport.table.output') }}
                  </th>
                  <th class="text-right">
                    {{ t('llmOps.manualPriceImport.table.image') }}
                  </th>
                  <th class="text-right">
                    {{ t('llmOps.manualPriceImport.table.audio') }}
                  </th>
                  <th class="text-right">
                    {{ t('llmOps.manualPriceImport.table.video') }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in parsedRows.slice(0, 20)" :key="row.__key">
                  <td>
                    <p class="font-medium text-slate-800">
                      {{ row.model_name || row.model_code }}
                    </p>
                    <p class="font-mono text-[11px] text-slate-400">
                      {{ row.model_code }}
                    </p>
                  </td>
                  <td>{{ modalityLabel(row.modality) }}</td>
                  <td class="font-mono">{{ row.currency || form.currency }}</td>
                  <td class="text-right font-mono">
                    {{ row.input_price_per_million || '-' }}
                  </td>
                  <td class="text-right font-mono">
                    {{ row.output_price_per_million || '-' }}
                  </td>
                  <td class="text-right font-mono">
                    {{ row.image_output_price_per_image || '-' }}
                  </td>
                  <td class="text-right font-mono">
                    {{
                      compactPair(
                        row.audio_input_price_per_second,
                        row.audio_output_price_per_second
                      )
                    }}
                  </td>
                  <td class="text-right font-mono">
                    {{
                      compactPair(
                        row.video_input_price_per_second,
                        row.video_output_price_per_second
                      )
                    }}
                  </td>
                </tr>
                <tr v-if="!parsedRows.length">
                  <td class="py-6 text-center text-slate-400" colspan="8">
                    {{ t('llmOps.manualPriceImport.emptyPreview') }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div class="modal-footer">
        <div class="modal-footer-actions">
          <button
            class="btn-secondary btn-action-cancel"
            type="button"
            @click="close"
          >
            {{ t('llmOps.manualPriceImport.actions.cancel') }}
          </button>
          <button
            class="btn-primary btn-action-import"
            type="button"
            :disabled="saving || !canSubmit"
            @click="submit"
          >
            <span class="icon-mark" :class="saving ? 'animate-spin' : ''" />
            {{
              saving
                ? t('llmOps.manualPriceImport.actions.importing')
                : t('llmOps.manualPriceImport.actions.confirmImport')
            }}
          </button>
        </div>
      </div>
    </div>
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
  providers: {
    type: Array,
    required: true
  }
})

const emit = defineEmits(['close', 'imported'])
const { t } = useI18n()

const rawTable = ref('')
const saving = ref(false)
const form = ref(defaultForm())

const currencyOptions = [
  { label: 'USD', value: 'USD' },
  { label: 'CNY', value: 'CNY' }
]

const providerOptions = computed(() => [
  {
    label: t('llmOps.manualPriceImport.placeholders.selectProvider'),
    value: ''
  },
  ...props.providers
    .slice()
    .sort((left, right) => left.name.localeCompare(right.name))
    .map((provider) => ({
      label: provider.name,
      value: provider.id
    }))
])

const parsed = computed(() => parseTable(rawTable.value))
const parsedRows = computed(() => parsed.value.rows)
const parseErrors = computed(() => parsed.value.errors)
const canSubmit = computed(
  () =>
    form.value.provider &&
    form.value.source_name.trim() &&
    parsedRows.value.length &&
    !parseErrors.value.length
)

watch(
  () => props.open,
  (open) => {
    if (open) {
      form.value = defaultForm()
      rawTable.value = ''
    }
  }
)

function defaultForm() {
  return {
    provider: '',
    source_name: '',
    source_url: '',
    currency: 'USD',
    updates_model_prices: true
  }
}

function close() {
  if (saving.value) return
  emit('close')
}

async function submit() {
  if (!canSubmit.value) return
  saving.value = true
  try {
    await llmOpsApi.importManualPrices({
      ...form.value,
      rows: parsedRows.value.map((row) => cleanRow(row))
    })
    emit('imported')
  } finally {
    saving.value = false
  }
}

function parseTable(value) {
  const text = String(value || '').trim()
  if (!text) return { rows: [], errors: [] }
  const lines = text.split(/\r?\n/).filter((line) => line.trim())
  if (lines.length < 2) {
    return {
      rows: [],
      errors: [t('llmOps.manualPriceImport.parseErrors.needHeaderAndRow')]
    }
  }
  const delimiter = lines[0].includes('\t') ? '\t' : ','
  const headers = splitLine(lines[0], delimiter).map(normalizeHeader)
  const errors = []
  if (!headers.includes('model_code')) {
    errors.push(t('llmOps.manualPriceImport.parseErrors.missingModelCode'))
  }
  const rows = lines.slice(1).map((line, index) => {
    const cells = splitLine(line, delimiter)
    const row = { __key: `${index}-${line}` }
    headers.forEach((header, cellIndex) => {
      if (!header) return
      row[header] = String(cells[cellIndex] || '').trim()
    })
    return normalizeRow(row, index + 2, errors)
  })
  return {
    rows: rows.filter(Boolean),
    errors
  }
}

function splitLine(line, delimiter) {
  if (delimiter === '\t') return line.split('\t')
  const cells = []
  let current = ''
  let quoted = false
  for (const char of line) {
    if (char === '"') {
      quoted = !quoted
      continue
    }
    if (char === ',' && !quoted) {
      cells.push(current)
      current = ''
      continue
    }
    current += char
  }
  cells.push(current)
  return cells
}

function normalizeHeader(header) {
  const aliases = {
    code: 'model_code',
    model: 'model_code',
    '\u6a21\u578b\u7f16\u7801': 'model_code',
    '\u6a21\u578b\u540d\u79f0': 'model_name',
    '\u7c7b\u578b': 'modality',
    '\u5e01\u79cd': 'currency',
    '\u8f93\u5165\u4ef7\u683c': 'input_price_per_million',
    '\u8f93\u51fa\u4ef7\u683c': 'output_price_per_million',
    '\u56fe\u7247\u8f93\u51fa': 'image_output_price_per_image',
    '\u97f3\u9891\u8f93\u5165': 'audio_input_price_per_second',
    '\u97f3\u9891\u8f93\u51fa': 'audio_output_price_per_second',
    '\u89c6\u9891\u8f93\u5165': 'video_input_price_per_second',
    '\u89c6\u9891\u8f93\u51fa': 'video_output_price_per_second',
    '\u6765\u6e90\u5730\u5740': 'source_url'
  }
  const normalized = String(header || '').trim()
  return aliases[normalized] || normalized
}

function normalizeRow(row, lineNumber, errors) {
  if (!row.model_code) {
    errors.push(
      t('llmOps.manualPriceImport.parseErrors.rowMissingModelCode', {
        line: lineNumber
      })
    )
    return null
  }
  const next = {
    ...row,
    modality: normalizeModality(row.modality),
    currency: normalizeCurrency(row.currency)
  }
  const priceFields = [
    'input_price_per_million',
    'output_price_per_million',
    'cache_input_price_per_million',
    'image_output_price_per_image',
    'audio_input_price_per_second',
    'audio_output_price_per_second',
    'video_input_price_per_second',
    'video_output_price_per_second'
  ]
  let hasPrice = false
  priceFields.forEach((field) => {
    if (next[field] === undefined || next[field] === '') {
      delete next[field]
      return
    }
    const value = Number(next[field])
    if (!Number.isFinite(value) || value < 0) {
      errors.push(
        t('llmOps.manualPriceImport.parseErrors.invalidNumber', {
          line: lineNumber,
          field
        })
      )
      return
    }
    next[field] = String(value)
    hasPrice = true
  })
  if (!hasPrice) {
    errors.push(
      t('llmOps.manualPriceImport.parseErrors.noPrice', {
        line: lineNumber
      })
    )
    return null
  }
  if (next.currency && !['USD', 'CNY'].includes(next.currency)) {
    errors.push(
      t('llmOps.manualPriceImport.parseErrors.unsupportedCurrency', {
        line: lineNumber
      })
    )
    return null
  }
  return next
}

function normalizeModality(value) {
  const text = String(value || '')
    .trim()
    .toLowerCase()
  const labels = {
    '\u6587\u672c': 'text',
    text: 'text',
    '\u56fe\u7247': 'multimodal',
    '\u591a\u6a21\u6001': 'multimodal',
    multimodal: 'multimodal',
    '\u97f3\u9891': 'audio',
    audio: 'audio',
    '\u89c6\u9891': 'video',
    video: 'video'
  }
  return labels[text] || 'text'
}

function normalizeCurrency(value) {
  return String(value || '')
    .trim()
    .toUpperCase()
}

function cleanRow(row) {
  const clean = { ...row }
  delete clean.__key
  Object.keys(clean).forEach((key) => {
    if (clean[key] === '') {
      delete clean[key]
    }
  })
  return clean
}

function compactPair(input, output) {
  if (!input && !output) return '-'
  return `${input || '-'} / ${output || '-'}`
}

function modalityLabel(value) {
  const labels = {
    text: t('llmOps.manualPriceImport.modalities.text'),
    multimodal: t('llmOps.manualPriceImport.modalities.multimodal'),
    audio: t('llmOps.manualPriceImport.modalities.audio'),
    video: t('llmOps.manualPriceImport.modalities.video')
  }
  return labels[value] || value || labels.text
}
</script>

<style scoped>
.modal-panel {
  width: min(100%, 980px);
  max-height: min(calc(100vh - 3rem), 860px);
  @apply flex flex-col overflow-hidden rounded-xl bg-white shadow-2xl;
}

.modal-header {
  @apply flex flex-col gap-3 border-b border-slate-200 px-5 py-4 sm:flex-row sm:items-start sm:justify-between;
}

.modal-body {
  @apply overflow-y-auto px-5 py-4;
}

.modal-footer {
  @apply flex justify-end gap-2 border-t border-slate-200 bg-slate-50 px-5 py-4;
}

.eyebrow {
  @apply text-xs font-semibold uppercase tracking-[0.18em] text-indigo-600;
}

.form-field {
  @apply flex min-w-0 flex-col gap-1.5;
}

.field-label {
  @apply text-xs font-medium text-slate-500;
}

.field {
  @apply min-h-9 w-full rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-indigo-300 focus:ring-4 focus:ring-indigo-50;
}

.table-input {
  min-height: 11rem;
  @apply mt-1 w-full resize-y rounded-lg border border-slate-200 bg-white p-3 font-mono text-xs leading-5 text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-indigo-300 focus:ring-4 focus:ring-indigo-50;
}

.example-box {
  @apply rounded-lg border border-slate-200 bg-white p-3 xl:w-72;
}

.preview-panel {
  @apply rounded-lg border border-slate-200 bg-white p-3;
}

.preview-table {
  @apply min-w-full divide-y divide-slate-100 text-xs;
}

.preview-table thead {
  @apply bg-slate-50 text-slate-500;
}

.preview-table th {
  @apply whitespace-nowrap px-3 py-2 text-left font-semibold;
}

.preview-table td {
  @apply whitespace-nowrap px-3 py-2 text-slate-600;
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

.badge-ok {
  @apply rounded-full border border-emerald-100 bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700;
}

.badge-warn {
  @apply rounded-full border border-amber-100 bg-amber-50 px-2 py-1 text-xs font-medium text-amber-700;
}
</style>
