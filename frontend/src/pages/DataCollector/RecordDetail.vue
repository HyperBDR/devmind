<template>
  <AppLayout>
    <div class="w-full max-w-full p-6">
      <div class="mb-4 flex items-center gap-3">
        <router-link
          :to="{ name: 'DataCollectorRecords' }"
          class="text-gray-500 hover:text-gray-700 flex items-center gap-1 text-sm"
        >
          <svg
            class="w-4 h-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M15 19l-7-7 7-7"
            />
          </svg>
          {{ t('dataCollector.records.backToList') }}
        </router-link>
      </div>

      <BaseLoading v-if="loading && !record" />
      <div v-else-if="!record" class="py-12 text-center text-sm text-gray-500">
        {{ t('dataCollector.records.recordNotFound') }}
      </div>
      <template v-else>
        <div class="mb-6">
          <h1 class="text-lg font-semibold text-gray-900">
            {{ t('dataCollector.records.detailTitle') }}
          </h1>
          <p class="mt-1 text-sm text-gray-500">
            {{ record.source_unique_id }} · {{ record.platform }}
          </p>
        </div>

        <div class="space-y-6">
          <section
            class="bg-white rounded border border-gray-200 shadow-sm overflow-hidden"
          >
            <h2
              class="px-4 py-3 bg-gray-50 border-b border-gray-200 text-sm font-semibold text-gray-700"
            >
              {{ t('dataCollector.records.basicInfo') }}
            </h2>
            <dl class="px-4 py-4 grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
              <div>
                <dt class="text-gray-500">
                  {{ t('dataCollector.records.platform') }}
                </dt>
                <dd class="font-medium text-gray-900">{{ record.platform }}</dd>
              </div>
              <div>
                <dt class="text-gray-500">
                  {{
                    record.platform === 'feishu'
                      ? t('dataCollector.records.approvalInstanceCode')
                      : t('dataCollector.records.sourceId')
                  }}
                </dt>
                <dd class="font-medium text-gray-900">
                  {{ record.source_unique_id }}
                </dd>
              </div>
              <div v-if="record.platform === 'license'" class="sm:col-span-2">
                <dt class="text-gray-500">
                  {{ t('dataCollector.records.resourceType') }}
                </dt>
                <dd class="font-medium text-gray-900">
                  {{ t('dataCollector.records.order') }}
                </dd>
              </div>
              <div v-else class="sm:col-span-2">
                <dt class="text-gray-500">
                  {{
                    record.platform === 'feishu'
                      ? t('dataCollector.records.approvalName')
                      : t('dataCollector.records.title')
                  }}
                </dt>
                <dd class="font-medium text-gray-900">
                  {{
                    record.platform === 'feishu'
                      ? (record.filter_metadata?.approval_name ?? displayTitle)
                      : displayTitle
                  }}
                </dd>
              </div>
              <div>
                <dt class="text-gray-500">
                  {{ t('dataCollector.records.lastCollected') }}
                </dt>
                <dd class="text-gray-900">
                  {{ formatDate(record.last_collected_at) }}
                </dd>
              </div>
              <div>
                <dt class="text-gray-500">
                  {{ t('dataCollector.records.deleted') }}
                </dt>
                <dd
                  :class="record.is_deleted ? 'text-red-600' : 'text-gray-900'"
                >
                  {{ record.is_deleted ? t('common.yes') : t('common.no') }}
                </dd>
              </div>
            </dl>
          </section>

          <section
            v-if="
              record.filter_metadata &&
              Object.keys(record.filter_metadata).length
            "
            class="bg-white rounded border border-gray-200 shadow-sm overflow-hidden"
          >
            <h2
              class="px-4 py-3 bg-gray-50 border-b border-gray-200 text-sm font-semibold text-gray-700"
            >
              {{ t('dataCollector.records.filterMetadata') }}
            </h2>
            <div class="px-4 py-4 flex flex-wrap gap-2">
              <span
                v-for="(val, key) in record.filter_metadata"
                :key="key"
                class="inline-flex items-center rounded-md bg-gray-100 px-2.5 py-1 text-sm font-medium text-gray-700"
              >
                {{ key }}: {{ val }}
              </span>
            </div>
          </section>

          <section
            v-if="record.platform === 'jira' && jiraKeyFields"
            class="bg-white rounded border border-gray-200 shadow-sm overflow-hidden"
          >
            <h2
              class="px-4 py-3 bg-gray-50 border-b border-gray-200 text-sm font-semibold text-gray-700"
            >
              {{ t('dataCollector.records.jiraKeyFields') }}
            </h2>
            <dl class="px-4 py-4 grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
              <div v-for="(v, k) in jiraKeyFields" :key="k">
                <dt class="text-gray-500">{{ k }}</dt>
                <dd class="text-gray-900 break-words">{{ v }}</dd>
              </div>
            </dl>
          </section>

          <section
            v-if="record.platform !== 'license' && commentsList.length"
            class="bg-white rounded border border-gray-200 shadow-sm overflow-hidden"
          >
            <h2
              class="px-4 py-3 bg-gray-50 border-b border-gray-200 text-sm font-semibold text-gray-700"
            >
              {{ t('dataCollector.records.comments') }} ({{
                commentsList.length
              }})
            </h2>
            <ul class="px-4 py-4 space-y-4">
              <li
                v-for="(c, idx) in commentsList"
                :key="c.id || idx"
                class="border border-gray-200 rounded-lg p-4 bg-gray-50"
              >
                <div class="flex items-center gap-2 text-xs text-gray-500 mb-2">
                  <span
                    >{{ t('dataCollector.records.commentAuthor') }}:
                    {{ commentAuthor(c) }}</span
                  >
                  <span v-if="c.created">
                    · {{ t('dataCollector.records.commentCreated') }}:
                    {{ formatDate(c.created) }}</span
                  >
                </div>
                <div
                  class="text-sm text-gray-900 whitespace-pre-wrap break-words"
                >
                  {{ commentBodyText(c) }}
                </div>
              </li>
            </ul>
          </section>

          <section
            class="bg-white rounded border border-gray-200 shadow-sm overflow-hidden"
          >
            <button
              type="button"
              class="w-full px-4 py-3 flex items-center justify-between bg-gray-50 border-b border-gray-200 text-left text-sm font-semibold text-gray-700 hover:bg-gray-100"
              @click="showRawData = !showRawData"
            >
              {{ t('dataCollector.records.rawData') }}
              <svg
                class="w-4 h-4 transition-transform"
                :class="{ 'rotate-180': showRawData }"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M19 9l-7 7-7-7"
                />
              </svg>
            </button>
            <div v-show="showRawData" class="p-4 overflow-x-auto">
              <pre
                class="text-xs text-gray-700 bg-gray-50 p-4 rounded border border-gray-200 whitespace-pre-wrap break-words"
                >{{ rawDataJson }}</pre
              >
            </div>
          </section>

          <section
            v-if="record.platform !== 'license' && effectiveAttachments.length"
            class="bg-white rounded border border-gray-200 shadow-sm overflow-hidden"
          >
            <h2
              class="px-4 py-3 bg-gray-50 border-b border-gray-200 text-sm font-semibold text-gray-700"
            >
              {{ t('dataCollector.records.attachments') }} ({{
                effectiveAttachments.length
              }})
            </h2>
            <ul class="px-4 py-4 divide-y divide-gray-200">
              <li
                v-for="(att, idx) in effectiveAttachments"
                :key="att.uuid || att.id || idx"
                class="py-2 flex items-center justify-between"
              >
                <span class="text-sm text-gray-900 truncate mr-2">{{
                  att.file_name
                }}</span>
                <a
                  v-if="att.file_url"
                  :href="att.file_url"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="text-primary-600 hover:text-primary-900 text-sm font-medium shrink-0"
                >
                  {{ t('dataCollector.records.download') }}
                </a>
              </li>
            </ul>
          </section>
        </div>
      </template>
    </div>
  </AppLayout>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppLayout from '@/components/layout/AppLayout.vue'
