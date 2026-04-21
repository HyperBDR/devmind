<template>
  <AppLayout :show-sidebar="false">
    <div class="mx-auto w-full max-w-[1440px]">
      <div class="mb-6 rounded-xl border border-gray-200 bg-white shadow-sm">
        <div
          class="flex flex-col gap-5 p-6 lg:flex-row lg:items-end lg:justify-between"
        >
          <div class="max-w-3xl">
            <div
              class="inline-flex items-center gap-2 rounded-full border border-primary-100 bg-primary-50 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-primary-700"
            >
              <span class="h-2 w-2 rounded-full bg-primary-500" />
              {{ t('operations.dashboard.badge') }}
            </div>
            <h1
              class="mt-4 text-2xl font-semibold tracking-tight text-gray-900"
            >
              {{ t('operations.dashboard.title') }}
            </h1>
            <p class="mt-2 max-w-2xl text-sm leading-6 text-gray-600">
              {{ t('operations.dashboard.subtitle') }}
            </p>
          </div>
          <div class="flex flex-wrap items-center gap-3">
            <label
              class="flex items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-600"
            >
              <span
                class="flex h-8 w-8 items-center justify-center rounded-md bg-white text-gray-400 shadow-sm"
              >
                <svg
                  class="h-4 w-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M12 21c4.97 0 9-3.806 9-8.5S16.97 4 12 4 3 7.806 3 12.5 7.03 21 12 21z"
                  />
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M12 4v17m-6-8.5h12"
                  />
                </svg>
              </span>
              <select
                v-model="selectedTimezone"
                class="min-w-[154px] bg-transparent text-sm font-medium text-gray-700 focus:outline-none"
                aria-label="Timezone"
              >
                <option
                  v-for="item in timezones"
                  :key="item.value"
                  :value="item.value"
                >
                  {{ item.label }}
                </option>
              </select>
            </label>
            <div
              class="flex items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 px-2 py-2"
            >
              <span
                class="flex h-8 w-8 items-center justify-center rounded-md bg-white text-gray-400 shadow-sm"
              >
                <svg
                  class="h-4 w-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="1.8"
                    d="M7 7.5C7 6.119 9.239 5 12 5s5 1.119 5 2.5S14.761 10 12 10 7 8.881 7 7.5Z"
                  />
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="1.8"
                    d="M7 12c0 1.381 2.239 2.5 5 2.5s5-1.119 5-2.5"
                  />
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="1.8"
                    d="M7 16.5C7 17.881 9.239 19 12 19s5-1.119 5-2.5"
                  />
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="1.8"
                    d="M7 7.5v9M17 7.5v9"
                  />
                </svg>
              </span>
              <div class="flex rounded-md bg-white p-1 shadow-sm">
                <button
                  v-for="item in currencies"
                  :key="item"
                  type="button"
                  class="rounded-md px-3 py-1.5 text-xs font-semibold transition-colors"
                  :class="
                    selectedCurrency === item
                      ? 'bg-primary-600 text-white'
                      : 'text-gray-500 hover:text-gray-700'
                  "
                  @click="selectedCurrency = item"
                >
                  {{ item }}
                </button>
              </div>
            </div>
            <BaseButton
              variant="outline"
              size="sm"
              @click="overviewPanelRef?.reload?.()"
            >
              {{ t('common.refresh') }}
            </BaseButton>
          </div>
        </div>
      </div>

      <CloudBillingOverviewPanel
        ref="overviewPanelRef"
        v-model:timezone="selectedTimezone"
        v-model:currency="selectedCurrency"
        :show-header="false"
      />
    </div>
  </AppLayout>
</template>

<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppLayout from '@/components/layout/AppLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import CloudBillingOverviewPanel from '@/components/cloud-billing/CloudBillingOverviewPanel.vue'
import {
  OPERATIONS_CURRENCIES,
  OPERATIONS_DEFAULT_TIMEZONE,
  OPERATIONS_TIMEZONES
} from '@/constants/operationsView'

const { t } = useI18n()
const overviewPanelRef = ref(null)
const selectedTimezone = ref(OPERATIONS_DEFAULT_TIMEZONE)
const selectedCurrency = ref('CNY')
const timezones = OPERATIONS_TIMEZONES
const currencies = OPERATIONS_CURRENCIES
</script>
