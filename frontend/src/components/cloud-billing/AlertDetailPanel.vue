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
          {{ t('cloudBilling.alerts.details') }}
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
        <div v-if="alert" class="p-6 space-y-6">
          <!-- Basic Information -->
          <div>
            <h3 class="text-sm font-semibold text-gray-900 mb-4">
              {{ t('cloudBilling.alerts.basicInfo') }}
            </h3>
            <dl class="grid grid-cols-1 gap-4">
              <div>
                <dt
                  class="text-xs font-semibold text-gray-700 mb-2 uppercase tracking-wider"
                >
                  {{ t('cloudBilling.alerts.alertTime') }}
                </dt>
                <dd class="text-sm font-medium text-gray-900">
                  {{ formatDate(alert.created_at) }}
                </dd>
              </div>
              <div>
                <dt
                  class="text-xs font-semibold text-gray-700 mb-2 uppercase tracking-wider"
                >
                  {{ t('cloudBilling.alerts.provider') }}
                </dt>
                <dd class="text-sm font-medium text-gray-900">
                  {{
                    alert.provider_label ||
                    alert.provider_name ||
                    alert.provider
                  }}
                </dd>
              </div>
              <div>
                <dt
                  class="text-xs font-semibold text-gray-700 mb-2 uppercase tracking-wider"
                >
                  {{ t('cloudBilling.alerts.webhookStatus') }}
                </dt>
                <dd>
                  <span
                    :class="getWebhookStatusClass(alert.webhook_status)"
                    class="px-2 py-1 text-xs font-semibold rounded-full"
                  >
                    {{ getWebhookStatusLabel(alert.webhook_status) }}
                  </span>
                </dd>
              </div>
            </dl>
          </div>

          <!-- Cost Information -->
          <div>
            <h3 class="text-sm font-semibold text-gray-900 mb-4">
              {{ t('cloudBilling.alerts.costInfo') }}
            </h3>
            <dl class="grid grid-cols-1 gap-4">
              <div>
                <dt
                  class="text-xs font-semibold text-gray-700 mb-2 uppercase tracking-wider"
                >
                  {{ t('cloudBilling.alerts.currentCost') }}
                </dt>
                <dd class="text-sm font-medium text-gray-900">
                  {{ formatCurrency(alert.current_cost, alert.currency) }}
                </dd>
              </div>
              <div>
                <dt
                  class="text-xs font-semibold text-gray-700 mb-2 uppercase tracking-wider"
                >
                  {{ t('cloudBilling.alerts.previousCost') }}
                </dt>
                <dd class="text-sm font-medium text-gray-900">
                  {{ formatCurrency(alert.previous_cost, alert.currency) }}
                </dd>
              </div>
              <div>
                <dt
                  class="text-xs font-semibold text-gray-700 mb-2 uppercase tracking-wider"
                >
                  {{ t('cloudBilling.alerts.increaseCost') }}
                </dt>
                <dd class="text-sm font-medium text-gray-900">
                  {{ formatCurrency(alert.increase_cost, alert.currency) }}
                </dd>
              </div>
              <div>
                <dt
                  class="text-xs font-semibold text-gray-700 mb-2 uppercase tracking-wider"
                >
                  {{ t('cloudBilling.alerts.increasePercent') }}
                </dt>
                <dd class="text-sm font-medium text-gray-900">
                  {{ alert.increase_percent }}%
                </dd>
              </div>
              <div
                v-if="
                  alert.current_balance !== null &&
                  alert.current_balance !== undefined
                "
              >
                <dt
                  class="text-xs font-semibold text-gray-700 mb-2 uppercase tracking-wider"
                >
                  {{ t('cloudBilling.alerts.currentBalance') }}
                </dt>
                <dd class="text-sm font-medium text-gray-900">
                  {{ formatCurrency(alert.current_balance, alert.currency) }}
                </dd>
              </div>
              <div
                v-if="
                  alert.balance_threshold !== null &&
                  alert.balance_threshold !== undefined
                "
              >
                <dt
                  class="text-xs font-semibold text-gray-700 mb-2 uppercase tracking-wider"
                >
                  {{ t('cloudBilling.alerts.balanceThreshold') }}
                </dt>
                <dd class="text-sm font-medium text-gray-900">
                  {{ formatCurrency(alert.balance_threshold, alert.currency) }}
                </dd>
              </div>
              <div
                v-if="
                  alert.current_days_remaining !== null &&
                  alert.current_days_remaining !== undefined
                "
              >
                <dt
                  class="text-xs font-semibold text-gray-700 mb-2 uppercase tracking-wider"
                >
                  {{ t('cloudBilling.alerts.currentDaysRemaining') }}
                </dt>
                <dd class="text-sm font-medium text-gray-900">
                  {{ alert.current_days_remaining }}
                </dd>
              </div>
              <div
                v-if="
                  alert.days_remaining_threshold !== null &&
                  alert.days_remaining_threshold !== undefined
                "
              >
                <dt
                  class="text-xs font-semibold text-gray-700 mb-2 uppercase tracking-wider"
                >
                  {{ t('cloudBilling.alerts.daysRemainingThreshold') }}
                </dt>
                <dd class="text-sm font-medium text-gray-900">
                  {{ alert.days_remaining_threshold }}
                </dd>
              </div>
            </dl>
          </div>

          <!-- Alert Message -->
          <div v-if="alert.alert_message">
            <h3 class="text-sm font-semibold text-gray-900 mb-4">
              {{ t('cloudBilling.alerts.message') }}
            </h3>
            <p class="text-sm text-gray-700 whitespace-pre-wrap">
              {{ alert.alert_message }}
            </p>
          </div>

          <!-- Webhook Response -->
          <div v-if="alert.webhook_response">
            <h3 class="text-sm font-semibold text-gray-900 mb-4">
              {{ t('cloudBilling.alerts.webhookResponse') }}
            </h3>
            <pre
              class="text-xs text-gray-700 bg-gray-50 p-3 rounded border border-gray-200 overflow-x-auto"
              >{{ JSON.stringify(alert.webhook_response, null, 2) }}</pre
            >
          </div>

          <!-- Webhook Error -->
          <div v-if="alert.webhook_error">
            <h3 class="text-sm font-semibold text-gray-900 mb-4">
              {{ t('cloudBilling.alerts.webhookError') }}
            </h3>
            <p class="text-sm text-red-700 whitespace-pre-wrap">
              {{ alert.webhook_error }}
            </p>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import { format } from 'date-fns'

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  },
  alert: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['close'])

const { t } = useI18n()

const formatDate = (dateString) => {
  if (!dateString) return '-'
  try {
    return format(new Date(dateString), 'yyyy-MM-dd HH:mm:ss')
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

const handleClose = () => {
  emit('close')
}
</script>
