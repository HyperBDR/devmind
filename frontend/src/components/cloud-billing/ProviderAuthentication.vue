<template>
  <div class="p-6">
    <!-- Toolbar -->
    <div
      class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6"
    >
      <!-- Batch Actions (Left) -->
      <div class="flex items-center gap-2 flex-wrap"></div>

      <!-- Search and Filter (Right) -->
      <div
        class="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 w-full sm:w-auto"
      >
        <div class="relative w-full sm:w-80">
          <span
            class="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-gray-400"
          >
            <svg
              class="h-4 w-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M21 21l-4.35-4.35m1.85-5.15a7 7 0 11-14 0 7 7 0 0114 0z"
              />
            </svg>
          </span>
          <input
            v-model="searchQuery"
            type="text"
            :placeholder="
              t('cloudBilling.settings.providers.searchPlaceholder')
            "
            class="w-full rounded-lg border border-gray-300 bg-white py-2 pl-9 pr-3 text-sm text-gray-900 shadow-sm transition focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-100"
          />
        </div>
        <BaseButton
          @click="showCreateModal = true"
          size="sm"
          class="flex items-center gap-1.5"
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
              d="M12 4v16m8-8H4"
            />
          </svg>
          {{ t('cloudBilling.settings.providers.addProvider') }}
        </BaseButton>
      </div>
    </div>

    <!-- Loading State -->
    <BaseLoading v-if="loading" size="lg" variant="primary" />

    <!-- Providers Table -->
    <template v-else>
      <div
        v-if="allProviders.length === 0"
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
            d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"
          />
        </svg>
        <p class="text-sm font-medium text-gray-600">
          {{ t('cloudBilling.settings.providers.noProviders') }}
        </p>
      </div>

      <div
        v-else-if="filteredProviders.length === 0"
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
            d="M21 21l-4.35-4.35m1.85-5.15a7 7 0 11-14 0 7 7 0 0114 0z"
          />
        </svg>
        <p class="text-sm font-medium text-gray-600">
          {{ t('cloudBilling.settings.providers.noSearchResults') }}
        </p>
      </div>

      <template v-else>
        <!-- Desktop Table View -->
        <div
          class="hidden md:block overflow-x-auto relative rounded-lg border border-gray-200 bg-white shadow-sm"
        >
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gradient-to-r from-gray-50 to-gray-100">
              <tr>
                <th
                  class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200 w-1/4 min-w-[200px]"
                >
                  {{ t('cloudBilling.providers.displayName') }}
                </th>
                <th
                  class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                >
                  {{ t('cloudBilling.settings.providers.providerType') }}
                </th>
                <th
                  class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200 min-w-[180px]"
                >
                  {{ t('cloudBilling.providers.authIdentifier') }}
                </th>
                <th
                  class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                >
                  {{ t('cloudBilling.providers.status') }}
                </th>
                <th
                  class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                >
                  {{ t('cloudBilling.settings.alertRule.title') }}
                </th>
                <th
                  class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                >
                  {{ t('cloudBilling.providers.createdAt') }}
                </th>
                <th
                  class="px-4 py-3 text-right text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
                >
                  {{ t('common.actions') }}
                </th>
              </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-100">
              <tr
                v-for="provider in paginatedProviders"
                :key="provider.id"
                class="transition-colors duration-150 hover:bg-gray-50"
              >
                <td class="px-4 py-3">
                  <div class="min-w-[180px]">
                    <div class="text-sm font-medium text-gray-900 break-words">
                      {{ getProviderDisplayName(provider) }}
                    </div>
                    <div
                      v-if="provider.notes"
                      class="text-xs text-gray-500 mt-1 truncate max-w-[300px]"
                      :title="provider.notes"
                    >
                      {{ provider.notes }}
                    </div>
                    <div
                      v-if="provider.tags?.length"
                      class="mt-2 flex flex-wrap gap-1.5"
                    >
                      <span
                        v-for="tag in provider.tags"
                        :key="`${provider.id}-${tag}`"
                        class="inline-flex items-center rounded-full border border-primary-100 bg-primary-50 px-2 py-0.5 text-[10px] font-medium text-primary-700"
                      >
                        {{ tag }}
                      </span>
                    </div>
                  </div>
                </td>
                <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                  {{ getProviderTypeText(provider.provider_type) }}
                </td>
                <td class="px-4 py-3 text-sm text-gray-500">
                  <div v-if="provider.auth_identifier" class="min-w-[180px]">
                    <div
                      class="text-[11px] font-medium uppercase tracking-wide text-gray-400"
                    >
                      {{ getProviderAuthLabel(provider) }}
                    </div>
                    <div class="mt-1 break-all font-mono text-xs text-gray-700">
                      {{ provider.auth_identifier }}
                    </div>
                  </div>
                  <span v-else class="text-xs text-gray-400">
                    {{ t('cloudBilling.providers.authIdentifierEmpty') }}
                  </span>
                </td>
                <td class="px-4 py-3 whitespace-nowrap">
                  <label
                    class="relative inline-flex items-center cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      :checked="provider.is_active"
                      @change="
                        toggleProvider(provider.id, $event.target.checked)
                      "
                      class="sr-only peer"
                      :disabled="togglingIds.includes(provider.id)"
                    />
                    <div
                      class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-600 peer-disabled:opacity-50 peer-disabled:cursor-not-allowed"
                    ></div>
                  </label>
                </td>
                <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                  <div
                    v-if="getAlertRuleSummary(provider.id).length"
                    class="space-y-1"
                  >
                    <div
                      v-for="item in getAlertRuleSummary(provider.id)"
                      :key="`${provider.id}-${item.key}`"
                      :class="item.muted ? 'text-xs text-gray-400' : 'text-xs'"
                    >
                      {{ item.text }}
                    </div>
                  </div>
                  <span v-else class="text-xs text-gray-400">{{
                    t('cloudBilling.settings.alertRule.notConfigured')
                  }}</span>
                </td>
                <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                  {{ formatDate(provider.created_at) }}
                </td>
                <td
                  class="px-4 py-3 whitespace-nowrap text-right text-sm font-medium"
                >
                  <div class="flex items-center justify-end gap-2">
                    <button
                      @click="editNotes(provider)"
                      class="text-gray-500 hover:text-gray-900 transition-colors"
                      :title="t('cloudBilling.providers.editNotes')"
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
                          d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.586a2 2 0 112.828 2.828L11 16H8v-3L18.586 5.414z"
                        />
                      </svg>
                    </button>
                    <button
                      @click="editAuthConfig(provider)"
                      class="text-primary-600 hover:text-primary-900 transition-colors"
                      :title="t('cloudBilling.providers.editAuthConfig')"
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
                          d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
                        />
                      </svg>
                    </button>
                    <button
                      @click="editAlertRule(provider)"
                      class="text-orange-600 hover:text-orange-900 transition-colors"
                      :title="t('cloudBilling.settings.alertRule.title')"
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
                          d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
                        />
                      </svg>
                    </button>
                    <button
                      @click="editRecharge(provider)"
                      class="text-sky-600 hover:text-sky-900 transition-colors"
                      :title="t('cloudBilling.providers.rechargeApproval')"
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
                          d="M17 9V7a5 5 0 00-10 0v2M5 9h14l-1 10H6L5 9zm4 4h6"
                        />
                      </svg>
                    </button>
                    <button
                      @click="validateProvider(provider.id)"
                      class="text-green-600 hover:text-green-900 transition-colors"
                      :title="t('cloudBilling.providers.testConnection')"
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
                          d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                        />
                      </svg>
                    </button>
                    <button
                      @click="deleteProvider(provider.id)"
                      class="text-red-600 hover:text-red-900 transition-colors"
                      :title="t('common.delete')"
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
                          d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                        />
                      </svg>
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Mobile Card View -->
        <div class="md:hidden space-y-3">
          <div
            v-for="provider in paginatedProviders"
            :key="provider.id"
            class="bg-white rounded-lg border border-gray-200 shadow-sm p-4"
          >
            <div class="flex items-start justify-between mb-3">
              <div class="flex-1">
                <h3 class="text-sm font-semibold text-gray-900 mb-1">
                  {{ getProviderDisplayName(provider) }}
                </h3>
                <p
                  v-if="provider.notes"
                  class="text-xs text-gray-500 mt-1 truncate"
                  :title="provider.notes"
                >
                  {{ provider.notes }}
                </p>
                <div
                  v-if="provider.tags?.length"
                  class="mt-2 flex flex-wrap gap-1.5"
                >
                  <span
                    v-for="tag in provider.tags"
                    :key="`${provider.id}-${tag}`"
                    class="inline-flex items-center rounded-full border border-primary-100 bg-primary-50 px-2 py-0.5 text-[10px] font-medium text-primary-700"
                  >
                    {{ tag }}
                  </span>
                </div>
              </div>
              <label class="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  :checked="provider.is_active"
                  @change="toggleProvider(provider.id, $event.target.checked)"
                  class="sr-only peer"
                  :disabled="togglingIds.includes(provider.id)"
                />
                <div
                  class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-600 peer-disabled:opacity-50 peer-disabled:cursor-not-allowed"
                ></div>
              </label>
            </div>
            <div class="space-y-2 text-sm text-gray-600">
              <div>
                <span class="font-medium"
                  >{{
                    t('cloudBilling.settings.providers.providerType')
                  }}:</span
                >
                {{ getProviderTypeText(provider.provider_type) }}
              </div>
              <div>
                <span class="font-medium"
                  >{{ t('cloudBilling.providers.authIdentifier') }}:</span
                >
                <div v-if="provider.auth_identifier" class="mt-1">
                  <div
                    class="text-[11px] uppercase tracking-wide text-gray-400"
                  >
                    {{ getProviderAuthLabel(provider) }}
                  </div>
                  <div class="break-all font-mono text-xs text-gray-700">
                    {{ provider.auth_identifier }}
                  </div>
                </div>
                <span v-else class="text-xs text-gray-400">
                  {{ t('cloudBilling.providers.authIdentifierEmpty') }}
                </span>
              </div>
              <div v-if="getAlertRule(provider.id)">
                <span class="font-medium"
                  >{{ t('cloudBilling.settings.alertRule.title') }}:</span
                >
                <div class="ml-2 mt-1 space-y-1">
                  <div
                    v-for="item in getAlertRuleSummary(provider.id)"
                    :key="`${provider.id}-${item.key}`"
                    :class="item.muted ? 'text-xs text-gray-400' : 'text-xs'"
                  >
                    {{ item.text }}
                  </div>
                </div>
              </div>
              <div v-else class="text-xs text-gray-400">
                {{ t('cloudBilling.settings.alertRule.notConfigured') }}
              </div>
              <div>
                <span class="font-medium"
                  >{{ t('cloudBilling.providers.createdAt') }}:</span
                >
                {{ formatDate(provider.created_at) }}
              </div>
            </div>
            <div
              class="flex items-center justify-end gap-2 mt-4 pt-4 border-t border-gray-200"
            >
              <button
                @click="editNotes(provider)"
                class="text-gray-500 hover:text-gray-900 transition-colors"
                :title="t('cloudBilling.providers.editNotes')"
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
                    d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.586a2 2 0 112.828 2.828L11 16H8v-3L18.586 5.414z"
                  />
                </svg>
              </button>
              <button
                @click="editAuthConfig(provider)"
                class="text-primary-600 hover:text-primary-900 text-sm font-medium"
              >
                {{ t('cloudBilling.providers.editAuthConfig') }}
              </button>
              <button
                @click="editAlertRule(provider)"
                class="text-orange-600 hover:text-orange-900 text-sm font-medium"
              >
                {{ t('cloudBilling.settings.alertRule.title') }}
              </button>
              <button
                @click="editRecharge(provider)"
                class="text-sky-600 hover:text-sky-900 text-sm font-medium"
              >
                {{ t('cloudBilling.providers.rechargeApproval') }}
              </button>
              <button
                @click="validateProvider(provider.id)"
                class="text-green-600 hover:text-green-900 text-sm font-medium"
              >
                {{ t('cloudBilling.providers.testConnection') }}
              </button>
              <button
                @click="deleteProvider(provider.id)"
                class="text-red-600 hover:text-red-900 text-sm font-medium"
              >
                {{ t('common.delete') }}
              </button>
            </div>
          </div>
        </div>

        <div
          v-if="!loading && filteredProviders.length > 0"
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
      </template>
    </template>

    <!-- Create/Edit Provider Modal -->
    <ProviderFormModal
      v-if="showCreateModal || editingProvider"
      :show="showCreateModal || !!editingProvider"
      :provider="editingProvider"
      :tag-options="tagOptions"
      :show-alert-rule="!editingProvider"
      @close="closeModal"
      @saved="handleSaved"
    />

    <!-- Edit Notes Modal -->
    <ProviderNotesModal
      v-if="editingNotesProvider"
      :show="!!editingNotesProvider"
      :provider="editingNotesProvider"
      :tag-options="tagOptions"
      @close="editingNotesProvider = null"
      @saved="handleNotesSaved"
    />

    <ProviderRechargeModal
      v-if="editingRechargeProvider"
      :show="!!editingRechargeProvider"
      :provider="editingRechargeProvider"
      @close="editingRechargeProvider = null"
      @saved="handleRechargeSaved"
    />

    <!-- Alert Rule Modal -->
    <AlertRuleModal
      v-if="editingAlertRuleProvider"
      :show="!!editingAlertRuleProvider"
      :provider="editingAlertRuleProvider"
      :alert-rule="getAlertRule(editingAlertRuleProvider.id)"
      @close="editingAlertRuleProvider = null"
      @saved="handleAlertRuleSaved"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { format } from 'date-fns'