import BaseLoading from '@/components/ui/BaseLoading.vue'
import { dataCollectorApi } from '@/api/dataCollector'
import { extractResponseData } from '@/utils/api'

const route = useRoute()
const { t } = useI18n()
const loading = ref(true)
const record = ref(null)
const showRawData = ref(false)

const displayTitle = computed(() => {
  if (!record.value) return ''
  if (record.value.raw_data?.issue?.fields?.summary)
    return record.value.raw_data.issue.fields.summary
  return record.value.source_unique_id || '—'
})

const jiraKeyFields = computed(() => {
  if (!record.value?.raw_data?.issue?.fields) return null
  const f = record.value.raw_data.issue.fields
  const status = f.status?.name ?? f.status
  const created = f.created ?? ''
  const updated = f.updated ?? ''
  const issuetype = f.issuetype?.name ?? f.issuetype
  const project = f.project?.key ?? f.project?.name ?? f.project
  return {
    [t('dataCollector.records.summary')]: f.summary ?? '—',
    [t('dataCollector.records.status')]: status ?? '—',
    [t('dataCollector.records.issuetype')]: issuetype ?? '—',
    [t('dataCollector.records.project')]: project ?? '—',
    [t('dataCollector.records.sourceCreated')]: created,
    [t('dataCollector.records.sourceUpdated')]: updated
  }
})

const rawDataJson = computed(() => {
  if (!record.value?.raw_data) return '{}'
  try {
    return JSON.stringify(record.value.raw_data, null, 2)
  } catch {
    return String(record.value.raw_data)
  }
})

const commentsList = computed(() => {
  const list = record.value?.raw_data?.comments
  return Array.isArray(list) ? list : []
})

function commentAuthor(c) {
  if (!c) return '—'
  const a = c.author
  if (typeof a === 'string') return a
  if (a?.displayName) return a.displayName
  if (a?.name) return a.name
  return '—'
}

function commentBodyText(c) {
  if (!c) return ''
  const b = c.body
  if (typeof b === 'string') return b
  if (b?.content && Array.isArray(b.content)) {
    return b.content.map((n) => (n?.text != null ? n.text : '')).join('')
  }
  try {
    return typeof b === 'object' ? JSON.stringify(b) : String(b)
  } catch {
    return ''
  }
}

const effectiveAttachments = computed(() => {
  const rec = record.value
  if (!rec) return []
  const fromDb = rec.attachments || []
  if (fromDb.length) {
    return fromDb.map((a) => ({
      uuid: a.uuid,
      file_name: a.file_name,
      file_url: a.file_url
    }))
  }
  const fromRaw = rec.raw_data?.attachments
  if (!Array.isArray(fromRaw)) return []
  return fromRaw.map((a, i) => ({
    id: a.id,
    file_name: a.filename || a.file_name || a.name || `attachment-${i + 1}`,
    file_url: a.content || a.url || a.file_url
  }))
})

function formatDate(s) {
  if (!s) return '—'
  try {
    return new Date(s).toLocaleString()
  } catch {
    return s
  }
}

async function loadRecord() {
  const uuid = route.params.uuid
  if (!uuid) return
  loading.value = true
  try {
    const res = await dataCollectorApi.getRecord(uuid)
    const data = extractResponseData(res)
    record.value = data
  } catch {
    record.value = null
  } finally {
    loading.value = false
  }
}

watch(() => route.params.uuid, loadRecord)
onMounted(loadRecord)
</script>
