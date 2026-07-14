<template>
  <section
    class="rounded-xl border border-rose-200 bg-rose-50 p-4 text-rose-950"
    role="alert"
  >
    <div class="flex items-start gap-3">
      <div
        class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-rose-100 text-rose-700"
      >
        <svg
          aria-hidden="true"
          class="h-4 w-4"
          fill="none"
          viewBox="0 0 24 24"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            d="M12 8v5m0 3h.01M10.3 3.8 2.4 17.5A2 2 0 0 0 4.1 20h15.8a2 2 0 0 0 1.7-2.5L13.7 3.8a2 2 0 0 0-3.4 0Z"
            stroke="currentColor"
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="1.8"
          />
        </svg>
      </div>
      <div class="min-w-0">
        <p class="text-sm font-bold">{{ t('dataOps.failure.title') }}</p>
        <p class="mt-1 text-sm leading-6 text-rose-800">
          {{ localizedFailureSummary }}
        </p>
      </div>
    </div>

    <details class="mt-4" open>
      <summary
        class="cursor-pointer text-sm font-semibold text-rose-800 marker:text-rose-500"
      >
        {{ t('dataOps.failure.details', { count: failure.items.length }) }}
      </summary>

      <div class="mt-3 space-y-3">
        <article
          v-for="item in failure.items"
          :key="item.key"
          class="rounded-lg border border-rose-200 bg-white p-4"
        >
          <div class="flex flex-wrap items-start justify-between gap-2">
            <div>
              <p class="text-sm font-bold text-slate-900">
                {{ item.key }}
              </p>
              <p class="mt-1 text-sm leading-6 text-slate-700">
                {{ displayMessage(item) }}
              </p>
            </div>
            <span
              v-if="item.issueCode"
              class="rounded-full bg-rose-100 px-2 py-1 text-xs font-semibold text-rose-700"
            >
              {{ issueLabel(item.issueCode) }}
            </span>
          </div>

          <dl class="mt-3 grid gap-2 text-xs sm:grid-cols-2 lg:grid-cols-3">
            <div v-if="item.stage" class="detail-item">
              <dt>{{ t('dataOps.failure.stage') }}</dt>
              <dd>{{ item.stage }}</dd>
            </div>
            <div v-if="item.httpStatus" class="detail-item">
              <dt>{{ t('dataOps.failure.httpStatus') }}</dt>
              <dd>{{ item.httpStatus }}</dd>
            </div>
            <div v-if="item.feishuCode" class="detail-item">
              <dt>{{ t('dataOps.failure.errorCode') }}</dt>
              <dd>{{ item.feishuCode }}</dd>
            </div>
            <div v-if="item.feishuMessage" class="detail-item">
              <dt>{{ t('dataOps.failure.response') }}</dt>
              <dd>{{ item.feishuMessage }}</dd>
            </div>
            <div v-if="item.requestId" class="detail-item">
              <dt>Request ID</dt>
              <dd class="break-all font-mono">{{ item.requestId }}</dd>
            </div>
            <div v-if="item.logId" class="detail-item">
              <dt>{{ t('dataOps.failure.logId') }}</dt>
              <dd class="break-all font-mono">{{ item.logId }}</dd>
            </div>
          </dl>

          <div class="mt-4 rounded-lg bg-slate-50 p-3">
            <p class="text-xs font-bold text-slate-800">
              {{ t('dataOps.failure.suggestions') }}
            </p>
            <ol class="mt-2 space-y-1.5 text-xs leading-5 text-slate-600">
              <li
                v-for="(suggestion, index) in displaySuggestions(item)"
                :key="suggestion"
                class="flex gap-2"
              >
                <span class="font-semibold text-slate-400">
                  {{ index + 1 }}.
                </span>
                <span>{{ suggestion }}</span>
              </li>
            </ol>
          </div>

          <a
            v-if="item.tableUrl"
            class="mt-3 inline-flex text-xs font-semibold text-indigo-700 hover:text-indigo-900"
            :href="item.tableUrl"
            rel="noopener noreferrer"
            target="_blank"
          >
            {{ t('dataOps.failure.openTable') }}
          </a>
        </article>
      </div>
    </details>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { locale, t, te } = useI18n()

const props = defineProps({
  failure: { type: Object, required: true },
})

const localizedFailureSummary = computed(() =>
  locale.value === 'zh-CN'
    ? props.failure.summary
    : t('dataOps.failure.summary', { count: props.failure.items.length })
)

function issueLabel(code) {
  const key = `dataOps.failure.issues.${code}`
  return te(key) ? t(key) : code
}

function displayMessage(item) {
  if (locale.value === 'zh-CN') {
    return item.message || t('dataOps.failure.readFailed')
  }
  return `${issueLabel(item.issueCode || 'unknown')}. ${t(
    'dataOps.failure.readFailed'
  )}`
}

function displaySuggestions(item) {
  if (locale.value === 'zh-CN') return item.suggestions
  const key = `dataOps.failure.recommendations.${item.issueCode || 'unknown'}`
  return [te(key) ? t(key) : t('dataOps.failure.recommendations.unknown'), t('dataOps.failure.retry')]
}
</script>

<style scoped>
.detail-item {
  border-radius: 0.375rem;
  background: rgb(248 250 252);
  padding: 0.5rem 0.75rem;
}

.detail-item dt {
  color: rgb(100 116 139);
}

.detail-item dd {
  margin-top: 0.25rem;
  color: rgb(30 41 59);
  font-weight: 600;
}
</style>