import { useToast } from '@/composables/useToast'
import { extractResponseData } from '@/utils/api'
import { cloudBillingApi } from '@/api/cloudBilling'
import BaseLoading from '@/components/ui/BaseLoading.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import ProviderFormModal from '@/components/cloud-billing/ProviderFormModal.vue'
import ProviderNotesModal from '@/components/cloud-billing/ProviderNotesModal.vue'
import ProviderRechargeModal from '@/components/cloud-billing/ProviderRechargeModal.vue'
import AlertRuleModal from '@/components/cloud-billing/AlertRuleModal.vue'
import {
  getLocalizedProviderDisplayName,
  getProviderAuthIdentifierLabel,
  getProviderTypeLabel
} from '@/utils/providerDisplay'

const { t } = useI18n()
const { showSuccess, showError } = useToast()

const loading = ref(true)
const allProviders = ref([])
const tagOptions = ref([])
const alertRulesByProvider = ref({})
const loadedAlertRuleProviderIds = ref({})
const searchQuery = ref('')
const showCreateModal = ref(false)
const editingProvider = ref(null)
const editingNotesProvider = ref(null)
const editingRechargeProvider = ref(null)
const editingAlertRuleProvider = ref(null)
const togglingIds = ref([])
const currentPage = ref(1)
const pageSize = ref(10)

