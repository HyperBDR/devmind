<template>
  <AppLayout>
    <div class="w-full max-w-full p-6">
      <div class="mb-4 flex items-center justify-between">
        <div>
          <h1 class="text-lg font-semibold text-gray-900">
            {{ t('cloudBilling.alerts.title') }}
          </h1>
          <p class="mt-1 text-sm text-gray-500">
            {{ t('cloudBilling.alerts.subtitle') }}
          </p>
        </div>
      </div>

      <div class="bg-white rounded border border-gray-200 shadow-sm">
        <div class="p-6">
          <!-- Toolbar -->
          <div
            class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6"
          >
            <!-- Batch Actions (Left) -->
            <div class="flex items-center gap-2 flex-wrap"></div>

            <!-- Search and Filter (Right) -->
            <div class="flex items-center gap-3 w-full sm:w-auto">
              <BaseInput
                v-model="searchQuery"
                :placeholder="t('common.search')"
                class="flex-1 sm:w-64"
                @update:modelValue="handleSearch"
              >
                <template #icon>
                  <svg
                    class="w-4 h-4 text-gray-400"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                    />
                  </svg>
                </template>
              </BaseInput>

              <BaseButton
                variant="outline"
                size="sm"
                :loading="loading"
                @click="handleRefresh"
                :title="t('common.refresh')"
                class="flex items-center gap-1 shadow-sm hover:shadow-md transition-shadow"
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
          </div>

          <BaseLoading v-if="loading && alerts.length === 0" />

          <div
            v-if="!loading && alerts.length === 0"
            class="py-16 text-center rounded-lg border border-gray-200 bg-gray-50"
          >
            <svg
              class="mx-auto h-12 w-12 text-gray-400 mb-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
            <p class="text-sm font-medium text-gray-600">
              {{ t('cloudBilling.alerts.noAlerts') }}
            </p>
          </div>

          <!-- Mobile Card View -->
          <div v-if="!loading && alerts.length > 0" class="md:hidden space-y-3">
            <AlertCard
              v-for="alert in alerts"
              :key="alert.id"
              :alert="alert"
              @view="handlePreview"
            />
          </div>

          <!-- Desktop Table View -->
          <div
            v-if="!loading && alerts.length > 0"
            class="hidden md:block overflow-x-auto relative rounded-lg border border-gray-200 bg-white shadow-sm"
          >
            <table class="min-w-full divide-y divide-gray-200">
              <thead class="bg-gradient-to-r from-gray-50 to-gray-100">
                <tr>
                  <th
                    class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                  >
                    {{ t('cloudBilling.alerts.alertTime') }}
                  </th>
                  <th
                    class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                  >
                    {{ t('cloudBilling.alerts.provider') }}
                  </th>
                  <th
                    class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                  >
                    {{ t('cloudBilling.alerts.costInfo') }}
                  </th>
                  <th
                    class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                  >
                    {{ t('cloudBilling.alerts.webhookStatus') }}
                  </th>
                  <th
                    class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                  >
                    {{ t('cloudBilling.alerts.message') }}
                  </th>
                </tr>
              </thead>
              <tbody class="bg-white divide-y divide-gray-100">
                <tr
                  v-for="alert in alerts"
                  :key="alert.id"
                  @click="handlePreview(alert)"
                  class="cursor-pointer transition-colors duration-150 hover:bg-gray-50"
                >
                  <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                    {{ formatDate(alert.created_at) }}
                  </td>
                  <td
                    class="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900"
                  >
                    {{
                      alert.provider_label ||
                      alert.provider_name ||
                      alert.provider
                    }}
                  </td>
                  <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                    <div class="space-y-1">
                      <div class="text-xs">
                        {{ t('cloudBilling.alerts.currentCost') }}:
                        {{ formatCurrency(alert.current_cost, alert.currency) }}
                      </div>
                      <div class="text-xs">
                        {{ t('cloudBilling.alerts.increase') }}:
                        {{
                          formatCurrency(alert.increase_cost, alert.currency)
                        }}
                        ({{ alert.increase_percent }}%)
                      </div>
                    </div>
                  </td>
                  <td class="px-4 py-3 whitespace-nowrap">
                    <span
                      :class="getWebhookStatusClass(alert.webhook_status)"
                      class="px-2 py-1 text-xs font-semibold rounded-full"
                    >
                      {{ getWebhookStatusLabel(alert.webhook_status) }}
                    </span>
                  </td>
                  <td class="px-4 py-3 text-sm text-gray-700">
                    <div class="max-w-md truncate">
                      {{ alert.alert_message }}
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div
            v-if="!loading && totalCount > 0"
            class="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-gray-200 pt-4"
          >
            <p class="text-sm text-gray-600">
              {{ t('common.pagination.showing', paginationShowing) }}
            </p>
            <div class="flex items-center gap-2">
              <label class="text-sm text-gray-600"
                >{{ t('common.pagination.itemsPerPage') }}:</label
              >
              <select
                v-model.number="pageSize"
                class="rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary-500 focus:border-primary-500"
                @change="handlePageSizeChange"
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

      <!-- Alert Detail Panel -->
      <AlertDetailPanel
        :show="showPreviewModal"
        :alert="selectedAlert"
        @close="showPreviewModal = false"
      />
    </div>
  </AppLayout>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { format } from 'date-fns'
