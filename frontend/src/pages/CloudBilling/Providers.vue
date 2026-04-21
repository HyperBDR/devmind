<template>
  <AppLayout>
    <div class="w-full max-w-full p-6">
      <div class="mb-4 flex items-center justify-between">
        <div>
          <h1 class="text-lg font-semibold text-gray-900">
            {{ t('cloudBilling.providers.title') }}
          </h1>
          <p class="mt-1 text-sm text-gray-500">
            {{ t('cloudBilling.providers.subtitle') }}
          </p>
        </div>
        <button
          @click="showCreateModal = true"
          class="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
        >
          {{ t('cloudBilling.providers.createProvider') }}
        </button>
      </div>

      <BaseLoading v-if="loading" full-page size="lg" variant="primary" />

      <template v-else>
        <div class="bg-white rounded-lg border border-gray-200 shadow-sm">
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
              <tr>
                <th
                  class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                >
                  {{ t('cloudBilling.providers.name') }}
                </th>
                <th
                  class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                >
                  {{ t('cloudBilling.providers.type') }}
                </th>
                <th
                  class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                >
                  {{ t('cloudBilling.providers.displayName') }}
                </th>
                <th
                  class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                >
                  {{ t('cloudBilling.providers.authIdentifier') }}
                </th>
                <th
                  class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                >
                  {{ t('cloudBilling.providers.status') }}
                </th>
                <th
                  class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                >
                  {{ t('cloudBilling.providers.createdAt') }}
                </th>
                <th
                  class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider"
                >
                  {{ t('common.actions') }}
                </th>
              </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
              <tr v-for="provider in providers" :key="provider.id">
                <td
                  class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900"
                >
                  {{ provider.name }}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {{ getProviderTypeText(provider.provider_type) }}
                </td>
                <td class="px-6 py-4 text-sm text-gray-500">
                  <div class="min-w-[180px]">
                    <div class="text-sm text-gray-700">
                      {{ getProviderDisplayName(provider) }}
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
                <td class="px-6 py-4 text-sm text-gray-500">
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
                <td class="px-6 py-4 whitespace-nowrap">
                  <span
                    :class="
                      provider.is_active
                        ? 'bg-green-100 text-green-800'
                        : 'bg-gray-100 text-gray-800'
                    "
                    class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full"
                  >
                    {{
                      provider.is_active
                        ? t('common.active')
                        : t('common.inactive')
                    }}
                  </span>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {{ formatDate(provider.created_at) }}
                </td>
                <td
                  class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium"
                >
                  <button
                    @click="editProvider(provider)"
                    class="text-blue-600 hover:text-blue-900 mr-4"
                  >
                    {{ t('common.edit') }}
                  </button>
                  <button
                    @click="validateProvider(provider.id)"
                    class="text-green-600 hover:text-green-900 mr-4"
                  >
                    {{ t('cloudBilling.providers.testConnection') }}
                  </button>
                  <button
                    @click="deleteProvider(provider.id)"
                    class="text-red-600 hover:text-red-900"
                  >
                    {{ t('common.delete') }}
                  </button>
                </td>
              </tr>
              <tr v-if="providers.length === 0">
                <td
                  colspan="7"
                  class="px-6 py-4 text-center text-sm text-gray-500"
                >
                  {{ t('cloudBilling.providers.noProviders') }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </div>

    <!-- Create/Edit Modal -->
    <ProviderFormModal
      v-if="showCreateModal || editingProvider"
      :show="showCreateModal || !!editingProvider"
      :provider="editingProvider"
      :tag-options="tagOptions"
      @close="closeModal"
      @saved="handleSaved"
    />
  </AppLayout>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { cloudBillingApi } from '@/api/cloudBilling'
import AppLayout from '@/components/layout/AppLayout.vue'
import BaseLoading from '@/components/ui/BaseLoading.vue'
import ProviderFormModal from '@/components/cloud-billing/ProviderFormModal.vue'
import { format } from 'date-fns'
import {
  getLocalizedProviderDisplayName,
  getProviderAuthIdentifierLabel,
  getProviderTypeLabel
} from '@/utils/providerDisplay'

const { t } = useI18n()
const loading = ref(true)
const providers = ref([])
const tagOptions = ref([])
const showCreateModal = ref(false)
const editingProvider = ref(null)

const getProviderTypeText = (type) => getProviderTypeLabel(type, t)
const getProviderDisplayName = (provider) =>
  getLocalizedProviderDisplayName(provider, t)
const getProviderAuthLabel = (provider) =>
  getProviderAuthIdentifierLabel(provider, t)

const formatDate = (dateString) => {
  if (!dateString) return ''
  return format(new Date(dateString), 'yyyy-MM-dd HH:mm')
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

const extractProviderList = (payload) => {
  if (Array.isArray(payload)) return payload
  if (Array.isArray(payload?.results)) return payload.results
  if (Array.isArray(payload?.list)) return payload.list
  return []
}

const loadProviders = async () => {
  loading.value = true
  try {
    const response = await cloudBillingApi.getProviders()
    providers.value = extractProviderList(response.data)
  } catch (error) {
    console.error('Failed to load providers:', error)
    providers.value = []
  } finally {
    loading.value = false
  }
}

const loadTagOptions = async () => {
  try {
    const response = await cloudBillingApi.getProviderTags()
    tagOptions.value = normalizeTagOptionList(response.data?.tags || [])
  } catch (error) {
    console.error('Failed to load provider tags:', error)
    tagOptions.value = normalizeTagOptionList(
      providers.value.flatMap((provider) => provider?.tags || [])
    )
  }
}

const editProvider = (provider) => {
  editingProvider.value = provider
}

const closeModal = () => {
  showCreateModal.value = false
  editingProvider.value = null
}

const handleSaved = () => {
  closeModal()
  loadTagOptions()
  loadProviders()
}

const validateProvider = async (id) => {
  try {
    const response = await cloudBillingApi.validateProvider(id)
    if (response.data?.valid) {
      alert(t('cloudBilling.providers.validationSuccess'))
    } else {
      alert(
        t('cloudBilling.providers.validationFailed') +
          ': ' +
          (response.data?.message || '')
      )
    }
  } catch (error) {
    console.error('Failed to validate provider:', error)
    alert(t('cloudBilling.providers.validationError'))
  }
}

const deleteProvider = async (id) => {
  if (!confirm(t('cloudBilling.providers.confirmDelete'))) {
    return
  }

  try {
    await cloudBillingApi.deleteProvider(id)
    loadTagOptions()
    loadProviders()
  } catch (error) {
    console.error('Failed to delete provider:', error)
    alert(t('cloudBilling.providers.deleteError'))
  }
}

onMounted(() => {
  loadTagOptions()
  loadProviders()
})
</script>