const getSearchableProviderTexts = (provider) => {
  const config = provider?.config || {}
  return [
    provider?.display_name,
    provider?.displayName,
    provider?.name,
    provider?.notes,
    provider?.auth_identifier,
    config.username,
    config.zhipu_username,
    config.ZHIPU_USERNAME,
    config.access_key_id,
    config.aws_access_key_id,
    config.AWS_ACCESS_KEY_ID,
    config.huawei_access_key_id,
    config.HUAWEI_ACCESS_KEY_ID,
    config.alibaba_access_key_id,
    config.ALIBABA_ACCESS_KEY_ID,
    config.tencent_access_key_id,
    config.TENCENT_ACCESS_KEY_ID,
    config.volcengine_access_key_id,
    config.VOLCENGINE_ACCESS_KEY_ID,
    config.baidu_access_key_id,
    config.BAIDU_ACCESS_KEY_ID,
    config.api_key,
    config.access_key
  ]
}

const filteredProviders = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  if (!query) {
    return allProviders.value
  }

  return allProviders.value.filter((provider) =>
    getSearchableProviderTexts(provider).some((value) =>
      String(value || '')
        .trim()
        .toLowerCase()
        .includes(query)
    )
  )
})

const totalCount = computed(() => filteredProviders.value.length)

const totalPages = computed(() =>
  totalCount.value > 0 ? Math.ceil(totalCount.value / pageSize.value) : 1
)

