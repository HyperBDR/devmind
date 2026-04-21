<template>
  <AppLayout>
    <div class="w-full max-w-full p-6">
      <div class="mb-4 flex items-center justify-between">
        <div>
          <h1 class="text-lg font-semibold text-gray-900">
            {{ t('dataCollector.records.pageTitle') }}
          </h1>
          <p class="mt-1 text-sm text-gray-500">
            {{ t('dataCollector.records.subtitle') }}
          </p>
        </div>
        <BaseButton
          variant="outline"
          size="sm"
          :loading="loading"
          @click="loadRecords"
          :title="t('common.refresh')"
          class="flex items-center gap-1"
        >
          <svg
            v-if="!loading"
            class="w-4 h-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            />
          </svg>
          <span class="sr-only">{{ t('common.refresh') }}</span>
        </BaseButton>
      </div>

      <div class="bg-white rounded border border-gray-200 shadow-sm">
        <div class="border-b border-gray-200">
          <nav class="flex gap-1 px-6 pt-4" aria-label="Platform tabs">
            <button
              v-for="p in platforms"
              :key="p"
              type="button"
              :class="
                platformFilter === p
                  ? 'border-primary-600 text-primary-600 bg-primary-50'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              "
              class="px-4 py-2.5 text-sm font-medium border-b-2 transition-colors"
              @click="selectPlatform(p)"
            >
              {{ getPlatformLabel(p) }}
            </button>
          </nav>
        </div>
        <div class="p-6">
          <BaseLoading v-if="loading && records.length === 0" />
          <div
            v-else-if="records.length === 0"
            class="py-12 text-center text-sm text-gray-500"
          >
            {{ t('common.noData') }}
          </div>
          <div v-else class="overflow-x-auto relative">
            <div
              v-if="loading"
              class="absolute inset-0 bg-white/70 flex items-center justify-center z-10 rounded"
            >
              <BaseLoading size="lg" variant="primary" />
            </div>
            <table class="min-w-full divide-y divide-gray-200">
              <thead class="bg-gray-50">
                <tr>
                  <th
                    scope="col"
                    class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase"
                  >
                    {{ t('dataCollector.records.platform') }}
                  </th>
                  <th
                    scope="col"
                    class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase"
                  >
                    <span v-if="platformFilter === 'feishu'">
                      {{ t('dataCollector.records.approvalInstanceCode') }}
                    </span>
                    <span v-else>
                      {{ t('dataCollector.records.sourceId') }}
                    </span>
                  </th>
                  <th
                    scope="col"
                    class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase"
                  >
                    <span v-if="platformFilter === 'license'">
                      {{ t('dataCollector.records.resourceType') }}
                    </span>
                    <span v-else-if="platformFilter === 'feishu'">
                      {{ t('dataCollector.records.approvalName') }}
                    </span>
                    <span v-else>
                      {{ t('dataCollector.records.title') }}
                    </span>
                  </th>
                  <th
                    scope="col"
                    class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase"
                  >
                    {{ t('dataCollector.records.filterMetadata') }}
                  </th>
                  <th
                    scope="col"
                    class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase"
                  >
                    {{ t('dataCollector.records.lastCollected') }}
                  </th>
                  <th
                    scope="col"
                    class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase"
                  >
                    {{ t('dataCollector.records.attachmentCount') }}
                  </th>
                  <th
                    scope="col"
                    class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase"
                  >
                    {{ t('dataCollector.records.deleted') }}
                  </th>
                </tr>
              </thead>
              <tbody class="bg-white divide-y divide-gray-200">
                <tr v-for="r in records" :key="r.uuid" class="hover:bg-gray-50">
                  <td class="px-4 py-3 text-sm text-gray-900">
                    {{ getPlatformLabel(r.platform) || '—' }}
                  </td>
                  <td class="px-4 py-3 text-sm font-medium">
                    <button
                      type="button"
                      class="text-primary-600 hover:text-primary-900 hover:underline text-left"
                      @click="openRecordDetail(r.uuid)"
                    >
                      {{ r.source_unique_id || '—' }}
                    </button>
                  </td>
                  <td
                    class="px-4 py-3 text-sm text-gray-700 max-w-[280px] truncate"
                  >
                    <template v-if="r.platform === 'license'">
                      <span
                        class="block truncate text-left w-full text-gray-900"
                      >
                        {{ t('dataCollector.records.order') }}
                      </span>
                    </template>
                    <template v-else-if="r.platform === 'feishu'">
                      <span
                        class="block truncate text-left w-full text-gray-900"
                        :title="r.display_title || r.source_unique_id || ''"
                      >
                        {{ r.display_title || r.source_unique_id || '—' }}
                      </span>
                    </template>
                    <template v-else>
                      <button
                        type="button"
                        class="text-primary-600 hover:text-primary-900 hover:underline block truncate text-left w-full"
                        :title="r.display_title || r.source_unique_id"
                        @click="openRecordDetail(r.uuid)"
                      >
                        {{ r.display_title || r.source_unique_id || '—' }}
                      </button>
                    </template>
                  </td>
                  <td class="px-4 py-3">
                    <span
                      v-for="(val, key) in r.filter_metadata || {}"
                      :key="key"
                      class="inline-flex items-center rounded-md bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-700 mr-1 mb-1"
                    >
                      {{ key }}: {{ val }}
                    </span>
                    <span
                      v-if="
                        !r.filter_metadata ||
                        !Object.keys(r.filter_metadata).length
                      "
                      class="text-gray-400 text-xs"
                      >—</span
                    >
                  </td>
                  <td class="px-4 py-3 text-sm text-gray-500">
                    {{ formatDate(r.last_collected_at) }}
                  </td>
                  <td class="px-4 py-3 text-sm text-gray-700">
                    {{ r.attachment_count ?? 0 }}
                  </td>
                  <td class="px-4 py-3 text-sm">
                    <span
                      :class="r.is_deleted ? 'text-red-600' : 'text-gray-500'"
                    >
                      {{ r.is_deleted ? t('common.yes') : t('common.no') }}
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div
            v-if="totalCount > 0"
            class="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-gray-200 pt-4 text-sm text-gray-600"
          >
            <span>{{
              t('common.pagination.showing', {
                from: (currentPage - 1) * pageSize + 1,
                to: Math.min(currentPage * pageSize, totalCount),
                total: totalCount
              })
            }}</span>
            <div class="flex items-center gap-2">
              <label class="text-gray-600"
                >{{ t('common.pagination.itemsPerPage') }}:</label
              >
              <select
                v-model.number="pageSize"
                class="rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary-500 focus:border-primary-500"
                @change="onPageSizeChange"
              >
                <option :value="10">10</option>
                <option :value="20">20</option>
                <option :value="50">50</option>
                <option :value="100">100</option>
              </select>
              <BaseButton
                variant="outline"
                size="sm"
                :disabled="currentPage <= 1"
                @click="goPrevPage"
              >
                {{ t('common.pagination.previous') }}
              </BaseButton>
              <BaseButton
                variant="outline"
                size="sm"
                :disabled="currentPage >= totalPages"
                @click="goNextPage"
              >
                {{ t('common.pagination.next') }}
              </BaseButton>
            </div>
          </div>
        </div>
      </div>

      <RecordDetailPanel
        :show="showDetailPanel"
        :record-uuid="selectedRecordUuid"
        @close="closeRecordDetail"
      />
    </div>
  </AppLayout>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import AppLayout from '@/components/layout/AppLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseLoading from '@/components/ui/BaseLoading.vue'