import { useDebounce } from '@/composables/useDebounce'
import { extractResponseData } from '@/utils/api'
import { cloudBillingApi } from '@/api/cloudBilling'
import AppLayout from '@/components/layout/AppLayout.vue'
import BaseLoading from '@/components/ui/BaseLoading.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import AlertCard from '@/components/cloud-billing/AlertCard.vue'
import AlertDetailPanel from '@/components/cloud-billing/AlertDetailPanel.vue'

const { t } = useI18n()

const loading = ref(false)
const alerts = ref([])
const searchQuery = ref('')
const showPreviewModal = ref(false)
const selectedAlert = ref(null)
const currentPage = ref(1)
const totalCount = ref(0)
const pageSize = ref(10)

const totalPages = computed(() =>
  totalCount.value > 0 ? Math.ceil(totalCount.value / pageSize.value) : 1
)

const paginationShowing = computed(() => ({
  from:
    totalCount.value === 0 ? 0 : (currentPage.value - 1) * pageSize.value + 1,
  to: Math.min(currentPage.value * pageSize.value, totalCount.value),
  total: totalCount.value
}))

const formatDate = (dateString) => {
  if (!dateString) return '-'
  try {
    return format(new Date(dateString), 'yyyy-MM-dd HH:mm')
  } catch {
    return dateString
  }
}

const formatCurrency = (value, currency = 'CNY') => {
  if (!value && value !== 0) return '-'
  const currencySymbols = {
    CNY: '¥',
    USD: '$',
    EUR: '€'
  }
  const symbol = currencySymbols[currency] || currency
  return `${symbol}${Number(value).toFixed(2)}`
}

const getWebhookStatusClass = (status) => {
  const statusClasses = {
    pending: 'bg-yellow-100 text-yellow-800',
    success: 'bg-green-100 text-green-800',
    failed: 'bg-red-100 text-red-800'
  }
  return statusClasses[status] || 'bg-gray-100 text-gray-800'
}

const getWebhookStatusLabel = (status) => {
  const statusLabels = {
    pending: t('cloudBilling.alerts.webhookStatusLabels.pending'),
    success: t('cloudBilling.alerts.webhookStatusLabels.success'),
    failed: t('cloudBilling.alerts.webhookStatusLabels.failed')
  }
  return statusLabels[status] || status
}

const { debouncedFn: debouncedSearch } = useDebounce((query) => {
  currentPage.value = 1
  loadAlerts(query, 1)
}, 300)

const handleSearch = (query) => {
  searchQuery.value = query
  debouncedSearch(query)
}

const handleRefresh = () => {
  loadAlerts(searchQuery.value, currentPage.value)
}

const goPrevPage = () => {
  if (currentPage.value <= 1) return
  currentPage.value--
  loadAlerts(searchQuery.value, currentPage.value)
}

const goNextPage = () => {
  if (currentPage.value >= totalPages.value) return
  currentPage.value++
  loadAlerts(searchQuery.value, currentPage.value)
}

const handlePageSizeChange = () => {
  currentPage.value = 1
  loadAlerts()
}

const handlePreview = (alert) => {
  selectedAlert.value = alert
  showPreviewModal.value = true
}

const loadAlerts = async (query = '', page = currentPage.value) => {
  loading.value = true
  try {
    const params = {
      page,
      page_size: pageSize.value
    }
    if (query) {
      params.search = query
    }
    const response = await cloudBillingApi.getAlertRecords(params)
    const data = extractResponseData(response)

    const list =
      data?.results ?? data?.list ?? (Array.isArray(data) ? data : [])
    const serverTotal = data?.count ?? data?.pagination?.total
    const hasServerPagination = Number.isFinite(Number(serverTotal))
    const total = hasServerPagination ? Number(serverTotal) : list.length

    totalCount.value = total
    currentPage.value = page
    if (hasServerPagination) {
      alerts.value = list
    } else {
      const start = (page - 1) * pageSize.value
      alerts.value = list.slice(start, start + pageSize.value)
    }
  } catch (error) {
    console.error('Failed to load alerts:', error)
    alerts.value = []
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadAlerts()
})
</script>