const paginationShowing = computed(() => ({
  from:
    totalCount.value === 0 ? 0 : (currentPage.value - 1) * pageSize.value + 1,
  to: Math.min(currentPage.value * pageSize.value, totalCount.value),
  total: totalCount.value
}))

const paginatedProviders = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredProviders.value.slice(start, start + pageSize.value)
})

const getProviderTypeText = (type) => getProviderTypeLabel(type, t)
const getProviderDisplayName = (provider) =>
  getLocalizedProviderDisplayName(provider, t)
const getProviderAuthLabel = (provider) =>
  getProviderAuthIdentifierLabel(provider, t)

const formatDate = (dateString) => {
  if (!dateString) return ''
  return format(new Date(dateString), 'yyyy-MM-dd HH:mm')
}

const formatCurrency = (value) => {
  if (value === null || value === undefined || value === '') return '-'
  return `¥${Number(value).toFixed(2)}`
}

const hasThresholdValue = (value) => {
  return value !== null && value !== undefined && value !== ''
}

const getAlertRule = (providerId) => {
  return alertRulesByProvider.value[providerId] || null
}

const getAlertRuleSummary = (providerId) => {
  const rule = getAlertRule(providerId)
  if (!rule) return []

  const items = []
  if (hasThresholdValue(rule.cost_threshold)) {
    items.push({
      key: 'cost_threshold',
      text: `${t('cloudBilling.settings.alertRule.costThreshold')}: ${formatCurrency(rule.cost_threshold)}`
    })
  }
  if (hasThresholdValue(rule.growth_threshold)) {
    items.push({
      key: 'growth_threshold',
      text: `${t('cloudBilling.settings.alertRule.growthThreshold')}: ${rule.growth_threshold}%`
    })
  }
  if (hasThresholdValue(rule.growth_amount_threshold)) {
    items.push({
      key: 'growth_amount_threshold',
      text: `${t('cloudBilling.settings.alertRule.growthAmountThreshold')}: ${formatCurrency(rule.growth_amount_threshold)}`
    })
  }
  if (hasThresholdValue(rule.balance_threshold)) {
    items.push({
      key: 'balance_threshold',
      text: `${t('cloudBilling.settings.alertRule.balanceThreshold')}: ${formatCurrency(rule.balance_threshold)}`
    })
  }
  if (hasThresholdValue(rule.days_remaining_threshold)) {
    items.push({
      key: 'days_remaining_threshold',
      text: `${t('cloudBilling.settings.alertRule.daysRemainingThreshold')}: ${rule.days_remaining_threshold}`
    })
  }
  items.push({
    key: 'auto_submit_recharge_approval',
    text: `${t('cloudBilling.settings.alertRule.autoSubmitRechargeApproval')}: ${
      rule.auto_submit_recharge_approval
        ? t('common.enabled')
        : t('common.disabled')
    }`,
    muted: !rule.auto_submit_recharge_approval
  })
  if (!rule.is_active) {
    items.push({
      key: 'is_active',
      text: t('common.disabled'),
      muted: true
    })
  }

  return items
}

