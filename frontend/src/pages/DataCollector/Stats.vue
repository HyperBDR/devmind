<template>
  <AppLayout>
    <div class="w-full max-w-full p-6">
      <div class="mb-4 flex items-center justify-between">
        <div>
          <h1 class="text-lg font-semibold text-gray-900">
            {{ t('dataCollector.stats.title') }}
          </h1>
          <p class="mt-1 text-sm text-gray-500">
            {{ t('dataCollector.stats.subtitle') }}
          </p>
        </div>
        <BaseButton
          variant="outline"
          size="sm"
          :loading="loading"
          @click="loadStats"
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
        <div class="p-6">
          <BaseLoading v-if="loading && !stats" />
          <div v-else-if="stats" class="space-y-6">
            <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div class="rounded-lg border border-gray-200 bg-gray-50 p-4">
                <p class="text-sm font-medium text-gray-500">
                  {{ t('dataCollector.stats.totalRecords') || '总记录数' }}
                </p>
                <p class="mt-1 text-2xl font-semibold text-gray-900">
                  {{ stats.total }}
                </p>
              </div>
              <div class="rounded-lg border border-gray-200 bg-gray-50 p-4">
                <p class="text-sm font-medium text-gray-500">
                  {{ t('dataCollector.stats.deletedRecords') || '已删除' }}
                </p>
                <p class="mt-1 text-2xl font-semibold text-gray-900">
                  {{ stats.deleted }}
                </p>
              </div>
              <div class="rounded-lg border border-gray-200 bg-gray-50 p-4">
                <p class="text-sm font-medium text-gray-500">
                  {{ t('dataCollector.stats.platforms') || '平台数' }}
                </p>
                <p class="mt-1 text-2xl font-semibold text-gray-900">
                  {{ (stats.by_platform || []).length }}
                </p>
              </div>
            </div>
            <div v-if="(stats.by_platform || []).length > 0">
              <h2 class="text-sm font-semibold text-gray-700 mb-3">
                {{ t('dataCollector.stats.byPlatform') || '按平台' }}
              </h2>
              <div class="overflow-x-auto">
                <table class="min-w-full divide-y divide-gray-200">
                  <thead class="bg-gray-50">
                    <tr>
                      <th
                        scope="col"
                        class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase"
                      >
                        {{ t('dataCollector.stats.platform') || '平台' }}
                      </th>
                      <th
                        scope="col"
                        class="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase"
                      >
                        {{ t('dataCollector.stats.count') || '数量' }}
                      </th>
                    </tr>
                  </thead>
                  <tbody class="bg-white divide-y divide-gray-200">
                    <tr v-for="row in stats.by_platform" :key="row.platform">
                      <td class="px-4 py-2 text-sm text-gray-900">
                        {{ getPlatformLabel(row.platform) }}
                      </td>
                      <td class="px-4 py-2 text-sm text-gray-900 text-right">
                        {{ row.count }}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
            <div v-else class="py-8 text-center text-sm text-gray-500">
              {{ t('common.noData') }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </AppLayout>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import AppLayout from '@/components/layout/AppLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseLoading from '@/components/ui/BaseLoading.vue'
import { dataCollectorApi } from '@/api/dataCollector'

const { t } = useI18n()
const loading = ref(false)
const stats = ref(null)
const platformLabels = {
  jira: 'Jira'
}

function getPlatformLabel(platform) {
  if (!platform) return ''
  if (platform === 'feishu') return t('dataCollector.platforms.feishu')
  if (platform === 'license') return t('dataCollector.platforms.license')
  if (platform === 'hyperbdr') return t('dataCollector.platforms.hyperbdr')
  if (platform === 'ai_pricehub')
    return t('dataCollector.platforms.ai_pricehub')
  return platformLabels[platform] || platform
}

function extractData(res) {
  return res?.data?.data ?? res?.data ?? res
}

async function loadStats() {
  loading.value = true
  try {
    const res = await dataCollectorApi.getStats()
    stats.value = extractData(res)
  } catch (e) {
    stats.value = null
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadStats()
})
</script>