import RecordDetailPanel from '@/components/data-collector/RecordDetailPanel.vue'
import { dataCollectorApi } from '@/api/dataCollector'

const { t } = useI18n()
const loading = ref(false)
const records = ref([])
const totalCount = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const platformFilter = ref('')
const platforms = ref([])
const showDetailPanel = ref(false)
const selectedRecordUuid = ref('')

const totalPages = computed(() =>
  Math.max(1, Math.ceil(totalCount.value / pageSize.value))
)

const platformLabels = { jira: 'Jira' }
function getPlatformLabel(platform) {
  if (platform === 'feishu') return t('dataCollector.platforms.feishu')
  if (platform === 'license') return t('dataCollector.platforms.license')
  if (platform === 'hyperbdr') return t('dataCollector.platforms.hyperbdr')
  if (platform === 'ai_pricehub')
    return t('dataCollector.platforms.ai_pricehub')
  return (
    platformLabels[platform] ||
    (platform ? platform.charAt(0).toUpperCase() + platform.slice(1) : platform)
  )
}

function selectPlatform(platform) {
  platformFilter.value = platform
  currentPage.value = 1
  loadRecords()
}

function openRecordDetail(uuid) {
  selectedRecordUuid.value = uuid
  showDetailPanel.value = true
}

function closeRecordDetail() {
  showDetailPanel.value = false
  selectedRecordUuid.value = ''
}

function onPageSizeChange() {
  currentPage.value = 1
  loadRecords()
}

function goPrevPage() {
  if (currentPage.value <= 1) return
  currentPage.value -= 1
  loadRecords()
}

function goNextPage() {
  if (currentPage.value >= totalPages.value) return
  currentPage.value += 1
  loadRecords()
}

function formatDate(s) {
  if (!s) return '-'
  try {
    return new Date(s).toLocaleString()
  } catch {
    return s
  }
}

function extractData(res) {
  return res?.data?.data ?? res?.data ?? res
}

async function loadRecords() {
  loading.value = true
  try {
    const params = { page: currentPage.value, page_size: pageSize.value }
    if (platformFilter.value) params.platform = platformFilter.value
    const res = await dataCollectorApi.getRecords(params)
    const data = extractData(res)
    const list =
      data?.results ?? data?.list ?? (Array.isArray(data) ? data : [])
    const total = data?.count ?? data?.pagination?.total ?? list.length
    records.value = list
    totalCount.value = Number(total) || list.length
  } catch (e) {
    records.value = []
  } finally {
    loading.value = false
  }
}

async function loadPlatforms() {
  try {
    const res = await dataCollectorApi.getStats()
    const data = extractData(res)
    platforms.value = (data?.by_platform || []).map((p) => p.platform)
  } catch {
    platforms.value = []
  }
}

onMounted(async () => {
  await loadPlatforms()
  if (!platformFilter.value && platforms.value.length > 0) {
    platformFilter.value = platforms.value[0]
  }
  await loadRecords()
})
</script>