const extractListData = (data) => {
  if (Array.isArray(data)) {
    return {
      list: data,
      total: data.length,
      paginated: false
    }
  }

  if (data?.results && Array.isArray(data.results)) {
    const total = Number(data.count)
    return {
      list: data.results,
      total: Number.isFinite(total) ? total : data.results.length,
      paginated: Number.isFinite(total)
    }
  }

  if (data?.list && Array.isArray(data.list)) {
    const total = Number(data?.pagination?.total)
    return {
      list: data.list,
      total: Number.isFinite(total) ? total : data.list.length,
      paginated: Number.isFinite(total)
    }
  }

  return {
    list: [],
    total: 0,
    paginated: false
  }
}

const normalizeTagOptionList = (items) => {
  const seen = new Set()
  const normalized = []

  ;(items || []).forEach((item) => {
    const value = String(item || '').trim()
    if (!value || seen.has(value)) {
      return
    }
    seen.add(value)
    normalized.push(value)
  })

  return normalized.sort((a, b) => a.localeCompare(b))
}

const loadTagOptions = async () => {
  try {
    const response = await cloudBillingApi.getProviderTags()
    const data = extractResponseData(response)
    tagOptions.value = normalizeTagOptionList(data?.tags || [])
  } catch (error) {
    console.error('Failed to load provider tags:', error)
    tagOptions.value = normalizeTagOptionList(
      allProviders.value.flatMap((provider) => provider?.tags || [])
    )
  }
}

