<template>
  <AppLayout>
    <div class="w-full max-w-full p-6 space-y-6">
      <SettingsNav
        :title="t('hyperbdrMonitor.settingsPage.title')"
        :subtitle="t('hyperbdrMonitor.settingsPage.dataSourcesSubtitle')"
      />

      <div class="bg-white border border-gray-200 rounded-xl shadow-sm">
        <div
          class="px-6 py-4 border-b border-gray-200 flex items-center justify-between"
        >
          <div>
            <h2 class="text-lg font-semibold text-gray-900">
              {{
                isEdit
                  ? t('hyperbdrMonitor.settingsPage.editDataSourceTitle')
                  : t('hyperbdrMonitor.settingsPage.newDataSourceTitle')
              }}
            </h2>
            <p class="mt-1 text-sm text-gray-500">
              {{
                isEdit
                  ? t('hyperbdrMonitor.settingsPage.editDataSourceSubtitle')
                  : t('hyperbdrMonitor.settingsPage.newDataSourceSubtitle')
              }}
            </p>
          </div>
          <router-link
            :to="{ name: 'OneProMonitorSettingsDataSources' }"
            class="text-sm font-medium text-primary-600 hover:text-primary-700"
          >
            {{ t('hyperbdrMonitor.actions.backToList') }}
          </router-link>
        </div>

        <form
          class="px-6 py-6 grid grid-cols-1 gap-6 lg:grid-cols-2"
          @submit.prevent="submit"
        >
          <div class="space-y-4">
            <div>
              <label class="block text-sm font-medium text-gray-700">{{
                t('hyperbdrMonitor.labels.name')
              }}</label>
              <input
                v-model="form.name"
                class="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
                required
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700">{{
                t('hyperbdrMonitor.labels.apiUrl')
              }}</label>
              <input
                v-model="form.api_url"
                class="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
                placeholder="https://example.com"
                required
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700">{{
                t('hyperbdrMonitor.labels.username')
              }}</label>
              <input
                v-model="form.username"
                class="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
                required
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700">{{
                isEdit
                  ? t('hyperbdrMonitor.settingsPage.passwordHintEdit')
                  : t('hyperbdrMonitor.labels.password')
              }}</label>
              <input
                v-model="form.password"
                type="password"
                class="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
                :required="!isEdit"
              />
            </div>
          </div>

          <div class="space-y-4">
            <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label class="block text-sm font-medium text-gray-700">{{
                  t('hyperbdrMonitor.labels.apiTimeout')
                }}</label>
                <input
                  v-model.number="form.api_timeout"
                  type="number"
                  min="5"
                  class="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700">{{
                  t('hyperbdrMonitor.labels.collectInterval')
                }}</label>
                <input
                  v-model.number="form.collect_interval"
                  type="number"
                  min="60"
                  class="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
                />
              </div>
            </div>
            <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label class="block text-sm font-medium text-gray-700">{{
                  t('hyperbdrMonitor.labels.retryCount')
                }}</label>
                <input
                  v-model.number="form.api_retry_count"
                  type="number"
                  min="0"
                  class="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700">{{
                  t('hyperbdrMonitor.labels.retryDelay')
                }}</label>
                <input
                  v-model.number="form.api_retry_delay"
                  type="number"
                  min="0"
                  class="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
                />
              </div>
            </div>
            <label class="inline-flex items-center gap-2 pt-2">
              <input
                v-model="form.is_active"
                type="checkbox"
                class="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
              />
              <span class="text-sm text-gray-700">{{
                t('hyperbdrMonitor.settingsPage.enableSource')
              }}</span>
            </label>
          </div>

          <div
            class="lg:col-span-2 flex justify-end gap-3 border-t border-gray-200 pt-6"
          >
            <router-link
              :to="{ name: 'OneProMonitorSettingsDataSources' }"
              class="inline-flex items-center justify-center rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:border-gray-400 hover:text-gray-900"
            >
              {{ t('hyperbdrMonitor.actions.cancel') }}
            </router-link>
            <BaseButton type="submit" :loading="saving">
              {{
                isEdit
                  ? t('hyperbdrMonitor.actions.saveUpdate')
                  : t('hyperbdrMonitor.actions.createDataSource')
              }}
            </BaseButton>
          </div>
        </form>
      </div>
    </div>
  </AppLayout>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { oneproMonitorApi } from '@/api/oneproMonitor'
import AppLayout from '@/components/layout/AppLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import { useToast } from '@/composables/useToast'

import SettingsNav from '../SettingsNav.vue'
import { unwrap } from '../shared'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const { showError, showSuccess } = useToast()

const saving = ref(false)
const isEdit = computed(() => Boolean(route.params.id))

const form = ref({
  name: '',
  api_url: '',
  username: '',
  password: '',
  is_active: true,
  api_timeout: 30,
  api_retry_count: 3,
  api_retry_delay: 2,
  collect_interval: 3600
})

async function loadSource() {
  if (!isEdit.value) return
  try {
    const response = await oneproMonitorApi.dataSources.get(route.params.id)
    const payload = unwrap(response)
    form.value = {
      ...form.value,
      ...payload,
      password: ''
    }
  } catch (error) {
    showError(
      error?.response?.data?.detail ||
        t('hyperbdrMonitor.settingsPage.loadSourceDetailError')
    )
  }
}

async function submit() {
  saving.value = true
  try {
    const payload = { ...form.value }
    if (isEdit.value && !payload.password) {
      delete payload.password
    }
    if (isEdit.value) {
      await oneproMonitorApi.dataSources.update(route.params.id, payload)
      showSuccess(t('hyperbdrMonitor.settingsPage.updateSuccess'))
    } else {
      await oneproMonitorApi.dataSources.create(payload)
      showSuccess(t('hyperbdrMonitor.settingsPage.createSuccess'))
    }
    router.push({ name: 'OneProMonitorSettingsDataSources' })
  } catch (error) {
    showError(
      error?.response?.data?.detail ||
        t('hyperbdrMonitor.settingsPage.saveSourceError')
    )
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadSource()
})
</script>
