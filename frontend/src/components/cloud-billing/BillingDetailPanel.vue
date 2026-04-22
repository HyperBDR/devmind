<template>
  <!-- Overlay -->
  <Transition
    enter-active-class="transition-opacity duration-200"
    enter-from-class="opacity-0"
    enter-to-class="opacity-100"
    leave-active-class="transition-opacity duration-150"
    leave-from-class="opacity-100"
    leave-to-class="opacity-0"
  >
    <div
      v-if="show"
      @click="handleClose"
      class="fixed inset-0 bg-gray-900 bg-opacity-50 z-40"
    />
  </Transition>

  <!-- Right Panel -->
  <Transition
    enter-active-class="transition-transform duration-300 ease-out"
    enter-from-class="translate-x-full"
    enter-to-class="translate-x-0"
    leave-active-class="transition-transform duration-250 ease-in"
    leave-from-class="translate-x-0"
    leave-to-class="translate-x-full"
  >
    <div
      v-if="show"
      class="fixed inset-y-0 right-0 w-full max-w-2xl bg-white shadow-xl z-50 flex flex-col"
    >
      <!-- Header -->
      <div
        class="flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-gradient-to-r from-gray-50 to-gray-100 flex-shrink-0"
      >
        <h2 class="text-lg font-semibold text-gray-900">
          {{ t('cloudBilling.billing.title') }}
        </h2>
        <button
          @click="handleClose"
          class="p-1.5 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
        >
          <svg
            class="w-5 h-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      </div>

      <!-- Content - Scrollable -->
      <div class="flex-1 overflow-y-auto">
        <div v-if="billing" class="p-6 space-y-6">
          <!-- Basic Information -->
          <div>
            <h3 class="text-sm font-semibold text-gray-900 mb-4">
              {{ t('cloudBilling.billing.basicInfo') }}
            </h3>
            <dl class="grid grid-cols-1 gap-4">
              <div>
                <dt
                  class="text-xs font-semibold text-gray-700 mb-2 uppercase tracking-wider"
                >
                  {{ t('cloudBilling.billing.provider') }}
                </dt>
                <dd class="text-sm font-medium text-gray-900">
                  {{ providerDisplayName }}
                </dd>
              </div>
              <div>
                <dt
                  class="text-xs font-semibold text-gray-700 mb-2 uppercase tracking-wider"
                >
                  {{ t('cloudBilling.billing.collectionTime') }}
                </dt>
                <dd class="text-sm font-medium text-gray-900">
                  {{
                    formatDate(billing.collection_time, 'yyyy-MM-dd HH:mm:ss')
                  }}
                </dd>
              </div>
              <div>
                <dt
                  class="text-xs font-semibold text-gray-700 mb-2 uppercase tracking-wider"
                >
                  {{ t('cloudBilling.billing.cost') }}
                </dt>
                <dd class="text-sm font-medium text-gray-900">
                  {{ formatCost(billing.cost) }}
                </dd>
              </div>
              <div>
                <dt
                  class="text-xs font-semibold text-gray-700 mb-2 uppercase tracking-wider"
                >
                  {{ t('cloudBilling.billing.balance') }}
                </dt>
                <dd class="text-sm font-medium text-gray-900">
                  {{
                    billing.balance_supported === false
                      ? formatCost(0, billing.currency)
                      : formatCost(billing.balance, billing.currency)
                  }}
                </dd>
                <p
                  v-if="billing.balance_supported === false"
                  class="mt-1 text-xs font-medium text-amber-600"
                >
                  {{
                    billing.balance_note ||
                    t('cloudBilling.billing.balanceUnsupported')
                  }}
                </p>
              </div>
              <div
                v-if="
                  billing.change_from_last_hour !== null &&
                  billing.change_from_last_hour !== undefined
                "
              >
                <dt
                  class="text-xs font-semibold text-gray-700 mb-2 uppercase tracking-wider"
                >
                  {{ t('cloudBilling.billing.changeFromLastHour') }}
                </dt>
                <dd
                  class="text-sm font-medium"
                  :class="
                    getChangeClass(
                      billing.change_from_last_hour,
                      'text-gray-900'
                    )
                  "
                >
                  {{ formatChange(billing.change_from_last_hour) }}
                </dd>
              </div>
            </dl>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { getLocalizedBillingProviderName } from '@/utils/providerDisplay'
import {
  formatCost,
  formatChange,
  formatDate,
  getChangeClass
} from '@/utils/formatting'

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  },
  billing: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['close'])

const { t } = useI18n()
const providerDisplayName = computed(() =>
  getLocalizedBillingProviderName(props.billing, t)
)

const handleClose = () => {
  emit('close')
}
</script>