const loadAlertRulesForProviders = async (providerList) => {
  if (!providerList.length) {
    return
  }

  const providersToLoad = providerList.filter(
    (provider) => !loadedAlertRuleProviderIds.value[provider.id]
  )

  if (!providersToLoad.length) {
    return
  }

  const responses = await Promise.all(
    providersToLoad.map((provider) =>
      cloudBillingApi
        .getAlertRules({ provider_id: provider.id, page_size: 1 })
        .catch(() => ({ data: { results: [] } }))
    )
  )

  providersToLoad.forEach((provider, index) => {
    const response = responses[index]
    const data = extractResponseData(response)
    const { list } = extractListData(data)
    alertRulesByProvider.value[provider.id] = list[0] || null
    loadedAlertRuleProviderIds.value[provider.id] = true
  })
}

const fetchAllProviders = async () => {
  const pageSizeValue = 100
  const providersResponse = await cloudBillingApi.getProviders({
    page: 1,
    page_size: pageSizeValue
  })

  const providersData = extractResponseData(providersResponse)
  const { list, total, paginated } = extractListData(providersData)

  if (!paginated) {
    return list
  }

  const allLoadedProviders = [...list]
  const totalPagesValue = Math.max(1, Math.ceil(total / pageSizeValue))

  for (let page = 2; page <= totalPagesValue; page += 1) {
    const pageResponse = await cloudBillingApi.getProviders({
      page,
      page_size: pageSizeValue
    })
    const pageData = extractResponseData(pageResponse)
    const { list: pageList } = extractListData(pageData)
    allLoadedProviders.push(...pageList)
  }

  return allLoadedProviders
}

const loadProviders = async (page = currentPage.value) => {
  loading.value = true
  try {
    const list = await fetchAllProviders()
    currentPage.value = page
    allProviders.value = list

    await Promise.all([
      loadAlertRulesForProviders(paginatedProviders.value),
      currentPage.value === 1 && tagOptions.value.length === 0
        ? loadTagOptions()
        : Promise.resolve()
    ])
  } catch (error) {
    console.error('Failed to load providers:', error)
    allProviders.value = []
    tagOptions.value = []
    alertRulesByProvider.value = {}
    loadedAlertRuleProviderIds.value = {}
  } finally {
    loading.value = false
  }
}

const upsertProvider = (provider) => {
  if (!provider?.id) return

  const index = allProviders.value.findIndex((item) => item.id === provider.id)
  if (index === -1) {
    allProviders.value = [provider, ...allProviders.value]
    return
  }

  allProviders.value[index] = {
    ...allProviders.value[index],
    ...provider
  }
}

const toggleProvider = async (id, enabled) => {
  togglingIds.value.push(id)
  try {
    await cloudBillingApi.patchProvider(id, { is_active: enabled })
    const provider = allProviders.value.find((p) => p.id === id)
    if (provider) {
      provider.is_active = enabled
    }
    showSuccess(
      enabled
        ? t('cloudBilling.providers.enableSuccess')
        : t('cloudBilling.providers.disableSuccess')
    )
  } catch (error) {
    console.error('Failed to toggle provider:', error)
    showError(t('cloudBilling.providers.toggleError'))
    const provider = allProviders.value.find((p) => p.id === id)
    if (provider) {
      provider.is_active = !enabled
    }
  } finally {
    togglingIds.value = togglingIds.value.filter((pid) => pid !== id)
  }
}

const editAuthConfig = (provider) => {
  editingProvider.value = provider
}

const editNotes = (provider) => {
  editingNotesProvider.value = provider
}

const editRecharge = (provider) => {
  editingRechargeProvider.value = provider
}

const editAlertRule = (provider) => {
  editingAlertRuleProvider.value = provider
}

const closeModal = () => {
  showCreateModal.value = false
  editingProvider.value = null
}

const handleNotesSaved = (provider) => {
  editingNotesProvider.value = null
  if (provider) {
    upsertProvider(provider)
  }
  tagOptions.value = normalizeTagOptionList(
    allProviders.value.flatMap((item) => item?.tags || [])
  )
}

const handleAlertRuleSaved = () => {
  if (editingAlertRuleProvider.value?.id) {
    const providerId = editingAlertRuleProvider.value.id
    loadedAlertRuleProviderIds.value[providerId] = false
    delete alertRulesByProvider.value[providerId]
  }
  editingAlertRuleProvider.value = null
  loadAlertRulesForProviders(paginatedProviders.value)
}

const handleRechargeSaved = (provider) => {
  editingRechargeProvider.value = null
  if (provider) {
    upsertProvider(provider)
  }
}

const handleSaved = (provider) => {
  closeModal()
  if (provider) {
    upsertProvider(provider)
  } else {
    loadProviders(currentPage.value)
    return
  }
  tagOptions.value = normalizeTagOptionList(
    allProviders.value.flatMap((item) => item?.tags || [])
  )
}

const goPrevPage = () => {
  if (currentPage.value <= 1) return
  currentPage.value -= 1
}

const goNextPage = () => {
  if (currentPage.value >= totalPages.value) return
  currentPage.value += 1
}

const handlePageSizeChange = () => {
  currentPage.value = 1
}

const validateProvider = async (id) => {
  try {
    const response = await cloudBillingApi.validateProvider(id)
    const data = extractResponseData(response)
    if (data?.valid) {
      showSuccess(t('cloudBilling.providers.validationSuccess'))
    } else {
      showError(
        t('cloudBilling.providers.validationFailed') +
          ': ' +
          (data?.message || '')
      )
    }
  } catch (error) {
    console.error('Failed to validate provider:', error)
    showError(t('cloudBilling.providers.validationError'))
  }
}

const deleteProvider = async (id) => {
  if (!confirm(t('cloudBilling.providers.confirmDelete'))) {
    return
  }

  try {
    await cloudBillingApi.deleteProvider(id)
    showSuccess(t('cloudBilling.providers.deleteSuccess'))
    allProviders.value = allProviders.value.filter(
      (provider) => provider.id !== id
    )
    delete alertRulesByProvider.value[id]
    delete loadedAlertRuleProviderIds.value[id]
    tagOptions.value = normalizeTagOptionList(
      allProviders.value.flatMap((provider) => provider?.tags || [])
    )
    if (paginatedProviders.value.length === 0 && currentPage.value > 1) {
      currentPage.value -= 1
    }
  } catch (error) {
    console.error('Failed to delete provider:', error)
    showError(t('cloudBilling.providers.deleteError'))
  }
}

onMounted(() => {
  loadProviders()
})

watch(searchQuery, () => {
  currentPage.value = 1
})

watch(totalPages, (value) => {
  if (currentPage.value > value) {
    currentPage.value = value || 1
  }
})

watch(
  paginatedProviders,
  (providers) => {
    if (!loading.value) {
      loadAlertRulesForProviders(providers)
    }
  },
  { deep: false }
)
</script>
